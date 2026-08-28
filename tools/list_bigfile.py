"""List entries of any .000 archive with names resolved via filelist."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dxhr

path = sys.argv[1]
big = dxhr.BigFile(path)
names = dxhr.load_filelist()
print("# %s: align=%08X base=%r entries=%d" %
      (path, big.alignment, big.base_path, len(big.entries)))
for e in sorted(big.entries, key=lambda e: (names.get(e.hash, ""), e.locale)):
    print("%08X %08X %10d  %s" %
          (e.hash, e.locale, e.size, names.get(e.hash, "?UNKNOWN?")))
