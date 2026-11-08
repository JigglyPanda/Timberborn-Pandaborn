"""Paint panda base-colour textures in the beaver UV layout.

Pattern shapes are evaluated in 3D on the panda rest surface (rasterised into UV space),
then combined with the original artist's fur-stroke detail (high-pass of the beaver texture).
"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
from PIL import Image
from scipy import ndimage
import raster


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 3D value noise (fbm)
def _hash(ix, iy, iz, seed):
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 144665) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def vnoise(p, seed=0):
    pi = np.floor(p).astype(np.int64)
    f = p - pi
    u = f * f * (3 - 2 * f)
    acc = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[..., 0] if dx else 1 - u[..., 0]) * (u[..., 1] if dy else 1 - u[..., 1]) * (u[..., 2] if dz else 1 - u[..., 2])
                acc = acc + w * _hash(pi[..., 0] + dx, pi[..., 1] + dy, pi[..., 2] + dz, seed)
    return acc * 2 - 1


def fbm(p, octaves=4, seed=0):
    a, s, tot = 0.5, 1.0, 0
    for o in range(octaves):
        tot = tot + a * vnoise(p * s, seed + o * 17)
        a *= 0.5; s *= 2.03
    return tot


class Painter:
    def __init__(self, paint_npz, ao_npy, size, landmarks, beaver_ao_png=None, scale=1.0):
        d = np.load(paint_npz)
        self.scale = scale
        self.d = d
        self.S = size
        self.lm = landmarks
        tri = d['tri']
        attrs = dict(P=d['P'], N=d['N'], ear=d['ear'], darm=np.minimum(d['darm'], 1.0),
                     dsole=np.minimum(d['dsole'], 1.0), head=d['head'], tail=d['tail'], teeth=d['teeth'],
                     sole=d['sole'])
        r = raster.rasterize(d['uv0'], tri, attrs, size)
        self.mask = r['mask']
        self.r = {k: raster.pad(v, self.mask) for k, v in r.items() if k not in ('mask', 'tri')}
        N = self.r['N']
        self.r['N'] = N / np.linalg.norm(N, axis=2, keepdims=True).clip(1e-9)
        # work in 'adult-equivalent' units so one set of pattern rules fits every model
        self.r['P'] = self.r['P'] / scale
        self.r['darm'] = self.r['darm'] / scale
        self.r['dsole'] = self.r['dsole'] / scale
        self.lm = {k: tuple(np.array(v) / scale) for k, v in landmarks.items()}
        ao = np.load(ao_npy)
        ao = np.array(Image.fromarray((ao * 255).clip(0, 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)) / 255.0
        self.ao = raster.pad(ao[..., None], self.mask & (ao > 0.02))[..., 0]
        self.beaver_ao = None
        if beaver_ao_png:
            bao = np.array(Image.open(beaver_ao_png).convert('L').resize((size, size), Image.BILINEAR)) / 255.0
            self.beaver_ao = bao

    # ------------------------------------------------------------ masks
    def masks(self, var):
        r, lm = self.r, self.lm
        P = r['P'][..., :]
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        N = r['N']
        seed = var.get('seed', 0)
        nz = fbm(P * 90.0, 4, seed)             # boundary wobble (fur clumps)
        nz2 = fbm(P * 260.0, 3, seed + 5)        # fine fur jaggedness
        jag = nz * var.get('wobble', 0.006) + nz2 * var.get('fine_jag', 0.0025)
        front = smoothstep(-0.15, 0.25, N[..., 2])
        head = r['head'][..., 0]
        out = {}

        # --- eye patches (droopy teardrops)
        ep = np.zeros_like(x)
        for sx in (1, -1):
            ex, ey, ez = lm['eye']
            c = np.array([sx * (ex + var.get('patch_dx', 0.004)), ey - var.get('patch_dy', 0.010)])
            ang = np.radians(var.get('patch_tilt', 34))
            ax = np.array([sx * np.sin(ang), -np.cos(ang)])     # major axis: inner-top -> outer-bottom
            ay = np.array([-ax[1], ax[0]])
            rel = np.stack([x - c[0], y - c[1]], -1)
            u = rel @ ax; v = rel @ ay
            a = var.get('patch_a', 0.031); b = var.get('patch_b', 0.018)
            bb = b * (1 + var.get('patch_tear', 0.45) * np.clip(u / a, -1, 1))          # teardrop: fuller at the bottom
            dist = np.sqrt((u / a) ** 2 + (v / bb) ** 2)
            m = 1 - smoothstep(0.92, 1.05, dist + jag * 18)
            m *= smoothstep(ez - 0.06, ez - 0.03, z) * front * (head > 0.5)
            ep = np.maximum(ep, m)
        out['eyepatch'] = ep

        # --- eyes (iris, catch-light) drawn on top
        er = var.get('eye_r', 0.0092); erw = var.get('eye_rim_w', 0.0020)
        eye = np.zeros_like(x); hi = np.zeros_like(x); rim = np.zeros_like(x); hi2 = np.zeros_like(x); ilow = np.zeros_like(x)
        for sx in (1, -1):
            ex, ey, ez = lm['eye']
            ex = ex + var.get('eye_dx', 0.0); ey = ey + var.get('eye_dy', 0.0)
            d2 = np.sqrt((x - sx * ex) ** 2 + ((y - ey) * var.get('eye_squash', 1.1)) ** 2)
            fr = smoothstep(ez - 0.05, ez - 0.02, z) * front
            eye = np.maximum(eye, (1 - smoothstep(er * 0.82, er, d2)) * fr)
            rim = np.maximum(rim, (1 - smoothstep(er, er + erw, d2)) * fr)
            # lower half of the iris catches bounce light (reads as a glossy eye)
            ilow = np.maximum(ilow, (1 - smoothstep(er * 0.3, er * 0.95, np.sqrt((x - sx * ex) ** 2 + (y - ey + er * 0.55) ** 2))) * fr)
            hs = var.get('hi_r', 0.0024)
            hd = np.sqrt((x - sx * ex - sx * er * 0.32) ** 2 + (y - ey - er * 0.36) ** 2)
            hi = np.maximum(hi, (1 - smoothstep(hs * 0.75, hs * 1.25, hd)) * fr)
            if var.get('sparkle2', False):
                hd2 = np.sqrt((x - sx * ex + sx * er * 0.38) ** 2 + (y - ey + er * 0.42) ** 2)
                hi2 = np.maximum(hi2, (1 - smoothstep(hs * 0.35, hs * 0.65, hd2)) * fr)
        out['eye'], out['eyehi'], out['eyerim'], out['eyehi2'], out['eyelow'] = eye, hi, rim, hi2, ilow * eye

        # --- blush (cute cubs)
        bl = np.zeros_like(x)
        if var.get('blush', 0) > 0:
            for sx in (1, -1):
                ex, ey, ez = lm['eye']
                bx, by = sx * (ex + var.get('blush_dx', 0.020)), ey - var.get('blush_dy', 0.036)
                dd = np.sqrt(((x - bx) / var.get('blush_rx', 0.020)) ** 2 + ((y - by) / var.get('blush_ry', 0.012)) ** 2)
                bl = np.maximum(bl, (1 - smoothstep(0.2, 1.0, dd)) * front * (head > 0.5))
        out['blush'] = bl * var.get('blush', 0)

        # --- nose (rounded inverted triangle) + mouth
        nx, ny, nzc = lm['nose']
        rx = (x - nx) / var.get('nose_w', 0.019)
        ry = (y - ny) / var.get('nose_h', 0.012)
        tri_w = 1 - 0.38 * np.clip(-ry, 0, 1.2)   # narrower towards the bottom
        nd = np.sqrt((rx / tri_w) ** 2 + ry ** 2)
        nose = (1 - smoothstep(0.85, 1.05, nd)) * smoothstep(nzc - 0.04, nzc - 0.015, z) * front
        out['nose'] = nose
        # nose highlight
        out['nosehi'] = (1 - smoothstep(0.0, 0.35, np.sqrt(((x - nx) / 0.010) ** 2 + ((y - ny - 0.004) / 0.004) ** 2))) * nose
        # mouth: philtrum + smile curves
        my = ny - var.get('nose_h', 0.012) * 0.9
        phil = (np.abs(x - nx) < 0.0016) & (y < my + 0.002) & (y > my - 0.011)
        mouth = phil.astype(float)
        for sx in (1, -1):
            cx, cy, rr = nx + sx * 0.0085, my - 0.0105 + 0.0085, 0.0085
            dd = np.abs(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - rr)
            arc = (dd < 0.0015) & (y < cy) & ((x - cx) * sx < 0.004)
            mouth = np.maximum(mouth, arc.astype(float))
        mouth *= smoothstep(nzc - 0.05, nzc - 0.025, z) * front
        out['mouth'] = ndimage.gaussian_filter(mouth, 0.6)

        # --- ears
        ear = r['ear'][..., 0]
        out['ears'] = smoothstep(0.35 - 0.2 * (nz * 0.5 + 0.5), 0.6, ear)

        # --- arms + shoulder band
        darm = r['darm'][..., 0]
        arms = 1 - smoothstep(var.get('arm_reach', 0.035) - 0.01, var.get('arm_reach', 0.035) + 0.01, darm + jag * 1.5)
        bc = var.get('band_y', 0.292) - var.get('band_front_drop', 0.012) * smoothstep(-0.06, 0.08, z)
        hw = var.get('band_hw', 0.046) - var.get('band_front_narrow', -0.004) * smoothstep(-0.04, 0.08, z)
        band = 1 - smoothstep(0.85, 1.05, np.abs(y - bc + jag * 1.2) / hw)
        band *= (head < 0.4) * (1 - r['tail'][..., 0])
        out['arms'] = np.maximum(arms, band)

        # --- legs
        dsole = r['dsole'][..., 0]
        lat = smoothstep(0.03, 0.08, np.abs(x))
        reach = var.get('leg_reach', 0.150) + 0.05 * lat * smoothstep(-0.05, -0.15, z * 0 - 0.1)
        legs = 1 - smoothstep(reach - 0.012, reach + 0.012, dsole + jag * 1.6)
        # keep the inner belly white
        belly = smoothstep(0.06, 0.02, np.abs(x)) * smoothstep(0.03, 0.08, y) * smoothstep(-0.05, 0.02, z)
        legs *= 1 - belly
        legs = np.maximum(legs, r['sole'][..., 0])
        out['legs'] = legs * (1 - r['tail'][..., 0])
        out['jag'] = jag
        out['front'] = front
        return out

    # ------------------------------------------------------------ red panda
    def red_masks(self, var, m):
        """Red-panda markings on the same body: white face mask, tear stripes, dark legs/belly/bib, ear rims, tail rings."""
        r, lm = self.r, self.lm
        P, N = r['P'], r['N']
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        head = r['head'][..., 0]
        front = m['front']
        jag = m['jag']
        ex, ey, ez = lm['eye']
        nx, ny, nzc = lm['nose']
        fz = smoothstep(ez - 0.07, ez - 0.035, z) * (head > 0.5)

        def ell(cx, cy, rx, ry, soft=0.15):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) + jag * 14
            return 1 - smoothstep(1 - soft, 1 + soft, d)

        s = var.get('face_scale', 1.0)
        white = ell(nx, ny - 0.010 * s, 0.047 * s, 0.036 * s)                      # muzzle
        for sx in (1, -1):
            white = np.maximum(white, ell(sx * (ex + 0.013 * s), ey - 0.031 * s, 0.026 * s, 0.022 * s))   # cheeks
            white = np.maximum(white, ell(sx * ex * 0.55, ny - 0.006 * s, 0.030 * s, 0.026 * s))         # joins cheeks to muzzle
            white = np.maximum(white, ell(sx * (ex + 0.002 * s), ey + 0.024 * s, 0.012 * s, 0.009 * s))   # brows
        white *= fz * front
        # authentic red-panda eye ring + tear line: soft mahogany around the eye (also covers the game's fixed
        # beaver eye-socket relief), tapering down to the corner of the mouth
        tear = np.zeros_like(x); band = np.zeros_like(x)
        for sx in (1, -1):
            ring = ell(sx * ex, ey - 0.0015 * s, var.get('ring_rx', 0.0125) * s, var.get('ring_ry', 0.0110) * s, 0.35)
            a = np.array([sx * (ex - 0.0015 * s), ey - 0.008 * s]); b = np.array([sx * (abs(nx) + 0.014 * s), ny - 0.017 * s])
            ab = b - a; t = np.clip(((x - a[0]) * ab[0] + (y - a[1]) * ab[1]) / (ab @ ab), 0, 1)
            d = np.sqrt((x - a[0] - t * ab[0]) ** 2 + (y - a[1] - t * ab[1]) ** 2)
            w = s * (0.0105 * (1 - t) + 0.0055 * t)
            line = 1 - smoothstep(w * 0.5, w * 1.25, d + jag * 0.6)
            tear = np.maximum(tear, ring)
            band = np.maximum(band, line)
        tear *= fz * front * var.get('tear_strength', 0.95)
        band *= fz * front
        white = white * (1 - np.maximum(tear, band))
        # dark throat/bib, belly, legs, arms
        darm = r['darm'][..., 0]
        arms = 1 - smoothstep(var.get('arm_reach', 0.035) - 0.012, var.get('arm_reach', 0.035) + 0.012, darm + jag * 1.5)
        dsole = r['dsole'][..., 0]
        legs = 1 - smoothstep(var.get('leg_reach', 0.150) * 0.85 - 0.015, var.get('leg_reach', 0.150) * 0.85 + 0.015, dsole + jag * 1.6)
        legs = np.maximum(legs, r['sole'][..., 0])
        under = smoothstep(-0.05, -0.45, N[..., 1] + jag * 6) * (head < 0.45)
        bib = smoothstep(0.15, 0.55, N[..., 2] + jag * 6) * (head < 0.45) * smoothstep(var.get('band_y', 0.292) - 0.02, var.get('band_y', 0.292) - 0.075, y + jag * 3)
        throat = (head > 0.3) * smoothstep(ny - 0.04 * s, ny - 0.075 * s, y + jag * 2) * front * 0.85
        dark = np.maximum.reduce([arms, legs, under, bib, throat]) * (1 - r['tail'][..., 0])
        dark = dark * (1 - white)
        # ears: white rims, dark inside
        ear = r['ear'][..., 0]
        rim = smoothstep(0.25, 0.42, ear) * (1 - smoothstep(0.55, 0.72, ear))
        inner = smoothstep(0.62, 0.8, ear)
        # tail rings along the tail's length
        tail = r['tail'][..., 0]
        rings = (0.5 + 0.5 * np.sin(-z * var.get('ring_freq', 160.0) + jag * 40)) ** 3 * tail
        return dict(white=white, tear=tear, band=band, dark=dark, ear_rim=rim * (head > 0.3), ear_in=inner, rings=rings)

    def paint_red(self, var, beaver_tex_png, out_png):
        S = self.S
        m = self.masks(var)
        rm = self.red_masks(var, m)
        r = self.r
        P, N = r['P'], r['N']
        tone = fbm(P * 18.0, 3, var.get('seed', 0) + 31)[..., None]
        red = np.array(var['red']); dark = np.array(var['dark']); white = np.array(var['white'])
        # coat: deeper red along the back, brighter gingery head and flanks
        back = smoothstep(-0.2, -0.8, N[..., 2])[..., None] * (r['head'][..., :1] < 0.5)
        top = smoothstep(0.2, 0.9, N[..., 1])[..., None]
        coat = red * (1 + 0.08 * tone) * (1 - 0.18 * back) + np.array(var.get('ginger', (0.06, 0.04, 0.0))) * top
        col = coat
        def over(c, a, k=0.6):
            a = ndimage.gaussian_filter(a, k)[..., None]
            return col * (1 - a) + c * a
        col = over(dark * (1 + 0.1 * tone), rm['dark'], 2.5)
        col = over(red * 0.82, rm['band'], 1.5)                    # rusty band between cheek and muzzle
        col = over(np.array(var.get('tear_col', (0.20, 0.055, 0.03))), rm['tear'], 2.0)
        col = over(white * (1 + 0.03 * tone), rm['white'])
        col = over(white * 0.95, rm['ear_rim'], 2.0)
        col = over(dark * 1.3 + 0.02, rm['ear_in'], 2.0)
        col = col * (1 - var.get('ring_depth', 0.45) * rm['rings'][..., None])
        # nose / mouth / eyes (shared with the giant panda)
        nose_c = np.array(var.get('nose_col', (0.045, 0.040, 0.042)))
        col = col * (1 - m['nose'][..., None]) + nose_c * m['nose'][..., None]
        col = col + 0.10 * m['nosehi'][..., None]
        col = col * (1 - 0.75 * m['mouth'][..., None]) + 0.06 * m['mouth'][..., None] * nose_c
        rim_c = np.array(var.get('eye_rim', (0.13, 0.08, 0.06)))
        col = col * (1 - m['eyerim'][..., None]) + rim_c * m['eyerim'][..., None]
        col = col * (1 - m['eye'][..., None]) + np.array(var.get('iris', (0.10, 0.065, 0.04))) * m['eye'][..., None]
        col = col + np.array(var.get('iris_low', (0.0, 0.0, 0.0))) * m['eyelow'][..., None]
        col = col * (1 - m['eyehi'][..., None]) + np.array((0.97, 0.97, 0.95)) * m['eyehi'][..., None]
        col = col * (1 - m['eyehi2'][..., None]) + np.array((0.92, 0.92, 0.95)) * m['eyehi2'][..., None]
        bl = ndimage.gaussian_filter(m['blush'], 2.0)[..., None]
        col = col * (1 - bl) + np.array(var.get('blush_col', (0.93, 0.62, 0.62))) * bl
        sole = r['sole'][..., 0]
        col = col * (1 - 0.35 * sole[..., None])
        # fur strokes from the original artwork + micro fur + AO (same as the giant panda)
        bt = np.array(Image.open(beaver_tex_png).convert('RGB').resize((S, S), Image.BICUBIC)) / 255.0
        lum = bt.mean(2)
        hp = lum - ndimage.gaussian_filter(lum, 5.0)
        hp = hp / (ndimage.gaussian_filter(lum, 5.0) + 0.05)
        hp = np.tanh(hp * 1.5) / 1.5
        k = var.get('fur_detail', 0.22) * (1 - m['eye'] - m['eyerim']).clip(0, 1) * (1 - m['nose'])
        col = col * (1 + (hp * k)[..., None])
        fine = fbm(P * np.array([900, 300, 900]) + N * 40, 2, var.get('seed', 0) + 77)[..., None]
        col = col * (1 + var.get('fluff', 0.035) * fine)
        if self.beaver_ao is not None:
            pa = ndimage.gaussian_filter(self.ao, 6)
            ba = ndimage.gaussian_filter(self.beaver_ao, 6)
            comp = np.clip((pa + 0.15) / (ba + 0.15), 0.8, 1.25) ** var.get('ao_comp', 0.35)
            col = col * comp[..., None]
        col = col * (0.82 + 0.18 * self.ao[..., None]) ** 0.7
        soot = var.get('soot', 0.0)
        if soot > 0:
            g = np.clip(fbm(P * 7.0, 4, var.get('seed', 0) + 101) * 1.6 + 0.1, 0, 1)
            col = col * (1 - soot * g[..., None] * np.array([1.0, 1.0, 0.92]))
        col = np.clip(col, 0, 1)
        img = raster.pad(col, self.mask)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(out_png, optimize=True)
        return img

    # ------------------------------------------------------------ compose
    def paint(self, var, beaver_tex_png, out_png):
        S = self.S
        m = self.masks(var)
        r = self.r
        P, N = r['P'], r['N']
        white = np.array(var['white'])
        black = np.array(var['black'])
        black_mask = np.clip(np.maximum.reduce([m['eyepatch'], m['ears'], m['arms'], m['legs']]), 0, 1)
        # soft anti-aliasing
        black_mask = ndimage.gaussian_filter(black_mask, 0.7)
        # tonal variation
        tone = fbm(P * 18.0, 3, var.get('seed', 0) + 31)[..., None]
        wcol = white * (1 + 0.035 * tone) + np.array(var.get('white_tint', (0, 0, 0))) * (0.5 + 0.5 * tone)
        # creamier underside / back of neck, slightly greyer muzzle-sides
        under = smoothstep(0.2, -0.6, N[..., 1])[..., None]
        wcol = wcol * (1 - 0.06 * under) + np.array(var.get('cream', (0.04, 0.025, -0.01))) * under
        bcol = black * (1 + 0.10 * tone)
        # subtle brown cast on black at limb extremities (sun-bleach), like real pandas
        bcol = bcol + np.array(var.get('black_warm', (0.018, 0.010, 0.004))) * smoothstep(0.1, 0.0, P[..., 1:2])
        col = wcol * (1 - black_mask[..., None]) + bcol * black_mask[..., None]

        # nose / mouth / eyes
        nose_c = np.array(var.get('nose_col', (0.045, 0.040, 0.042)))
        col = col * (1 - m['nose'][..., None]) + nose_c * m['nose'][..., None]
        col = col + 0.10 * m['nosehi'][..., None]
        col = col * (1 - 0.75 * m['mouth'][..., None]) + 0.06 * m['mouth'][..., None] * nose_c
        rim_c = np.array(var.get('eye_rim', (0.13, 0.11, 0.10)))
        col = col * (1 - m['eyerim'][..., None]) + rim_c * m['eyerim'][..., None]
        col = col * (1 - m['eye'][..., None]) + np.array(var.get('iris', (0.10, 0.065, 0.04))) * m['eye'][..., None]
        col = col + np.array(var.get('iris_low', (0.0, 0.0, 0.0))) * m['eyelow'][..., None]
        col = col * (1 - m['eyehi'][..., None]) + np.array((0.97, 0.97, 0.95)) * m['eyehi'][..., None]
        col = col * (1 - m['eyehi2'][..., None]) + np.array((0.92, 0.92, 0.95)) * m['eyehi2'][..., None]
        bl = ndimage.gaussian_filter(m['blush'], 2.0)[..., None]
        col = col * (1 - bl) + np.array(var.get('blush_col', (0.93, 0.62, 0.62))) * bl

        # pads on the soles
        sole = r['sole'][..., 0]
        col = col * (1 - 0.35 * sole[..., None])

        # fur stroke detail from the original artwork (high-pass luminance)
        bt = np.array(Image.open(beaver_tex_png).convert('RGB').resize((S, S), Image.BICUBIC)) / 255.0
        lum = bt.mean(2)
        hp = lum - ndimage.gaussian_filter(lum, 5.0)
        hp = hp / (ndimage.gaussian_filter(lum, 5.0) + 0.05)
        hp = np.tanh(hp * 1.5) / 1.5
        amt = var.get('fur_detail', 0.22)
        k = amt * (1 - 0.35 * black_mask) * (1 - m['eye'] - m['eyerim']).clip(0, 1) * (1 - m['nose'])
        col = col * (1 + (hp * k)[..., None])

        # procedural micro-fur so the white reads as fluffy at 2K
        fine = fbm(P * np.array([900, 300, 900]) + N * 40, 2, var.get('seed', 0) + 77)[..., None]
        col = col * (1 + var.get('fluff', 0.035) * fine)
        # dusty, slightly matted belly/underside like real pandas
        dust = var.get('belly_dust', 0.0)
        if dust > 0:
            dz = smoothstep(0.25, 0.02, P[..., 1]) * (1 - black_mask) * (0.6 + 0.4 * np.clip(fbm(P * 30, 3, 9) + 0.5, 0, 1))
            col = col * (1 - dust * dz[..., None] * np.array([1.0, 1.0, 1.08]))

        # ambient-occlusion: panda shape vs beaver AO baked into the material
        if self.beaver_ao is not None:
            pa = ndimage.gaussian_filter(self.ao, 6)
            ba = ndimage.gaussian_filter(self.beaver_ao, 6)
            comp = np.clip((pa + 0.15) / (ba + 0.15), 0.8, 1.25) ** var.get('ao_comp', 0.35)
            col = col * comp[..., None]
        col = col * (0.82 + 0.18 * self.ao[..., None]) ** 0.7
        # optional soot / grime (Iron Teeth)
        soot = var.get('soot', 0.0)
        if soot > 0:
            g = np.clip(fbm(P * 7.0, 4, var.get('seed', 0) + 101) * 1.6 + 0.1, 0, 1)
            g = g * (1 - 0.7 * black_mask)
            col = col * (1 - soot * g[..., None] * np.array([1.0, 1.0, 0.92]))
        col = np.clip(col, 0, 1)
        img = raster.pad(col, self.mask)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(out_png, optimize=True)
        return img
