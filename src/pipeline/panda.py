"""Beaver -> panda geometry builder (rest pose sculpt + all-animation transfer)."""
import sys
import time
import numpy as np
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import tmesh
import geom

V3 = lambda *a: np.array(a, dtype=np.float64)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Source:
    """Beaver model data (rest + animations) for the main mesh node."""

    def __init__(self, path, node_index=1):
        self.model = tmesh.load(path)
        n = self.model.nodes[node_index]
        self.node_index = node_index
        self.node = n
        g = lambda k: tmesh.prop_array(n.vertexProperties, k)
        self.P = g('position').astype(np.float64)
        self.N = g('normal').astype(np.float64)
        self.T = g('tangent').astype(np.float64)
        self.C = g('color')
        self.uv0 = g('uv0').astype(np.float64)
        self.uv1 = g('uv1').astype(np.float64)
        self.tri = np.array(n.meshes[0].indices).reshape(-1, 3)
        self.material = n.meshes[0].material
        self.Pw, self.winv = geom.weld(self.P)
        self.sg = geom.smoothing_groups(self.P, self.N)
        self.anims = list(n.vertexAnimations)

    def frames(self, anim):
        """(F,V,3) positions for an animation."""
        out = np.empty((len(anim.frames), len(self.P), 3))
        for i, fr in enumerate(anim.frames):
            off = tmesh.prop_array(fr.vertexProperties, 'offset')
            out[i] = self.P
            out[i, :len(off)] += off
        return out


def mesh_components(tri, winv):
    nw = winv.max() + 1
    t = winv[tri]
    r = np.r_[t[:, 0], t[:, 1], t[:, 2]]
    c = np.r_[t[:, 1], t[:, 2], t[:, 0]]
    k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(nw, nw)), directed=False)
    return lab[winv]


def uv_islands(tri, nv):
    r = np.r_[tri[:, 0], tri[:, 1], tri[:, 2]]
    c = np.r_[tri[:, 1], tri[:, 2], tri[:, 0]]
    k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(nv, nv)), directed=False)
    return lab


def geodesic_from(Pw, tri_w, seeds_w, limit=np.inf):
    A, _ = geom.edge_graph(tri_w, len(Pw), Pw)
    d = dijkstra(A, directed=False, indices=np.unique(seeds_w), limit=limit, min_only=True)
    return d


