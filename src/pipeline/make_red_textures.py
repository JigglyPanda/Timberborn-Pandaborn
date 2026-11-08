"""Paint every faction texture variant for a model.
usage: python3 make_red_textures.py ADULT|CHILD paint.npz outdir"""
import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import os, subprocess, numpy as np
import paint, configs
from PIL import Image

E = '/root/w/ext/materials/beavers/'
which = sys.argv[1]; pn = sys.argv[2]; outdir = sys.argv[3]
cfg = getattr(configs, which)
d = np.load(pn); P = d['P']


def front_point(x, y, tol):
    s = (np.abs(P[:, 0] - x) < tol) & (np.abs(P[:, 1] - y) < tol) & (d['head'] > 0.5) & (d['teeth'] < 0.5)
    return P[np.argmax(np.where(s, P[:, 2], -9))]


if which.startswith('ADULT'):
    lm = dict(eye=tuple(front_point(0.040, 0.490, 0.006)), nose=tuple(front_point(0.0, 0.440, 0.008)))   # eye seated in the game's socket
    S, scale, kind, nvar = 2048, 1.0, 'adult', 5
    beaver_ao = E + 'common/adult_ao_2k.png'
    extra = {}
elif which == 'CHILD_V3':
    # v3: eyes seated exactly in the game's fixed eyelid sockets (normal-map relief) so they read as one pair
    lm = dict(eye=tuple(front_point(0.0341, 0.3079, 0.005)), nose=tuple(front_point(0.0, 0.266, 0.006)))   # socket
    S, scale, kind, nvar = 2048, 0.66, 'child', 3
    beaver_ao = E + 'common/child_ao_1k.png'
    extra = dict(band_y=0.268, leg_reach=0.145, arm_reach=0.040, patch_a=0.034, patch_b=0.021, nose_w=0.021, nose_h=0.013, wobble=0.005)
else:
    lm = dict(eye=tuple(front_point(0.034, 0.298, 0.006)), nose=tuple(front_point(0.0, 0.266, 0.006)))
    S, scale, kind, nvar = 2048, 0.66, 'child', 3
    beaver_ao = E + 'common/child_ao_1k.png'
    extra = dict(band_y=0.268, leg_reach=0.145, arm_reach=0.040, patch_a=0.034, patch_b=0.021, nose_w=0.021, nose_h=0.013, wobble=0.005)
print('landmarks', lm)
ao_npy = pn.replace('.paint.npz', '.ao.npy')
if not os.path.exists(ao_npy):
    subprocess.run(['python3', '/root/w/lib/bake_ao.py', pn, ao_npy, '1024'], check=True, capture_output=True)
pt = paint.Painter(pn, ao_npy, S, lm, beaver_ao, scale=scale)


# Iron Teeth become red pandas
RED = [
    dict(name=1, seed=31, red=(0.60, 0.25, 0.085), dark=(0.075, 0.045, 0.035), white=(0.92, 0.89, 0.83)),                 # classic
    dict(name=2, seed=32, red=(0.47, 0.17, 0.065), dark=(0.060, 0.035, 0.030), white=(0.90, 0.87, 0.80), tear_col=(0.33, 0.11, 0.05)),  # deep chestnut
    dict(name=3, seed=33, red=(0.70, 0.35, 0.12), dark=(0.11, 0.065, 0.045), white=(0.94, 0.92, 0.86), ginger=(0.08, 0.05, 0.0)),    # golden
    dict(name=4, seed=34, red=(0.52, 0.22, 0.085), dark=(0.065, 0.045, 0.040), white=(0.84, 0.82, 0.78), soot=0.16),        # soot-grimed
    dict(name=5, seed=35, red=(0.78, 0.55, 0.33), dark=(0.30, 0.19, 0.12), white=(0.95, 0.93, 0.88), tear_col=(0.58, 0.32, 0.16),
         ring_depth=0.3, iris=(0.24, 0.15, 0.08)),                                                                               # rare cinnamon
]
V2 = which.endswith('_V2') or which.endswith('_V3')
REAL = dict(patch_a=0.037, patch_b=0.022, patch_tear=0.55, patch_tilt=36, patch_dy=0.011,
            eye_r=0.0070, eye_rim_w=0.0012, hi_r=0.0017, iris=(0.07, 0.05, 0.04), eye_rim=(0.10, 0.09, 0.085),
            nose_w=0.024, nose_h=0.0145, belly_dust=0.10, fluff=0.06, wobble=0.008, fine_jag=0.004, fur_detail=0.26)
CUTE = dict(patch_a=0.031, patch_b=0.026, patch_tear=0.12, patch_tilt=16, patch_dy=0.004, patch_dx=0.002,
            eye_r=0.0140, eye_rim_w=0.0014, eye_squash=1.0, eye_dy=-0.002, iris=(0.05, 0.035, 0.03), iris_low=(0.13, 0.09, 0.06),
            eye_rim=(0.16, 0.13, 0.11), hi_r=0.0044, sparkle2=True,
            blush=0.95, blush_dx=0.010, blush_dy=0.042, blush_rx=0.024, blush_ry=0.014,
            nose_w=0.016, nose_h=0.0105, fluff=0.05, fur_detail=0.15, wobble=0.005)
if kind == 'child':
    # cubs: lighter, fluffier fur; three variants each
    RED = [dict(v, fur_detail=0.18) for v in RED[:3]]
if which == 'CHILD_V3':
    CUTE = dict(CUTE, eye_dy=0.0, eye_r=0.0165, hi_r=0.0050, patch_a=0.034, patch_b=0.031, patch_dy=-0.002, patch_dx=0.001)
if V2:
    style = CUTE if kind == 'child' else REAL
    RED = [dict(dict(v, **style), blush=0.25 if kind == 'child' else 0, ring_rx=0.0215 if kind == 'child' else 0.0140, ring_ry=0.0200 if kind == 'child' else 0.0125) for v in RED]
    if kind == 'adult':
        # bigger, glossier eyes than the giant-panda adults: red pandas read as cute, not stern
        RED = [dict(v, eye_r=0.0080, eye_rim_w=0.0014, hi_r=0.0026, ring_rx=0.0140, ring_ry=0.0125, sparkle2=True, eye_squash=1.0,
                    iris=(0.07, 0.045, 0.035), iris_low=(0.10, 0.06, 0.04)) for v in RED]
os.makedirs(outdir, exist_ok=True)
for v in RED:
    v = dict(extra, **v)
    n = v['name']
    tex_ref = E + f'ironteeth/{kind}/beaver{kind}{n}.ironteeth.png'
    nm = f'Beaver{kind.capitalize()}{n}.IronTeeth.png'
    pt.paint_red(v, tex_ref, os.path.join(outdir, nm))
    print('painted', nm)
