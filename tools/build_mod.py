"""Build mods/DS4ICONS.000 for the Gibbed ModHook.

Takes every DRM in the bigfile that embeds Xbox button textures, swaps
the pixel payloads for the DS4 art (in place, same sizes), re-wraps the
CDRM and packs the patched files into a standalone mod archive.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt
import icons
import swf_template
from dump_textures import decode_dxt1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
DIST = os.path.join(ROOT, "dist")
CSV = os.path.join(WORK, "texture_index.csv")


def mip_down(px, w, h):
    nw, nh = max(1, w // 2), max(1, h // 2)
    out = []
    for y in range(nh):
        row = []
        for x in range(nw):
            acc = [0, 0, 0, 0]
            n = 0
            for dy in (0, 1):
                for dx in (0, 1):
                    sy, sx = min(h - 1, y * 2 + dy), min(w - 1, x * 2 + dx)
                    p = px[sy][sx]
                    for k in range(4):
                        acc[k] += p[k]
                    n += 1
            row.append(tuple(v // n for v in acc))
        out.append(row)
    return out, nw, nh


def encode_payload(art, t):
    """Encode art (w,h,px) to exactly t.data_size bytes in t's format."""
    w, h, px = art
    if (w, h) != (t.width, t.height):
        raise ValueError("size mismatch: art %dx%d vs tex %dx%d" %
                         (w, h, t.width, t.height))
    blob = bytearray()
    for level in range(t.mips):
        if t.format == 0x35545844:
            blob += dxt.encode(px, w, h)
        elif t.format == 0x31545844:
            blob += dxt.encode_dxt1(px, w, h)
        elif t.format == 21:
            for row in px:
                for r, g, b, a in row:
                    blob += bytes((b, g, r, a))
        else:
            raise ValueError("format %08X" % t.format)
        if level + 1 < t.mips:
            px, w, h = mip_down(px, w, h)
    if len(blob) != t.data_size:
        raise ValueError("payload %d != expected %d" %
                         (len(blob), t.data_size))
    return bytes(blob)


def load_originals(big, want):
    orig = {}
    for name in (r"pc-w\tutorialvolume.drm",
                 r"pc-w\globalscaleformdatabase.drm"):
        e = big.find(name, dxhr.LOCALE_DEFAULT)[0]
        data = big.read(e)
        data, _ = dxhr.cdrm_unwrap(data)
        meta, sections = dxhr.drm_parse(data)
        for s in sections:
            if s.type != 5 or s.id not in want or s.id in orig:
                continue
            t = dxhr.pcd9_parse(data, s.data_off)
            payload = data[t.payload_off:t.payload_off + t.data_size]
            if t.format == 0x35545844:
                orig[s.id] = (t.width, t.height,
                              dxt.decode(payload, t.width, t.height))
            elif t.format == 0x31545844:
                orig[s.id] = (t.width, t.height,
                              decode_dxt1(payload, t.width, t.height))
    return orig


def write_mod_archive(path, alignment, base_path, entries):
    """entries: list of (name_hash, locale, data)"""
    entries = sorted(entries, key=lambda e: (e[0], len(e[2])))
    count = len(entries)
    header = 4 + 64 + 4 + 4 * count + 16 * count
    header = (header + 2047) & ~2047
    sector = header // 2048
    table = []
    for h, loc, data in entries:
        table.append((h, len(data), sector, loc))
        sector += (len(data) + 2047) // 2048
    total = sector * 2048
    if total > alignment:
        raise ValueError("mod archive would span parts")
    with open(path, "wb") as f:
        f.write(struct.pack("<I", alignment))
        f.write(base_path.encode("ascii").ljust(64, b"\0"))
        f.write(struct.pack("<I", count))
        for h, size, off, loc in table:
            f.write(struct.pack("<I", h))
        for h, size, off, loc in table:
            f.write(struct.pack("<4I", size, off, loc, 0))
        for (h, loc, data), (h2, size, off, loc2) in zip(entries, table):
            f.seek(off * 2048)
            f.write(data)
        f.seek(total - 1)
        f.write(b"\0")
    return count, total


# movies whose platform switch gets retargeted WIN -> PS3 template
# (controller-layout screen: PS3 callouts + PS3 pad render)
SWF_PATCH_FILES = {r"pc-w\globaloutershell.drm",
                   r"pc-w\globalscaleformdatabase.drm"}
RAW_COPY = {}


def main():
    big = dxhr.BigFile()
    new_art = icons.build_all(load_originals(big, set(icons.build_all())))
    print("art ready: %d textures" % len(new_art))

    # group csv rows by (file, locale)
    plan = {}
    with open(CSV) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(";")
            if p[4] == "ERR" or not p[1]:
                continue
            sid = int(p[5], 16)
            if sid in new_art or sid in RAW_COPY:
                plan.setdefault((p[1], int(p[2], 16)), set()).add(sid)

    print("files to patch: %d" % len(plan))
    entries = []
    total_swaps = 0
    for (name, locale), ids in sorted(plan.items()):
        found = big.find(name, locale)
        if len(found) != 1:
            raise RuntimeError("%s locale %08X: %d entries" %
                               (name, locale, len(found)))
        e = found[0]
        raw = big.read(e)
        wrapped = raw[:4] == b"CDRM"
        if wrapped:
            payload, info = dxhr.cdrm_unwrap(raw)
        else:
            payload = raw
        blob = bytearray(payload)
        meta, sections = dxhr.drm_parse(payload)
        by_id = {s.id: s for s in sections if s.type == 5}
        n = 0
        for s in sections:
            if s.type != 5 or s.id not in ids:
                continue
            t = dxhr.pcd9_parse(payload, s.data_off)
            if t is None:
                continue
            if s.id in RAW_COPY:
                src = by_id.get(RAW_COPY[s.id])
                if src is None:
                    continue
                ts = dxhr.pcd9_parse(payload, src.data_off)
                if (ts.width, ts.height, ts.format, ts.data_size) != \
                        (t.width, t.height, t.format, t.data_size):
                    print("  ! raw-copy mismatch for %04X in %s, skipped" %
                          (s.id, name))
                    continue
                enc = payload[ts.payload_off:ts.payload_off + ts.data_size]
            else:
                enc = encode_payload(new_art[s.id], t)
            blob[t.payload_off:t.payload_off + t.data_size] = enc
            n += 1
        total_swaps += n
        if name in SWF_PATCH_FILES:
            for s in sections:
                if s.type != 7:
                    continue
                sec = bytes(blob[s.data_off:s.data_off + s.data_size])
                try:
                    patched = swf_template.patch_section(sec)
                except Exception as ex:
                    raise RuntimeError("swf patch failed in %s section "
                                       "#%d: %s" % (name, s.index, ex))
                if patched is not None:
                    assert len(patched) == s.data_size
                    blob[s.data_off:s.data_off + s.data_size] = patched
                    print("    patched platform switch in section #%d "
                          "id=%08X" % (s.index, s.id))
        out = dxhr.cdrm_wrap(bytes(blob), info) if wrapped else bytes(blob)
        entries.append((e.hash, e.locale, out))
        print("  %-64s %2d textures swapped, %d -> %d bytes" %
              (name, n, len(raw), len(out)))

    os.makedirs(DIST, exist_ok=True)
    out_path = os.path.join(DIST, "DS4ICONS.000")
    count, total = write_mod_archive(out_path, big.alignment,
                                     big.base_path, entries)
    print("wrote %s: %d entries, %d bytes, %d texture swaps" %
          (out_path, count, total, total_swaps))


if __name__ == "__main__":
    main()
