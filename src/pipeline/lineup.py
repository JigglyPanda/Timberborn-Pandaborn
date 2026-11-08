"""Hero lineup render: several characters with different textures/poses in one scene.
usage: python3 lineup.py out.png spec... where spec = model.timbermesh|texture.png|pose|x|z"""
import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, tmesh, render, preview, bpy
out = sys.argv[1]; specs = sys.argv[2:]
args = dict(a.split('=') for a in specs if a.startswith('--'))
specs = [s for s in specs if not s.startswith('--')]
render.reset()
mats = {}
cache = {}
for i, sp in enumerate(specs):
    mp, tex, pose, x, z = sp.split('|')
    if mp not in cache:
        cache[mp] = preview.decode(tmesh.load(mp))
    P, N, uv, tri, anims = cache[mp]
    child = 'Child' in mp
    nrm = '/root/w/ext/chilkd_normal_1k_rgb.png' if child else '/root/w/ext/adult_normal_2k_rgb.png'
    ao = '/root/w/ext/materials/beavers/common/' + ('child_ao_1k.png' if child else 'adult_ao_2k.png')
    if tex not in mats:
        mats[tex] = render.make_material(f'm{len(mats)}', tex, nrm, ao)
    p, nr = preview.pose(P, anims, pose)
    o = render.add_mesh(f'o{i}', p, tri, uv, nr if nr is not None else N, mats[tex], offset=(float(x), -float(z), 0))
render.add_camera(target=(0, 0, float(args.get('--tz', 0.25))), dist=float(args.get('--dist', 3.4)), az=float(args.get('--az', 18)),
                  el=float(args.get('--el', 9)), lens=float(args.get('--lens', 50)))
render.render(out, int(args.get('--w', 1800)), int(args.get('--h', 800)), int(args.get('--s', 64)))
