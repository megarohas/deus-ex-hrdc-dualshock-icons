"""Pure-python BC3 (DXT5) codec + minimal DDS container. No dependencies."""
import struct

# ---------- DDS container ----------
DDS_MAGIC = b'DDS '
def dds_header(w, h, fourcc=b'DXT5'):
    linear = max(1, (w+3)//4) * max(1, (h+3)//4) * 16
    h_ = bytearray(124)
    struct.pack_into('<I', h_, 0, 124)                       # size
    struct.pack_into('<I', h_, 4, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000)  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    struct.pack_into('<I', h_, 8, h)
    struct.pack_into('<I', h_, 12, w)
    struct.pack_into('<I', h_, 16, linear)
    struct.pack_into('<I', h_, 24, 0)                        # mipCount
    struct.pack_into('<I', h_, 72, 32)                       # pf.size
    struct.pack_into('<I', h_, 76, 0x4)                      # pf.flags = FOURCC
    h_[80:84] = fourcc
    struct.pack_into('<I', h_, 104, 0x1000)                  # caps = TEXTURE
    return DDS_MAGIC + bytes(h_)

def dds_parse(blob):
    assert blob[:4] == DDS_MAGIC
    h = int.from_bytes(blob[12:16],'little'); w = int.from_bytes(blob[16:20],'little')
    fourcc = blob[84:88]
    return w, h, fourcc, blob[128:]

# ---------- decode ----------
def _c565(v):
    r = (v >> 11) & 0x1f; g = (v >> 5) & 0x3f; b = v & 0x1f
    return (r*255+15)//31, (g*255+31)//63, (b*255+15)//31

def decode(data, w, h):
    px = [[(0,0,0,0)]*w for _ in range(h)]
    bw, bh = (w+3)//4, (h+3)//4
    o = 0
    for by in range(bh):
        for bx in range(bw):
            b = data[o:o+16]; o += 16
            a0, a1 = b[0], b[1]
            abits = int.from_bytes(b[2:8], 'little')
            if a0 > a1:
                al = [a0, a1] + [((7-i)*a0 + i*a1)//7 for i in range(1,7)]
            else:
                al = [a0, a1] + [((5-i)*a0 + i*a1)//5 for i in range(1,5)] + [0, 255]
            c0, c1 = struct.unpack_from('<HH', b, 8)
            e0, e1 = _c565(c0), _c565(c1)
            cl = [e0, e1,
                  tuple((2*e0[i]+e1[i])//3 for i in range(3)),
                  tuple((e0[i]+2*e1[i])//3 for i in range(3))]
            cbits = struct.unpack_from('<I', b, 12)[0]
            for i in range(16):
                x, y = bx*4 + (i & 3), by*4 + (i >> 2)
                if x >= w or y >= h: continue
                a = al[(abits >> (3*i)) & 7]
                c = cl[(cbits >> (2*i)) & 3]
                px[y][x] = (c[0], c[1], c[2], a)
    return px

# ---------- encode ----------
def _to565(c):
    return ((c[0]*31+127)//255 << 11) | ((c[1]*63+127)//255 << 5) | ((c[2]*31+127)//255)

def _enc_alpha(vals):
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return bytes([lo, lo]) + b'\x00'*6
    a0, a1 = hi, lo
    tbl = [a0, a1] + [((7-i)*a0 + i*a1)//7 for i in range(1,7)]
    bits = 0
    for i, v in enumerate(vals):
        best = min(range(8), key=lambda k: abs(tbl[k]-v))
        bits |= best << (3*i)
    return bytes([a0, a1]) + bits.to_bytes(6, 'little')

def _enc_color(cols):
    # endpoints from the RGB bounding box, then least-squares refinement
    mn = tuple(min(c[i] for c in cols) for i in range(3))
    mx = tuple(max(c[i] for c in cols) for i in range(3))
    best = None
    for e0, e1 in ((mx, mn), (mn, mx)):
        q0, q1 = _to565(e0), _to565(e1)
        if q0 == q1:
            if q0 == 0: q1 = 0
            else: q1 = q0 - 1
        if q0 < q1: q0, q1 = q1, q0
        d0, d1 = _c565(q0), _c565(q1)
        tbl = [d0, d1,
               tuple((2*d0[i]+d1[i])//3 for i in range(3)),
               tuple((d0[i]+2*d1[i])//3 for i in range(3))]
        bits = 0; err = 0
        for i, c in enumerate(cols):
            k = min(range(4), key=lambda j: sum((tbl[j][t]-c[t])**2 for t in range(3)))
            err += sum((tbl[k][t]-c[t])**2 for t in range(3))
            bits |= k << (2*i)
        if best is None or err < best[0]:
            best = (err, struct.pack('<HHI', q0, q1, bits))
    return best[1]

def encode(px, w, h):
    out = bytearray()
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            cols, alps = [], []
            for i in range(16):
                x = min(bx*4 + (i & 3), w-1); y = min(by*4 + (i >> 2), h-1)
                p = px[y][x]
                cols.append((p[0], p[1], p[2])); alps.append(p[3])
            out += _enc_alpha(alps) + _enc_color(cols)
    return bytes(out)
