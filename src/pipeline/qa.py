import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, tmesh
def load(p):
    m=tmesh.load(p); n=m.nodes[1]
    P=tmesh.prop_array(n.vertexProperties,'position').astype(float); tri=np.array(n.meshes[0].indices).reshape(-1,3)
    return P,tri,list(n.vertexAnimations)
def stats(P,tri,anims):
    e=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),1),axis=0)
    L0=np.linalg.norm(P[e[:,0]]-P[e[:,1]],axis=1)+1e-9
    fn0=np.cross(P[tri[:,1]]-P[tri[:,0]],P[tri[:,2]]-P[tri[:,0]])
    res={}
    for a in anims:
        mx=0; flips=0
        for f in a.frames:
            p=P.copy(); off=tmesh.prop_array(f.vertexProperties,'offset'); p[:len(off)]+=off
            r=np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1)/L0
            mx=max(mx,np.percentile(r,99.9))
            # flip relative to rest orientation using local area sign is not meaningful for big rotations;
            # use: triangle area collapse (degenerate) count
            fn=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
            flips=max(flips,int((np.linalg.norm(fn,axis=1)<0.05*np.linalg.norm(fn0,axis=1)).sum()))
        res[a.name.split('_',1)[1] if '_' in a.name else a.name]=(mx,flips)
    return res
b=stats(*load(sys.argv[1])); p=stats(*load(sys.argv[2]))
print(f"{'anim':34s} beaver_stretch99.9 panda_stretch99.9  beaver_collapsed panda_collapsed")
worst=[]
for k in b:
    print(f"{k:34s} {b[k][0]:6.2f} {p[k][0]:6.2f}   {b[k][1]:4d} {p[k][1]:4d}")
    worst.append((p[k][0]/b[k][0],k))
print('worst stretch ratio panda/beaver', sorted(worst)[-5:])
