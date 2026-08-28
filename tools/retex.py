"""Erase the label on an original icon and write a new one in its place.

Keeps the authored shape/gloss pixels; only the letters change. The erase
is a per-row linear inpaint between the nearest clean neighbours.
"""
import draw


def lum(p):
    return (p[0] * 3 + p[1] * 6 + p[2]) / 10.0


def clone(px):
    return [row[:] for row in px]


def _roi(w, h):
    return (int(w * 0.17), int(h * 0.22), int(w * 0.84), int(h * 0.80))


def erase_mask(px, kind, roi=None, erode_r=2):
    h, w = len(px), len(px[0])
    x0, y0, x1, y1 = roi or _roi(w, h)
    base = draw.alpha_mask(px, 200)
    inner = draw.erode(base, erode_r)
    mask = [[False] * w for _ in range(h)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not inner[y][x]:
                continue
            r, g, b, a = px[y][x]
            L = lum((r, g, b))
            if kind == "dark":
                hit = L < 112
            elif kind == "light":
                hit = L > 150
            elif kind == "darker":
                hit = L < 84
            elif kind == "orange":
                hit = (r > 140 and 50 < g < 215 and b < 115
                       and r - b > 60)
            elif kind == "box":
                hit = True
            else:
                raise ValueError(kind)
            mask[y][x] = hit
    # dilate by 1 for AA fringe
    out = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and inner[yy][xx]:
                            out[yy][xx] = True
    return out


def sample_color(px, mask):
    rs, gs, bs = [], [], []
    for y in range(len(px)):
        for x in range(len(px[0])):
            if mask[y][x]:
                r, g, b, a = px[y][x]
                rs.append(r)
                gs.append(g)
                bs.append(b)
    if not rs:
        return (40, 40, 40)
    rs.sort(), gs.sort(), bs.sort()
    m = len(rs) // 2
    return (rs[m], gs[m], bs[m])


def mask_bbox(mask):
    xs = [x for y in range(len(mask)) for x in range(len(mask[0]))
          if mask[y][x]]
    ys = [y for y in range(len(mask)) for x in range(len(mask[0]))
          if mask[y][x]]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def inpaint_h(px, mask):
    h, w = len(px), len(px[0])
    for y in range(h):
        x = 0
        while x < w:
            if not mask[y][x]:
                x += 1
                continue
            run0 = x
            while x < w and mask[y][x]:
                x += 1
            run1 = x  # exclusive
            lcol = px[y][run0 - 1] if run0 > 0 and not mask[y][run0 - 1] \
                else None
            rcol = px[y][run1] if run1 < w and not mask[y][run1] else None
            if lcol is None and rcol is None:
                continue
            if lcol is None:
                lcol = rcol
            if rcol is None:
                rcol = lcol
            n = run1 - run0 + 1
            for i in range(run0, run1):
                t = (i - run0 + 1) / n
                px[y][i] = tuple(
                    round(lcol[k] + (rcol[k] - lcol[k]) * t)
                    for k in range(4))
    return px


def stamp_ink(px, text, box, color):
    """Rasterise `text` into box as real alpha ink (transparent canvas)."""
    crop, sw, sh = draw.text_ink(text, "font_bold.ttf")
    bw, bh = box[2] - box[0] + 1, box[3] - box[1] + 1
    dh = bh
    dw = max(1, round(sw * dh / sh))
    if dw > bw:
        dw = bw
        dh = max(1, round(sh * dw / sw))
    cov = draw.resample(crop, sw, sh, dw, dh)
    ox = box[0] + (bw - dw) // 2
    oy = box[1] + (bh - dh) // 2
    for y in range(dh):
        for x in range(dw):
            c = cov[y][x] / 255.0
            if c <= 0.02:
                continue
            X, Y = ox + x, oy + y
            if not (0 <= X < len(px[0]) and 0 <= Y < len(px)):
                continue
            r, g, b, a = px[Y][X]
            na = round(255 * c)
            if na >= a:
                px[Y][X] = (color[0], color[1], color[2], max(a, na))


def swap_ink(orig, text, interior, color=None, box=None):
    """For alpha-ink textures (labels/badges): keep everything outside
    `interior`, wipe the ink inside it, stamp `text` into the old bbox."""
    px = clone(orig)
    x0, y0, x1, y1 = interior
    xs, ys, rs, gs, bs = [], [], [], [], []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b, a = px[y][x]
            if a > 40:
                xs.append(x)
                ys.append(y)
                if a > 160:
                    rs.append(r)
                    gs.append(g)
                    bs.append(b)
                px[y][x] = (0, 0, 0, 0)
    if box is None:
        box = (min(xs), min(ys), max(xs), max(ys)) if xs else interior
    if color is None:
        if rs:
            rs.sort(), gs.sort(), bs.sort()
            m = len(rs) // 2
            color = (rs[m], gs[m], bs[m])
        else:
            color = (240, 240, 240)
    stamp_ink(px, text, box, color)
    return len(px[0]), len(px), px


def relabel(orig, text, kind, box=None, color=None, grow=1.0, roi=None,
            erode_r=2):
    """Return a copy of `orig` with its label replaced by `text`."""
    px = clone(orig)
    mask = erase_mask(px, kind, roi, erode_r)
    bbox = mask_bbox(mask)
    col = color or sample_color(px, mask)
    inpaint_h(px, mask)
    if box is None:
        if bbox is None:
            h, w = len(px), len(px[0])
            box = (w // 4, h // 3, 3 * w // 4, 2 * h // 3)
        else:
            x0, y0, x1, y1 = bbox
            cy = (y0 + y1) / 2
            hh = (y1 - y0 + 1) * grow / 2
            box = (max(2, x0 - 2), round(cy - hh), min(len(px[0]) - 3,
                   x1 + 2), round(cy + hh))
    draw.draw_text(px, text, box, col)
    return len(px[0]), len(px), px
