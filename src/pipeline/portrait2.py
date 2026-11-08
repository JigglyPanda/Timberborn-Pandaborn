"""Pandaborn UI portraits: clean studio renders framed like the game's avatars (no smear/oil filters).

usage: python3 portrait2.py adult|child out.png texture.png [--contam] [--full] [--pose name:frame] [--az 22]
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, bpy
import tmesh, render, preview
from PIL import Image, ImageFilter
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument('kind'); ap.add_argument('out'); ap.add_argument('tex')
ap.add_argument('--contam', action='store_true')
ap.add_argument('--full', action='store_true')
ap.add_argument('--pose', default=None)
ap.add_argument('--az', type=float, default=-18)
ap.add_argument('--models', default='/root/w/out2')
ap.add_argument('--aomask', default='/root/w/v6/PandaColonists/AssetBundles/Resources/PandaFur6')
ap.add_argument('--seed', type=int, default=3)
ap.add_argument('--samples', type=int, default=96)
a = ap.parse_args()

child = a.kind == 'child'
mp = a.models + ('/BeaverChild.Model.timbermesh' if child else '/BeaverAdult.Model.timbermesh')
P, N, uv, tri, anims = preview.decode(tmesh.load(mp))
P = np.asarray(P)

# ---------------------------------------------------------------- texture: panda texture x panda AO (+ contamination)
base = np.array(Image.open(a.tex).convert('RGB').resize((2048, 2048), Image.BICUBIC)).astype(float) / 255
aom = np.array(Image.open(f"{a.aomask}/FurMask{'Child' if child else 'Adult'}.png").convert('RGBA'))[..., 1].astype(float) / 255
aom = np.array(Image.fromarray((aom * 255).astype(np.uint8)).resize((2048, 2048), Image.BILINEAR)) / 255.0
base = base * (0.55 + 0.45 * aom[..., None])
if a.contam:
    c = np.array(Image.open('/root/w/ext/materials/beavers/common/injuries/contamination_d.png').convert('RGBA').resize((2048, 2048))).astype(float) / 255
    al = c[..., 3:] * 0.6
    base = base * (1 - al) + c[..., :3] * al
texfile = '/tmp/portrait2_tex.png'
Image.fromarray((base.clip(0, 1) * 255).astype(np.uint8)).save(texfile)

# ---------------------------------------------------------------- scene
render.reset()
sc = bpy.context.scene
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
for o in list(bpy.data.objects):
    if o.type in ('MESH', 'LIGHT'):
        bpy.data.objects.remove(o)
sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.20, 0.30, 0.32, 1)
sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.35

m = bpy.data.materials.new('fur'); m.use_nodes = True
nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
bsdf.inputs['Roughness'].default_value = 0.85
for k, v in (('Specular IOR Level', 0.12), ('Sheen Weight', 0.25), ('Sheen Roughness', 0.5)):
    try: bsdf.inputs[k].default_value = v
    except Exception: pass
uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'uv0'
t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(texfile)
nt.links.new(uvn.outputs['UV'], t.inputs['Vector']); nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])

pose = a.pose or ('BeaverChild_idle:10' if child else 'BeaverAdult_idle:10')
p, nr = preview.pose(P, anims, pose)
p = np.asarray(p)
ob = render.add_mesh('panda', p, tri, uv, None, m)
# weld UV-seam duplicates, then subdivide so the low-poly game mesh reads as a soft, round panda
import bmesh
bm = bmesh.new(); bm.from_mesh(ob.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.to_mesh(ob.data); bm.free()
for poly in ob.data.polygons: poly.use_smooth = True
sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 2
# real hair strands, coloured from the panda texture at the root, density/length from the fur mask
fm = np.array(Image.open(f"{a.aomask}/FurMask{'Child' if child else 'Adult'}.png").convert('RGBA'))[..., 0].astype(float) / 255
Sm = fm.shape[0]
vg = ob.vertex_groups.new(name='fur')
me = ob.data
uvl = me.uv_layers['uv0'].data
vw = np.zeros(len(me.vertices))
for poly in me.polygons:
    for li in poly.loop_indices:
        u, v = uvl[li].uv
        w = fm[int(np.clip((1 - v) * Sm, 0, Sm - 1)), int(np.clip(u * Sm, 0, Sm - 1))]
        vi = me.loops[li].vertex_index
        vw[vi] = max(vw[vi], w)
for i, w in enumerate(vw):
    vg.add([i], float(w), 'REPLACE')
ps = ob.modifiers.new('hair', 'PARTICLE_SYSTEM').particle_system
st = ps.settings
st.type = 'HAIR'; st.count = 60000; st.hair_length = (0.011 if child else 0.013) * 1.6
st.child_type = 'INTERPOLATED'; st.rendered_child_count = 6; st.child_percent = 6
st.clump_factor = 0.15; st.roughness_2 = 0.002; st.roughness_endpoint = 0.004
st.use_advanced_hair = False
st.root_radius = 0.0011 if child else 0.0013; st.tip_radius = 0.0; st.radius_scale = 1.0
try: st.display_step = 3; st.render_step = 4
except Exception: pass
ps.vertex_group_density = 'fur'; ps.vertex_group_length = 'fur'
ob.modifiers.move(ob.modifiers.find('hair'), len(ob.modifiers) - 1)
hm = bpy.data.materials.new('hair'); hm.use_nodes = True
hn = hm.node_tree; hb = hn.nodes['Principled BSDF']
hb.inputs['Roughness'].default_value = 0.7
try: hb.inputs['Specular IOR Level'].default_value = 0.15
except Exception: pass
huv = hn.nodes.new('ShaderNodeUVMap'); huv.uv_map = 'uv0'
ht = hn.nodes.new('ShaderNodeTexImage'); ht.image = t.image
hn.links.new(huv.outputs['UV'], ht.inputs['Vector'])
# a touch darker at the root, lighter at the tip
hi = hn.nodes.new('ShaderNodeHairInfo'); mix = hn.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
ramp = hn.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1); ramp.color_ramp.elements[1].color = (1.05, 1.05, 1.05, 1)
hn.links.new(hi.outputs['Intercept'], ramp.inputs['Fac'])
hn.links.new(ht.outputs['Color'], mix.inputs[6]); hn.links.new(ramp.outputs['Color'], mix.inputs[7]); mix.inputs['Factor'].default_value = 1.0
hn.links.new(mix.outputs[2], hb.inputs['Base Color'])
ob.data.materials.append(hm); st.material = 2
# fur strands from the painted texture as fine bump
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.002
nt.links.new(t.outputs['Color'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])


def light(name, loc, energy, size, color):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size; L.color = color
    o = bpy.data.objects.new(name, L); o.location = loc
    o.rotation_euler = render._look_rot(-np.array(loc) + np.array([0, 0, tz]))
    sc.collection.objects.link(o)


# framing: head-and-shoulders, or full body for the new-game portrait
top = p[:, 1].max(); bot = p[:, 1].min(); h = top - bot
if a.full:
    tz, dist, el, lens = bot + 0.5 * h, h * 3.3, 6, 70
else:
    tz, dist, el, lens = top - 0.33 * h, h * 1.95 if child else h * 1.85, 6, 70
# Blender space: z up; character faces -Y
light('Key', (-1.4, -2.0, tz + 1.6), 300, 1.8, (1.0, 0.90, 0.76))
light('Rim', (1.6, 1.8, tz + 1.0), 420, 1.2, (0.62, 0.80, 1.0))
light('Fill', (1.8, -1.6, tz + 0.2), 70, 2.5, (0.85, 0.92, 1.0))
render.add_camera(target=(0, 0, tz), dist=dist, az=a.az, el=el, lens=lens)
W, H = (420, 560) if a.full else (512, 512)
raw = '/tmp/portrait2_raw.png'
render.render(raw, W * 2, H * 2, a.samples)

# ---------------------------------------------------------------- frame: own painted teal plate with rough edges
rng = np.random.default_rng(a.seed)
fg = Image.open(raw).convert('RGBA').resize((W, H), Image.LANCZOS)
fg = fg.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
yy, xx = np.mgrid[0:H, 0:W] / max(W, H)


def noise(scale, octaves=4):
    out = np.zeros((H, W))
    for o in range(octaves):
        s = scale * 2 ** o
        n = rng.random((int(H / s) + 2, int(W / s) + 2))
        out += ndimage.zoom(n, (H / n.shape[0], W / n.shape[1]), order=3)[:H, :W] / 2 ** o
    return out / 2


cx, cy = 0.5 * W / max(W, H), 0.42 * H / max(W, H)
r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
bg = np.zeros((H, W, 3))
teal_hi, teal_lo = np.array([0.20, 0.33, 0.33]), np.array([0.06, 0.12, 0.13])
g = np.clip(1 - r * 1.5, 0, 1)[..., None]
bg = teal_lo + (teal_hi - teal_lo) * g
strokes = noise(24, 4)[..., None]
bg *= 0.88 + 0.24 * strokes
if not a.full:
    # rough, dry-brush edge so the plate sits in the game's avatar frame
    edge = np.minimum.reduce([xx, (W / max(W, H)) - xx, yy, (H / max(W, H)) - yy])
    rough = edge + (noise(10, 3) - 0.5) * 0.035
    alpha = np.clip((rough - 0.012) / 0.012, 0, 1)
else:
    alpha = np.zeros((H, W))
plate = np.dstack([(bg * 255).clip(0, 255), alpha * 255]).astype(np.uint8)
out = Image.fromarray(plate, 'RGBA')
out.alpha_composite(fg)
out.save(a.out, optimize=True)
print('saved', a.out)
