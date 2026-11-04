import sys, struct
import numpy as np

p = sys.argv[1]
d = open(p, "rb").read()
print("file:", p, "size:", len(d))

bases = [0, 0x08000000, 0x10000000, 0x20000000, 0x40000000,
         0x80000000, 0x90000000, 0xA0000000]

print("\n--- pointer-like words in first 64KB ---")
w = np.frombuffer(d[:min(len(d), 0x10000)], dtype="<u4")
for b in bases:
    cnt = int(np.count_nonzero((w >= b) & (w < b + len(d))))
    print("  base 0x%08X : %d" % (b, cnt))

print("\n--- first 64 bytes as words ---")
for i in range(0, 64, 4):
    print("  0x%02X: 0x%08X" % (i, struct.unpack_from("<I", d, i)[0]))

print("\n--- string pointer search ---")
for s in [b"Nikon", b"Ver.1.15a", b"T-Kernel"]:
    off = d.find(s)
    if off < 0:
        continue
    print("string %r at 0x%X" % (s, off))
    for b in bases:
        ptr = struct.pack("<I", b + off)
        pos = d.find(ptr)
        if pos >= 0:
            print("  base 0x%08X -> pointer found at 0x%X" % (b, pos))
