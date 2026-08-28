"""Inflate the GFx movie from a DRM DTPData section and map its tags.

usage: swfdump.py <drm.dec> <section_index> [needle ...]
Prints: header, frame labels, sprites, GFX external-image tags, and
placements of any character whose external name contains a needle.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

TAGS = {0: 'End', 1: 'ShowFrame', 4: 'PlaceObject', 5: 'RemoveObject',
        9: 'SetBackgroundColor', 12: 'DoAction', 26: 'PlaceObject2',
        28: 'RemoveObject2', 39: 'DefineSprite', 43: 'FrameLabel',
        56: 'ExportAssets', 69: 'FileAttributes', 70: 'PlaceObject3',
        76: 'SymbolClass', 82: 'DoABC',
        86: 'DefineSceneAndFrameLabelData',
        1000: 'GFX_ExporterInfo', 1001: 'GFX_DefineExternalImage',
        1008: 'GFX_DefineSubImage', 1009: 'GFX_FileAttributes',
        1010: 'GFX_ExternalImage2'}


def inflate_cfx(blob):
    assert blob[:3] == b'CFX', blob[:3]
    ver = blob[3]
    total, = struct.unpack_from('<I', blob, 4)
    raw = zlib.decompressobj().decompress(blob[8:], total - 8)
    return b'GFX' + bytes([ver]) + struct.pack('<I', total) + raw


def rect_skip(d, p):
    nb = d[p] >> 3
    total = 5 + nb * 4
    return p + (total + 7) // 8


def walk(d, p, end, depth=0, path="main"):
    """Yield (path, frame, code, body_off, body_len, tag_off)."""
    frame = 1
    while p + 2 <= end:
        tag_off = p
        th, = struct.unpack_from('<H', d, p)
        p += 2
        code, ln = th >> 6, th & 0x3F
        if ln == 0x3F:
            ln, = struct.unpack_from('<I', d, p)
            p += 4
        body = p
        yield (path, frame, code, body, ln, tag_off)
        if code == 1:
            frame += 1
        elif code == 39:
            sid, nf = struct.unpack_from('<HH', d, body)
            for item in walk(d, body + 4, body + ln, depth + 1,
                             "sprite%d" % sid):
                yield item
        elif code == 0 and depth == 0:
            return
        p += ln


def main():
    dec_path, sec_idx = sys.argv[1], int(sys.argv[2])
    needles = [n.lower() for n in sys.argv[3:]]
    data = open(dec_path, 'rb').read()
    meta, sections = dxhr.drm_parse(data)
    s = sections[sec_idx]
    sec = data[s.data_off:s.data_off + s.data_size]
    cfx = sec.find(b'CFX')
    swf = inflate_cfx(sec[cfx:])
    out = os.path.splitext(dec_path)[0] + '.sec%d.gfx' % sec_idx
    open(out, 'wb').write(swf)
    print("section #%d id=%08X: CFX at +%#x -> %d bytes swf -> %s" %
          (sec_idx, s.id, cfx, len(swf), out))

    p = rect_skip(swf, 8)
    rate, nframes = struct.unpack_from('<HH', swf, p)
    p += 4
    print("main timeline: %d frames @%.1ffps" % (nframes, rate / 256.0))

    ext = {}          # cid -> name
    tags = list(walk(swf, p, len(swf)))
    for path, frame, code, off, ln, _ in tags:
        if code == 1001:
            cid, fmt, w, h = struct.unpack_from('<HHHH', swf, off)
            nl = swf[off + 8]
            name = swf[off + 9:off + 9 + nl].decode('latin1')
            ext[cid] = name
            print("EXTIMG  %-9s f%-3d cid=%-4d %dx%d %s" %
                  (path, frame, cid, w, h, name))
        elif code == 1010:
            cid, = struct.unpack_from('<H', swf, off)
            rest = swf[off + 2:off + ln]
            # name is a length-prefixed string somewhere after bitmap info
            print("EXTIMG2 %-9s f%-3d cid=%-4d raw=%s" %
                  (path, frame, cid, rest[:40].hex()))
        elif code == 43:
            e = swf.index(b'\0', off)
            print("LABEL   %-9s f%-3d %r" %
                  (path, frame, swf[off:e].decode('latin1')))
        elif code == 39:
            sid, nf = struct.unpack_from('<HH', swf, off)
            print("SPRITE  %-9s f%-3d sprite%d frames=%d len=%d" %
                  (path, frame, sid, nf, ln))
        elif code == 56:
            n, = struct.unpack_from('<H', swf, off)
            q = off + 2
            names = []
            for _ in range(n):
                cid, = struct.unpack_from('<H', swf, q)
                q += 2
                e = swf.index(b'\0', q)
                names.append("%d=%s" % (cid, swf[q:e].decode('latin1')))
                q = e + 1
            print("EXPORT  %-9s f%-3d %s" % (path, frame, ", ".join(names)))

    if needles:
        want = {cid for cid, nm in ext.items()
                if any(n in nm.lower() for n in needles)}
        print("\nplacements of %s:" % sorted(want))
        for path, frame, code, off, ln, tag_off in tags:
            if code not in (26, 70):
                continue
            fl = swf[off]
            q = off + (2 if code == 70 else 1)
            depth_v, = struct.unpack_from('<H', swf, q)
            q += 2
            if code == 70:
                pass
            cid = None
            if fl & 2:
                cid, = struct.unpack_from('<H', swf, q)
            if cid in want:
                print("PLACE   %-9s f%-3d depth=%d cid=%d flags=%02X "
                      "tag@%#x len=%d" %
                      (path, frame, depth_v, cid, fl, tag_off, ln))


if __name__ == '__main__':
    main()