class PandaBuilder:
    def __init__(self, src: Source, cfg: dict, log=print):
        self.s = src
        self.cfg = cfg
        self.log = log

    # ------------------------------------------------------------ regions on the source mesh
    def source_regions(self):
        s, cfg = self.s, self.cfg
        comp = mesh_components(s.tri, s.winv)
        main = np.bincount(comp).argmax()
        self.teeth_src = comp != main
        isl = uv_islands(s.tri, len(s.P))
        # tail: islands whose vertices are all behind tail_root_z
        tail = np.zeros(len(s.P), bool)
        for i in np.unique(isl):
            m = isl == i
            if s.P[m, 2].max() < cfg['tail_root'][2] + 0.01 and s.P[m, 1].max() < 0.32 * cfg['height']:
                tail |= m
        self.tail_src = tail
        # arms / soles: islands matched by centroid
        self.arm_src = np.zeros(len(s.P), bool)
        self.sole_src = np.zeros(len(s.P), bool)
        for i in np.unique(isl):
            m = isl == i
            c = s.P[m].mean(0)
            if m.sum() > 30 and abs(c[0]) > cfg['arm_island_x'] and not tail[m].any():
                self.arm_src |= m
            if m.sum() >= 8 and c[1] < 0.02 * cfg['height'] / 0.53 and abs(c[0]) > 0.04 * cfg['scale']:
                self.sole_src |= m
        self.log(f"regions: teeth={self.teeth_src.sum()} tail={tail.sum()} arms={self.arm_src.sum()} soles={self.sole_src.sum()}")

    # ------------------------------------------------------------ rest-pose sculpt
    def build_rest(self):
        s, cfg = self.s, self.cfg
        self.source_regions()
        # --- refinement on head (and ears twice)
        head_y = cfg['neck_y'][0]
        cent = s.P[s.tri].mean(1)
        is_head_tri = (cent[:, 1] > head_y) & (cent[:, 2] > cfg['head_zmin']) & ~self.teeth_src[s.tri].any(1)
        attrs = dict(uv0=s.uv0, uv1=s.uv1, T=s.T, C=s.C.astype(np.float64), N=s.N, src=np.eye(1)[np.zeros(len(s.P), int)])
        P, tri, at, winv, parents = geom.refine(s.P, s.tri, attrs, s.winv, is_head_tri, iterations=1)
        # second level around ears
        ears = np.array(cfg['ear']['c'])
        earc = [ears * [1, 1, 1], ears * [-1, 1, 1]]
        cent = P[tri].mean(1)
        near_ear = np.zeros(len(tri), bool)
        for e in earc:
            near_ear |= np.linalg.norm(cent - e, axis=1) < cfg['ear']['r'] * 1.25
        # parents must be composed across levels
        P2, tri2, at2, winv2, parents2 = geom.refine(P, tri, at, winv, near_ear, iterations=1)
        comp_par = []
        for d in parents2:
            dd = {}
            for k, w in d.items():
                for k2, w2 in parents[k].items():
                    dd[k2] = dd.get(k2, 0) + w * w2
            comp_par.append(dd)
        P, tri, at, winv, parents = P2, tri2, at2, winv2, comp_par
        self.parents = parents
        V = len(P)
        self.log(f"refined: {len(s.P)} -> {V} verts, {len(s.tri)} -> {len(tri)} tris")
        # region flags inherited from parents (any parent flagged)
        def inherit(flag):
            return np.array([any(flag[k] for k in d) for d in parents])
        def inherit_all(flag):
            return np.array([all(flag[k] for k in d) for d in parents])
        teeth = inherit_all(self.teeth_src)
        tail = inherit_all(self.tail_src)
        arm = inherit_all(self.arm_src)
        sole = inherit(self.sole_src)
        N0 = at['N'] / np.linalg.norm(at['N'], axis=1, keepdims=True)
        # welded graph for geodesics
        Pw = np.zeros((winv.max() + 1, 3)); Pw[winv] = P
        tw = winv[tri]
        A, _ = geom.edge_graph(tw, len(Pw), Pw)
        dsole = dijkstra(A, directed=False, indices=np.unique(winv[sole]), min_only=True)[winv]
        darm = dijkstra(A, directed=False, indices=np.unique(winv[arm]), min_only=True)[winv]
        self.geo = dict(dsole=dsole, darm=darm)
        X = P.copy()
        y = P[:, 1]

        # ---- head SDF (union of cranium, cheeks, muzzle, jaw)
        H = cfg
        cr = H['cranium']; ch = H['cheek']; mz = H['muzzle']; jw = H['jaw']
        def f_head(x):
            d = geom.sd_ellipsoid(x, V3(*cr['c']), V3(*cr['r']))
            for sx in (1, -1):
                d = geom.smin(d, geom.sd_ellipsoid(x, V3(ch['c'][0] * sx, *ch['c'][1:]), V3(*ch['r'])), ch['k'])
            d = geom.smin(d, geom.sd_ellipsoid(x, V3(*mz['c']), V3(*mz['r'])), mz['k'])
            d = geom.smin(d, geom.sd_ellipsoid(x, V3(*jw['c']), V3(*jw['r'])), jw['k'])
            return d
        self.f_head = f_head
        w_head = smoothstep(cfg['neck_y'][0], cfg['neck_y'][1], y) * smoothstep(cfg['head_zmin'] - 0.03, cfg['head_zmin'] + 0.02, P[:, 2])
        w_head *= ~teeth
        X = geom.project_to_sdf(f_head, X, w_head * cfg['head_strength'])

        # ---- body SDF
        bd = cfg['body']
        def f_body(x):
            d = geom.sd_ellipsoid(x, V3(*bd['belly_c']), V3(*bd['belly_r']))
            d = geom.smin(d, geom.sd_ellipsoid(x, V3(*bd['chest_c']), V3(*bd['chest_r'])), bd['k'])
            return d
        w_body = (1 - smoothstep(cfg['neck_y'][0] - 0.04, cfg['neck_y'][0] + 0.01, y))
        w_body *= smoothstep(0.02, bd['limb_fade'], darm) * smoothstep(bd['leg_fade'][0], bd['leg_fade'][1], dsole)
        w_body *= ~tail & ~teeth
        # only allow outward growth mostly (pandas are chubby) - inward motion damped
        Xb = geom.project_to_sdf(f_body, X, w_body * bd['strength'])
        inward = np.sum((Xb - X) * N0, 1) < 0
        Xb[inward] = X[inward] + (Xb[inward] - X[inward]) * bd['inward_keep']
        X = Xb

        # ---- limbs: chunkier (normal inflation)
        lm = cfg['limbs']
        w_arm_infl = (1 - smoothstep(0.0, lm['arm_fade'], darm)) * (1 - smoothstep(0.30, 0.42, y / cfg['height'] * 0.53 / 0.53))
        w_leg_infl = (1 - smoothstep(lm['leg_len'] * 0.6, lm['leg_len'], dsole))
        infl = lm['arm'] * w_arm_infl + lm['leg'] * w_leg_infl
        infl *= ~tail & ~teeth & ~sole
        X = X + N0 * infl[:, None]

        # ---- v2: real limb thickening (radial scaling around each limb's centreline) + rounder paws
        if cfg.get('tubes'):
            X = self.tube_sculpt(X, P, tri, winv, arm, sole, darm, dsole, teeth, tail, cfg['tubes'])

        # ---- ears: half-ellipsoid bumps mapped from a surface disk
        er = cfg['ear']
        for sx in (1, -1):
            c0 = V3(er['c'][0] * sx, *er['c'][1:])
            # snap centre to current surface
            k = np.argmin(np.linalg.norm(X - c0, axis=1) + 10 * teeth)
            c = X[k]
            n = N0[k]
            up = V3(0, 1, 0)
            dirv = n * er['normal_mix'] + up * (1 - er['normal_mix']) + V3(sx * er['splay'], 0, 0)
            dirv /= np.linalg.norm(dirv)
            fwd = V3(0, 0, 1) - dirv * dirv[2]; fwd /= np.linalg.norm(fwd)
            side = np.cross(dirv, fwd)
            rel = X - c
            a = rel @ side; b = rel @ fwd; h0 = rel @ dirv
            rho2 = (a ** 2 + b ** 2) / er['r'] ** 2
            m = (rho2 < 1) & (np.abs(h0) < er['r']) & w_head.astype(bool) & ~teeth
            prof = np.sqrt(np.clip(1 - rho2, 0, 1))
            # dome: lift by profile, squash front/back thickness
            lift = er['h'] * prof ** er['sharp']
            newb = b * (er['thick'] + (1 - er['thick']) * (1 - prof))
            X[m] = (c + side * a[m, None] + fwd * newb[m, None] + dirv * (h0[m, None] + lift[m, None]))
            self.ear_mask = getattr(self, 'ear_mask', np.zeros(V, bool)) | m
            setattr(self, f'ear_centre_{sx}', c + dirv * er['h'] * 0.55)
            setattr(self, f'ear_dir_{sx}', dirv)

        # ---- tail: collapse to a round stub
        tr = V3(*cfg['tail_root'])
        tl = cfg['tail_stub']
        if tail.any():
            Pt = P[tail]
            L = np.clip(tr[2] - Pt[:, 2], 0, None)            # distance behind the root
            t01 = np.clip(L / L.max(), 0, 1)
            # half-width of the paddle as a function of t (binned max |x|)
            bins = np.clip((t01 * 12).astype(int), 0, 11)
            wmax = np.array([np.abs(Pt[bins == k, 0]).max() if np.any(bins == k) else 1e-3 for k in range(12)])
            wmax = np.maximum(np.maximum.accumulate(wmax[::-1])[::-1] * 0 + wmax, 1e-3)
            u = np.clip(Pt[:, 0] / wmax[bins], -1, 1)
            # top/bottom side from the paddle mid-surface height at that t
            mid = np.array([Pt[bins == k, 1].mean() if np.any(bins == k) else 0 for k in range(12)])
            side = np.where(Pt[:, 1] >= mid[bins], 1.0, -1.0)
            side = np.where(np.abs(N0[tail, 1]) > 0.3, np.sign(N0[tail, 1]), side)
            phi = np.where(side > 0, 0.5 * np.pi * u, np.sign(u + 1e-9) * (np.pi - 0.5 * np.pi * np.abs(u)))
            th_root = np.radians(tl.get('root_deg', 115))
            th = (1 - t01) * th_root
            c = tr + V3(0, tl['dy'], -tl['len'] * 0.45)
            R = V3(tl['w'], tl['h'], tl['len'] * 0.55)
            dirv = np.stack([np.sin(th) * np.sin(phi), np.sin(th) * np.cos(phi), -np.cos(th)], 1)
            newp = c + dirv * R
            blend = smoothstep(0.0, 0.10, t01)[:, None]
            X[tail] = Pt * (1 - blend) + newp * blend
        self.stub_centre = tr + V3(0, tl['dy'], -tl['len'] * 0.45)

        # ---- teeth: tuck away inside the muzzle
        if teeth.any():
            tc = V3(*cfg['teeth_hide'])
            X[teeth] = tc + (P[teeth] - tc) * 0.04

        # ---- gentle smoothing of head surface (Laplacian on welded graph, head & ears only)
        X = self.laplacian_smooth(X, tri, winv, (w_head > 0.5) & ~teeth, cfg.get('smooth_iters', 4), 0.35)

        self.P0, self.P1, self.tri, self.winv, self.at = P, X, tri, winv, at
        self.flags = dict(teeth=teeth, tail=tail, arm=arm, sole=sole, head=w_head > 0.5)
        self.w_head = w_head
        self.sg = self.smoothing_ids(P, at['N'], winv)
        return X

    def tube_sculpt(self, X, P, tri, winv, arm, sole, darm, dsole, teeth, tail, tc):
        """Thicken arms/legs like a panda's and turn long beaver feet into round paws."""
        V = len(X)
        nw = winv.max() + 1
        Pw = np.zeros((nw, 3)); Pw[winv] = P
        A, _ = geom.edge_graph(winv[tri], nw, Pw)
        Y = X.copy()
        x = P[:, 0]
        for side in (1, -1):
            sidem = (x * side) > 0.005
            # ---------------- arms: param from the hand tip along the arm
            am = arm & sidem
            if am.any():
                tip = np.nonzero(am)[0][np.argmax(np.abs(x[am]) - 0.5 * P[am, 1])]
                t = dijkstra(A, directed=False, indices=winv[tip])[winv]
                reg = (darm < tc['arm_reach']) & sidem & ~teeth & ~tail & np.isfinite(t)
                w = 1 - smoothstep(0.0, tc['arm_reach'], darm)
                s_prof = lambda tt: tc['paw_scale'] + (tc['arm_scale'] - tc['paw_scale']) * smoothstep(0.0, tc['paw_len'], tt)
                Y = self._tube(Y, X, reg, t, w, s_prof, tc['bin'])
            # ---------------- legs: horizontal slices above the paw
            lm = (dsole < tc['leg_reach']) & sidem & ~teeth & ~tail
            if lm.any():
                tl = P[:, 1].copy()
                w = (1 - smoothstep(tc['leg_reach'] * 0.55, tc['leg_reach'], dsole)) * smoothstep(tc['foot_y'] * 0.6, tc['foot_y'] * 1.4, P[:, 1])
                Y = self._tube(Y, X, lm, tl, w, lambda tt: np.full_like(tt, tc['leg_scale']), tc['bin'], axis=np.array([0, 1.0, 0]))
                # ---------------- hind paw: shorter, wider, puffier
                fm = lm & (P[:, 1] < tc['foot_y'] * 1.4)
                if fm.any():
                    fw = 1 - smoothstep(tc['foot_y'] * 0.8, tc['foot_y'] * 1.4, P[:, 1])
                    fc = P[fm & (P[:, 1] < tc['foot_y'])].mean(0)
                    anchor_z = fc[2] + tc['paw_anchor_dz']
                    d = Y[fm] - np.array([fc[0], 0, anchor_z])
                    sc = np.array([tc['paw_wide'], 1.0, tc['paw_short']])
                    nd = d * sc
                    nd[:, 1] = d[:, 1] * (1 + (tc['paw_puff'] - 1) * (d[:, 1] > 0.004))
                    newp = np.array([fc[0], 0, anchor_z]) + nd
                    Y[fm] = Y[fm] * (1 - fw[fm, None]) + newp * fw[fm, None]
        return Y

    def _tube(self, Y, X, reg, t, w, s_prof, binw, axis=None):
        idx = np.nonzero(reg)[0]
        if len(idx) < 10:
            return Y
        tt = t[idx]
        b = np.floor((tt - tt.min()) / binw).astype(int)
        nb = b.max() + 1
        cent = np.zeros((nb, 3)); cnt = np.zeros(nb)
        np.add.at(cent, b, X[idx]); np.add.at(cnt, b, 1)
        good = cnt > 0
        cent[good] /= cnt[good, None]
        # fill empty bins and smooth the centreline
        for k in range(nb):
            if not good[k]:
                j = np.nonzero(good)[0]; cent[k] = cent[j[np.argmin(np.abs(j - k))]]
        for _ in range(3):
            cent[1:-1] = 0.25 * cent[:-2] + 0.5 * cent[1:-1] + 0.25 * cent[2:]
        # continuous position on the centreline
        f = (tt - tt.min()) / binw - 0.5
        k0 = np.clip(np.floor(f).astype(int), 0, nb - 1); k1 = np.clip(k0 + 1, 0, nb - 1)
        a = np.clip(f - np.floor(f), 0, 1)[:, None]
        c = cent[k0] * (1 - a) + cent[k1] * a
        if axis is None:
            ax = cent[k1] - cent[k0]
            ax[np.linalg.norm(ax, axis=1) < 1e-6] = (cent[-1] - cent[0])
            ax /= np.linalg.norm(ax, axis=1, keepdims=True) + 1e-12
        else:
            ax = np.broadcast_to(axis, (len(idx), 3))
        r = X[idx] - c
        rpar = np.sum(r * ax, 1, keepdims=True) * ax
        rperp = r - rpar
        s = 1 + (s_prof(tt) - 1) * w[idx]
        Y[idx] = Y[idx] + rperp * (s[:, None] - 1)
        return Y

    def laplacian_smooth(self, X, tri, winv, mask, iters, lam):
        nw = winv.max() + 1
        Xw = np.zeros((nw, 3)); Xw[winv] = X
        mw = np.zeros(nw, bool); mw[winv[mask]] = True
        tw = winv[tri]
        e = np.unique(np.sort(np.concatenate([tw[:, [0, 1]], tw[:, [1, 2]], tw[:, [2, 0]]]), 1), axis=0)
        for _ in range(iters):
            acc = np.zeros_like(Xw); cnt = np.zeros(nw)
            np.add.at(acc, e[:, 0], Xw[e[:, 1]]); np.add.at(acc, e[:, 1], Xw[e[:, 0]])
            np.add.at(cnt, e[:, 0], 1); np.add.at(cnt, e[:, 1], 1)
            avg = acc / cnt[:, None].clip(1)
            # Taubin (lambda/mu) to avoid shrink
            Xw[mw] += lam * (avg[mw] - Xw[mw])
            acc = np.zeros_like(Xw)
            np.add.at(acc, e[:, 0], Xw[e[:, 1]]); np.add.at(acc, e[:, 1], Xw[e[:, 0]])
            avg = acc / cnt[:, None].clip(1)
            Xw[mw] += -0.36 * (avg[mw] - Xw[mw])
        return Xw[winv]

    def smoothing_ids(self, P, N, winv):
        N = N / np.linalg.norm(N, axis=1, keepdims=True)
        gid = np.full(len(P), -1); nxt = 0
        order = np.argsort(winv, kind='stable')
        ws = winv[order]
        starts = np.r_[0, np.nonzero(np.diff(ws))[0] + 1, len(ws)]
        for a, b in zip(starts[:-1], starts[1:]):
            ids = order[a:b]
            for i in ids:
                if gid[i] >= 0: continue
                gid[i] = nxt
                for j in ids:
                    if gid[j] < 0 and np.dot(N[i], N[j]) > 0.98: gid[j] = nxt
                nxt += 1
        return gid

    # ------------------------------------------------------------ binding
    def bind(self, ring=4, radius=None, K=20):
        s = self.s
        P1 = self.P1
        V = len(P1)
        radius = radius or self.cfg['bind_radius']
        sP = s.P
        stri = s.tri
        tw_s = s.winv[stri]
        A, _ = geom.edge_graph(tw_s, s.winv.max() + 1)
        # forbidden source triangles: teeth, and tail beyond root zone
        tail_far = self.tail_src & (s.P[:, 2] < self.cfg['tail_root'][2] - self.cfg['tail_bind_zone'])
        bad_tri = self.teeth_src[stri].any(1) | tail_far[stri].any(1)
        self.bad_tri = bad_tri
        # origin welded vertex for each panda vertex = heaviest parent
        origin = np.array([max(d.items(), key=lambda kv: kv[1])[0] for d in self.parents])
        ow = s.winv[origin]
        uniq = np.unique(ow)
        Dring = dijkstra(A, directed=False, indices=uniq, limit=ring + 0.5)
        row = {w: i for i, w in enumerate(uniq)}
        # triangle lists per source welded vertex by ring distance
        tri_tbl = {}
        bt = np.zeros(V, int); bb = np.zeros((V, 3))
        tri_c = sP[stri].mean(1)
        flags = self.flags
        root_zone = ~bad_tri & (tri_c[:, 2] < self.cfg['tail_root'][2] + 0.05) & (tri_c[:, 1] < 0.35 * self.cfg['height'])
        head_tris = ~bad_tri & (tri_c[:, 1] > self.cfg['neck_y'][0]) & (tri_c[:, 2] > 0.0)
        for i in range(V):
            if flags['tail'][i]:
                cand = np.nonzero(root_zone)[0]
            elif flags['teeth'][i]:
                cand = np.nonzero(head_tris)[0]
            else:
                w = ow[i]
                if w not in tri_tbl:
                    near = np.isfinite(Dring[row[w]])
                    tri_tbl[w] = np.nonzero(near[tw_s].all(1) & ~bad_tri)[0]
                cand = tri_tbl[w]
                if len(cand) == 0:
                    cand = np.nonzero(~bad_tri)[0]
            d2, bary = geom.closest_point_on_triangles(P1[i], sP[stri[cand, 0]], sP[stri[cand, 1]], sP[stri[cand, 2]])
            j = np.argmin(d2)
            bt[i] = cand[j]; bb[i] = bary[j]
        self.bind_tri, self.bind_bary = bt, bb
        base = np.einsum('vk,vkd->vd', bb, sP[stri[bt]])
        self.offset = P1 - base
        # Kabsch neighbourhoods over source *welded* vertices (excluding teeth / far tail)
        Pw = s.Pw
        okw = np.ones(len(Pw), bool)
        okw[s.winv[self.teeth_src]] = False
        okw[s.winv[tail_far]] = False
        # representative split vertex for each welded
        rep = np.zeros(len(Pw), int); rep[s.winv] = np.arange(len(s.P))
        Ag, _ = geom.edge_graph(tw_s, len(Pw), Pw)
        tri_w = s.winv[stri[bt]]
        uniq_t = np.unique(bt)
        nb_idx = np.zeros((V, K), int); nb_w = np.zeros((V, K))
        cache = {}
        for t in uniq_t:
            seeds = np.unique(s.winv[stri[t]])
            dist = dijkstra(Ag, directed=False, indices=seeds, min_only=True, limit=radius * 2.5)
            cand = np.nonzero(np.isfinite(dist) & okw)[0]
            cache[t] = (cand, dist[cand])
        for i in range(V):
            cand, dg = cache[bt[i]]
            base_i = base[i]
            de = np.linalg.norm(Pw[cand] - base_i, axis=1)
            score = np.maximum(dg, de)
            o = np.argsort(score)[:K]
            sel = cand[o]; sc = score[o]
            w = np.exp(-(sc / radius) ** 2)
            if len(sel) < K:
                sel = np.r_[sel, np.repeat(sel[:1], K - len(sel))]
                w = np.r_[w, np.zeros(K - len(w))]
            nb_idx[i] = rep[sel]; nb_w[i] = w
        self.nb_idx, self.nb_w = nb_idx, nb_w
        self.log(f"bound {V} verts; max offset {np.linalg.norm(self.offset, axis=1).max():.4f}")

    def transfer(self, Fsrc):
        """Fsrc: (F, Vs, 3) source frame positions -> (F, V, 3) panda positions."""
        s = self.s
        tri = s.tri[self.bind_tri]
        base = np.einsum('vk,fvkd->fvd', self.bind_bary, Fsrc[:, tri])
        X = s.P[self.nb_idx]                     # (V,K,3)
        Y = Fsrc[:, self.nb_idx]                 # (F,V,K,3)
        w = np.broadcast_to(self.nb_w, Y.shape[:-1])
        R, cx, cy = geom.kabsch_batch(np.broadcast_to(X, Y.shape), Y, w)
        return base + np.einsum('fvij,vj->fvi', R, self.offset)


