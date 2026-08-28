"""Minimal AS2 (SWF ActionScript 2) stream tools for surgical patches."""
import struct

OPS = {0x00: 'End', 0x04: 'NextFrame', 0x06: 'Play', 0x07: 'Stop',
       0x0A: 'Add', 0x0B: 'Subtract', 0x0C: 'Multiply', 0x0D: 'Divide',
       0x0E: 'Equals', 0x0F: 'Less', 0x10: 'And', 0x11: 'Or', 0x12: 'Not',
       0x13: 'StringEquals', 0x17: 'Pop', 0x1C: 'GetVariable',
       0x1D: 'SetVariable', 0x21: 'StringAdd', 0x22: 'GetProperty',
       0x23: 'SetProperty', 0x24: 'CloneSprite', 0x26: 'Trace',
       0x33: 'AsciiToChar', 0x34: 'GetTime', 0x3A: 'Delete',
       0x3B: 'Delete2', 0x3C: 'DefineLocal', 0x3D: 'CallFunction',
       0x3E: 'Return', 0x40: 'NewObject', 0x41: 'DefineLocal2',
       0x42: 'InitArray', 0x43: 'InitObject', 0x44: 'TypeOf',
       0x46: 'Enumerate', 0x47: 'Add2', 0x48: 'Less2', 0x49: 'Equals2',
       0x4A: 'ToNumber', 0x4B: 'ToString', 0x4C: 'PushDuplicate',
       0x4D: 'StackSwap', 0x4E: 'GetMember', 0x4F: 'SetMember',
       0x50: 'Increment', 0x51: 'Decrement', 0x52: 'CallMethod',
       0x53: 'NewMethod', 0x54: 'InstanceOf', 0x55: 'Enumerate2',
       0x60: 'BitAnd', 0x61: 'BitOr', 0x62: 'BitXor', 0x63: 'BitLShift',
       0x64: 'BitRShift', 0x66: 'StrictEquals', 0x67: 'Greater',
       0x81: 'GotoFrame', 0x83: 'GetURL', 0x87: 'StoreRegister',
       0x88: 'ConstantPool', 0x8A: 'WaitForFrame', 0x8B: 'SetTarget',
       0x8C: 'GotoLabel', 0x8E: 'DefineFunction2', 0x94: 'With',
       0x96: 'Push', 0x99: 'Jump', 0x9A: 'GetURL2', 0x9B: 'DefineFunction',
       0x9D: 'If', 0x9E: 'Call', 0x9F: 'GotoFrame2'}


def actions(d, p, end):
    """Yield (off, code, body_off, body_len, next_off)."""
    while p < end:
        code = d[p]
        if code == 0:
            yield (p, 0, p + 1, 0, p + 1)
            p += 1
            continue
        if code >= 0x80:
            ln, = struct.unpack_from('<H', d, p + 1)
            yield (p, code, p + 3, ln, p + 3 + ln)
            p += 3 + ln
        else:
            yield (p, code, p + 1, 0, p + 1)
            p += 1


def parse_pool(d, body, ln):
    n, = struct.unpack_from('<H', d, body)
    q = body + 2
    out = []
    for _ in range(n):
        e = d.index(b'\0', q)
        out.append(d[q:e].decode('latin1'))
        q = e + 1
    return out


def push_items(d, body, ln):
    """Yield (item_off, type, value) for a Push action body."""
    q = body
    end = body + ln
    while q < end:
        t = d[q]
        q += 1
        if t == 0:
            e = d.index(b'\0', q)
            yield (q - 1, t, d[q:e].decode('latin1'))
            q = e + 1
        elif t == 1:
            v, = struct.unpack_from('<f', d, q)
            yield (q - 1, t, v)
            q += 4
        elif t == 2:
            yield (q - 1, t, None)
        elif t == 3:
            yield (q - 1, t, 'undefined')
        elif t == 4:
            yield (q - 1, t, 'reg%d' % d[q])
            q += 1
        elif t == 5:
            yield (q - 1, t, bool(d[q]))
            q += 1
        elif t == 6:
            v, = struct.unpack('<d', d[q + 4:q + 8] + d[q:q + 4])
            yield (q - 1, t, v)
            q += 8
        elif t == 7:
            v, = struct.unpack_from('<i', d, q)
            yield (q - 1, t, v)
            q += 4
        elif t == 8:
            yield (q - 1, t, ('c8', d[q]))
            q += 1
        elif t == 9:
            v, = struct.unpack_from('<H', d, q)
            yield (q - 1, t, ('c16', v))
            q += 2
        else:
            raise ValueError('push type %d at %#x' % (t, q - 1))


def disasm(d, p, end, pool=None, resolve=True):
    """Return list of readable lines."""
    lines = []
    for off, code, body, ln, nxt in actions(d, p, end):
        name = OPS.get(code, 'op%02X' % code)
        if code == 0x88:
            pool = parse_pool(d, body, ln)
            lines.append((off, 'ConstantPool[%d]' % len(pool)))
        elif code == 0x96:
            vals = []
            for _, t, v in push_items(d, body, ln):
                if isinstance(v, tuple) and pool and v[1] < len(pool):
                    vals.append('%s:%r' % (v[0], pool[v[1]]))
                else:
                    vals.append(repr(v))
            lines.append((off, 'Push ' + ', '.join(vals)))
        elif code in (0x99, 0x9D):
            delta, = struct.unpack_from('<h', d, body)
            lines.append((off, '%s -> %#x' % (name, nxt + delta)))
        elif code in (0x9B, 0x8E):
            e = d.index(b'\0', body if code == 0x9B else body + 0)
            lines.append((off, name))
        else:
            lines.append((off, name))
    return lines, pool
