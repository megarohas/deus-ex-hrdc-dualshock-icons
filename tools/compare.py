"""Side-by-side sheet: original texture vs DS4 replacement."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
import icons
from dump_textures import decode_dxt1

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work")

big = dxhr.BigFile()

# originals: prefer tutorialvolume (has almost everything), else gsfdb
WANT = set(icons.build_all().keys())
orig = {}
for name in (r"pc-w\tutorialvolume.drm", r"pc-w\globalscaleformdatabase.drm"):
    e = big.find(name, dxhr.LOCALE_DEFAULT)[0]
    data = big.read(e)
    data, _ = dxhr.cdrm_unwrap(data)
    meta, sections = dxhr.drm_parse(data)
    for s in sections:
        if s.type != 5 or s.id not in WANT or s.id in orig:
            continue
        t = dxhr.pcd9_parse(data, s.data_off)
        payload = data[t.payload_off:t.payload_off + t.data_size]
        if t.format == 0x35545844:
            orig[s.id] = (t.width, t.height, dxt.decode(payload, t.width,
                                                        t.height))
        elif t.format == 0x31545844:
            orig[s.id] = (t.width, t.height,
                          decode_dxt1(payload, t.width, t.height))

new = icons.build_all(orig)

ids = sorted(new)
COLS = 6            # pairs per row
CELL = 68
W = COLS * CELL * 2
rows_n = (len(ids) + COLS - 1) // COLS
H = rows_n * CELL
sheet = [[(40 + 20 * (((x // 8) + (y // 8)) & 1),) * 3 + (255,)
          for x in range(W)] for y in range(H)]


def blit(px, w, h, ox, oy):
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[y][x]
            if a == 0:
                continue
            br, bg, bb, _ = sheet[oy + y][ox + x]
            k = a / 255.0
            sheet[oy + y][ox + x] = (round(br + (r - br) * k),
                                     round(bg + (g - bg) * k),
                                     round(bb + (b - bb) * k), 255)


for i, sid in enumerate(ids):
    ox = (i % COLS) * CELL * 2
    oy = (i // COLS) * CELL
    if sid in orig:
        w, h, px = orig[sid]
        blit(px, w, h, ox + 2, oy + 2)
    w, h, px = new[sid]
    blit(px, w, h, ox + CELL + 2, oy + 2)
    print("pair %2d: %08X" % (i, sid))

dxhr.write_png(os.path.join(WORK, "compare.png"), sheet)
print("-> compare.png")
