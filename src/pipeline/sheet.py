"""Fast QA contact sheet: one (or more) frames from every animation, flat-lit polygons.
usage: python3 sheet.py model.timbermesh texture.png out.png [frac=0.5] [az=30]"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from PIL import Image
import tmesh

model = tmesh.load(sys.argv[1])
tex = np.array(Image.open(sys.argv[2]).convert('RGB')) / 255.0
out = sys.argv[3]
frac = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
az = np.radians(float(sys.argv[5]) if len(sys.argv) > 5 else 30)
n = model.nodes[1]
P = tmesh.prop_array(n.vertexProperties, 'position')
uv = tmesh.prop_array(n.vertexProperties, 'uv0')
tri = np.array(n.meshes[0].indices).reshape(-1, 3)
H = tex.shape[0]
fcol = np.array([tex[int((1 - u[1]) * H) % H, int(u[0] * H) % H] for u in uv[tri].mean(1)])
anims = list(n.vertexAnimations)
cols = 8
rows = int(np.ceil(len(anims) / cols))
fig, axs = plt.subplots(rows, cols, figsize=(cols * 2.4, rows * 2.6))
R = np.array([[np.cos(az), 0, np.sin(az)], [0, 1, 0], [-np.sin(az), 0, np.cos(az)]])
L = np.array([0.4, 0.8, 0.5]); L /= np.linalg.norm(L)
for ax, a in zip(axs.ravel(), anims):
    f = a.frames[int(frac * (len(a.frames) - 1))]
    p, nr, _, _ = tmesh.decode_frame(P, f)
    q = p @ R.T
    fn = np.cross(q[tri[:, 1]] - q[tri[:, 0]], q[tri[:, 2]] - q[tri[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    vis = fn[:, 2] > -0.05
    sh = 0.45 + 0.55 * np.clip(fn @ (R @ L), 0, 1)
    o = np.argsort(q[tri].mean(1)[:, 2])
    o = o[vis[o]]
    ax.add_collection(PolyCollection(q[tri[o]][:, :, :2], facecolors=np.clip(fcol[o] * sh[o, None], 0, 1), edgecolors='none'))
    ax.set_xlim(-0.45, 0.45); ax.set_ylim(-0.1, 0.75); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(a.name.replace('BeaverAdult_', '').replace('BeaverChild_', ''), fontsize=7)
for ax in axs.ravel()[len(anims):]:
    ax.axis('off')
plt.tight_layout()
plt.savefig(out, dpi=55)
