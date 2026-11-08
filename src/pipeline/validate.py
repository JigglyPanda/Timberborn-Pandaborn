import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, tmesh, json, os
from PIL import Image
ok=True
def chk(c,msg):
    global ok
    if not c: ok=False; print('FAIL:',msg)
M=sys.argv[1] if len(sys.argv)>1 else '/root/w/mod/PandaBeavers'
for n,orig in [('BeaverAdult','beaveradult'),('BeaverChild','beaverchild')]:
    p=f'{M}/Characters/Beaver/{n}.Model.timbermesh'
    raw=open(p,'rb').read(); chk(raw[:2]==b'\x78\x9c',f'{n} zlib header')
    m=tmesh.load(p); o=tmesh.load(f'/root/w/ext/characters/beaver/{orig}.model.timbermesh')
    chk([x.name for x in m.nodes]==[x.name for x in o.nodes],f'{n} node names')
    chk([x.parent for x in m.nodes]==[x.parent for x in o.nodes],f'{n} node parents')
    for a,b in zip(m.nodes,o.nodes):
        chk([(x.name,len(x.frames)) for x in a.nodeAnimations]==[(x.name,len(x.frames)) for x in b.nodeAnimations],f'{n} {a.name} node anims')
    nd=m.nodes[1]; V=nd.vertexCount
    for k in ['position','normal','tangent','color','uv0','uv1']:
        arr=tmesh.prop_array(nd.vertexProperties,k); chk(arr is not None and len(arr)==V and np.isfinite(arr).all(),f'{n} prop {k}')
    idx=np.array(nd.meshes[0].indices); chk(idx.max()<V and idx.min()>=0 and len(idx)%3==0,f'{n} indices')
    chk(nd.meshes[0].material==o.nodes[1].meshes[0].material,f'{n} material')
    ob={x.name:(len(x.frames),x.framerate) for x in o.nodes[1].vertexAnimations}
    mb={x.name:(len(x.frames),x.framerate) for x in nd.vertexAnimations}
    chk(ob==mb,f'{n} vertex anim names/frames/fps')
    worst=0; qn=[]
    for a in nd.vertexAnimations:
        chk(a.animatedVertexCount==V,f'{n} {a.name} count')
        for f in a.frames:
            off=tmesh.prop_array(f.vertexProperties,'offset'); rot=tmesh.prop_array(f.vertexProperties,'rotation')
            if off is None or rot is None or len(off)!=V or len(rot)!=V or not np.isfinite(off).all() or not np.isfinite(rot).all():
                chk(False,f'{n} {a.name} frame data'); break
            worst=max(worst,np.abs(off).max()); qn.append(np.abs(np.linalg.norm(rot,axis=1)-1).max())
    chk(worst<60000,f'{n} half range'); chk(max(qn)<0.01,f'{n} quat norms {max(qn)}')
    print(f'{n}: {V} verts, {len(idx)//3} tris, {len(mb)} anims, {sum(v[0] for v in mb.values())} frames, max offset {worst:.3f} m, max |q|-1 {max(qn):.4f}')
for r,ds,fs in os.walk(M):
    for f in fs:
        if f.endswith('.png'):
            im=Image.open(os.path.join(r,f)); im.load()
    for f in fs:
        if f.endswith('.json'): json.load(open(os.path.join(r,f)))
# expected texture set
for fac in ['Folktails','IronTeeth']:
    for i in range(1,6): chk(os.path.exists(f'{M}/Materials/Beavers/{fac}/Adult/BeaverAdult{i}.{fac}.png'),f'adult tex {fac}{i}')
    for i in range(1,4): chk(os.path.exists(f'{M}/Materials/Beavers/{fac}/Child/BeaverChild{i}.{fac}.png'),f'child tex {fac}{i}')
# paths referenced by faction blueprints resolve to our files
import glob
for fb in glob.glob('/root/w/bp/Factions/*.json'):
    d=json.load(open(fb))['FactionSpec']
    for t in d['Textures']+d['ChildTextures']:
        chk(os.path.exists(f'{M}/{t}.png') or any(x.lower()==f'{M}/{t}.png'.lower() for x in glob.glob(f'{M}/Materials/**/*.png',recursive=True)),f'faction ref {t}')
    for k in ['Avatar','ChildAvatar','ContaminatedAdultAvatar','ContaminatedChildAvatar','NewGameFullAvatar']:
        chk(any(x.lower()==f'{M}/{d[k]}.png'.lower() for x in glob.glob(f'{M}/Sprites/**/*.png',recursive=True)),f'avatar {d[k]}')
print('ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED')
