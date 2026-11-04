import sys, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

d = open(sys.argv[1], "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

ptrs = [struct.unpack_from("<I", d, 0x20 + i * 4)[0] for i in range(8)]
print("vector pointers:", [hex(p) for p in ptrs])

for base in [0x90000000, 0x90200000, 0x80000000, 0]:
    print("\nbase 0x%08X" % base)
    for p in ptrs[:6]:
        off = p - base
        if 0 <= off < len(d) - 16:
            ins = list(md.disasm(d[off:off+16], off))[:3]
            txt = "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins)
            print("  ptr 0x%08X -> off 0x%06X: %s" % (p, off, txt))
