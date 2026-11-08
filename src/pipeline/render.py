"""Headless Blender (bpy) preview renderer for Timbermesh character frames.

Coordinates in: game/Unity space (x right, y up, z forward, left-handed).
Converted to Blender: bx=-ux, by=-uz, bz=uy (inverse of the Timbermesh exporter).
"""
import bpy
import numpy as np
import os


def u2b(p):
    p = np.asarray(p, dtype=np.float64)
    return np.stack([-p[:, 0], -p[:, 2], p[:, 1]], axis=1)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.62, 0.70, 0.78, 1)
    bg.inputs[1].default_value = 0.55
    # key + rim light
    for name, loc, en, sz in [('Key', (1.8, -2.2, 2.6), 260, 2.0), ('Rim', (-1.6, 2.0, 1.8), 140, 1.5),
                              ('Fill', (-2.4, -1.2, 0.8), 60, 3.0)]:
        L = bpy.data.lights.new(name, 'AREA')
        L.energy = en
        L.size = sz
        o = bpy.data.objects.new(name, L)
        o.location = loc
        sc.collection.objects.link(o)
        d = -np.array(loc)
        o.rotation_euler = _look_rot(d)
    # ground
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    g = bpy.context.active_object
    gm = bpy.data.materials.new('Ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.52, 0.30, 1)
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
    g.data.materials.append(gm)


def _look_rot(d):
    from mathutils import Vector
    return Vector(tuple(d)).to_track_quat('-Z', 'Y').to_euler()


def make_material(name, base_png=None, normal_png=None, ao_png=None, color=(0.8, 0.8, 0.8)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.85
    try:
        bsdf.inputs['Specular IOR Level'].default_value = 0.25
    except Exception:
        pass
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'uv0'
    if base_png:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(base_png, check_existing=True)
        nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
        col = tex.outputs['Color']
        if ao_png:
            ao = nt.nodes.new('ShaderNodeTexImage')
            ao.image = bpy.data.images.load(ao_png, check_existing=True)
            ao.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(uv.outputs['UV'], ao.inputs['Vector'])
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 0.5   # in-game AO only darkens ambient light
            nt.links.new(col, mix.inputs[6])
            nt.links.new(ao.outputs['Color'], mix.inputs[7])
            col = mix.outputs[2]
        nt.links.new(col, bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*color, 1)
    if normal_png:
        nt_ = nt.nodes.new('ShaderNodeTexImage')
        nt_.image = bpy.data.images.load(normal_png, check_existing=True)
        nt_.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(uv.outputs['UV'], nt_.inputs['Vector'])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.uv_map = 'uv0'
        nm.inputs['Strength'].default_value = float(__import__('os').environ.get('NSTR', '1.0'))
        nt.links.new(nt_.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def add_mesh(name, pos_u, tris, uv0=None, normals_u=None, material=None, offset=(0, 0, 0), smooth=True):
    P = u2b(pos_u) + np.array(offset)
    me = bpy.data.meshes.new(name)
    # Unity is left-handed: flip winding when converting
    t = np.asarray(tris)[:, [0, 2, 1]]
    me.from_pydata(P.tolist(), [], t.tolist())
    if uv0 is not None:
        uvl = me.uv_layers.new(name='uv0')
        loop_v = np.array([l.vertex_index for l in me.loops])
        uv = np.asarray(uv0)[loop_v]
        uvl.data.foreach_set('uv', uv.astype(np.float32).ravel())
    me.update()
    if normals_u is not None:
        N = u2b(normals_u)
        N /= np.linalg.norm(N, axis=1, keepdims=True).clip(1e-9)
        try:
            me.normals_split_custom_set_from_vertices(N.tolist())
        except Exception:
            pass
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if material:
        me.materials.append(material)
    return o


def add_camera(target=(0, 0, 0.27), dist=1.6, az=35, el=12, lens=60):
    sc = bpy.context.scene
    cam = bpy.data.cameras.new('Cam')
    cam.lens = lens
    o = bpy.data.objects.new('Cam', cam)
    sc.collection.objects.link(o)
    a, e = np.radians(az), np.radians(el)
    # Blender: beaver faces -Y (game +Z -> blender -Y)
    loc = np.array(target) + dist * np.array([np.sin(a) * np.cos(e), -np.cos(a) * np.cos(e), np.sin(e)])
    o.location = loc
    o.rotation_euler = _look_rot(np.array(target) - loc)
    sc.camera = o
    return o


def render(path, w=900, h=700, samples=None):
    sc = bpy.context.scene
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    if samples:
        sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
