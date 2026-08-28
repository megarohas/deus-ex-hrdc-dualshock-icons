"""Save zoomed previews of chosen replacement icons (with reuse art)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
import icons
from dump_textures import decode_dxt1

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work")
OUT = os.path.join(WORK, "png", "zoom")
os.makedirs(OUT, exist_ok=True)

ids = [int(a, 16) for a in sys.argv[1:]]
big = dxhr.BigFile()
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
            orig[s.id] = (t.width, t.height,
                          dxt.decode(payload, t.width, t.height))
        elif t.format == 0x31545844:
            orig[s.id] = (t.width, t.height,
                          decode_dxt1(payload, t.width, t.height))

new = icons.build_all(orig)
Z = 3
for sid in ids:
    pair = []
    for src in (orig.get(sid), new.get(sid)):
        if src is None:
            continue
        w, h, px = src
        pair.append((w, h, px))
    tw = sum(w for w, h, _ in pair) * Z + 8
    th = max(h for w, h, _ in pair) * Z + 4
    sheet = [[(40 + 20 * (((x // 12) + (y // 12)) & 1),) * 3 + (255,)
              for x in range(tw)] for y in range(th)]
    ox = 2
    for w, h, px in pair:
        for y in range(h * Z):
            for x in range(w * Z):
                r, g, b, a = px[y // Z][x // Z]
                if a == 0:
                    continue
                br, bg, bb, _ = sheet[y + 2][ox + x]
                k = a / 255.0
                sheet[y + 2][ox + x] = (round(br + (r - br) * k),
                                        round(bg + (g - bg) * k),
                                        round(bb + (b - bb) * k), 255)
        ox += w * Z + 4
    dxhr.write_png(os.path.join(OUT, "%08X.png" % sid), sheet)
    print("zoomed %08X" % sid)
