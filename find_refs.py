import sys, struct

d = open(sys.argv[1], "rb").read()
base = 0x90000000

targets = [
    b"CMoviePlayApplicationService_RequestStartPlay",
    b"CMoviePlayApplicationService_Is_Enable_CutMovie_MenuStartUp_Detail",
    b"D750_MenuList_FU-02",
    b"APPMENU",
    b"HI ISO,HIGH",
]

for t in targets:
    off = d.find(t)
    print("\n=== %r ===" % t)
    if off < 0:
        print("  not found")
        continue
    print("  string offset: 0x%08X" % off)

    for name, val in [("absolute", base + off), ("relative", off)]:
        needle = struct.pack("<I", val)
        pos, hits = 0, []
        while True:
            p = d.find(needle, pos)
            if p < 0:
                break
            hits.append(p)
            pos = p + 1
        print("  %-8s pointer 0x%08X hits: %s"
              % (name, val, [hex(x) for x in hits[:10]]))

        for p in hits[:2]:
            print("    around 0x%08X:" % p)
            for i in range(p - 16, p + 48, 4):
                if 0 <= i <= len(d) - 4:
                    print("      0x%08X: 0x%08X"
                          % (i, struct.unpack_from("<I", d, i)[0]))
