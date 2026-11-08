"""Build a panda .timbermesh from a beaver .timbermesh + config.

usage: python3 build_model.py ADULT out.timbermesh
"""
import sys, time, copy
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
import tmesh, geom, panda, configs
import model_pb2 as pb


def build(cfg, out_path, log=print, chunk=48, only=None):
    t0 = time.time()
    src = panda.Source(cfg['path'])
    b = panda.PandaBuilder(src, cfg, log)
    b.build_rest()
    if cfg.get('beaver_ao'):
        panda.remap_cavity(b, cfg['beaver_ao'], log=log, **cfg.get('cavity', {}))
    b.bind()
    V = len(b.P1)
    tri = b.tri
    uv0 = b.at['uv0']
    tw = np.sign(b.at['T'][:, 3]); tw[tw == 0] = -1
    sg = b.sg
    # rest attributes
    P1 = b.P1
    N1 = geom.vertex_normals(P1, tri, sg)
    T1 = geom.tangents_batch(P1[None], N1[None], uv0, tri)[0]

    model = pb.Model()
    model.CopyFrom(src.model)
    node = model.nodes[src.node_index]
    # rewrite mesh node
    del node.vertexProperties[:]
    for name, arr in [('position', P1), ('normal', N1), ('tangent', np.c_[T1, tw]), ('color', b.at['C']),
                      ('uv0', uv0), ('uv1', b.at['uv1'])]:
        node.vertexProperties.append(tmesh.make_prop(name, arr))
    node.vertexCount = V
    del node.meshes[:]
    m = node.meshes.add()
    m.indices.extend(tri.ravel().tolist())
    m.material = src.material
    anims = src.anims
    del node.vertexAnimations[:]
    stats = []
    for a in anims:
        if only and a.name not in only:
            continue
        Fs = src.frames(a)
        va = node.vertexAnimations.add()
        va.name = a.name
        va.framerate = a.framerate
        va.animatedVertexCount = V
        for c0 in range(0, len(Fs), chunk):
            Fp = b.transfer(Fs[c0:c0 + chunk])
            Nf = geom.vertex_normals_batch(Fp, tri, sg)
            Tf = geom.tangents_batch(Fp, Nf, uv0, tri)
            for k in range(len(Fp)):
                q = tmesh.frame_to_quat(Nf[k], Tf[k])
                fr = va.frames.add()
                # the game converts VAT data to half floats on load: pre-round so zlib can compress it
                off = (Fp[k] - P1).astype(np.float16).astype(np.float32)
                qh = q.astype(np.float16).astype(np.float32)
                fr.vertexProperties.append(tmesh.make_prop('offset', off))
                fr.vertexProperties.append(tmesh.make_prop('rotation', qh))
        stats.append((a.name, len(Fs)))
    adjust_nodes(model, src, b, cfg, log)
    panda.export_paint_data(b, out_path.replace('.timbermesh', '') + '.paint.npz')
    size = tmesh.save(model, out_path)
    log(f"wrote {out_path}: {V} verts, {len(tri)} tris, {len(stats)} anims, {sum(s[1] for s in stats)} frames, "
        f"{size / 1e6:.1f} MB in {time.time() - t0:.0f}s")
    return b, model


def adjust_nodes(model, src, b, cfg, log):
    """Move/scale attachment nodes (e.g. #Head for hats) so they fit the panda."""
    adj = cfg.get('node_adjust', {})
    for n in model.nodes:
        if n.name not in adj:
            continue
        a = adj[n.name]
        dp = a.get('dpos', (0, 0, 0))
        sc = a.get('scale', 1.0)
        n.position.x += dp[0]; n.position.y += dp[1]; n.position.z += dp[2]
        for na in n.nodeAnimations:
            for fr in na.frames:
                # offset expressed in the node's animated local rotation
                q = np.array([fr.rotation.x, fr.rotation.y, fr.rotation.z, fr.rotation.w])
                d = tmesh.quat_rotate(q[None], np.array(dp)[None])[0] if np.any(dp) else np.zeros(3)
                fr.position.x += d[0]; fr.position.y += d[1]; fr.position.z += d[2]
                fr.scale.x *= sc; fr.scale.y *= sc; fr.scale.z *= sc
        log(f"adjusted node {n.name}: dpos={dp} scale={sc}")


if __name__ == '__main__':
    cfg = getattr(configs, sys.argv[1])
    only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
    build(cfg, sys.argv[2], only=only)
