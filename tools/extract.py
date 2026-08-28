"""Extract bigfile entries by name to work/extracted/ (raw, as stored)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work", "extracted")
os.makedirs(WORK, exist_ok=True)

big = dxhr.BigFile()
for name in sys.argv[1:]:
    for e in big.find(name):
        base = os.path.basename(name.replace("\\", os.sep))
        if e.locale != dxhr.LOCALE_DEFAULT:
            base = "%08X_%s" % (e.locale, base)
        dst = os.path.join(WORK, base)
        with open(dst, "wb") as f:
            f.write(big.read(e))
        print("%s (locale %08X, %d bytes) -> %s" %
              (name, e.locale, e.size, dst))
