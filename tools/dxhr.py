"""Deus Ex: Human Revolution - Director's Cut file formats (pure stdlib).

Formats ported from Gibbed.CrystalDynamics / Gibbed.DeusEx3 (zlib-licensed
sources by Rick Gibbed), verified against the GOG DC build:

BIGFILE.000 (BigArchiveFileV2, little-endian):
    u32  data_alignment          (0x7FF00000 = max bytes per .NNN part)
    char base_path[64]           ("pc-w", zero-padded)
    u32  count
    u32  name_hashes[count]      (sorted ascending)
    struct entry[count]: u32 uncompressed_size, u32 offset, u32 locale, u32 zero
    -- data --
    entry.offset is in 2048-byte sectors across the concatenated parts:
    part_index = offset // (alignment//2048), byte_off = (offset % that) * 2048.

Name hash: CRC-32/MPEG-2 variant (poly 0x04C11DB7, MSB-first, init 0xFFFFFFFF,
result inverted) over the lowercased path, e.g. "pc-w\\foo.drm".

CDRM: compression wrapper around DRM payloads.
DRM v21: sectioned resource container (textures = RenderResource/PCD9).
"""
import io
import os
import struct
import zlib

GAME_DIR = os.environ.get("DXHR_GAME_DIR", r"C:\Games\Deus Ex HRDC")
BIGFILE = os.path.join(GAME_DIR, "BIGFILE.000")
FILELIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work",
    "Gibbed.CrystalDynamics", "bin_dx3", "projects",
    "Deus Ex 3 - Director's Cut", "files", "bigfile.filelist")

LOCALE_DEFAULT = 0xFFFFFFFF

# ---------------------------------------------------------------- name hash
def name_hash(path):
    h = 0xFFFFFFFF
    for c in path.lower():
        h ^= (ord(c) & 0xFF) << 24
        for _ in range(8):
            h = ((h << 1) ^ 0x04C11DB7) if h & 0x80000000 else (h << 1)
            h &= 0xFFFFFFFF
    return h ^ 0xFFFFFFFF


def load_filelist(path=FILELIST):
    names = {}
    with open(path, "r", encoding="ascii", errors="replace") as f:
        for line in f:
            line = line.strip().lower()
            if line:
                names[name_hash(line)] = line
    return names


# ---------------------------------------------------------------- bigfile
class Entry(object):
    __slots__ = ("hash", "size", "offset", "locale", "extra")

    def __init__(self, h, size, offset, locale, extra):
        self.hash, self.size, self.offset = h, size, offset
        self.locale, self.extra = locale, extra

    def __repr__(self):
        return "Entry(%08X loc=%08X size=%d off=%d)" % (
            self.hash, self.locale, self.size, self.offset)


class BigFile(object):
    def __init__(self, path000=BIGFILE):
        self.path000 = path000
        with open(path000, "rb") as f:
            self.alignment, = struct.unpack("<I", f.read(4))
            self.base_path = f.read(64).split(b"\0")[0].decode("ascii")
            count, = struct.unpack("<I", f.read(4))
            hashes = struct.unpack("<%dI" % count, f.read(4 * count))
            self.entries = []
            for i in range(count):
                size, off, loc, extra = struct.unpack("<4I", f.read(16))
                self.entries.append(Entry(hashes[i], size, off, loc, extra))
        self.by_hash = {}
        for e in self.entries:
            self.by_hash.setdefault(e.hash, []).append(e)
        self.max_sectors = self.alignment // 2048

    def find(self, name, locale=None):
        """All entries for `name` (or hash), optionally locale-filtered."""
        h = name if isinstance(name, int) else name_hash(name)
        found = self.by_hash.get(h, [])
        if locale is not None:
            found = [e for e in found if e.locale == locale]
        return found

    def part_path(self, index):
        return os.path.splitext(self.path000)[0] + ".%03d" % index

    def read(self, entry):
        part = entry.offset // self.max_sectors
        byte_off = (entry.offset % self.max_sectors) * 2048
        with open(self.part_path(part), "rb") as f:
            f.seek(byte_off)
            data = f.read(entry.size)
        if len(data) != entry.size:
            raise IOError("short read: entry spans parts? %r" % entry)
        return data


# ---------------------------------------------------------------- CDRM
def _align16(v):
    return (v + 15) & ~15


def cdrm_unwrap(data):
    """-> (payload, info). info preserves version/block size for re-wrap."""
    if data[:4] != b"CDRM":
        raise ValueError("not CDRM")
    version, = struct.unpack_from("<I", data, 4)
    if version == 0:
        count, = struct.unpack_from("<I", data, 8)
        table_end = 16 + count * 8
        padding = _align16(table_end) - table_end
    elif version == 2:
        count, padding = struct.unpack_from("<II", data, 8)
    else:
        raise ValueError("CDRM version %d unsupported" % version)

    blocks = []
    for i in range(count):
        flags, csize = struct.unpack_from("<II", data, 16 + i * 8)
        blocks.append(((flags >> 8) & 0xFFFFFF, flags & 0xFF, csize))

    pos = 16 + count * 8 + padding
    out = bytearray()
    block_usizes = []
    for usize, btype, csize in blocks:
        chunk = data[pos:pos + csize]
        if btype == 1:
            if csize != usize:
                raise ValueError("stored block size mismatch")
            out += chunk
            out += b"\0" * (_align16(csize) - csize)
        elif btype == 2:
            raw = zlib.decompress(chunk)
            if len(raw) != usize:
                raise ValueError("inflate size mismatch")
            out += raw
            out += b"\0" * (_align16(usize) - usize)
        else:
            raise ValueError("block type %d" % btype)
        block_usizes.append(usize)
        pos += _align16(csize)
    # trim trailing pad of the final block
    total = sum(_align16(u) for u in block_usizes[:-1]) + block_usizes[-1]
    info = {"version": version, "block_usizes": block_usizes}
    return bytes(out[:total]), info


