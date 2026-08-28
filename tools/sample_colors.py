"""Print dominant colors + probe lines for reference textures."""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt

SRC = {
    0x5D0: "A", 0x1091: "A_hi", 0x5D1: "B", 0x5D3: "dpad", 0x1094: "dpad_hi",
    0x5D8: "dpad_up", 0x1098: "LB_pill", 0x1099: "LB_pill_hi",
    0x109A: "LB_dark", 0x109B: "LS_silver", 0x109C: "LS_tan",
    0x5DB: "LT_ang", 0x10A2: "LT_ang_hi", 0x10AD: "RT_ang_wh",
    0x5DC: "RB_rect", 0x5D2: "BACK", 0x1093: "BACK_hi", 0x5DF: "START",
    0x10AF: "START_hi", 0x5DA: "L_stick", 0x10B0: "X_dark", 0x5E0: "X",
    0x5E1: "Y", 0x10BC: "A_circ64",
}

big = dxhr.BigFile()
name = r"pc-w\tutorialvolume.drm"
e = big.find(name, dxhr.LOCALE_DEFAULT)[0]
data = big.read(e)
data, _ = dxhr.cdrm_unwrap(data)
meta, sections = dxhr.drm_parse(data)

for s in sections:
    if s.type != 5 or s.id not in SRC:
        continue
    t = dxhr.pcd9_parse(data, s.data_off)
    if t.format != 0x35545844:
        print("%s id=%04X fmt=%08X (skip)" % (SRC[s.id], s.id, t.format))
        continue
    px = dxt.decode(data[t.payload_off:t.payload_off + t.data_size],
                    t.width, t.height)
    hist = collections.Counter()
    for row in px:
        for r, g, b, a in row:
            if a > 60:
                hist[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += 1
    top = ", ".join("#%02X%02X%02X x%d" % (c[0], c[1], c[2], n)
                    for c, n in hist.most_common(6))
    print("%-10s id=%04X %dx%d : %s" % (SRC[s.id], s.id, t.width, t.height,
                                        top))
    cx = t.width // 2
    col = " | ".join("y%02d %02X%02X%02X.%02X" % (y, *px[y][cx])
                     for y in range(4, t.height, max(4, t.height // 8)))
    print("    center col: %s" % col)
