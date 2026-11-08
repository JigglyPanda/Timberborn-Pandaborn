"""Bake ambient occlusion of a rest mesh into its uv0 layout (Cycles)."""
import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, bpy, render
d=np.load(sys.argv[1]); out=sys.argv[2]; S=int(sys.argv[3]) if len(sys.argv)>3 else 1024
render.reset()
for o in list(bpy.data.objects):
    if o.type=='MESH': bpy.data.objects.remove(o)
mat=bpy.data.materials.new('bk'); mat.use_nodes=True
img=bpy.data.images.new('ao',S,S,float_buffer=True)
tn=mat.node_tree.nodes.new('ShaderNodeTexImage'); tn.image=img; mat.node_tree.nodes.active=tn
tri=d['tri']; keep=~(d['teeth'][tri].any(1))
o=render.add_mesh('m',d['P'],tri[keep],d['uv0'],d['N'],mat)
bpy.context.view_layer.objects.active=o; o.select_set(True)
sc=bpy.context.scene; sc.cycles.samples=128; sc.world.light_settings.distance=0.12
sc.render.bake.margin=16
bpy.ops.object.bake(type='AO')
a=np.array(img.pixels[:]).reshape(S,S,4)[::-1,:,0]
np.save(out,a); print('ao',a.min(),a.mean())