def export_paint_data(b, path):
    """Per-vertex fields on the panda rest mesh used by the texture painter."""
    import numpy as np
    P1, tri = b.P1, b.tri
    N1 = geom.vertex_normals(P1, tri, b.sg)
    ear = getattr(b, 'ear_mask', np.zeros(len(P1), bool)).astype(float)
    cav = getattr(b, 'cavity_tri', np.zeros(len(tri), bool)).astype(float)
    np.savez(path, P=P1, N=N1, tri=tri, uv0=b.at['uv0'], ear=ear, cavity=cav,
             darm=b.geo['darm'], dsole=b.geo['dsole'], head=b.w_head,
             tail=b.flags['tail'].astype(float), teeth=b.flags['teeth'].astype(float),
             sole=b.flags['sole'].astype(float), arm=b.flags['arm'].astype(float),
             ear_c1=b.ear_centre_1, ear_c2=b.ear_centre_m1 if hasattr(b, 'ear_centre_m1') else getattr(b, 'ear_centre_-1'),
             stub=b.stub_centre)


def remap_cavity(b, beaver_ao_png, ao_thr=0.35, region=None, target_xy=(0.060, 0.395), scale=0.12, free_uv=(0.848, 0.914), free_r=0.044, log=print):
    """Replace the beaver's mouth cavity (and folded lip undersides) with a clean cap that lies on the
    sculpted head surface and samples a neutral patch of fur in the fixed beaver AO/normal maps."""
    import collections
    from PIL import Image
    ao = np.array(Image.open(beaver_ao_png).convert('L')) / 255.0
    S = ao.shape[0]
    uv = b.at['uv0']
    A = ao[((1 - uv[:, 1]) * S).astype(int).clip(0, S - 1), (uv[:, 0] * S).astype(int).clip(0, S - 1)]
    P = b.P1
    tri = b.tri
    r = region or dict(z=0.10, y=(0.34, 0.40))
    vm = (b.w_head > 0.5) & (P[:, 2] > r['z']) & (P[:, 1] > r['y'][0]) & (P[:, 1] < r['y'][1]) & (A < ao_thr) & ~b.flags['teeth']
    cav = vm[tri].sum(1) >= 2
    fc = P[tri].mean(1)
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    g = geom.sdf_grad(b.f_head, fc); g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-12
    win = (fc[:, 2] > r['z']) & (fc[:, 1] > r['y'][0]) & (fc[:, 1] < r.get('y_top', 0.415)) & (np.abs(fc[:, 0]) < 0.05) \
        & ~b.flags['teeth'][tri].any(1)
    cav |= win & (np.sum(fn * g, 1) < 0.3)
    for _ in range(2):
        wv = np.zeros(b.winv.max() + 1, bool); wv[b.winv[np.unique(tri[cav])]] = True
        cav |= win & (wv[b.winv[tri]].sum(1) >= 2)
    # absorb small islands of kept faces that the cavity encloses (keeps a single disk-shaped hole)
    teeth_t = b.flags['teeth'][tri].any(1)
    for _ in range(3):
        keep = ~cav & ~teeth_t
        kt = np.nonzero(keep)[0]
        tw_ = b.winv[tri[kt]]
        nwv = b.winv.max() + 1
        rr = np.r_[tw_[:, 0], tw_[:, 1], tw_[:, 2]]; cc = np.r_[tw_[:, 1], tw_[:, 2], tw_[:, 0]]
        ncomp, lab = connected_components(coo_matrix((np.ones(len(rr)), (rr, cc)), shape=(nwv, nwv)), directed=False)
        tl = lab[tw_[:, 0]]
        sizes = np.bincount(tl, minlength=ncomp)
        small = sizes[tl] < 0.05 * len(tri)
        if not small.any():
            break
        cav[kt[small]] = True
    log(f"cavity: {cav.sum()} tris removed")
    # boundary loops on welded ids
    tw = b.winv[tri]
    e = np.sort(np.concatenate([tw[cav][:, [0, 1]], tw[cav][:, [1, 2]], tw[cav][:, [2, 0]]]), 1)
    u, c = np.unique(e, axis=0, return_counts=True)
    be = u[c == 1]
    adj = collections.defaultdict(list)
    for a_, b_ in be:
        adj[a_].append(b_); adj[b_].append(a_)
    loops, seen = [], set()
    for v0 in list(adj):
        if v0 in seen: continue
        loop = [v0]; seen.add(v0); prev = None; cur = v0
        while True:
            nxts = [w for w in adj[cur] if w != prev and (w not in seen or (w == v0 and len(loop) > 2))]
            if not nxts: break
            nx = nxts[0]
            if nx == v0: break
            loop.append(nx); seen.add(nx); prev, cur = cur, nx
        loops.append(loop)
    log(f"cavity boundary loops: {[len(l) for l in loops]}")
    # representative split vertex per welded id from the kept side
    keep_tri = ~cav
    rep = {}
    for t in tri[keep_tri]:
        for v in t:
            rep.setdefault(b.winv[v], v)
    # neutral target UVs per UV half
        newP, newA, newPar, newW, newFlagsFrom = [], {k: [] for k in b.at}, [], [], []
    newtri = []
    V = len(P)
    nextw = b.winv.max() + 1

    def addv(pos, src_v, uvv, wid):
        newP.append(pos)
        for k in b.at:
            newA[k].append(b.at[k][src_v].copy())
        newA['uv0'][-1] = uvv
        newPar.append(dict(b.parents[src_v])); newW.append(wid); newFlagsFrom.append(src_v)
        return V + len(newP) - 1

    for loop in loops:
        ring = [rep[w] for w in loop]
        pr = P[ring]
        c0 = pr.mean(0)
        Uc = np.array(free_uv)
        # local plane for UV layout: x across the face, y up (keeps painting orientation sane)
        _, _, Vt = np.linalg.svd(pr - c0)
        nrm = Vt[2] if Vt[2][2] > 0 else -Vt[2]
        e1 = np.array([1.0, 0, 0]) - nrm * nrm[0]; e1 /= np.linalg.norm(e1)
        e2 = np.cross(nrm, e1)
        rad = max(np.max(np.abs((pr - c0) @ e1)), np.max(np.abs((pr - c0) @ e2)))
        sc = free_r / rad
        uvof = lambda p: Uc + np.array([(p - c0) @ e1, (p - c0) @ e2]) * sc
        outer = [addv(P[v], v, uvof(P[v]), b.winv[v]) for v in ring]
        n = len(ring)
        q2 = np.stack([(pr - c0) @ e1, (pr - c0) @ e2], 1)
        # polygon orientation (CCW in plane)
        area = 0.5 * np.sum(q2[:, 0] * np.roll(q2[:, 1], -1) - np.roll(q2[:, 0], -1) * q2[:, 1])
        order = list(range(n)) if area > 0 else list(range(n))[::-1]
        tris_l = []
        rem = order[:]
        guard = 0
        def cross2(o, a_, b_):
            return (a_[0] - o[0]) * (b_[1] - o[1]) - (a_[1] - o[1]) * (b_[0] - o[0])
        def in_tri(p, a_, b_, c_):
            d1, d2, d3 = cross2(a_, b_, p), cross2(b_, c_, p), cross2(c_, a_, p)
            return (d1 > 1e-12) and (d2 > 1e-12) and (d3 > 1e-12)
        while len(rem) > 3 and guard < 10000:
            guard += 1
            m_ = len(rem)
            best = None
            for k in range(m_):
                i0, i1, i2 = rem[k - 1], rem[k], rem[(k + 1) % m_]
                A_, B_, C_ = q2[i0], q2[i1], q2[i2]
                if cross2(A_, B_, C_) <= 1e-12:
                    continue
                if any(in_tri(q2[j], A_, B_, C_) for j in rem if j not in (i0, i1, i2)):
                    continue
                # prefer well-shaped ears (largest minimum angle proxy)
                e_ = [np.linalg.norm(B_ - A_), np.linalg.norm(C_ - B_), np.linalg.norm(A_ - C_)]
                qual = cross2(A_, B_, C_) / (max(e_) ** 2 + 1e-12)
                if best is None or qual > best[0]:
                    best = (qual, k)
            if best is None:
                break
            k = best[1]
            tris_l.append([rem[k - 1], rem[k], rem[(k + 1) % len(rem)]])
            rem.pop(k)
        if len(rem) == 3:
            tris_l.append(rem[:])
        # local mesh: vertices = outer ring; subdivide twice projecting new points on the head SDF
        lp = [P[v].copy() for v in ring]
        lid = list(outer)
        lt = [list(t) for t in tris_l]
        for it in range(1):
            emid = {}
            nt = []
            def mid(i, j):
                key = (min(i, j), max(i, j))
                if key not in emid:
                    pm = 0.5 * (lp[i] + lp[j])
                    pm = geom.project_to_sdf(b.f_head, pm[None], np.ones(1))[0]
                    lp.append(pm)
                    nonlocal nextw
                    lid.append(addv(pm, ring[0], uvof(pm), nextw)); nextw += 1
                    emid[key] = len(lp) - 1
                return emid[key]
            for (i, j, k) in lt:
                ij, jk, ki = mid(i, j), mid(j, k), mid(k, i)
                nt += [[i, ij, ki], [ij, j, jk], [ki, jk, k], [ij, jk, ki]]
            lt = nt
        allP = np.vstack([P, newP])
        loc = np.array([[lid[i] for i in t] for t in lt])
        ff = np.cross(allP[loc[:, 1]] - allP[loc[:, 0]], allP[loc[:, 2]] - allP[loc[:, 0]])
        gg = geom.sdf_grad(b.f_head, allP[loc].mean(1))
        if np.sum(ff * gg) < 0:
            loc = loc[:, [0, 2, 1]]
        newtri.append(loc)
    # assemble
    b.P1 = np.vstack([P, newP]); b.P0 = np.vstack([b.P0, newP])
    for k in b.at:
        b.at[k] = np.vstack([b.at[k], np.array(newA[k]).reshape(len(newP), -1)])
    b.winv = np.r_[b.winv, newW]
    b.parents = b.parents + newPar
    fi = np.array(newFlagsFrom)
    for k in list(b.flags):
        b.flags[k] = np.r_[b.flags[k], b.flags[k][fi]]
    b.w_head = np.r_[b.w_head, b.w_head[fi]]
    for k in b.geo:
        b.geo[k] = np.r_[b.geo[k], b.geo[k][fi]]
    if hasattr(b, 'ear_mask'):
        b.ear_mask = np.r_[b.ear_mask, b.ear_mask[fi]]
    tri2 = np.vstack([tri[~cav]] + newtri)
    capflag = np.r_[np.zeros((~cav).sum(), bool), np.ones(sum(len(t) for t in newtri), bool)]
    # drop unreferenced vertices
    used = np.zeros(len(b.P1), bool); used[tri2.ravel()] = True
    remap = -np.ones(len(b.P1), int); remap[used] = np.arange(used.sum())
    sel = np.nonzero(used)[0]
    b.P1 = b.P1[sel]; b.P0 = b.P0[sel]
    for k in b.at: b.at[k] = b.at[k][sel]
    b.winv = np.unique(b.winv[sel], return_inverse=True)[1]
    b.parents = [b.parents[i] for i in sel]
    for k in list(b.flags): b.flags[k] = b.flags[k][sel]
    b.w_head = b.w_head[sel]
    for k in b.geo: b.geo[k] = b.geo[k][sel]
    if hasattr(b, 'ear_mask'): b.ear_mask = b.ear_mask[sel]
    b.tri = remap[tri2]
    b.cavity_tri = capflag
    b.sg = b.smoothing_ids(b.P0, b.at['N'], b.winv)
    log(f"cap: {capflag.sum()} new tris; verts now {len(b.P1)}")
    return capflag


