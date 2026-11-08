"""Fur-length masks (R channel) in the panda UV layout for the shell-fur shader."""
import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, paint
from PIL import Image
from scipy import ndimage

def build(paint_npz, ao_npy, lm, scale, var, out, S=1024):
    pt = paint.Painter(paint_npz, ao_npy, S, lm, None, scale=scale)
    m = pt.masks(var)
    r = pt.r
    head = r['head'][..., 0]
    N = r['N']
    face = (head > 0.5) * smoothstep(-0.1, 0.5, N[..., 2])
    L = np.full((S, S), 0.85)
    L = L * (1 - 0.30 * (head > 0.5)) * (1 - 0.35 * face)          # shorter on the head, shortest on the face
    L = np.maximum(L, r['tail'][..., 0] * 1.0)                      # pom-pom tail
    eye_zone = ndimage.grey_dilation(np.maximum(m['eye'], m['eyerim']), size=(int(S * 0.012) | 1,) * 2)
    L *= 1 - np.clip(eye_zone, 0, 1)
    L *= 1 - np.clip(ndimage.grey_dilation(m['nose'], size=(5, 5)), 0, 1)
    L *= 1 - 0.9 * np.clip(m['mouth'] * 3, 0, 1)
    L *= 1 - r['sole'][..., 0]
    L *= 1 - r['teeth'][..., 0]
    L = ndimage.gaussian_filter(L, 1.5)
    L = paint.raster.pad(L[..., None], pt.mask)[..., 0]
    Image.fromarray((np.clip(L, 0, 1) * 255).astype(np.uint8)).save(out)
    print('mask', out, L.min(), L.mean())

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

if __name__ == '__main__':
    import make_textures_lm as ml
