"""UV-space rasterisation of per-vertex attributes + seam padding."""
import numpy as np
from scipy import ndimage


def rasterize(uv, tri, attrs, size):
    """Returns dict name->(S,S,k) float images, plus 'mask' (S,S) bool and 'tri' (S,S) int.
    Row 0 = top of texture (v=1)."""
    S = size
    out = {k: np.zeros((S, S, v.shape[1] if v.ndim > 1 else 1)) for k, v in attrs.items()}
    mask = np.zeros((S, S), bool)
    tid = np.full((S, S), -1, int)
    px = np.stack([uv[:, 0] * S - 0.5, (1 - uv[:, 1]) * S - 0.5], 1)
    for t_i, t in enumerate(tri):
        p = px[t]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, S - 1), min(y1, S - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        a, b, c = p
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        l2 = 1 - l0 - l1
        eps = -1e-3
        inside = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        if not inside.any():
            continue
        yy, xx = ys[inside], xs[inside]
        L = np.stack([l0[inside], l1[inside], l2[inside]], 1)
        for k, v in attrs.items():
            vv = v[t] if v.ndim > 1 else v[t][:, None]
            out[k][yy, xx] = L @ vv
        mask[yy, xx] = True
        tid[yy, xx] = t_i
    out['mask'] = mask
    out['tri'] = tid
    return out


def pad(img, mask, iterations=None):
    """Fill texels outside mask with nearest inside value (prevents seams with mipmaps)."""
    idx = ndimage.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    return img[idx[0], idx[1]]
