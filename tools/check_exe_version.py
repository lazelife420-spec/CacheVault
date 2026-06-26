"""Check if a version string exists in the exe binary using bytes search."""
import sys
from pathlib import Path

exe = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/CacheVault.exe")
data = exe.read_bytes()

for ver_str in ["0.1.4", "0.1.3"]:
    for enc, label in [("ascii", "ASCII"), ("utf-8", "UTF-8"), ("utf-16-le", "UTF-16LE"), ("utf-16-be", "UTF-16BE")]:
        ver_bytes = ver_str.encode(enc)
        idx = data.find(ver_bytes)
        if idx >= 0:
            print(f"{ver_str} found as {label} at index: {idx}")
            break
    else:
        print(f"{ver_str} NOT found in any encoding")
