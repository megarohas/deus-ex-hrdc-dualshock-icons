"""Index every PCD9 texture in every DRM of the whole bigfile -> CSV.

Writes work/texture_index.csv: file_hash;name;locale;entry_size;section_index;
section_id;width;height;format;data_size
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work")
OUT = os.path.join(WORK, "texture_index.csv")

big = dxhr.BigFile()
names = dxhr.load_filelist()

t0 = time.time()
n_drm = n_tex = n_err = 0
with open(OUT, "w", encoding="utf-8") as out:
    out.write("hash;name;locale;entry_size;section;id;w;h;fmt;dsize\n")
    for i, e in enumerate(big.entries):
        if i % 5000 == 0:
            print("%d/%d drm=%d tex=%d err=%d %.0fs" %
                  (i, len(big.entries), n_drm, n_tex, n_err,
                   time.time() - t0), flush=True)
        name = names.get(e.hash, "")
        if name.endswith((".mul", ".usm", ".mus", ".sam", ".fsb")):
            continue
        try:
            part = e.offset // big.max_sectors
            byte_off = (e.offset % big.max_sectors) * 2048
            with open(big.part_path(part), "rb") as f:
                f.seek(byte_off)
                magic = f.read(4)
            if magic == b"CDRM":
                data = big.read(e)
                payload, _ = dxhr.cdrm_unwrap(data)
            elif magic[:1] in (b"\x15",) and False:
                continue
            else:
                # raw DRM? check version 21 little-endian
                if magic[:4] != b"\x15\x00\x00\x00":
                    continue
                payload = big.read(e)
            meta, sections = dxhr.drm_parse(payload)
            n_drm += 1
            for s in sections:
                if s.type != 5:
                    continue
                t = dxhr.pcd9_parse(payload, s.data_off)
                if t is None:
                    continue
                n_tex += 1
                fmt = ("%08X" % t.format)
                out.write("%08X;%s;%08X;%d;%d;%08X;%d;%d;%s;%d\n" %
                          (e.hash, name, e.locale, e.size, s.index, s.id,
                           t.width, t.height, fmt, t.data_size))
        except Exception as ex:
            n_err += 1
            out.write("%08X;%s;%08X;%d;ERR;%s;;;;\n" %
                      (e.hash, name, e.locale, e.size,
                       str(ex)[:60].replace(";", ",")))

print("done: drm=%d tex=%d err=%d in %.0fs -> %s" %
      (n_drm, n_tex, n_err, time.time() - t0, OUT), flush=True)