def cdrm_wrap(payload, info):
    """Re-wrap payload mirroring the original block layout (same usizes).

    The unwrapped stream places each block at a 16-aligned position, so
    chunk i starts at sum(align16(usize) for earlier blocks).
    """
    usizes = list(info["block_usizes"])
    version = info["version"]
    chunks, pos = [], 0
    for u in usizes:
        chunk = payload[pos:pos + u]
        if len(chunk) != u:
            raise ValueError("payload does not match block layout")
        chunks.append(chunk)
        pos += _align16(u)
    if _align16(pos) < _align16(len(payload)):
        raise ValueError("payload larger than original block layout")
    # compress each block; store it raw (type 1) when zlib does not help,
    # exactly like the original packer — the engine chokes on blocks whose
    # compressed size exceeds their uncompressed size
    blobs = []
    for c in chunks:
        z = zlib.compress(c, 9)
        if len(z) >= len(c):
            blobs.append((1, c))
        else:
            blobs.append((2, z))
    count = len(blobs)
    if version == 0:
        head = struct.pack("<4sIII", b"CDRM", 0, count, 0)
        table_end = 16 + count * 8
        padding = _align16(table_end) - table_end
    else:
        table_end = 16 + count * 8
        padding = _align16(table_end) - table_end
        head = struct.pack("<4sIII", b"CDRM", 2, count, padding)
    out = bytearray(head)
    for u, (btype, b) in zip(usizes, blobs):
        out += struct.pack("<II", (u << 8) | btype, len(b))
    out += b"\0" * padding
    for btype, b in blobs:
        out += b
        out += b"\0" * (_align16(len(b)) - len(b))
    return bytes(out)


# ---------------------------------------------------------------- DRM v21
SECTION_TYPES = {0: "Generic", 1: "Empty", 2: "Animation", 5: "RenderResource",
                 6: "Wave", 7: "DTPData", 8: "Script", 9: "ShaderLib",
                 10: "Material", 11: "Object", 12: "RenderMesh",
                 13: "CollisionMesh", 14: "StreamGroupList"}


class Section(object):
    __slots__ = ("index", "id", "type", "u05", "u06", "flags", "spec",
                 "header_size", "resolver_off", "data_off", "data_size")

    @property
    def type_name(self):
        return SECTION_TYPES.get(self.type, "?%d" % self.type)

    def __repr__(self):
        return "Section(#%d id=%08X %s data@%d+%d hdr=%d)" % (
            self.index, self.id, self.type_name, self.data_off,
            self.data_size, self.header_size)


def drm_parse(blob):
    """Parse an *uncompressed* DRM v21 blob. Returns (meta, sections)."""
    (version, dep04_size, dep08_size, unk0C, unk10, flags,
     nsec, unk1C) = struct.unpack_from("<8I", blob, 0)
    if version != 21:
        raise ValueError("DRM version %d" % version)
    if unk0C != 0:
        raise ValueError("unk0C != 0 unsupported")
    pos = 32
    heads = []
    for i in range(nsec):
        dsize, = struct.unpack_from("<I", blob, pos)
        stype, u05 = blob[pos + 4], blob[pos + 5]
        u06, = struct.unpack_from("<H", blob, pos + 6)
        sflags, sid, spec = struct.unpack_from("<III", blob, pos + 8)
        heads.append((dsize, stype, u05, u06, sflags, sid, spec))
        pos += 20
    pos += dep08_size + dep04_size
    if flags & 1:
        pos = _align16(pos)
    sections = []
    for i, (dsize, stype, u05, u06, sflags, sid, spec) in enumerate(heads):
        s = Section()
        s.index, s.id, s.type = i, sid, stype
        s.u05, s.u06, s.flags, s.spec = u05, u06, sflags, spec
        s.header_size = (sflags & 0xFFFFFF00) >> 8
        s.resolver_off = pos
        pos += s.header_size
        if flags & 1:
            pos = _align16(pos)
        s.data_off, s.data_size = pos, dsize
        pos += dsize
        if flags & 1:
            pos = _align16(pos)
        sections.append(s)
    meta = {"flags": flags, "dep04": dep04_size, "dep08": dep08_size,
            "end": pos}
    return meta, sections


# ---------------------------------------------------------------- PCD9
class Pcd9(object):
    __slots__ = ("format", "data_size", "unk0C", "width", "height", "bpp",
                 "unk16", "mips", "flags", "unk1A", "payload_off")

    def __repr__(self):
        f = self.format
        name = {21: "ARGB8"}.get(f) or struct.pack("<I", f).decode("ascii")
        return "PCD9(%s %dx%d mips=%d flags=%04X size=%d)" % (
            name, self.width, self.height, self.mips, self.flags,
            self.data_size)


def pcd9_parse(blob, off=0):
    if blob[off:off + 4] != b"PCD9":
        return None
    t = Pcd9()
    (t.format, t.data_size, t.unk0C, t.width, t.height, t.bpp, t.unk16,
     mips_m1, t.flags, t.unk1A) = struct.unpack_from("<IIIHHHBBHH", blob,
                                                     off + 4)
    t.mips = mips_m1 + 1
    t.payload_off = off + 28
    return t


# ---------------------------------------------------------------- misc
def write_png(path, rows):
    """rows: list of rows of (r,g,b,a) tuples."""
    h = len(rows)
    w = len(rows[0])
    raw = b"".join(
        b"\0" + bytes(v for px in row for v in px) for row in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))
