"""Render poses decoded from a .timbermesh exactly as the game's VAT shader would.

usage: python3 preview.py model.timbermesh out.png base.png [anim:frame,...] [--normal n.png --ao ao.png] [--hat hat.timbermesh]
"""
import sys, argparse
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
import tmesh, render, bpy


def decode(model, node_index=1):
    n = model.nodes[node_index]
    g = lambda k: tmesh.prop_array(n.vertexProperties, k)
    P, N, uv = g('position'), g('normal'), g('uv0')
    tri = np.array(n.meshes[0].indices).reshape(-1, 3)
    anims = {a.name: a for a in n.vertexAnimations}
    return P, N, uv, tri, anims


def pose(P, anims, spec):
    if spec in (None, 'rest'):
        return P, None
    name, fr = spec.rsplit(':', 1)
    a = anims[name]
    f = a.frames[int(fr) % len(a.frames)]
    p, nr, _, _ = tmesh.decode_frame(P, f)
    return p, nr


def node_matrix_at(model, node_name, anim_name, frame):
    for n in model.nodes:
        if n.name == node_name:
            for na in n.nodeAnimations:
                if na.name == anim_name:
                    fr = na.frames[int(frame) % len(na.frames)]
                    return (np.array([fr.position.x, fr.position.y, fr.position.z]),
                            np.array([fr.rotation.x, fr.rotation.y, fr.rotation.z, fr.rotation.w]),
                            np.array([fr.scale.x, fr.scale.y, fr.scale.z]))
            return (np.array([n.position.x, n.position.y, n.position.z]),
                    np.array([n.rotation.x, n.rotation.y, n.rotation.z, n.rotation.w]),
                    np.array([n.scale.x, n.scale.y, n.scale.z]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model'); ap.add_argument('out'); ap.add_argument('base')
    ap.add_argument('poses', nargs='?', default='rest')
    ap.add_argument('--normal'); ap.add_argument('--ao')
    ap.add_argument('--hat', action='append', default=[])
    ap.add_argument('--hatbase', default='/root/w/ext/hat_atlas.png')
    ap.add_argument('--only_sub', default=None)
    ap.add_argument('--az', type=float, default=28); ap.add_argument('--el', type=float, default=10)
    ap.add_argument('--dist', type=float, default=0); ap.add_argument('--w', type=int, default=1600)
    ap.add_argument('--h', type=int, default=700); ap.add_argument('--samples', type=int, default=48)
    ap.add_argument('--spacing', type=float, default=0.62); ap.add_argument('--target_z', type=float, default=0.27)
    ap.add_argument('--lens', type=float, default=50)
    a = ap.parse_args()
    model = tmesh.load(a.model)
    P, N, uv, tri, anims = decode(model)
    render.reset()
    mat = render.make_material('m', a.base, a.normal, a.ao)
    specs = a.poses.split(',')
    n = len(specs)
    for i, sp in enumerate(specs):
        p, nr = pose(P, anims, sp)
        off = ((i - (n - 1) / 2) * a.spacing, 0, 0)
        render.add_mesh(f'o{i}', p, tri, uv, nr if nr is not None else N, mat, offset=off)
        for hp in a.hat:
            node_name = '#Head'
            if '=' in hp:
                node_name, hp = hp.split('=', 1)
            hm = tmesh.load(hp)
            an, fr = (sp.rsplit(':', 1) if sp != 'rest' else (None, 0))
            pos, q, sc = node_matrix_at(model, node_name, an, fr)
            hm_mat = render.make_material('hat', None, color=(0.75, 0.6, 0.3))
            for hn in hm.nodes:
                if hn.vertexCount == 0 or not hn.meshes: continue
                if a.only_sub and a.only_sub not in hn.name and hn.parent >= 0: continue
                hp_ = tmesh.prop_array(hn.vertexProperties, 'position').astype(float)
                # node local transform (rotation+position) of hat sub-node
                hq = np.array([hn.rotation.x, hn.rotation.y, hn.rotation.z, hn.rotation.w])
                hp_ = tmesh.quat_rotate(np.broadcast_to(hq, (len(hp_), 4)), hp_) * [hn.scale.x, hn.scale.y, hn.scale.z] + [hn.position.x, hn.position.y, hn.position.z]
                wp = tmesh.quat_rotate(np.broadcast_to(q, (len(hp_), 4)), hp_ * sc) + pos
                htri = np.concatenate([np.array(mm.indices).reshape(-1, 3) for mm in hn.meshes])
                render.add_mesh(f'hat{i}', wp, htri, None, None, hm_mat, offset=off, smooth=False)
    dist = a.dist or (1.2 + 0.55 * n)
    render.add_camera(target=(0, 0, a.target_z), dist=dist, az=a.az, el=a.el, lens=a.lens)
    render.render(a.out, a.w, a.h, a.samples)


if __name__ == '__main__':
    main()
