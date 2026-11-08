"""Offline preview of the v4 shell fur (same shell construction and strand maths as PandaShellFur.shader).
usage: python3 fur_preview.py out.png  spec ...   spec = model|basetex|furmask|pose|x|length|density
"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import os
import numpy as np, bpy
from PIL import Image
import tmesh, render, preview

SHELLS = int(os.environ.get('SHELLS', 8))
THICK = float(os.environ.get('THICK', 0.85))
ROOT = float(os.environ.get('ROOT', 0.45))
TEX = 4096


def frac(x):
    return x - np.floor(x)


def hash21(px, py):
    px = frac(px * 123.34); py = frac(py * 456.21)
    d = px * (px + 45.32) + py * (py + 45.32)
    px = px + d; py = py + d
    return frac(px * py)


CLUMP = float(os.environ.get('CLUMP', 0.55)); CSIZE = float(os.environ.get('CSIZE', 4.5))


def coverage_maps(density, thickness=None, S=TEX, mtex=None):
    """v5: soft anti-aliased strands squeezed into clumps towards the tips (same maths as the shader)."""
    thickness = THICK if thickness is None else thickness
    u = (np.arange(S) + 0.5) / S
    U, Vv = np.meshgrid(u, 1 - u)            # image row 0 = v=1
    g0x, g0y = U * density, Vv * density
    ccx, ccy = np.floor(g0x / CSIZE), np.floor(g0y / CSIZE)
    cjx = hash21(ccx + 3.7, ccy + 3.7) - 0.5
    cjy = hash21(ccx + 9.1, ccy + 9.1) - 0.5
    cenx, ceny = (ccx + 0.5 + cjx * 0.5) * CSIZE, (ccy + 0.5 + cjy * 0.5) * CSIZE
    cvar = 0.6 + 0.8 * hash21(ccx, ccy)
    if mtex is not None:
        cvar = cvar * np.clip(mtex * 1.4 - 0.2, 0, 1)
    maps = []
    for k in range(SHELLS):
        s = (k + 1) / SHELLS
        cl = 1 + CLUMP * s * cvar
        gx, gy = cenx + (g0x - cenx) * cl, ceny + (g0y - ceny) * cl
        pw = density / S * cl
        cx, cy = np.floor(gx), np.floor(gy)
        fx, fy = frac(gx) - 0.5, frac(gy) - 0.5
        h = hash21(cx, cy)
        jx = hash21(cx + 17.0, cy + 17.0) - 0.5
        jy = hash21(cx + 41.0, cy + 41.0) - 0.5
        d = np.hypot(fx - jx * 0.4, fy - jy * 0.4)
        height = 0.6 + 0.4 * h
        radius = thickness * 0.5 * np.clip(1 - s / height, 0, 1) + 0.04
        a = np.clip((radius - d) / pw + 0.5, 0, 1) * (s <= height)
        a = 1 - (1 - a) ** (16.0 / SHELLS)
        maps.append((a * 255).astype(np.uint8))
    return maps


def comb_dirs(P, N):
    maxy = P[:, 1].max()
    sel = P[:, 1] > 0.6 * maxy
    m = P[np.where(sel)[0][np.argmax(P[sel, 2])]]
    away = P - m
    dist = np.linalg.norm(away, axis=1, keepdims=True)
    face = np.clip(1.3 - dist / (0.45 * maxy), 0, 1)
    body = np.array([0, -1, -0.35]); body /= np.linalg.norm(body)
    c = body * (1 - face) + away / np.maximum(dist, 1e-6) * face
    n = N / np.linalg.norm(N, axis=1, keepdims=True)
    c -= n * (c * n).sum(1, keepdims=True)
    return c / np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-6)


def carry(c, n0, n1):
    """rotate c by the shortest arc from n0 to n1"""
    n0 = n0 / np.linalg.norm(n0, axis=1, keepdims=True); n1 = n1 / np.linalg.norm(n1, axis=1, keepdims=True)
    ax = np.cross(n0, n1); w = 1 + (n0 * n1).sum(1)
    q = np.concatenate([ax, w[:, None]], 1); q /= np.linalg.norm(q, axis=1, keepdims=True)
    t = 2 * np.cross(q[:, :3], c)
    r = c + q[:, 3:] * t + np.cross(q[:, :3], t)
    r -= n1 * (r * n1).sum(1, keepdims=True)
    return r


def main():
    out = sys.argv[1]
    specs = [a for a in sys.argv[2:] if not a.startswith('--')]
    opts = dict(a[2:].split('=') for a in sys.argv[2:] if a.startswith('--'))
    render.reset()
    bpy.context.scene.cycles.transparent_max_bounces = 128
    bpy.context.scene.cycles.max_bounces = 128
    E = '/root/w/ext/'
    cache = {}
    for i, sp in enumerate(specs):
        mp, base, mask, pose, x, length, density = sp.split('|')
        length, density, x = float(length), float(density), float(x)
        child = 'Child' in mp
        P, N, uv, tri, anims = preview.decode(tmesh.load(mp))
        p, nr = preview.pose(P, anims, pose)
        nr = N if nr is None else nr
        nrm = E + ('chilkd_normal_1k_rgb.png' if child else 'adult_normal_2k_rgb.png')
        ao = E + 'materials/beavers/common/' + ('child_ao_1k.png' if child else 'adult_ao_2k.png')
        body = render.make_material(f'b{i}', base, nrm, ao)
        render.add_mesh(f'body{i}', p, tri, uv, nr, body, offset=(x, 0, 0))
        if length <= 0:
            continue
        mimg = np.array(Image.open(mask).convert('L')).astype(float) / 255
        Sm = mimg.shape[0]
        mv = mimg[((1 - uv[:, 1]) * Sm).astype(int).clip(0, Sm - 1), (uv[:, 0] * Sm).astype(int).clip(0, Sm - 1)]
        key = (density, mask)
        if key not in cache:
            cache[key] = coverage_maps(density, mtex=np.array(Image.open(mask).convert('L').resize((TEX, TEX), Image.BILINEAR)).astype(float) / 255)
        cov = cache[key]
        btex = np.array(Image.open(base).convert('RGB').resize((TEX, TEX))).astype(float) / 255
        mtex = np.array(Image.open(mask).convert('L').resize((TEX, TEX), Image.BILINEAR)).astype(float) / 255
        n = nr / np.linalg.norm(nr, axis=1, keepdims=True)
        comb = carry(comb_dirs(np.asarray(P), np.asarray(N)), np.asarray(N), n)
        LEAN = float(os.environ.get('LEAN', 0.9))
        for k in range(SHELLS):
            s = (k + 1) / SHELLS
            ln = length * mv
            q = p + n * (s * ln)[:, None] + comb * (s * s * ln * LEAN)[:, None]
            q[:, 1] -= 0.3 * s * s * ln
            keep = (mv[tri] > 0.02).any(1)
            # per-shell RGBA texture: colour with root darkening, alpha = strand coverage * mask
            col = btex * ((1 - ROOT) + (ROOT + 0.06) * s)
            alpha = cov[k].astype(float) / 255 * np.clip(mtex * 10, 0, 1)
            rgba = np.dstack([np.clip(col, 0, 1) * 255, alpha * 255]).astype(np.uint8)
            fn = f'/tmp/fur_{i}_{k}.png'
            Image.fromarray(rgba).save(fn)
            m = bpy.data.materials.new(f'fur{i}_{k}')
            m.use_nodes = True
            nt = m.node_tree
            bsdf = nt.nodes['Principled BSDF']
            bsdf.inputs['Roughness'].default_value = 0.9
            try:
                bsdf.inputs['Specular IOR Level'].default_value = 0.1
            except Exception:
                pass
            uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'uv0'
            t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(fn); t.interpolation = 'Linear'
            nt.links.new(uvn.outputs['UV'], t.inputs['Vector'])
            nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
            nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
            try:
                m.blend_method = 'BLEND'
            except Exception:
                pass
            render.add_mesh(f'fur{i}_{k}', q, tri[keep], uv, n, m, offset=(x, 0, 0))
    render.add_camera(target=(0, 0, float(opts.get('tz', 0.3))), dist=float(opts.get('dist', 1.6)),
                      az=float(opts.get('az', 20)), el=float(opts.get('el', 8)), lens=float(opts.get('lens', 50)))
    render.render(out, int(opts.get('w', 1400)), int(opts.get('h', 700)), int(opts.get('s', 48)))


if __name__ == '__main__':
    main()
