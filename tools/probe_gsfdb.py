"""Probe: parse BIGFILE, extract globalscaleformdatabase.drm, inventory it."""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work")

big = dxhr.BigFile()
print("bigfile: base=%r align=%08X entries=%d" %
      (big.base_path, big.alignment, len(big.entries)))

name = r"pc-w\globalscaleformdatabase.drm"
entries = big.find(name)
print("entries for %s:" % name)
for e in entries:
    print("  ", e)
if not entries:
    sys.exit("not found!")

entry = next((e for e in entries if e.locale == dxhr.LOCALE_DEFAULT),
             entries[0])
data = big.read(entry)
raw_path = os.path.join(WORK, "globalscaleformdatabase.drm")
with open(raw_path, "wb") as f:
    f.write(data)
print("extracted %d bytes -> %s" % (len(data), raw_path))
print("magic:", data[:4])

if data[:4] == b"CDRM":
    payload, info = dxhr.cdrm_unwrap(data)
    print("CDRM v%d, %d blocks (usize[0]=%#x), payload %d bytes" %
          (info["version"], len(info["block_usizes"]),
           info["block_usizes"][0], len(payload)))
    with open(raw_path + ".dec", "wb") as f:
        f.write(payload)
    # round-trip sanity
    rew = dxhr.cdrm_wrap(payload, info)
    p2, _ = dxhr.cdrm_unwrap(rew)
    assert p2 == payload, "cdrm round-trip failed"
    print("cdrm re-wrap round-trip OK (rewrapped %d vs orig %d bytes)" %
          (len(rew), len(data)))
else:
    payload = data

meta, sections = dxhr.drm_parse(payload)
print("DRM flags=%X sections=%d end=%d (payload %d)" %
      (meta["flags"], len(sections), meta["end"], len(payload)))
counts = collections.Counter(s.type_name for s in sections)
print("section types:", dict(counts))

ntex = 0
for s in sections:
    if s.type_name == "RenderResource":
        t = dxhr.pcd9_parse(payload, s.data_off)
        if t:
            ntex += 1
            print("  tex #%d id=%08X %r" % (s.index, s.id, t))
print("textures:", ntex)
