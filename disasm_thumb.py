import sys
from capstone import *

d = open(sys.argv[1], "rb").read()

for off, mode, name in [
    (0x250000, CS_MODE_THUMB, "THUMB"),
    (0x27D524, CS_MODE_THUMB, "THUMB"),
    (0x1200000, CS_MODE_ARM, "ARM"),
]:
    print("\n--- 0x%X  %s ---" % (off, name))
    md = Cs(CS_ARCH_ARM, mode)
    for ins in list(md.disasm(d[off:off+64], off))[:16]:
        print("0x%06X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
