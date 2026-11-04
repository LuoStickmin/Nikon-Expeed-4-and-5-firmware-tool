import sys, struct, collections

d = open(sys.argv[1], "rb").read()
c = collections.Counter()
for i in range(0, len(d) - 4, 4):
    w = struct.unpack_from("<I", d, i)[0]
    if 0x80000000 <= w < 0xA0000000:
        c[w] += 1

print("file:", sys.argv[1], "size:", len(d))
print("--- frequent words in 0x80000000-0xA0000000 ---")
for w, n in c.most_common(40):
    print("  0x%08X  x%d" % (w, n))
