"""Render panda UI portraits (avatars) to match the game's painted avatar style.

usage: python3 portrait.py kind out.png texture.png [--contam] [--hat model.timbermesh] [--full]
kind: adult|child
"""
import sys, argparse
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, bpy
import tmesh, render, preview
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('kind'); ap.add_argument('out'); ap.add_argument('tex')
ap.add_argument('--contam', action='store_true')
ap.add_argument('--hat', default=None)
ap.add_argument('--full', action='store_true')
ap.add_argument('--pose', default=None)
ap.add_argument('--size', type=int, default=512)
ap.add_argument('--outdir', default='/root/w/out')
ap.add_argument('--fur', default=None, help='fur mask png: add v5 shell fur')
ap.add_argument('--furlen', type=float, default=0.014)
ap.add_argument('--furdensity', type=float, default=520)
a = ap.parse_args()

child = a.kind == 'child'
mp = a.outdir + ('/BeaverChild.Model.timbermesh' if child else '/BeaverAdult.Model.timbermesh')
model = tmesh.load(mp)
P, N, uv, tri, anims = preview.decode(model)
E = '/root/w/ext/'
tex = a.tex
if a.contam:
    base = np.array(Image.open(a.tex).convert('RGB').resize((2048, 2048))).astype(float)
    c = np.array(Image.open(E + 'materials/beavers/common/injuries/contamination_d.png').convert('RGBA')).astype(float)
    al = (c[..., 3:] / 255.0) * 0.55
    mix = base * (1 - al) + c[..., :3] * al
    tex = '/tmp/contam_tex.png'
    Image.fromarray(mix.clip(0, 255).astype(np.uint8)).save(tex)

render.reset()
sc = bpy.context.scene
sc.render.film_transparent = True
# remove ground for clean alpha
for o in list(bpy.data.objects):
    if o.type == 'MESH':
        bpy.data.objects.remove(o)
# portrait lighting: warm key, cool rim
for o in list(bpy.data.objects):
    if o.type == 'LIGHT':
        if o.name == 'Key':
            o.data.color = (1.0, 0.93, 0.82); o.data.energy = 210
        if o.name == 'Rim':
            o.data.color = (0.75, 0.85, 1.0); o.data.energy = 260
