"""Dump specific texture ids from a named bigfile entry to PNGs.

usage: dump_one.py <entry-name> <out_dir> <id_hex> [id_hex ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
from dump_textures import decode_dxt1, decode_argb

name, out_dir = sys.argv[1], sys.argv[2]
want = {int(x, 16) for x in sys.argv[3:]}
os.makedirs(out_dir, exist_ok=True)

big = dxhr.BigFile()
for e in big.find(name):
    data = big.read(e)
    if data[:4] == b"CDRM":
        data, _ = dxhr.cdrm_unwrap(data)
    meta, sections = dxhr.drm_parse(data)
    for s in sections:
        if s.type != 5 or (want and s.id not in want):
            continue
        t = dxhr.pcd9_parse(data, s.data_off)
        if t is None:
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
        # composite on dark checkerboard so white/transparent art is visible
        out = []
        for y in range(t.height):
            row = []
            for x in range(t.width):
                r, g, b, a = px[y][x]
                bg = 40 + 20 * (((x // 8) + (y // 8)) & 1)
                k = a / 255.0
                row.append((round(bg + (r - bg) * k),
                            round(bg + (g - bg) * k),
                            round(bg + (b - bg) * k), 255))
            out.append(row)
        fn = "%08X_%dx%d.png" % (s.id, t.width, t.height)
        dxhr.write_png(os.path.join(out_dir, fn), out)
        print("dumped", fn, "from", name, "locale %08X" % e.locale)
