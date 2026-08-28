"""Verify DS4ICONS.000: parse, unwrap every entry, decode sample icons."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
import icons
from dump_textures import decode_dxt1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "dist", "DS4ICONS.000")
OUT = os.path.join(ROOT, "work", "png", "modcheck")
os.makedirs(OUT, exist_ok=True)

names = dxhr.load_filelist()
art_ids = set(icons.build_all())

mod = dxhr.BigFile(MOD)
print("mod: align=%08X base=%r entries=%d" %
      (mod.alignment, mod.base_path, len(mod.entries)))

ok = True
total = 0
for e in sorted(mod.entries, key=lambda e: names.get(e.hash, "")):
    name = names.get(e.hash, "?%08X?" % e.hash)
    data = mod.read(e)
    try:
        payload, info = dxhr.cdrm_unwrap(data)
        meta, sections = dxhr.drm_parse(payload)
        hits = [s for s in sections if s.type == 5 and s.id in art_ids]
        total += len(hits)
        print("  OK %-64s %d icon textures" % (name, len(hits)))
    except Exception as ex:
        ok = False
        print("  FAIL %s: %s" % (name, ex))

# decode a few icons straight from the mod to prove the art landed
CHECK = {r"pc-w\tutorialvolume.drm": (0x5D0, 0x5DF, 0x1094, 0x109C),
         r"pc-w\globalscaleformdatabase.drm": (0x5E1, 0x26B9, 0x25D7)}
for name, ids in CHECK.items():
    e = mod.find(name)[0]
    payload, _ = dxhr.cdrm_unwrap(mod.read(e))
    meta, sections = dxhr.drm_parse(payload)
    for s in sections:
        if s.type != 5 or s.id not in ids:
            continue
        t = dxhr.pcd9_parse(payload, s.data_off)
        raw = payload[t.payload_off:t.payload_off + t.data_size]
        if t.format == 0x35545844:
            px = dxt.decode(raw, t.width, t.height)
        elif t.format == 0x31545844:
            px = decode_dxt1(raw, t.width, t.height)
        else:
            continue
        vis = []
        for y in range(t.height):
            row = []
            for x in range(t.width):
                r, g, b, a = px[y][x]
                bg = 40 + 20 * (((x // 8) + (y // 8)) & 1)
                k = a / 255.0
                row.append((round(bg + (r - bg) * k),
                            round(bg + (g - bg) * k),
                            round(bg + (b - bg) * k), 255))
            vis.append(row)
        dxhr.write_png(os.path.join(OUT, "%08X.png" % s.id), vis)
        print("decoded %08X from mod %s" % (s.id, name))

print("total icon textures in mod: %d, %s" %
      (total, "ALL OK" if ok else "FAILURES!"))
