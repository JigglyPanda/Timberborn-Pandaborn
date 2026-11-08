"""Paint every faction texture variant for a model.
usage: python3 make_textures.py ADULT|CHILD paint.npz outdir"""
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
    lm = dict(eye=tuple(front_point(0.051, 0.487, 0.008)), nose=tuple(front_point(0.0, 0.440, 0.008)))
    S, scale, kind, nvar = 2048, 1.0, 'adult', 5
    beaver_ao = E + 'common/adult_ao_2k.png'
    extra = {}
elif which == 'CHILD_V3':
    # v3: eyes seated exactly in the game's fixed eyelid sockets (normal-map relief) so they read as one pair
    lm = dict(eye=tuple(front_point(0.031, 0.303, 0.005)), nose=tuple(front_point(0.0, 0.266, 0.006)))
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

FT = [
    dict(name=1, seed=11, white=(0.90, 0.88, 0.83), black=(0.070, 0.065, 0.068)),
    dict(name=2, seed=12, white=(0.89, 0.85, 0.76), black=(0.085, 0.075, 0.070), patch_a=0.033, patch_b=0.020, cream=(0.05, 0.03, -0.01)),
    dict(name=3, seed=13, white=(0.93, 0.92, 0.895), black=(0.060, 0.060, 0.066), patch_a=0.029, patch_b=0.017, patch_tilt=30),
    dict(name=4, seed=14, white=(0.86, 0.82, 0.72), black=(0.100, 0.085, 0.075), band_hw=0.052, patch_tilt=38),
    dict(name=5, seed=15, white=(0.86, 0.79, 0.68), black=(0.31, 0.21, 0.14), iris=(0.24, 0.15, 0.08),
         nose_col=(0.22, 0.15, 0.12), eye_rim=(0.36, 0.26, 0.19), black_warm=(0.03, 0.015, 0.0)),   # Qinling brown panda
]
IT = [
    dict(name=1, seed=21, white=(0.84, 0.85, 0.86), black=(0.060, 0.065, 0.075), cream=(0.0, 0.0, 0.01), soot=0.06),
    dict(name=2, seed=22, white=(0.80, 0.80, 0.80), black=(0.080, 0.080, 0.090), cream=(-0.01, -0.01, 0.0), soot=0.14, patch_a=0.033),
    dict(name=3, seed=23, white=(0.82, 0.845, 0.88), black=(0.050, 0.060, 0.080), cream=(-0.01, 0.0, 0.02), soot=0.05, patch_tilt=30),
    dict(name=4, seed=24, white=(0.78, 0.77, 0.74), black=(0.070, 0.070, 0.070), soot=0.24, band_hw=0.052),
    dict(name=5, seed=25, white=(0.80, 0.76, 0.70), black=(0.27, 0.19, 0.14), iris=(0.22, 0.14, 0.08),
         nose_col=(0.20, 0.14, 0.11), eye_rim=(0.33, 0.24, 0.18), soot=0.08),
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
    FT = [dict(v, white=tuple(min(1, c * 1.02) for c in v['white']), fur_detail=0.18) for v in FT[:3]]
    IT = [dict(v, soot=v.get('soot', 0) * 0.5, fur_detail=0.18) for v in IT[:3]]
if which == 'CHILD_V3':
    CUTE = dict(CUTE, eye_dy=0.0, eye_r=0.0165, hi_r=0.0050, patch_a=0.034, patch_b=0.031, patch_dy=-0.002, patch_dx=0.001)
if V2:
    style = CUTE if kind == 'child' else REAL
    FT = [dict(v, **style) for v in FT]
    IT = [dict(v, **style) for v in IT]
os.makedirs(outdir, exist_ok=True)
for fac, vs, ref in [('Folktails', FT, 'folktails'), ('IronTeeth', IT, 'ironteeth')]:
    for v in vs:
        v = dict(extra, **v)
        n = v['name']
        tex_ref = E + f'{ref}/{kind}/beaver{kind}{n}.{ref}.png'
        nm = f'Beaver{kind.capitalize()}{n}.{fac}.png'
        pt.paint(v, tex_ref, os.path.join(outdir, nm))
        print('painted', nm)
