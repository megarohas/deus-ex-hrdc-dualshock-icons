"""Retarget the controller-layout platform switch: WIN -> PS3 template.

The options movies pick an exported layout sprite via an AS2 chain:
    if (platform === PLATFORM_PS3)    name = 'template_PS3';  ...
    if (platform === PLATFORM_XBOX360) name = 'template_XBOX'; ...
    if (platform === PLATFORM_WIN)    name = isOnlive ? 'template_OnLive'
                                                      : 'template_PC';
Patching the WIN comparison's If offset to jump straight into the PS3
branch replays the authored PS3 path (name + its positioning registers).
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import as2
from swfdump import walk, rect_skip, inflate_cfx


def _pool_index(pool, name):
    try:
        return pool.index(name)
    except ValueError:
        return None


def _push_refs(swf, body, ln, idx):
    """Does this Push reference constant `idx`?"""
    for _, t, v in as2.push_items(swf, body, ln):
        if isinstance(v, tuple) and v[1] == idx:
            return True
    return False


def patch_swf(swf):
    """Return (patched_swf, n_patches). Pattern-driven, offset-free."""
    swf = bytearray(swf)
    p = rect_skip(swf, 8)
    p += 4
    n = 0
    for path, frame, code, off, ln, tag_off in walk(bytes(swf), p,
                                                    len(swf)):
        if code not in (12, 59):
            continue
        body = off + (2 if code == 59 else 0)
        acts = list(as2.actions(bytes(swf), body, off + ln))
        pool = None
        for aoff, acode, ab, al, anext in acts:
            if acode == 0x88:
                pool = as2.parse_pool(bytes(swf), ab, al)
                break
        if not pool:
            continue
        i_win = _pool_index(pool, "PLATFORM_WIN")
        i_ps3 = _pool_index(pool, "template_PS3")
        i_pc = _pool_index(pool, "template_PC")
        if i_win is None or i_ps3 is None or i_pc is None:
            continue
        # branch entry: Push 'template_PS3' immediately followed by
        # StoreRegister
        entries = []
        for k, (aoff, acode, ab, al, anext) in enumerate(acts):
            if acode != 0x96 or not _push_refs(swf, ab, al, i_ps3):
                continue
            if k + 1 < len(acts) and acts[k + 1][1] == 0x87:
                entries.append(aoff)
        # WIN comparison: Push(PLATFORM_WIN), GetMember, StrictEquals, If
        for k, (aoff, acode, ab, al, anext) in enumerate(acts):
            if acode != 0x96 or not _push_refs(swf, ab, al, i_win):
                continue
            if k + 3 >= len(acts):
                continue
            if (acts[k + 1][1], acts[k + 2][1],
                    acts[k + 3][1]) != (0x4E, 0x66, 0x9D):
                continue
            if len(entries) != 1:
                raise RuntimeError("expected 1 PS3 branch entry, got %d"
                                   % len(entries))
            if_off, _, if_body, if_len, if_next = acts[k + 3]
            old_delta, = struct.unpack_from("<h", swf, if_body)
            new_delta = entries[0] - if_next
            struct.pack_into("<h", swf, if_body, new_delta)
            print("      swf: WIN If @%#x delta %+d -> %+d "
                  "(PS3 branch @%#x)" %
                  (if_off, old_delta, new_delta, entries[0]))
            n += 1
    return bytes(swf), n


def patch_section(sec):
    """Patch the CFX movie inside a DTPData section blob, size-preserving.

    Returns new section bytes, or None when no switch pattern exists."""
    c = sec.find(b"CFX")
    if c < 0:
        return None
    total, = struct.unpack_from("<I", sec, c + 4)
    dz = zlib.decompressobj()
    raw = dz.decompress(bytes(sec[c + 8:]), total - 8)
    used = len(sec) - (c + 8) - len(dz.unused_data)
    swf = b"GFX" + sec[c + 3:c + 4] + struct.pack("<I", total) + raw
    patched, n = patch_swf(swf)
    if n == 0:
        return None
    comp = zlib.compress(patched[8:], 9)
    if len(comp) > used:
        raise RuntimeError("recompressed movie larger than original slot "
                           "(%d > %d)" % (len(comp), used))
    out = bytearray(sec)
    out[c + 8:c + 8 + used] = comp + b"\0" * (used - len(comp))
    return bytes(out)


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    out, n = patch_swf(data)
    print("patched %d switch(es)" % n)
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(out)
