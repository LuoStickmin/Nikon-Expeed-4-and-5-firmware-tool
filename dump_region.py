import sys, struct

d = open(sys.argv[1], "rb").read()
start = int(sys.argv[2], 0)
end = int(sys.argv[3], 0)

print("--- hex ---")
for i in range(start, end, 16):
    ch = d[i:i+16]
    print("%08X  %s  |%s|" % (i, " ".join("%02X" % b for b in ch),
          "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))

print("\n--- address-like words (0x90xxxxxx) ---")
for i in range(start, end - 4, 4):
    w = struct.unpack_from("<I", d, i)[0]
    if 0x90000000 <= w < 0x91000000:
        print("0x%08X: 0x%08X" % (i, w))
