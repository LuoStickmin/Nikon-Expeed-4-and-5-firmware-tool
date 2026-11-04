import sys, struct

d = open(sys.argv[1], "rb").read()
base = 0x90000000

runs = []
cur = []

for i in range(0, len(d) - 4, 4):
    w = struct.unpack_from("<I", d, i)[0]
    good = (0x90000000 <= w < 0x90200000) and (w & 1) == 1
    if good:
        cur.append((i, w))
    else:
        if len(cur) >= 4:
            runs.append(cur)
        cur = []
if len(cur) >= 4:
    runs.append(cur)

print("found %d runs" % len(runs))
for run in runs[:50]:
    print("\ntable at 0x%X  len=%d" % (run[0][0], len(run)))
    print("  " + ", ".join("0x%08X" % w for _, w in run[:16]))
