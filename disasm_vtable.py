import sys, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

d = open(sys.argv[1], "rb").read()
base = 0x90000000

region_start = int(sys.argv[2], 0)
region_end = int(sys.argv[3], 0)

targets = []
for i in range(region_start, region_end, 4):
    w = struct.unpack_from("<I", d, i)[0]
    if 0x90000000 <= w < 0x90200000:
        targets.append((i, w))

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for slot, ptr in targets:
    off = (ptr - base) & ~1
    print("\nslot 0x%X -> 0x%08X (file 0x%X)" % (slot, ptr, off))
    for ins in list(md.disasm(d[off:off+64], off))[:12]:
        print("   0x%06X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
