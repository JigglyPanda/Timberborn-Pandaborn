"""Timbermesh (.timbermesh) reader/writer: gzip + protobuf (Mechanistry model.proto).

All geometry here is kept in the game's (Unity, left-handed, Y-up) node space.
"""
import gzip
import zlib
import numpy as np
import model_pb2 as pb

F32 = pb.SCALAR_TYPE_FLOAT
_DT = {pb.SCALAR_TYPE_UNSIGNED_BYTE: np.uint8, pb.SCALAR_TYPE_UNSIGNED_INT: np.uint32,
       pb.SCALAR_TYPE_INT: np.int32, pb.SCALAR_TYPE_FLOAT: np.float32, pb.SCALAR_TYPE_DOUBLE: np.float64}


def load(path_or_bytes):
    raw = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else open(path_or_bytes, 'rb').read()
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    elif raw[:1] == b'\x78':
        raw = zlib.decompressobj().decompress(raw)
    m = pb.Model()
    m.ParseFromString(raw)
    return m


def save(model, path):
    # Game requires zlib header bytes 0x78 0x9C exactly (= default level 6).
    data = zlib.compress(model.SerializeToString(), 6)
    assert data[:2] == b'\x78\x9c'
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


def prop_array(props, name):
    for p in props:
        if p.name == name:
            a = np.frombuffer(p.data, dtype=_DT[p.scalarType])
            return a.reshape(-1, p.scalarTypeDimension) if p.scalarTypeDimension > 1 else a.copy()
    return None


def prop_names(props):
    return [p.name for p in props]


def make_prop(name, arr):
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    p = pb.VertexProperty()
    p.name = name
    p.scalarType = F32
    p.scalarTypeDimension = 1 if arr.ndim == 1 else arr.shape[1]
    p.data = arr.tobytes()
    return p


def set_prop(props, name, arr):
    """Replace (or append) a float property in a repeated VertexProperty field."""
    newp = make_prop(name, arr)
    for i, p in enumerate(props):
        if p.name == name:
            props[i].CopyFrom(newp)
            return
    props.append(newp)


def describe(model):
    lines = [f"Model '{model.name}' v{model.version}, {len(model.nodes)} nodes"]
    for i, n in enumerate(model.nodes):
        va = ', '.join(f"{a.name}[{len(a.frames)}f@{a.framerate:g},{a.animatedVertexCount}v]" for a in n.vertexAnimations)
        na = ', '.join(f"{a.name}[{len(a.frames)}]" for a in n.nodeAnimations)
        lines.append(f"  [{i}] parent={n.parent} '{n.name}' verts={n.vertexCount} props={prop_names(n.vertexProperties)} "
                     f"meshes={[(len(m.indices)//3, m.material) for m in n.meshes]} pos=({n.position.x:.3f},{n.position.y:.3f},{n.position.z:.3f})"
                     + (f"\n      VA({len(n.vertexAnimations)}): {va[:300]}" if va else '')
                     + (f"\n      NA({len(n.nodeAnimations)}): {na[:300]}" if na else ''))
    return '\n'.join(lines)


# ---------------------------------------------------------------- VAT frames
# Shader: normal = q * (-1,0,0), tangent = q * (0,0,-1)   (see AnimateVAT.hlsl)

def quat_rotate(q, v):
    """q (...,4) xyzw, v (...,3)."""
    u = q[..., :3]
    w = q[..., 3:4]
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def frame_to_quat(normal, tangent):
    """Build quaternions q with q*(-1,0,0)=n and q*(0,0,-1)=t (t orthonormalized against n)."""
    n = normal / np.linalg.norm(normal, axis=1, keepdims=True).clip(1e-9)
    t = tangent - n * np.sum(tangent * n, axis=1, keepdims=True)
    bad = np.linalg.norm(t, axis=1) < 1e-6
    if bad.any():  # pick any perpendicular
        alt = np.where(np.abs(n[bad, 0:1]) < 0.9, [[1, 0, 0]], [[0, 1, 0]])
        t[bad] = np.cross(n[bad], alt)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    # R columns = images of basis vectors ex, ey, ez
    ex = -n
    ez = -t
    ey = np.cross(ez, ex)          # right-handed basis so det(R)=+1
    R = np.stack([ex, ey, ez], axis=2)  # (N,3,3) columns
    return mat_to_quat(R)


def mat_to_quat(R):
    m00, m11, m22 = R[:, 0, 0], R[:, 1, 1], R[:, 2, 2]
    tr = m00 + m11 + m22
    q = np.zeros((len(R), 4))
    c0 = tr > 0
    s = np.sqrt(np.maximum(tr[c0] + 1, 1e-12)) * 2
    q[c0, 3] = 0.25 * s
    q[c0, 0] = (R[c0, 2, 1] - R[c0, 1, 2]) / s
    q[c0, 1] = (R[c0, 0, 2] - R[c0, 2, 0]) / s
    q[c0, 2] = (R[c0, 1, 0] - R[c0, 0, 1]) / s
    c1 = ~c0 & (m00 > m11) & (m00 > m22)
    s = np.sqrt(np.maximum(1 + m00[c1] - m11[c1] - m22[c1], 1e-12)) * 2
    q[c1, 3] = (R[c1, 2, 1] - R[c1, 1, 2]) / s
    q[c1, 0] = 0.25 * s
    q[c1, 1] = (R[c1, 0, 1] + R[c1, 1, 0]) / s
    q[c1, 2] = (R[c1, 0, 2] + R[c1, 2, 0]) / s
    c2 = ~c0 & ~c1 & (m11 > m22)
    s = np.sqrt(np.maximum(1 + m11[c2] - m00[c2] - m22[c2], 1e-12)) * 2
    q[c2, 3] = (R[c2, 0, 2] - R[c2, 2, 0]) / s
    q[c2, 0] = (R[c2, 0, 1] + R[c2, 1, 0]) / s
    q[c2, 1] = 0.25 * s
    q[c2, 2] = (R[c2, 1, 2] + R[c2, 2, 1]) / s
    c3 = ~c0 & ~c1 & ~c2
    s = np.sqrt(np.maximum(1 + m22[c3] - m00[c3] - m11[c3], 1e-12)) * 2
    q[c3, 3] = (R[c3, 1, 0] - R[c3, 0, 1]) / s
    q[c3, 0] = (R[c3, 0, 2] + R[c3, 2, 0]) / s
    q[c3, 1] = (R[c3, 1, 2] + R[c3, 2, 1]) / s
    q[c3, 2] = 0.25 * s
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    q[q[:, 3] < 0] *= -1
    return q.astype(np.float32)


def decode_frame(rest_pos, frame):
    off = prop_array(frame.vertexProperties, 'offset')
    rot = prop_array(frame.vertexProperties, 'rotation')
    k = len(off)
    pos = rest_pos.copy()
    pos[:k] += off
    nrm = quat_rotate(rot, np.array([-1.0, 0, 0]))
    tan = quat_rotate(rot, np.array([0, 0, -1.0]))
    return pos, nrm, tan, k
