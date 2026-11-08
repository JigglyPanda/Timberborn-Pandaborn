"""Geometry utilities: split-mesh refinement, SDF sculpting, surface binding and
neighbourhood-rigid (Kabsch) animation transfer, normal/tangent rebuild.

Conventions: game/Unity space (x right, y up, z forward); triangle winding such that
cross(p1-p0, p2-p0) points outward (verified against the beaver's authored normals).
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree


# ---------------------------------------------------------------- welding / groups
def weld(P, decimals=5):
    key = np.round(P, decimals)
    u, inv = np.unique(key, axis=0, return_inverse=True)
    return u, inv.ravel()


def smoothing_groups(P, N, decimals=5, cos_thresh=0.98):
    """Split vertices that share a position AND a similar authored normal share a smoothing id."""
    _, inv = weld(P, decimals)
    gid = np.full(len(P), -1)
    nxt = 0
    for g in np.unique(inv):
        ids = np.where(inv == g)[0]
        for i in ids:
            if gid[i] >= 0:
                continue
            gid[i] = nxt
            for j in ids:
                if gid[j] < 0 and np.dot(N[i], N[j]) > cos_thresh:
                    gid[j] = nxt
            nxt += 1
    return gid


def edge_graph(tri, nverts, P=None):
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    w = np.ones(len(e)) if P is None else np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
    A = coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(nverts, nverts)).tocsr()
    return A, e


# ---------------------------------------------------------------- refinement
def refine(P, tri, attrs, weld_inv, mark_tri, iterations=1):
    """Red-green refinement on a split mesh.

    mark_tri: bool per triangle -> those are 1:4 split; conforming closure adds 1:2 splits.
    attrs: dict name -> (V, k) arrays interpolated linearly (positions handled separately).
    weld_inv: welded id per split vertex (seam duplicates share an id).
    Returns P, tri, attrs, weld_inv, parent (list of {orig_idx: weight}) for new mesh.
    """
    parents = [{i: 1.0} for i in range(len(P))]
    for it in range(iterations):
        W = weld_inv
        # welded edges to split
        def wedge(a, b):
            x, y = W[a], W[b]
            return (x, y) if x < y else (y, x)
        split = set()
        for t, m in zip(tri, mark_tri):
            if m:
                split.update(wedge(t[k], t[(k + 1) % 3]) for k in range(3))
        # closure: triangles with 2 split edges -> split the third as well
        changed = True
        while changed:
            changed = False
            for t in tri:
                es = [wedge(t[k], t[(k + 1) % 3]) for k in range(3)]
                c = sum(e in split for e in es)
                if c == 2:
                    split.update(es)
                    changed = True
        P = list(P)
        A = {k: list(v) for k, v in attrs.items()}
        W = list(W)
        mid = {}
        welded_mid = {}

        def midpoint(a, b):
            key = (a, b) if a < b else (b, a)
            if key in mid:
                return mid[key]
            idx = len(P)
            P.append((np.asarray(P[a]) + np.asarray(P[b])) * 0.5)
            for k in A:
                A[k].append((np.asarray(A[k][a]) + np.asarray(A[k][b])) * 0.5)
            we = wedge(a, b)
            if we not in welded_mid:
                welded_mid[we] = max(max(W), max(welded_mid.values(), default=-1)) + 1
            W.append(welded_mid[we])
            pa, pb = parents[a], parents[b]
            d = {}
            for kk, vv in pa.items():
                d[kk] = d.get(kk, 0) + 0.5 * vv
            for kk, vv in pb.items():
                d[kk] = d.get(kk, 0) + 0.5 * vv
            parents.append(d)
            mid[key] = idx
            return idx

        new_tri, new_mark = [], []
        for t, m in zip(tri, mark_tri):
            a, b, c = t
            es = [wedge(a, b) in split, wedge(b, c) in split, wedge(c, a) in split]
            n = sum(es)
            if n == 0:
                new_tri.append([a, b, c]); new_mark.append(False)
            elif n == 3:
                ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
                new_tri += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
                new_mark += [m] * 4
            else:  # n == 1
                k = es.index(True)
                v = [a, b, c]
                p, q, r = v[k], v[(k + 1) % 3], v[(k + 2) % 3]
                mm = midpoint(p, q)
                new_tri += [[p, mm, r], [mm, q, r]]
                new_mark += [False, False]
        P = np.array(P, dtype=np.float64)
        attrs = {k: np.array(v) for k, v in A.items()}
        weld_inv = np.array(W)
        tri = np.array(new_tri)
        mark_tri = np.array(new_mark)
    return P, tri, attrs, weld_inv, parents


# ---------------------------------------------------------------- SDF primitives
def sd_ellipsoid(x, c, r, R=None):
    """Approximate signed distance to an ellipsoid (centre c, radii r, optional rotation R (3x3, columns=axes))."""
    d = x - c
    if R is not None:
        d = d @ R
    k0 = np.linalg.norm(d / r, axis=-1)
    k1 = np.linalg.norm(d / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sd_capsule(x, a, b, ra, rb=None):
    rb = ra if rb is None else rb
    ba = b - a
    h = np.clip(np.sum((x - a) * ba, -1) / np.dot(ba, ba), 0, 1)
    r = ra + (rb - ra) * h
    return np.linalg.norm(x - a - h[..., None] * ba, axis=-1) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sdf_grad(f, x, eps=1e-4):
    g = np.zeros_like(x)
    for i in range(3):
        e = np.zeros(3); e[i] = eps
        g[:, i] = (f(x + e) - f(x - e)) / (2 * eps)
    return g


def project_to_sdf(f, x, weight, iters=8):
    """Move points toward the zero set of f, by fraction weight (0..1)."""
    y = x.copy()
    for _ in range(iters):
        d = f(y)
        g = sdf_grad(f, y)
        gn = np.sum(g * g, 1).clip(1e-9)
        y = y - (d / gn)[:, None] * g
    return x + weight[:, None] * (y - x)


# ---------------------------------------------------------------- normals / tangents
def vertex_normals(P, tri, smooth_gid):
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    ng = smooth_gid.max() + 1
    acc = np.zeros((ng, 3))
    for k in range(3):
        np.add.at(acc, smooth_gid[tri[:, k]], fn)
    acc /= np.linalg.norm(acc, axis=1, keepdims=True).clip(1e-12)
    return acc[smooth_gid]


def vertex_normals_batch(Pf, tri, smooth_gid):
    """Pf: (F,V,3) -> (F,V,3)."""
    fn = np.cross(Pf[:, tri[:, 1]] - Pf[:, tri[:, 0]], Pf[:, tri[:, 2]] - Pf[:, tri[:, 0]])
    ng = smooth_gid.max() + 1
    acc = np.zeros((Pf.shape[0], ng, 3))
    for k in range(3):
        np.add.at(acc, (slice(None), smooth_gid[tri[:, k]]), fn)
    acc /= np.linalg.norm(acc, axis=2, keepdims=True).clip(1e-12)
    return acc[:, smooth_gid]


def tangents_batch(Pf, Nf, uv, tri, tangent_gid=None):
    p0, p1, p2 = Pf[:, tri[:, 0]], Pf[:, tri[:, 1]], Pf[:, tri[:, 2]]
    w0, w1, w2 = uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = w1 - w0, w2 - w0
    det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    r = 1.0 / det
    sd = (e1 * d2[None, :, 1:2] - e2 * d1[None, :, 1:2]) * r[None, :, None]
    ts = np.zeros_like(Pf)
    for k in range(3):
        np.add.at(ts, (slice(None), tri[:, k]), sd)
    if tangent_gid is not None:  # share across same position+uv duplicates
        ng = tangent_gid.max() + 1
        acc = np.zeros((Pf.shape[0], ng, 3))
        np.add.at(acc, (slice(None), tangent_gid), ts)
        ts = acc[:, tangent_gid]
    t = ts - Nf * np.sum(ts * Nf, 2, keepdims=True)
    t /= np.linalg.norm(t, axis=2, keepdims=True).clip(1e-12)
    return t


# ---------------------------------------------------------------- binding
def closest_point_on_triangles(p, A, B, C):
    """p (3,), A,B,C (T,3) -> (dist2 (T,), bary (T,3)). Ericson's algorithm, vectorised over T."""
    ab, ac, ap = B - A, C - A, p - A
    d1, d2 = np.sum(ab * ap, 1), np.sum(ac * ap, 1)
    bp = p - B
    d3, d4 = np.sum(ab * bp, 1), np.sum(ac * bp, 1)
    cp = p - C
    d5, d6 = np.sum(ab * cp, 1), np.sum(ac * cp, 1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    T = len(A)
    bary = np.zeros((T, 3))
    done = np.zeros(T, bool)

    def setb(mask, b):
        nonlocal done
        m = mask & ~done
        bary[m] = b[m] if b.ndim == 2 else b
        done |= m

    one = np.ones(T)
    z = np.zeros(T)
    setb((d1 <= 0) & (d2 <= 0), np.stack([one, z, z], 1))
    setb((d3 >= 0) & (d4 <= d3), np.stack([z, one, z], 1))
    v = d1 / np.where(d1 - d3 == 0, 1e-12, d1 - d3)
    setb((vc <= 0) & (d1 >= 0) & (d3 <= 0), np.stack([1 - v, v, z], 1))
    setb((d6 >= 0) & (d5 <= d6), np.stack([z, z, one], 1))
    w = d2 / np.where(d2 - d6 == 0, 1e-12, d2 - d6)
    setb((vb <= 0) & (d2 >= 0) & (d6 <= 0), np.stack([1 - w, z, w], 1))
    w2 = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1e-12, (d4 - d3) + (d5 - d6))
    setb((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), np.stack([z, 1 - w2, w2], 1))
    den = 1.0 / np.where(va + vb + vc == 0, 1e-12, va + vb + vc)
    vv, ww = vb * den, vc * den
    setb(np.ones(T, bool), np.stack([1 - vv - ww, vv, ww], 1))
    q = bary[:, 0:1] * A + bary[:, 1:2] * B + bary[:, 2:3] * C
    return np.sum((q - p) ** 2, 1), bary


def kabsch_batch(X, Y, w):
    """Weighted rotations mapping centred X->Y. X,Y: (...,K,3), w: (...,K). Returns R (...,3,3), cx, cy."""
    ws = w / w.sum(-1, keepdims=True)
    cx = np.einsum('...k,...kd->...d', ws, X)
    cy = np.einsum('...k,...kd->...d', ws, Y)
    Xc = X - cx[..., None, :]
    Yc = Y - cy[..., None, :]
    H = np.einsum('...k,...ki,...kj->...ij', ws, Xc, Yc)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(np.swapaxes(Vt, -1, -2) @ np.swapaxes(U, -1, -2)))
    D = np.zeros_like(H)
    D[..., 0, 0] = 1
    D[..., 1, 1] = 1
    D[..., 2, 2] = d
    R = np.swapaxes(Vt, -1, -2) @ D @ np.swapaxes(U, -1, -2)
    return R, cx, cy