nrm = E + ('chilkd_normal_1k_rgb.png' if child else 'adult_normal_2k_rgb.png')
ao = E + 'materials/beavers/common/' + ('child_ao_1k.png' if child else 'adult_ao_2k.png')
mat = render.make_material('m', tex, nrm, ao)
pose = a.pose or 'rest'
p, nr = preview.pose(P, anims, pose)
render.add_mesh('panda', p, tri, uv, nr if nr is not None else N, mat)
if a.fur:
    import os
    import fur_preview5 as fp
    fp.TEX = 2048
    nn = (nr if nr is not None else N)
    nn = nn / np.linalg.norm(nn, axis=1, keepdims=True)
    mimg = np.array(Image.open(a.fur).convert('L')).astype(float) / 255
    Sm = mimg.shape[0]
    mv = mimg[((1 - uv[:, 1]) * Sm).astype(int).clip(0, Sm - 1), (uv[:, 0] * Sm).astype(int).clip(0, Sm - 1)]
    mtex = np.array(Image.open(a.fur).convert('L').resize((fp.TEX, fp.TEX), Image.BILINEAR)).astype(float) / 255
    # portraits are painted at 2x then downsampled, so use fewer, chunkier strands
    cov = fp.coverage_maps(a.furdensity * 0.6, S=fp.TEX, mtex=mtex)
    btex = np.array(Image.open(tex).convert('RGB').resize((fp.TEX, fp.TEX))).astype(float) / 255
    comb = fp.carry(fp.comb_dirs(np.asarray(P), np.asarray(N)), np.asarray(N), nn)
    keep = (mv[tri] > 0.02).any(1)
    for k in range(fp.SHELLS):
        s_ = (k + 1) / fp.SHELLS
        ln = a.furlen * 1.3 * mv
        q = p + nn * (s_ * ln)[:, None] + comb * (s_ * s_ * ln * 0.8)[:, None]
        q[:, 1] -= 0.3 * s_ * s_ * ln
        col = btex * ((1 - fp.ROOT) + (fp.ROOT + 0.06) * s_)
        al = cov[k].astype(float) / 255 * np.clip(mtex * 10, 0, 1)
        fn = f'/tmp/pfur_{k}.png'
        Image.fromarray(np.dstack([np.clip(col, 0, 1) * 255, al * 255]).astype(np.uint8)).save(fn)
        m = bpy.data.materials.new(f'pfur{k}'); m.use_nodes = True; nt = m.node_tree
        bsdf = nt.nodes['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.9
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'uv0'
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(fn)
        nt.links.new(uvn.outputs['UV'], t.inputs['Vector'])
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
        nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
        render.add_mesh(f'pfur{k}', q, tri[keep], uv, nn, m)
    sc.cycles.transparent_max_bounces = 64
if a.hat:
    hm = tmesh.load(a.hat)
    an, fr = (pose.rsplit(':', 1) if pose != 'rest' else (None, 0))
    pos, q, scl = preview.node_matrix_at(model, '#Head', an, fr)
    hmat = render.make_material('hat', E + 'materials/goods/beavercarryingmodels/beavercarryingmodels_d.png')
    for hn in hm.nodes:
        if hn.vertexCount == 0 or not hn.meshes:
            continue
        hp = tmesh.prop_array(hn.vertexProperties, 'position').astype(float)
        huv = tmesh.prop_array(hn.vertexProperties, 'uv0')
        wp = tmesh.quat_rotate(np.broadcast_to(q, (len(hp), 4)), hp * scl) + pos
        htri = np.concatenate([np.array(mm.indices).reshape(-1, 3) for mm in hn.meshes])
        render.add_mesh('hat', wp, htri, huv, None, hmat, smooth=False)

h = 0.32 if child else 0.53
if a.full:
    render.add_camera(target=(0, 0, h * 0.56), dist=h * 2.45, az=22, el=4, lens=50)
    sc.view_settings.exposure = -0.3
    W, H = 420, 560
else:
    render.add_camera(target=(0, 0, h * (0.80 if child else 0.79)), dist=h * (1.45 if child else 1.30), az=12, el=1, lens=60)
    sc.view_settings.exposure = -0.35
    W, H = a.size, a.size
render.render('/tmp/portrait_raw.png', W * 2, H * 2, 40 if a.fur else 96)

# ---- painterly finish + frame
import cv2
from scipy import ndimage
raw = np.array(Image.open('/tmp/portrait_raw.png').convert('RGBA'))
rgb = cv2.cvtColor(raw[..., :3], cv2.COLOR_RGB2BGR)
paint = cv2.xphoto.oilPainting(rgb, 7, 1)
paint = cv2.edgePreservingFilter(paint, flags=1, sigma_s=30, sigma_r=0.25)
paint = cv2.cvtColor(paint, cv2.COLOR_BGR2RGB).astype(float)
# gentle contrast/saturation lift like the hand-painted originals
paint = np.clip((paint - 128) * 1.08 + 132, 0, 255)
alpha = raw[..., 3].astype(float) / 255.0
# dark painted outline
edge = ndimage.binary_dilation(alpha > 0.5, iterations=3) & ~(alpha > 0.5)
fig = np.dstack([paint, alpha * 255])
fig[edge] = [18, 16, 16, 255]
fig = Image.fromarray(fig.astype(np.uint8)).resize((W, H), Image.LANCZOS)

if a.full:
    fig.save(a.out)
    sys.exit(0)


def frame(size, colour, seed):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size] / size
    import paint as pnt
    n = pnt.fbm(np.dstack([xx * 9, yy * 9, np.full_like(xx, seed)]), 5, seed)
    n2 = pnt.fbm(np.dstack([xx * 40, yy * 40, np.full_like(xx, seed + 3)]), 3, seed + 1)
    # rough brushed square
    d = np.minimum.reduce([xx, yy, 1 - xx, 1 - yy])
    inside = d + n * 0.035 + n2 * 0.008 > 0.075
    border = (d + n * 0.04 + n2 * 0.01 > 0.035) & ~inside
    col = np.array(colour, float)
    bg = col[None, None, :] * (0.82 + 0.18 * (n[..., None] * 0.5 + 0.5)) * (0.92 + 0.08 * n2[..., None])
    # vignette
    v = 1 - 0.35 * np.clip((np.hypot(xx - 0.5, yy - 0.45) - 0.25) / 0.45, 0, 1)
    bg = bg * v[..., None]
    img = np.zeros((size, size, 4))
    img[..., :3] = np.where(inside[..., None], bg, 14)
    img[..., 3] = np.where(inside | border, 255, 0)
    return Image.fromarray(img.clip(0, 255).astype(np.uint8))


colour = (122, 34, 44) if a.contam else (33, 74, 72)
fr = frame(W, colour, 7 if child else 3)
# character breaks the bottom frame edge, like the originals
fr.alpha_composite(fig, (0, int(H * 0.04)))
fr.save(a.out)
