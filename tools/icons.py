"""DS4 replacement art for every Xbox button texture in DXHR DC.

Each builder returns a 64x64 (or smaller) RGBA pixel grid in the visual
language of the original icons (palette sampled from the originals).
ICONS maps texture section id -> (width, height, pixels).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import draw
from draw import (blank, paint, sd_circle, sd_ring, sd_seg, sd_rrect,
                  sd_poly, outline, draw_text)

# Sony glyph colours (PS1..DS4 heritage, tuned for dark faces)
CROSS = (122, 178, 235)
CIRCLE = (235, 97, 97)
SQUARE = (222, 118, 190)
TRIANGLE = (72, 205, 165)
WHITE = (242, 242, 242)
ORANGE = (247, 174, 66)       # game's pressed-orange (#F7AE42)
ORANGE_TXT = (230, 125, 25)   # pressed pill text  (#E67D19)


def mul(c, k):
    return tuple(min(255, max(0, round(v * k))) for v in c)


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- helpers
def vgrad(px, sdf, top, bot, y0, y1, opacity=1.0):
    """Fill sdf<0 with a vertical gradient."""
    h, w = len(px), len(px[0])
    for y in range(h):
        t = min(1.0, max(0.0, (y - y0) / max(1, (y1 - y0))))
        col = mix(top, bot, t)
        row_sdf = lambda x, yy, yy_fix=y: sdf(x, yy)
        for x in range(w):
            d = sdf(x + 0.5, y + 0.5)
            if d > 0.75:
                continue
            c = min(1.0, max(0.0, 0.5 - d)) * opacity
            if c <= 0:
                continue
            r, g, b, a = px[y][x]
            px[y][x] = (round(r + (col[0] - r) * c),
                        round(g + (col[1] - g) * c),
                        round(b + (col[2] - b) * c),
                        max(a, round(255 * c)))
    return px


def glyph_sdf(shape, cx, cy, r):
    """SDF of a PS glyph stroke centreline (distance to the line work)."""
    if shape == "cross":
        a = r * 0.72
        s1 = sd_seg(cx - a, cy - a, cx + a, cy + a, 0)
        s2 = sd_seg(cx - a, cy + a, cx + a, cy - a, 0)
        return lambda x, y: min(s1(x, y), s2(x, y))
    if shape == "circle":
        return lambda x, y: abs(math.hypot(x - cx, y - cy) - r * 0.80)
    if shape == "square":
        a = r * 0.70
        rr = sd_rrect(cx, cy, a, a, 1.5)
        return lambda x, y: abs(rr(x, y))
    if shape == "triangle":
        a = r * 0.92
        h_up = a * 0.90
        pts = [(cx, cy - h_up), (cx + a * 0.95, cy + a * 0.62),
               (cx - a * 0.95, cy + a * 0.62)]
        pg = sd_poly(pts)
        return lambda x, y: abs(pg(x, y))
    raise ValueError(shape)


def stroke(px, sdf, width, color, opacity=1.0, set_alpha=False):
    paint(px, lambda x, y: sdf(x, y) - width / 2.0, color, opacity,
          set_alpha)


# ---------------------------------------------------------------- families
def face_button(shape, state="normal"):
    """64x64 round button. state: normal | lit | dark"""
    col = {"cross": CROSS, "circle": CIRCLE, "square": SQUARE,
           "triangle": TRIANGLE}[shape]
    px = blank(64, 64)
    # outer dark ring (bezel)
    paint(px, sd_circle(32, 32, 30.0), (13, 13, 13), 1.0, True)
    paint(px, sd_ring(32, 32, 29.0, 2.6), (30, 30, 30), 1.0, True)
    # face sphere
    if state == "lit":
        top, bot = mix(mul(col, 0.55), (40, 40, 40), 0.25), mul(col, 0.28)
    elif state == "dark":
        top, bot = (30, 31, 34), (12, 12, 14)
    else:
        top, bot = (52, 53, 58), (18, 18, 21)
    vgrad(px, sd_circle(32, 32, 26.8), top, bot, 7, 58)
    # glossy top highlight (ellipse-ish band)
    gloss = sd_circle(32, 14, 26.0)
    face = sd_circle(32, 32, 26.8)
    hi = lambda x, y: max(gloss(x, y), face(x, y))
    paint(px, hi, mix(top, (255, 255, 255), 0.28), 0.35)
    # glyph shadow + stroke
    g = glyph_sdf(shape, 32, 33, 15.5)
    gs = {"normal": col, "lit": (250, 250, 250),
          "dark": mix(col, (140, 140, 140), 0.55)}[state]
    stroke(px, lambda x, y: g(x, y - 1.4), 4.6, (0, 0, 0), 0.55)
    stroke(px, g, 4.4, gs)
    if state != "dark":
        stroke(px, g, 2.0, mix(gs, (255, 255, 255), 0.35))
    return 64, 64, px


def circled_glyph(shape, size, ring_col, glyph_col, dark_bg=False):
    px = blank(size, size)
    c = size / 2.0
    r = c - size * 0.08
    if dark_bg:
        paint(px, sd_circle(c, c, r), (16, 16, 16), 1.0, True)
    paint(px, sd_ring(c, c, r - size * 0.02, max(2.0, size * 0.055)),
          ring_col, 1.0, True)
    g = glyph_sdf(shape, c, c + size * 0.01, r * 0.52)
    stroke(px, g, max(2.2, size * 0.075), glyph_col, 1.0, True)
    return size, size, px


def pill_text(text, hi=False):
    """BACK/START style: silver stadium + label."""
    px = blank(64, 64)
    body = sd_rrect(32, 32, 27, 14.5, 14.0)
    paint(px, lambda x, y: body(x, y) + 0.0, (30, 30, 30), 1.0, True)
    top, bot = ((196, 197, 196), (110, 110, 112)) if not hi else \
               ((160, 161, 160), (96, 96, 98))
    vgrad(px, sd_rrect(32, 32, 25.6, 13.2, 12.8), top, bot, 18, 46)
    paint(px, sd_rrect(32, 26.2, 23.5, 6.2, 6.0),
          mix(top, (255, 255, 255), 0.55), 0.5)
    color = ORANGE_TXT if hi else (38, 38, 38)
    n = len(text)
    hw = min(23, 3.4 * n)
    draw_text(px, text, (round(32 - hw), 27, round(32 + hw), 38), color)
    return 64, 64, px


def bumper(text, hi=False, boxy=False):
    """LB/RB style: silver pill (or box) + big label."""
    px = blank(64, 64)
    r = 7.0 if boxy else 12.5
    paint(px, sd_rrect(32, 32, 27.5, 13.5, r), (26, 26, 26), 1.0, True)
    top, bot = ((252, 252, 252), (58, 57, 58)) if not hi else \
               ((150, 152, 155), (49, 49, 49))
    vgrad(px, sd_rrect(32, 32, 26, 12.2, max(5.5, r - 1.5)), top, bot,
          20, 45)
    color = ORANGE_TXT if hi else (34, 34, 34)
    draw_text(px, text, (20, 25, 44, 40), color)
    return 64, 64, px


def trigger(text, side="l", tint=None, text_col=None):
    """LT/RT angular trigger silhouette + label. side: l|r"""
    px = blank(64, 64)
    body = sd_rrect(32, 30, 24, 22, 9.0)
    cutx = 62 if side == "l" else 2
    cut = sd_circle(cutx, 62, 26.0)
    shape = lambda x, y: max(body(x, y), -(cut(x, y)))
    paint(px, shape, (30, 30, 30), 1.0, True)
    inner_body = sd_rrect(32, 30, 22.6, 20.6, 7.8)
    cut2 = sd_circle(cutx, 62, 27.6)
    inner = lambda x, y: max(inner_body(x, y), -(cut2(x, y)))
    top, bot = (252, 252, 252), (128, 130, 128)
    if tint:
        top, bot = mix(top, tint, 0.25), mix(bot, tint, 0.35)
    vgrad(px, inner, top, bot, 10, 52)
    tc = text_col or (40, 40, 40)
    tx = 30 if side == "l" else 34
    draw_text(px, text, (tx - 11, 20, tx + 11, 36), tc)
    return 64, 64, px


def dark_circle(text):
    px = blank(64, 64)
    paint(px, sd_circle(32, 32, 29.0), (16, 16, 16), 1.0, True)
    paint(px, sd_ring(32, 32, 27.8, 2.2), (36, 36, 36), 1.0, True)
    draw_text(px, text, (17, 22, 47, 42), (198, 199, 198))
    return 64, 64, px


def stick3(text, tan=False):
    """LS/RS -> L3/R3 stick-top disc with screws."""
    px = blank(64, 64)
    paint(px, sd_circle(32, 33, 27.0), (20, 20, 20), 1.0, True)
    if tan:
        top, bot = (181, 164, 140), (99, 82, 56)
        tc = (46, 36, 20)
        screw = (74, 60, 38)
    else:
        top, bot = (123, 121, 123), (58, 57, 58)
        tc = (222, 222, 222)
        screw = (40, 40, 40)
    vgrad(px, sd_circle(32, 33, 25.4), top, bot, 9, 57)
    for ang in (45, 135, 225, 315):
        sx = 32 + 19.5 * math.cos(math.radians(ang))
        sy = 33 + 19.5 * math.sin(math.radians(ang))
        paint(px, sd_circle(sx, sy, 2.4), screw, 0.9)
    draw_text(px, text, (20, 24, 44, 41), tc)
    return 64, 64, px


# ---------------------------------------------------------------- dpad
def _wedge(cx, cy, hw, hh, r):
    return sd_rrect(cx, cy, hw, hh, r)


def dpad(white=(), orange=()):
    """DS4-style split dpad. white/orange: subset of n,s,w,e."""
    px = blank(64, 64)
    keys = {
        "n": (32, 17, 9.5, 13.5),
        "s": (32, 47, 9.5, 13.5),
        "w": (17, 32, 13.5, 9.5),
        "e": (47, 32, 13.5, 9.5),
    }
    arrows = {
        "n": [(32, 9), (27.4, 16.4), (36.6, 16.4)],
        "s": [(32, 55), (27.4, 47.6), (36.6, 47.6)],
        "w": [(9, 32), (16.4, 27.4), (16.4, 36.6)],
        "e": [(55, 32), (47.6, 27.4), (47.6, 36.6)],
    }
    for k, (cx, cy, hw, hh) in keys.items():
        body = _wedge(cx, cy, hw, hh, 5.0)
        paint(px, body, (14, 14, 14), 1.0, True)
        inner = _wedge(cx, cy, hw - 1.4, hh - 1.4, 4.0)
        vgrad(px, inner, (66, 66, 68), (34, 34, 36), cy - hh, cy + hh)
        if k in orange:
            ac = ORANGE
        elif k in white:
            ac = (242, 242, 242)
        else:
            ac = (110, 110, 112)
        paint(px, sd_poly(arrows[k]), ac, 1.0)
    return 64, 64, px


# ---------------------------------------------------------------- labels
def text_label(text, w, h, color=(240, 240, 240)):
    px = blank(w, h)
    m = max(2, h // 6)
    draw_text(px, text, (m, m, w - m, h - m), color)
    # give the letters real alpha (draw_text blends rgb only)
    return w, h, px


def text_label_alpha(text, w, h, color=(240, 240, 240)):
    """Text stamped with alpha (transparent background)."""
    crop, sw, sh = draw.text_ink(text, "font_bold.ttf")
    dh = h - max(3, h // 5)
    dw = max(1, round(sw * dh / sh))
    if dw > w - 4:
        dw = w - 4
        dh = max(1, round(sh * dw / sw))
    cov = draw.resample(crop, sw, sh, dw, dh)
    px = blank(w, h)
    ox, oy = (w - dw) // 2, (h - dh) // 2
    for y in range(dh):
        for x in range(dw):
            c = cov[y][x] / 255.0
            if c <= 0.02:
                continue
            px[oy + y][ox + x] = (color[0], color[1], color[2],
                                  round(255 * c))
    return w, h, px


def badge(text, w, h, color=(235, 235, 235)):
    """Outlined rounded box + label (missionlog/map trigger badges)."""
    px = blank(w, h)
    paint(px, outline(sd_rrect(w / 2, h / 2, w / 2 - 2.5, h / 2 - 2.5,
                               min(5.0, h / 4)), 1.6), color, 1.0, True)
    _, _, tpx = text_label_alpha(text, w, h - 2, color)
    for y in range(h - 2):
        for x in range(w):
            r, g, b, a = tpx[y][x]
            if a:
                px[y + 1][x] = (r, g, b, a)
    return w, h, px


# ---------------------------------------------------------------- table
BAND = (12, 21, 52, 43)     # letters live in this middle band (64x64)
STICK_ROI = (17, 21, 47, 44)
PILL_BOX = (12, 27, 52, 38)  # SHARE/OPTIONS label box on the oval pill


def build_all(orig=None):
    """orig: dict id -> (w, h, pixels) of the ORIGINAL textures.

    When given, the silver/dark hardware buttons keep their authored art
    and only get relabelled; without it everything is procedural.
    """
    import retex
    icons = {}

    def reuse(sid, text, kind, box=None, roi=BAND, grow=1.0, color=None):
        if orig and sid in orig:
            w, h, px = orig[sid]
            return retex.relabel(px, text, kind, box=box, roi=roi,
                                 grow=grow, color=color)
        return None

    # face buttons: A->cross B->circle X->square Y->triangle
    icons[0x5D0] = face_button("cross")
    icons[0x1091] = face_button("cross", "lit")
    icons[0x5D1] = face_button("circle")
    icons[0x1092] = face_button("circle", "lit")
    icons[0x5E0] = face_button("square")
    icons[0x10B0] = face_button("square", "dark")
    icons[0x5E1] = face_button("triangle")
    icons[0x10B1] = face_button("triangle", "dark")
    # start/back -> OPTIONS/SHARE (reuse pill, swap arrow for text)
    ARROW_ROI = (13, 22, 51, 43)

    def pill(sid, text, hi):
        if orig and sid in orig:
            w, h, px = orig[sid]
            col = (238, 162, 49) if hi else (48, 48, 50)
            return retex.relabel(px, text, "box", box=PILL_BOX,
                                 roi=ARROW_ROI, color=col)
        return pill_text(text, hi=hi)

    icons[0x5D2] = pill(0x5D2, "SHARE", False)
    icons[0x1093] = pill(0x1093, "SHARE", True)
    icons[0x5DF] = pill(0x5DF, "OPTIONS", False)
    icons[0x10AF] = pill(0x10AF, "OPTIONS", True)
    # dpad (intentionally redrawn DS4-style)
    icons[0x5D3] = dpad()
    icons[0x5D4] = dpad(white=("s",))
    icons[0x5D5] = dpad(white=("w", "e"))
    icons[0x5D6] = dpad(white=("w",))
    icons[0x5D7] = dpad(white=("e",))
    icons[0x5D8] = dpad(white=("n",))
    icons[0x5D9] = dpad(white=("n", "s"))
    icons[0x1094] = dpad(orange=("s",))
    icons[0x1095] = dpad(orange=("w",))
    icons[0x1096] = dpad(orange=("e",))
    icons[0x1097] = dpad(orange=("n",))
    # bumpers
    icons[0x1098] = reuse(0x1098, "L1", "dark") or bumper("L1")
    icons[0x1099] = reuse(0x1099, "L1", "orange") or bumper("L1", hi=True)
    icons[0x109A] = reuse(0x109A, "L1", "light") or dark_circle("L1")
    icons[0x5DC] = reuse(0x5DC, "R1", "dark") or bumper("R1", boxy=True)
    icons[0x10A4] = reuse(0x10A4, "R1", "orange") or bumper("R1")
    # 10A5 is the RB *dark circle* variant (white letters on black)
    icons[0x10A5] = reuse(0x10A5, "R1", "light", color=(226, 227, 226)) \
        or dark_circle("R1")
    # triggers (fixed label boxes: LT letters sit right of the curl,
    # RT letters mirrored)
    TBOX_L = (26, 22, 50, 40)
    TBOX_R = (14, 22, 38, 40)
    icons[0x5DB] = reuse(0x5DB, "L2", "dark", box=TBOX_L) or \
        trigger("L2", "l")
    icons[0x10A2] = reuse(0x10A2, "L2", "orange", box=TBOX_L,
                          color=(244, 168, 52)) or \
        trigger("L2", "l", text_col=ORANGE_TXT)
    icons[0x10A3] = reuse(0x10A3, "L2", "light") or dark_circle("L2")
    icons[0x5DE] = reuse(0x5DE, "R2", "dark", box=TBOX_R) or \
        trigger("R2", "r")
    icons[0x10AD] = reuse(0x10AD, "R2", "orange", box=TBOX_R,
                          color=(244, 168, 52)) or \
        trigger("R2", "r", text_col=ORANGE_TXT)
    # 10AE is the RT *dark circle* variant (white letters on black)
    icons[0x10AE] = reuse(0x10AE, "R2", "light", color=(226, 227, 226)) \
        or dark_circle("R2")
    # stick clicks
    icons[0x109B] = reuse(0x109B, "L3", "darker", roi=STICK_ROI) or \
        stick3("L3")
    icons[0x109C] = reuse(0x109C, "L3", "dark", roi=STICK_ROI) or \
        stick3("L3", tan=True)
    icons[0x10A6] = reuse(0x10A6, "R3", "darker", roi=STICK_ROI) or \
        stick3("R3")
    icons[0x10A7] = reuse(0x10A7, "R3", "dark", roi=STICK_ROI) or \
        stick3("R3", tan=True)
    # circled glyphs
    icons[0x10BC] = circled_glyph("cross", 64, (178, 179, 178),
                                  (255, 255, 255))
    icons[0x10B9] = circled_glyph("cross", 32, (205, 205, 205),
                                  (255, 255, 255))
    icons[0x10BE] = circled_glyph("square", 32, (205, 205, 205),
                                  (255, 255, 255))
    icons[0x26B9] = circled_glyph("cross", 32, (16, 16, 16), (16, 16, 16))
    icons[0x26BA] = circled_glyph("circle", 32, (16, 16, 16), (16, 16, 16))
    # text labels / badges
    icons[0x25C6] = text_label_alpha("L2", 32, 32)
    icons[0x25C7] = text_label_alpha("R2", 32, 32)
    icons[0x25CE] = badge("L2", 32, 16)
    icons[0x25CF] = badge("R2", 32, 16)
    icons[0x25D7] = badge("L2", 64, 32)
    return icons


if __name__ == "__main__":
    import dxhr
    out = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "work", "png", "new")
    os.makedirs(out, exist_ok=True)
    for sid, (w, h, px) in sorted(build_all().items()):
        # composite on checkerboard for eyeballing
        vis = []
        for y in range(h):
            row = []
            for x in range(w):
                r, g, b, a = px[y][x]
                bg = 40 + 20 * (((x // 8) + (y // 8)) & 1)
                k = a / 255.0
                row.append((round(bg + (r - bg) * k),
                            round(bg + (g - bg) * k),
                            round(bg + (b - bg) * k), 255))
            vis.append(row)
        dxhr.write_png(os.path.join(out, "%08X.png" % sid), vis)
        print("drew %08X %dx%d" % (sid, w, h))