def find_free_uv(src, ao_png, normal_png, S=512, pad_px=6, contam_png=None):
    """Largest UV disk not covered by any source triangle where the material AO is ~1 and normal ~flat."""
    import raster
    from PIL import Image
    from scipy import ndimage
    r = raster.rasterize(src.uv0, src.tri, {'one': np.ones((len(src.uv0), 1))}, S)
    cov = ndimage.binary_dilation(r['mask'], iterations=pad_px)
    ao = np.array(Image.open(ao_png).convert('L').resize((S, S))) / 255.0
    nm = np.array(Image.open(normal_png).resize((S, S))).astype(float) / 255.0
    nx, ny = nm[..., 3] * 2 - 1, nm[..., 1] * 2 - 1
    flat = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    ok = (~cov) & (ao > 0.88) & (flat > 0.96)
    if contam_png:
        c = np.array(Image.open(contam_png).convert('RGBA').resize((S, S))).astype(float)
        # contamination overlay must look like ordinary pink-red fur there (not the opaque orange teeth paint)
        ok &= (c[..., 3] < 235) & (c[..., 2] > 0.3 * c[..., 0]) & (c[..., 1] < 0.6 * c[..., 0])
    dist = ndimage.distance_transform_edt(ok)
    iy, ix = np.unravel_index(np.argmax(dist), dist.shape)
    return (ix / S, 1 - iy / S), dist.max() / S
