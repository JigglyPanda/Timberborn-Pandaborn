"""Pandaborn thumbnail: giant + red pandas (adults and kits) with real hair, on the painted teal plate.
usage: python3 thumb.py out.png [--samples 96]
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, bpy, bmesh
import tmesh, render, preview
from PIL import Image, ImageFilter
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('--samples', type=int, default=96)
ap.add_argument('--models', default='/root/w/out2')
ap.add_argument('--masks', default='/root/w/v6/PandaColonists/AssetBundles/Resources/PandaFur6')
a = ap.parse_args()

render.reset()
sc = bpy.context.scene
sc.render.film_transparent = True
for o in list(bpy.data.objects):
    if o.type in ('MESH', 'LIGHT'):
        bpy.data.objects.remove(o)
sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.20, 0.30, 0.32, 1)
sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.35
cache = {}


def add_panda(kind, tex, pose, offset, yaw_deg):
    child = kind == 'child'
    mp = a.models + ('/BeaverChild.Model.timbermesh' if child else '/BeaverAdult.Model.timbermesh')
    if mp not in cache:
        cache[mp] = preview.decode(tmesh.load(mp))
    P, N, uv, tri, anims = cache[mp]
    p, _ = preview.pose(np.asarray(P), anims, pose)
    p = np.asarray(p).copy()
    yaw = np.radians(yaw_deg)
    c, s = np.cos(yaw), np.sin(yaw)
    p[:, 0], p[:, 2] = c * p[:, 0] + s * p[:, 2], -s * p[:, 0] + c * p[:, 2]
    name = f'{kind}_{len(bpy.data.objects)}'
    base = np.array(Image.open(tex).convert('RGB').resize((2048, 2048), Image.BICUBIC)).astype(float) / 255
    mk = np.array(Image.open(f"{a.masks}/FurMask{'Child' if child else 'Adult'}.png").convert('RGBA')).astype(float) / 255
    aom = np.array(Image.fromarray((mk[..., 1] * 255).astype(np.uint8)).resize((2048, 2048), Image.BILINEAR)) / 255.0
    base = base * (0.55 + 0.45 * aom[..., None])
    tf = f'/tmp/thumb_{name}.png'
    Image.fromarray((base.clip(0, 1) * 255).astype(np.uint8)).save(tf)
    img = bpy.data.images.load(tf)
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.85
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'uv0'
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
    nt.links.new(uvn.outputs['UV'], t.inputs['Vector']); nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    ob = render.add_mesh(name, p, tri, uv, None, m, offset=offset)
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.to_mesh(ob.data); bm.free()
    for poly in ob.data.polygons: poly.use_smooth = True
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 2
    fm = mk[..., 0]; Sm = fm.shape[0]
    vg = ob.vertex_groups.new(name='fur'); me = ob.data; uvl = me.uv_layers['uv0'].data
    vw = np.zeros(len(me.vertices))
    for poly in me.polygons:
        for li in poly.loop_indices:
            u, v = uvl[li].uv
            vi = me.loops[li].vertex_index
            vw[vi] = max(vw[vi], fm[int(np.clip((1 - v) * Sm, 0, Sm - 1)), int(np.clip(u * Sm, 0, Sm - 1))])
    for i, w in enumerate(vw): vg.add([i], float(w), 'REPLACE')
    ps = ob.modifiers.new('hair', 'PARTICLE_SYSTEM').particle_system
    st = ps.settings
    st.type = 'HAIR'; st.count = 60000; st.hair_length = (0.011 if child else 0.013) * 1.6
    st.child_type = 'INTERPOLATED'; st.rendered_child_count = 6
    st.clump_factor = 0.15; st.roughness_2 = 0.002; st.roughness_endpoint = 0.004
    st.use_advanced_hair = False
    st.root_radius = 0.0011 if child else 0.0013; st.tip_radius = 0.0
    ps.vertex_group_density = 'fur'; ps.vertex_group_length = 'fur'
    hm = bpy.data.materials.new(name + 'h'); hm.use_nodes = True
    hn = hm.node_tree; hb = hn.nodes['Principled BSDF']; hb.inputs['Roughness'].default_value = 0.7
    huv = hn.nodes.new('ShaderNodeUVMap'); huv.uv_map = 'uv0'
    ht = hn.nodes.new('ShaderNodeTexImage'); ht.image = img
    hn.links.new(huv.outputs['UV'], ht.inputs['Vector'])
    hi = hn.nodes.new('ShaderNodeHairInfo'); mix = hn.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    ramp = hn.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1); ramp.color_ramp.elements[1].color = (1.05, 1.05, 1.05, 1)
    hn.links.new(hi.outputs['Intercept'], ramp.inputs['Fac'])
    hn.links.new(ht.outputs['Color'], mix.inputs[6]); hn.links.new(ramp.outputs['Color'], mix.inputs[7]); mix.inputs['Factor'].default_value = 1.0
    hn.links.new(mix.outputs[2], hb.inputs['Base Color'])
    ob.data.materials.append(hm); st.material = 2


T2, T3, T7 = '/root/w/out2/tex_adult', '/root/w/out3/tex_child', '/root/w/out7'
CAST = [('adult', f'{T2}/BeaverAdult1.Folktails.png', 'BeaverAdult_idle:10', (-0.42, 0.0, 0), -14),
        ('adult', f'{T7}/tex_adult/BeaverAdult3.IronTeeth.png', 'BeaverAdult_idle:40', (0.44, 0.02, 0), 16),
        ('child', f'{T3}/BeaverChild1.Folktails.png', 'BeaverChild_idle:30', (-0.10, -0.22, 0), 8),
        ('child', f'{T7}/tex_child/BeaverChild1.IronTeeth.png', 'BeaverChild_idle:60', (0.14, -0.24, 0), -10)]
ONLY = int(os.environ.get('ONLY', '-1'))
for i, c in enumerate(CAST):
    if ONLY < 0 or ONLY == i:
        add_panda(*c)


def light(name, loc, energy, size, color, tz=0.3):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size; L.color = color
    o = bpy.data.objects.new(name, L); o.location = loc
    o.rotation_euler = render._look_rot(-np.array(loc) + np.array([0, 0, tz]))
    sc.collection.objects.link(o)


light('Key', (-1.6, -2.4, 2.2), 600, 2.2, (1.0, 0.90, 0.76))
light('Rim', (1.8, 2.0, 1.6), 600, 1.6, (0.62, 0.80, 1.0))
light('Fill', (2.2, -1.8, 0.6), 120, 3.0, (0.85, 0.92, 1.0))
render.add_camera(target=(0, 0, 0.27), dist=2.15, az=0, el=7, lens=55)
W, H = 1280, 720
raw = '/tmp/thumb_raw.png'
render.render(raw, W * 2, H * 2, a.samples)
if ONLY >= 0:
    Image.open(raw).convert('RGBA').resize((W, H), Image.LANCZOS).save(a.out); print('saved layer', a.out); sys.exit(0)

fg = Image.new('RGBA', (W, H), (0, 0, 0, 0))
for i in range(len(CAST)):   # back row first, kits in front
    fg.alpha_composite(Image.open(f'/tmp/thumb_layer{i}.png').convert('RGBA'))
fg = fg.filter(ImageFilter.UnsharpMask(radius=1.2, percent=50, threshold=2))
rng = np.random.default_rng(5)
yy, xx = np.mgrid[0:H, 0:W] / W


def noise(scale, octaves=4):
    out = np.zeros((H, W))
    for o in range(octaves):
        s = scale * 2 ** o
        n = rng.random((int(H / s) + 2, int(W / s) + 2))
        out += ndimage.zoom(n, (H / n.shape[0], W / n.shape[1]), order=3)[:H, :W] / 2 ** o
    return out / 2


r = np.sqrt((xx - 0.5) ** 2 + ((yy - 0.42 * H / W) * 1.3) ** 2)
g = np.clip(1 - r * 1.6, 0, 1)[..., None]
bg = np.array([0.06, 0.12, 0.13]) + (np.array([0.22, 0.35, 0.34]) - np.array([0.06, 0.12, 0.13])) * g
bg *= 0.88 + 0.24 * noise(28, 4)[..., None]
out = Image.fromarray((np.dstack([bg.clip(0, 1), np.ones((H, W))]) * 255).astype(np.uint8), 'RGBA')
out.alpha_composite(fg)
out.convert('RGB').save(a.out, optimize=True)
print('saved', a.out)
