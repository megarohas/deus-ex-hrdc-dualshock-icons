"""Tile small textures from a DRM into one contact sheet PNG (+ index map)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
from dump_textures import decode_dxt1, decode_argb

drm_path, out_png, max_px = sys.argv[1], sys.argv[2], int(sys.argv[3])

data = open(drm_path, "rb").read()
if data[:4] == b"CDRM":
    data, _ = dxhr.cdrm_unwrap(data)
meta, sections = dxhr.drm_parse(data)

cells = []
for s in sections:
    if s.type != 5:
        continue
    t = dxhr.pcd9_parse(data, s.data_off)
    if t is None or max(t.width, t.height) > max_px:
        continue
    payload = data[t.payload_off:t.payload_off + t.data_size]
    if t.format == 0x35545844:
        px = dxt.decode(payload, t.width, t.height)
    elif t.format == 0x31545844:
        px = decode_dxt1(payload, t.width, t.height)
    elif t.format == 21:
        px = decode_argb(payload, t.width, t.height)
    else:
        continue
    cells.append((s.index, s.id, t, px))

CELL = max_px + 4
COLS = 16
rows_n = (len(cells) + COLS - 1) // COLS
W, H = COLS * CELL, rows_n * CELL
# checkerboard background so alpha is visible
sheet = [[(40 + 20 * (((x // 8) + (y // 8)) & 1),) * 3 + (255,)
          for x in range(W)] for y in range(H)]

for i, (idx, sid, t, px) in enumerate(cells):
    ox = (i % COLS) * CELL + 2
    oy = (i // COLS) * CELL + 2
    for y in range(t.height):
        for x in range(t.width):
            r, g, b, a = px[y][x]
            if a == 0:
                continue
            br, bg, bb, _ = sheet[oy + y][ox + x]
            k = a / 255.0
            sheet[oy + y][ox + x] = (round(br + (r - br) * k),
                                     round(bg + (g - bg) * k),
                                     round(bb + (b - bb) * k), 255)
    print("cell %3d (row %2d col %2d): section #%d id=%08X %dx%d" %
          (i, i // COLS, i % COLS, idx, sid, t.width, t.height))

dxhr.write_png(out_png, sheet)
print("sheet: %s (%dx%d, %d cells)" % (out_png, W, H, len(cells)))
