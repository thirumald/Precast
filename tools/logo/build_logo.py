# Rebuilds docs/brand/presight-logo*.svg from a raster logo: layered potrace tracing + analytic conic-gradient ring.
# Usage: python tools/logo/build_logo.py  (expects the source PNG path below; needs potracer, opencv-python, fonttools, pillow)
import math, sys, numpy as np, potrace
from PIL import Image

S = 12  # supersampling factor for tracing
SRC = sys.argv[1] if len(sys.argv) > 1 else 'presight-source.png'
OUT = sys.argv[2] if len(sys.argv) > 2 else '.'
im = Image.open(SRC).convert('RGBA')
bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
W, H = im.size
big = np.asarray(bg.convert('RGB').resize((W * S, H * S), Image.LANCZOS)).astype(float)
small = np.asarray(bg.convert('RGB')).astype(float)
L = big.mean(2)
mx, mn = big.max(2), big.min(2)
sat = (mx - mn) / np.maximum(mx, 1)
yy, xx = np.mgrid[0:H * S, 0:W * S] / S

LIGHT, DARK = 151, 89
# Ring geometry (fitted below from the saturated pixels)
ys, xs = np.where((sat > 0.3) & ((255 - L) > 50))
cx, cy = xs.mean() / S, ys.mean() / S
r = np.hypot(xs / S - cx, ys / S - cy)
r_out, r_in = np.percentile(r, 97), np.percentile(r, 3)

import cv2
def cov(color):
    c = np.clip((255 - L) / (255 - color), 0, 1).astype(np.float32)
    return cv2.GaussianBlur(c, (0, 0), S * 0.45)  # removes pixel-stair artefacts from the low-res source

def trace(mask):
    bm = potrace.Bitmap(~mask)  # potracer treats False as ink
    path = bm.trace(turdsize=20 * S, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.15, opticurve=True, opttolerance=0.5)
    d = []
    f = lambda p: f"{p.x / S:.2f},{p.y / S:.2f}"
    for c in path:
        d.append("M" + f(c.start_point))
        for seg in c.segments:
            if seg.is_corner:
                d.append("L" + f(seg.c) + "L" + f(seg.end_point))
            else:
                d.append("C" + f(seg.c1) + " " + f(seg.c2) + " " + f(seg.end_point))
        d.append("Z")
    return "".join(d)

ring_zone = np.hypot(xx - cx, yy - cy) < r_out + 0.9
# tagline zone: under "pre"/"s", right of p's descender
tag_zone = (yy > 62.5) & (xx > 36) & (xx < 143)
light_mask = (cov(LIGHT) > 0.5) & (xx < 103.5) & ~tag_zone
dark_mask = (cov(DARK) > 0.5) & (xx >= 103.5) & ~tag_zone & ~(ring_zone & (sat > 0.18))
# the ring itself is drawn analytically, so remove the coloured annulus from the dark layer
dark_mask &= ~((np.hypot(xx - cx, yy - cy) > r_in - 0.3) & (np.hypot(xx - cx, yy - cy) < r_out + 0.3) & (yy < cy + 2))
light_d, dark_d = trace(light_mask), trace(dark_mask)

# conic gradient sampled from the source, angle measured counter-clockwise from +x
stops = {}
sy, sx = np.where(((small.max(2) - small.min(2)) / np.maximum(small.max(2), 1) > 0.3) & (small.mean(2) < 225))
for ang in range(0, 360, 15):
    pts = [small[y, x] for x, y in zip(sx, sy)
           if abs(((math.degrees(math.atan2(-(y + .5 - cy), x + .5 - cx)) - ang + 180) % 360) - 180) < 9
           and 0.85 * r_in < math.hypot(x + .5 - cx, y + .5 - cy) < 1.1 * r_out]
    if pts:
        c = np.array(pts)
        # take the most saturated half: antialiased edge pixels are washed out
        s = (c.max(1) - c.min(1)); c = c[s >= np.median(s)]
        stops[ang] = c.mean(0)
angs = sorted(stops)
def col(a):
    a %= 360
    for i, a0 in enumerate(angs):
        a1 = angs[(i + 1) % len(angs)]; span = (a1 - a0) % 360 or 360
        if (a - a0) % 360 <= span:
            t = ((a - a0) % 360) / span
            c = stops[a0] * (1 - t) + stops[a1] * t
            return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)
N = 120
ring = []
for i in range(N):
    a0, a1 = 360 * i / N, 360 * (i + 1) / N + 0.6  # slight overlap hides seams
    def pt(r, a): return f"{cx + r * math.cos(math.radians(a)):.3f},{cy - r * math.sin(math.radians(a)):.3f}"
    ring.append(f'<path fill="{col((a0 + a1) / 2)}" d="M{pt(r_out, a0)}A{r_out:.3f},{r_out:.3f} 0 0 0 {pt(r_out, a1)}L{pt(r_in, a1)}A{r_in:.3f},{r_in:.3f} 0 0 1 {pt(r_in, a0)}Z"/>')

x0, y0, x1, y1 = 11, 9, 263, 80
vb = f"{x0} {y0} {x1 - x0} {y1 - y0}"
def svg(light, dark, title="Presight"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-labelledby="t">
<title id="t">{title}</title>
<path fill="{light}" fill-rule="evenodd" d="{light_d}"/>
<path fill="{dark}" fill-rule="evenodd" d="{dark_d}"/>
<g>{''.join(ring)}</g>
</svg>
'''
open(f'{OUT}/presight-logo.svg', 'w').write(svg("#97989C", "#58595B"))
# reversed version for dark backgrounds
open(f'{OUT}/presight-logo-white.svg', 'w').write(svg("#C9CDD0", "#FFFFFF"))
print("ring", round(cx, 2), round(cy, 2), round(r_in, 2), round(r_out, 2))
print({a: tuple(int(v) for v in c) for a, c in stops.items()})
