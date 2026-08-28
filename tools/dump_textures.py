"""Dump every PCD9 texture in a (CDRM-wrapped) DRM to PNG for eyeballing."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr
import dxt


def decode_dxt1(data, w, h):
    px = [[(0, 0, 0, 255)] * w for _ in range(h)]
    o = 0
    for by in range((h + 3) // 4):
        for bx in range((w + 3) // 4):
            c0, c1, bits = struct.unpack_from("<HHI", data, o)
            o += 8
            e0, e1 = dxt._c565(c0), dxt._c565(c1)
            if c0 > c1:
                cl = [e0 + (255,), e1 + (255,),
                      tuple((2 * e0[i] + e1[i]) // 3 for i in range(3)) + (255,),
                      tuple((e0[i] + 2 * e1[i]) // 3 for i in range(3)) + (255,)]
            else:
                cl = [e0 + (255,), e1 + (255,),
                      tuple((e0[i] + e1[i]) // 2 for i in range(3)) + (255,),
                      (0, 0, 0, 0)]
            for i in range(16):
                x, y = bx * 4 + (i & 3), by * 4 + (i >> 2)
                if x < w and y < h:
                    px[y][x] = cl[(bits >> (2 * i)) & 3]
    return px


def decode_argb(data, w, h):
    px = []
    o = 0
    for _ in range(h):
        row = []
        for _ in range(w):
            b, g, r, a = data[o], data[o + 1], data[o + 2], data[o + 3]
            row.append((r, g, b, a))
            o += 4
        px.append(row)
    return px


def main():
    drm_path = sys.argv[1]
    out_dir = sys.argv[2]
    max_dim = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    os.makedirs(out_dir, exist_ok=True)

    data = open(drm_path, "rb").read()
    if data[:4] == b"CDRM":
        data, _ = dxhr.cdrm_unwrap(data)
    meta, sections = dxhr.drm_parse(data)

    n = 0
    for s in sections:
        if s.type != 5:
            continue
        t = dxhr.pcd9_parse(data, s.data_off)
        if t is None:
            continue
        if max(t.width, t.height) > max_dim:
            print("skip big #%d %r" % (s.index, t))
            continue
        payload = data[t.payload_off:t.payload_off + t.data_size]
        if t.format == 0x35545844:  # DXT5
            px = dxt.decode(payload, t.width, t.height)
            fmt = "dxt5"
        elif t.format == 0x31545844:  # DXT1
            px = decode_dxt1(payload, t.width, t.height)
            fmt = "dxt1"
        elif t.format == 21:
            px = decode_argb(payload, t.width, t.height)
            fmt = "argb"
        else:
            print("skip fmt %08X #%d" % (t.format, s.index))
            continue
        name = "%04d_%08X_%dx%d_%s.png" % (s.index, s.id, t.width, t.height,
                                           fmt)
        dxhr.write_png(os.path.join(out_dir, name), px)
        n += 1
    print("dumped %d textures -> %s" % (n, out_dir))


if __name__ == "__main__":
    main()
