import sys, re
import numpy as np

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
    HAS_CS = True
except ImportError:
    HAS_CS = False

def entropy(b):
    if not b:
        return 0.0
    c = np.bincount(np.frombuffer(b, dtype=np.uint8), minlength=256).astype(np.float64)
    p = c / c.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())

p = sys.argv[1]
d = open(p, "rb").read()
print("file:", p)
print("size:", len(d))
print("overall entropy: %.3f" % entropy(d))

print("\n--- entropy per 64KB (first 4MB) ---")
for off in range(0, min(len(d), 4 * 1024 * 1024), 65536):
    print("%08X  %.3f" % (off, entropy(d[off:off+65536])))

print("\n--- ARM instruction ratio per 64KB ---")
ratios = []
for off in range(0, min(len(d), 4 * 1024 * 1024), 65536):
    chunk = d[off:off+65536]
    n = len(chunk) // 4
    if n == 0:
        continue
    w = np.frombuffer(chunk[:n * 4], dtype="<u4")
    r = float(np.count_nonzero((w >> 28) == 0xE)) / n
    ratios.append((off, r))
for off, r in ratios[:32]:
    print("%08X  %.3f" % (off, r))
if ratios:
    print("average: %.3f" % (sum(r for _, r in ratios) / len(ratios)))

print("\n--- keywords ---")
for kw in [b"Nikon", b"VxWorks", b"ThreadX", b"ITRON", b"T-Kernel", b"eCos",
           b"Linux", b"ARM", b"FR-V", b"FRFamily", b"SOFTUNE", b"__aeabi",
           b"GCC:", b"Copyright", b"Ver."]:
    pos = d.find(kw)
    print("  %-10s %s" % (kw.decode("ascii", "ignore"),
                          hex(pos) if pos >= 0 else "not found"))

print("\n--- strings (first 200KB) ---")
n = 0
for m in re.finditer(rb"[ -~]{8,}", d[:200 * 1024]):
    print("  %08X  %s" % (m.start(), m.group().decode("ascii", "ignore")))
    n += 1
    if n >= 80:
        break

print("\n--- first 64 bytes ---")
for i in range(0, 64, 16):
    ch = d[i:i+16]
    print("%04X  %s  |%s|" % (i, " ".join("%02X" % b for b in ch),
          "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))

if HAS_CS:
    print("\n--- ARM disasm first 64 bytes ---")
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for ins in list(md.disasm(d[:64], 0))[:16]:
        print("0x%04X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
    print("\n--- THUMB disasm first 64 bytes ---")
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for ins in list(md.disasm(d[:64], 0))[:20]:
        print("0x%04X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
