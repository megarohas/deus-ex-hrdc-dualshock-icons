"""Tiny dependency-free raster toolkit: SDF shapes, compositing, ffmpeg text."""
import math, subprocess, os

W = H = 64
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- canvas ----------
def blank(w=W, h=H): return [[(0,0,0,0)]*w for _ in range(h)]
def clone(px): return [row[:] for row in px]

def paint(px, sdf, color, opacity=1.0, set_alpha=False):
    """Composite `color` where sdf(x,y) < 0, analytically antialiased."""
    h, w = len(px), len(px[0])
    for y in range(h):
        for x in range(w):
            d = sdf(x + 0.5, y + 0.5)
            if d > 0.75: continue
            c = min(1.0, max(0.0, 0.5 - d)) * opacity
            if c <= 0: continue
            r, g, b, a = px[y][x]
            px[y][x] = (round(r + (color[0]-r)*c),
                        round(g + (color[1]-g)*c),
                        round(b + (color[2]-b)*c),
                        max(a, round(255*c)) if set_alpha else a)

# ---------- SDFs (distances in pixels) ----------
def sd_circle(cx, cy, r):
    return lambda x, y: math.hypot(x-cx, y-cy) - r
def sd_ring(cx, cy, r, wdt):
    return lambda x, y: abs(math.hypot(x-cx, y-cy) - r) - wdt/2
def sd_seg(ax, ay, bx, by, wdt):
    dx, dy = bx-ax, by-ay
    L2 = dx*dx + dy*dy or 1e-9
    def f(x, y):
        t = max(0.0, min(1.0, ((x-ax)*dx + (y-ay)*dy) / L2))
        return math.hypot(x-ax-t*dx, y-ay-t*dy) - wdt/2
    return f
def sd_rrect(cx, cy, hw, hh, rad):
    def f(x, y):
        qx, qy = abs(x-cx) - hw + rad, abs(y-cy) - hh + rad
        return (math.hypot(max(qx,0), max(qy,0)) + min(max(qx,qy), 0.0)) - rad
    return f
def outline(sdf, wdt):
    return lambda x, y: abs(sdf(x, y)) - wdt/2
def sd_poly(pts):
    n = len(pts)
    def f(x, y):
        d = 1e9; s = 1.0
        for i in range(n):
            ax, ay = pts[i]; bx, by = pts[(i-1) % n]
            ex, ey = bx-ax, by-ay; wx, wy = x-ax, y-ay
            t = max(0.0, min(1.0, (wx*ex + wy*ey) / (ex*ex + ey*ey or 1e-9)))
            d = min(d, (wx-ex*t)**2 + (wy-ey*t)**2)
            c = (y >= ay, y < by, ex*wy > ey*wx)
            if all(c) or not any(c): s = -s
        return s * math.sqrt(d)
    return f

# ---------- alpha helpers ----------
def alpha_mask(px, thr=8):
    return [[px[y][x][3] > thr for x in range(len(px[0]))] for y in range(len(px))]

def erode(mask, r):
    h, w = len(mask), len(mask[0])
    disc = [(dx,dy) for dy in range(-r,r+1) for dx in range(-r,r+1) if dx*dx+dy*dy <= r*r]
    out = [[False]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if all(0 <= x+dx < w and 0 <= y+dy < h and mask[y+dy][x+dx] for dx,dy in disc):
                out[y][x] = True
    return out

def blank_interior(px, r=5, fill=(0,0,0)):
    """Keep the outer rim/ring exactly; flatten everything inside it to `fill`."""
    out = clone(px)
    inner = erode(alpha_mask(px, 200), r)
    for y in range(len(px)):
        for x in range(len(px[0])):
            if inner[y][x]:
                out[y][x] = (fill[0], fill[1], fill[2], px[y][x][3])
    return out

def ink_bbox(px, base, lum=120):
    """Bounding box of pixels markedly brighter than `base` (i.e. the glyph)."""
    xs, ys = [], []
    for y in range(len(px)):
        for x in range(len(px[0])):
            p = px[y][x]
            if p[3] > 200 and base[y][x] and (p[0]+p[1]+p[2])/3 > lum:
                xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None

# ---------- text via ffmpeg ----------
def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, cwd=HERE)
    if p.returncode: raise RuntimeError(p.stderr.decode('utf8','replace')[-800:])
    return p.stdout

def text_ink(text, font="font_bold.ttf", big=600):
    """Render text huge on transparent canvas; return (pixels,w,h) cropped to ink."""
    cw = ch = big * 2
    vf = (f"drawtext=fontfile={font}:text='{text}':fontsize={big}:"
          f"fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2")
    raw = _run(["ffmpeg","-v","error","-f","lavfi","-i",
                f"color=c=black@0.0:s={cw}x{ch},format=rgba","-vf",vf,
                "-frames:v","1","-f","rawvideo","-pix_fmt","rgba","-"])
    A = [[raw[(y*cw+x)*4+3] for x in range(cw)] for y in range(ch)]
    xs = [x for y in range(ch) for x in range(cw) if A[y][x] > 10]
    ys = [y for y in range(ch) for x in range(cw) if A[y][x] > 10]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    crop = [[A[y][x] for x in range(x0, x1+1)] for y in range(y0, y1+1)]
    return crop, x1-x0+1, y1-y0+1

def resample(a, sw, sh, dw, dh):
    """Area-average downscale of a single-channel image."""
    out = [[0.0]*dw for _ in range(dh)]
    for dy in range(dh):
        sy0, sy1 = dy*sh/dh, (dy+1)*sh/dh
        for dx in range(dw):
            sx0, sx1 = dx*sw/dw, (dx+1)*sw/dw
            tot = wsum = 0.0
            for sy in range(int(sy0), min(sh, int(math.ceil(sy1)))):
                fy = min(sy+1, sy1) - max(sy, sy0)
                if fy <= 0: continue
                for sx in range(int(sx0), min(sw, int(math.ceil(sx1)))):
                    fx = min(sx+1, sx1) - max(sx, sx0)
                    if fx <= 0: continue
                    tot += a[sy][sx]*fx*fy; wsum += fx*fy
            out[dy][dx] = tot/wsum if wsum else 0.0
    return out

def stamp(px, cov, dw, dh, ox, oy, color):
    """Alpha-blend a coverage bitmap onto the canvas at integer offset."""
    for y in range(dh):
        for x in range(dw):
            c = cov[y][x]/255.0
            if c <= 0.002: continue
            X, Y = ox+x, oy+y
            if not (0 <= X < len(px[0]) and 0 <= Y < len(px)): continue
            r, g, b, a = px[Y][X]
            px[Y][X] = (round(r+(color[0]-r)*c), round(g+(color[1]-g)*c),
                        round(b+(color[2]-b)*c), a)

def draw_text(px, text, box, color=(255,255,255), font="font_bold.ttf", fit="height"):
    """Render `text` scaled to fit `box`=(x0,y0,x1,y1), preserving aspect."""
    crop, sw, sh = text_ink(text, font)
    bw, bh = box[2]-box[0]+1, box[3]-box[1]+1
    if fit == "height": dh = bh; dw = max(1, round(sw*dh/sh))
    else:               dw = bw; dh = max(1, round(sh*dw/sw))
    if dw > bw: dw = bw; dh = max(1, round(sh*dw/sw))
    cov = resample(crop, sw, sh, dw, dh)
    ox = box[0] + (bw-dw)//2; oy = box[1] + (bh-dh)//2
    stamp(px, cov, dw, dh, ox, oy, color)
