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
        hw = r * 0.80
        hh = r * 0.69
        pts = [(cx, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
        pg = sd_poly(pts)
        return lambda x, y: abs(pg(x, y))
    raise ValueError(shape)


def stroke(px, sdf, width, color, opacity=1.0, set_alpha=False):
    paint(px, lambda x, y: sdf(x, y) - width / 2.0, color, opacity,
          set_alpha)


# ---------------------------------------------------------------- families
def face_button(shape, state="normal"):
    """64x64 round button. state: normal | pressed.

    Pressed = the same neutral dark button, only darker with a top inner
    shadow; the glyph keeps its Sony colour, just dimmed."""
    col = {"cross": CROSS, "circle": CIRCLE, "square": SQUARE,
           "triangle": TRIANGLE}[shape]
    px = blank(64, 64)
    # outer dark ring (bezel)
    paint(px, sd_circle(32, 32, 30.0), (13, 13, 13), 1.0, True)
    paint(px, sd_ring(32, 32, 29.0, 2.6), (30, 30, 30), 1.0, True)
    # face sphere
    if state == "pressed":
        top, bot = (27, 27, 30), (10, 10, 12)
    else:
        top, bot = (52, 53, 58), (18, 18, 21)
    face = sd_circle(32, 32, 26.8)
    vgrad(px, face, top, bot, 7, 58)
    if state == "pressed":
        # pressed-in look: soft shadow hanging from the top rim
        for y in range(7, 24):
            k = 1.0 - 0.42 * (24 - y) / 17.0
            for x in range(64):
                if face(x + 0.5, y + 0.5) < 0:
                    r, g, b, a = px[y][x]
                    px[y][x] = (round(r * k), round(g * k),
                                round(b * k), a)
    else:
        # glossy top highlight (ellipse-ish band)
        gloss = sd_circle(32, 14, 26.0)
        hi = lambda x, y: max(gloss(x, y), face(x, y))
        paint(px, hi, mix(top, (255, 255, 255), 0.28), 0.35)
    # glyph shadow + stroke (dead centre of the sphere)
    g = glyph_sdf(shape, 32, 32, 15.5)
    gs = mul(col, 0.74) if state == "pressed" else col
    stroke(px, lambda x, y: g(x, y - 1.0), 4.6, (0, 0, 0),
           0.35 if state == "pressed" else 0.5)
    stroke(px, g, 4.4, gs)
    if state == "normal":
        stroke(px, g, 2.0, mix(gs, (255, 255, 255), 0.35))
    return 64, 64, px


def circled_glyph(shape, size, ring_col, glyph_col, center=None,
                  ring_r=None, ring_w=None, fill=None, glyph_r=None,
                  stroke_w=None):
    """Ring + PS glyph, geometry matched to the original it replaces."""
    px = blank(size, size)
    cx, cy = center or (size / 2.0 - 0.5, size / 2.0 - 0.5)
    rr = ring_r if ring_r is not None else (size / 2.0 - size * 0.10)
    rw = ring_w if ring_w is not None else max(2.0, size * 0.055)
    if fill:
        paint(px, sd_circle(cx, cy, rr + rw / 2.0 - 0.4), fill, 1.0, True)
    paint(px, sd_ring(cx, cy, rr, rw), ring_col, 1.0, True)
    g = glyph_sdf(shape, cx, cy, glyph_r if glyph_r is not None
                  else rr * 0.70)
    stroke(px, g, stroke_w or max(2.2, size * 0.075), glyph_col, 1.0,
           True)
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
def dpad(white=(), orange=()):
    """DS4-style split dpad: four wedge keys tapering to the centre,
    clearly separated (no overlap). white/orange: subset of n,s,w,e."""
    px = blank(64, 64)
    keys = {
        "n": [(23.5, 4), (40.5, 4), (40.5, 20), (32, 26.5), (23.5, 20)],
        "s": [(23.5, 60), (40.5, 60), (40.5, 44), (32, 37.5),
              (23.5, 44)],
        "w": [(4, 23.5), (20, 23.5), (26.5, 32), (20, 40.5), (4, 40.5)],
        "e": [(60, 23.5), (44, 23.5), (37.5, 32), (44, 40.5),
              (60, 40.5)],
    }
    arrows = {
        "n": [(32, 9.5), (27.8, 16), (36.2, 16)],
        "s": [(32, 54.5), (27.8, 48), (36.2, 48)],
        "w": [(9.5, 32), (16, 27.8), (16, 36.2)],
        "e": [(54.5, 32), (48, 27.8), (48, 36.2)],
    }
    for k, pts in keys.items():
        body = sd_poly(pts)
        ys = [p[1] for p in pts]
        paint(px, lambda x, y, b=body: b(x, y) - 1.6, (12, 12, 12), 1.0,
              True)
        vgrad(px, lambda x, y, b=body: b(x, y) - 0.3, (64, 64, 66),
              (33, 33, 35), min(ys), max(ys))
        if k in orange:
            ac = ORANGE
        elif k in white:
            ac = (242, 242, 242)
        else:
            ac = (108, 108, 110)
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

    def reuse(sid, text, kind, box=None, roi=BAND, grow=1.0, color=None,
              circle=None, inpaint="h"):
        if orig and sid in orig:
            w, h, px = orig[sid]
            return retex.relabel(px, text, kind, box=box, roi=roi,
                                 grow=grow, color=color, circle=circle,
                                 inpaint=inpaint)
        return None

    # face buttons: A->cross B->circle X->square Y->triangle
    # (1091/1092/10B0/10B1 are the pressed states of the same buttons)
    icons[0x5D0] = face_button("cross")
    icons[0x1091] = face_button("cross", "pressed")
    icons[0x5D1] = face_button("circle")
    icons[0x1092] = face_button("circle", "pressed")
    icons[0x5E0] = face_button("square")
    icons[0x10B0] = face_button("square", "pressed")
    icons[0x5E1] = face_button("triangle")
    icons[0x10B1] = face_button("triangle", "pressed")
    # start/back -> OPTIONS/SHARE (reuse pill, swap arrow for text);
    # the ROI reaches the arrow's very top/bottom rows so no smudge stays
    ARROW_ROI = (13, 19, 51, 46)

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
    # bumpers — label boxes sized to the original letters (~15px tall);
    # all four dark circles share one box and the original grey
    BBOX = (20, 25, 44, 39)
    DCBOX = (17, 22, 47, 41)
    DCGREY = (189, 190, 189)
    icons[0x1098] = reuse(0x1098, "L1", "dark", box=BBOX) or bumper("L1")
    icons[0x1099] = reuse(0x1099, "L1", "orange", box=BBOX) or \
        bumper("L1", hi=True)
    icons[0x109A] = reuse(0x109A, "L1", "light", box=DCBOX,
                          color=DCGREY) or dark_circle("L1")
    icons[0x5DC] = reuse(0x5DC, "R1", "dark", box=BBOX) or \
        bumper("R1", boxy=True)
    icons[0x10A4] = reuse(0x10A4, "R1", "orange", box=BBOX) or \
        bumper("R1")
    # 10A5 is the RB *dark circle* variant (white letters on black)
    icons[0x10A5] = reuse(0x10A5, "R1", "light", box=DCBOX,
                          color=DCGREY) or dark_circle("R1")
    # triggers (fixed label boxes: LT letters sit right of the curl,
    # RT letters mirrored)
    TBOX_L = (28, 25, 48, 39)
    TBOX_R = (16, 25, 38, 39)
    icons[0x5DB] = reuse(0x5DB, "L2", "dark", box=TBOX_L) or \
        trigger("L2", "l")
    icons[0x10A2] = reuse(0x10A2, "L2", "orange", box=TBOX_L,
                          color=(244, 168, 52)) or \
        trigger("L2", "l", text_col=ORANGE_TXT)
    icons[0x10A3] = reuse(0x10A3, "L2", "light", box=DCBOX,
                          color=DCGREY) or dark_circle("L2")
    icons[0x5DE] = reuse(0x5DE, "R2", "dark", box=TBOX_R) or \
        trigger("R2", "r")
    icons[0x10AD] = reuse(0x10AD, "R2", "orange", box=TBOX_R,
                          color=(244, 168, 52)) or \
        trigger("R2", "r", text_col=ORANGE_TXT)
    # 10AE is the RT *dark circle* variant (white letters on black)
    icons[0x10AE] = reuse(0x10AE, "R2", "light", box=DCBOX,
                          color=DCGREY) or dark_circle("R2")
    # stick clicks — the LS/RS engraving (dark strokes + wide light
    # bevels) fills the whole label zone, so wipe it entirely and refill
    # with 2D diffusion, then write L3/R3
    STICK_ROI2 = (20, 17, 46, 37)
    STICK_BOX = (19, 21, 45, 35)
    icons[0x109B] = reuse(0x109B, "L3", "box", roi=STICK_ROI2,
                          box=STICK_BOX, color=(52, 52, 53),
                          inpaint="hv") or stick3("L3")
    icons[0x109C] = reuse(0x109C, "L3", "box", roi=STICK_ROI2,
                          box=STICK_BOX, color=(66, 52, 30),
                          inpaint="hv") or stick3("L3", tan=True)
    icons[0x10A6] = reuse(0x10A6, "R3", "box", roi=STICK_ROI2,
                          box=STICK_BOX, color=(52, 52, 53),
                          inpaint="hv") or stick3("R3")
    icons[0x10A7] = reuse(0x10A7, "R3", "box", roi=STICK_ROI2,
                          box=STICK_BOX, color=(66, 52, 30),
                          inpaint="hv") or stick3("R3", tan=True)
    # circled glyphs — geometry measured off the originals' ink bboxes
    icons[0x10BC] = circled_glyph("cross", 64, (178, 179, 178),
                                  (255, 255, 255), center=(31.5, 31.5),
                                  ring_r=22.3, ring_w=3.0, glyph_r=16.0,
                                  stroke_w=3.8)
    icons[0x10B9] = circled_glyph("cross", 32, (205, 205, 205),
                                  (255, 255, 255), center=(15.5, 15.5),
                                  ring_r=13.6, ring_w=2.2, glyph_r=9.6,
                                  stroke_w=2.6)
    icons[0x10BE] = circled_glyph("square", 32, (205, 205, 205),
                                  (255, 255, 255), center=(15.5, 15.5),
                                  ring_r=13.6, ring_w=2.2, glyph_r=9.8,
                                  stroke_w=2.6)
    # mini black-on-white pips (subtitle icons): white disc + dark glyph
    icons[0x26B9] = circled_glyph("cross", 32, (18, 18, 18), (18, 18, 18),
                                  center=(15.5, 16.5), ring_r=10.3,
                                  ring_w=1.9, fill=(248, 248, 248),
                                  glyph_r=6.4, stroke_w=2.0)
    icons[0x26BA] = circled_glyph("circle", 32, (18, 18, 18),
                                  (18, 18, 18), center=(15.5, 16.5),
                                  ring_r=10.3, ring_w=1.9,
                                  fill=(248, 248, 248), glyph_r=6.6,
                                  stroke_w=2.0)

    # text labels / badges — sized to the original ink (12px caps)
    def ink_label(text, w, h, box, color=(240, 240, 240)):
        px = blank(w, h)
        retex.stamp_ink(px, text, box, color)
        return w, h, px

    icons[0x25C6] = ink_label("L2", 32, 32, (8, 10, 24, 21))
    icons[0x25C7] = ink_label("R2", 32, 32, (8, 10, 24, 21))
    if orig and 0x25CE in orig:
        icons[0x25CE] = retex.swap_ink(orig[0x25CE][2], "L2", (9, 5, 24, 11))
        icons[0x25CF] = retex.swap_ink(orig[0x25CF][2], "R2", (9, 5, 24, 11))
    else:
        icons[0x25CE] = badge("L2", 32, 16)
        icons[0x25CF] = badge("R2", 32, 16)
    if orig and 0x25D7 in orig:
        icons[0x25D7] = retex.swap_ink(orig[0x25D7][2], "L2",
                                       (5, 5, 33, 20))
    else:
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
