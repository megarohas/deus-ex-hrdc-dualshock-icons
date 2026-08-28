"""Verify same-id PCD9 payloads are byte-identical across all DRMs."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work")
IDS = [int(x, 16) for x in sys.argv[1:]] or [
    0x5D0, 0x5D1, 0x5D2, 0x5D3, 0x5D4, 0x5D5, 0x5D6, 0x5D7, 0x5D8, 0x5D9,
    0x5DA, 0x5DB, 0x5DC, 0x5DD, 0x5DE, 0x5DF, 0x5E0, 0x5E1, 0x1098, 0x109C,
    0x601, 0x10B2, 0x25D7, 0x26B9, 0x26BA]
IDSET = set(IDS)

files = {}
with open(os.path.join(WORK, "texture_index.csv")) as f:
    next(f)
    for line in f:
        p = line.rstrip("\n").split(";")
        if p[4] == "ERR" or not p[1]:
            continue
        if int(p[5], 16) in IDSET:
            files.setdefault((p[1], int(p[2], 16)), []).append(int(p[5], 16))

big = dxhr.BigFile()
seen = {}
for (name, locale), ids in sorted(files.items()):
    for e in big.find(name, locale):
        data = big.read(e)
        if data[:4] == b"CDRM":
            data, _ = dxhr.cdrm_unwrap(data)
        meta, sections = dxhr.drm_parse(data)
        for s in sections:
            if s.type != 5 or s.id not in IDSET:
                continue
            t = dxhr.pcd9_parse(data, s.data_off)
            head = data[s.data_off:t.payload_off]
            body = data[t.payload_off:t.payload_off + t.data_size]
            key = (hashlib.md5(head).hexdigest()[:8],
                   hashlib.md5(body).hexdigest()[:8], t.width, t.height,
                   t.data_size)
            seen.setdefault(s.id, {}).setdefault(key, []).append(name)

for sid in sorted(seen):
    variants = seen[sid]
    n = sum(len(v) for v in variants.values())
    if len(variants) == 1:
        print("%08X: %2d copies, IDENTICAL" % (sid, n))
    else:
        print("%08X: %2d copies, %d VARIANTS:" % (sid, n, len(variants)))
        for k, v in variants.items():
            print("    %s x%d e.g. %s" % (k, len(v), v[0]))
