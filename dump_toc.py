import numpy as np, struct
import extract_key as ek
from fill_t3 import load

imgs = load("output")
norm = ek.recover_family(imgs[0]["sec"])
t1, _ = ek.fix_constant(imgs[0]["sec"], norm)
obs = ek.collect_observations(
    [(i["name"], i["sha"], i["sec"]) for i in imgs], t1)
t2d, t3d = ek.solve_tables(obs)
t2 = np.array([t2d[i] for i in range(256)], dtype=np.uint8)
t3 = np.zeros(256, dtype=np.uint8)
for b, v in t3d.items():
    t3[b] = v

im = [i for i in imgs if i["name"] == "D750_0101.bin"][0]
body = im["raw"][im["hdr"]:]
sec = np.frombuffer(body[:65536], dtype=np.uint8).reshape(256, 256)
plain = sec ^ t1[None, :] ^ t2[:, None] ^ t3[0]
data = plain.tobytes()

print("--- first 0x200 bytes ---")
for i in range(0, 0x200, 16):
    ch = data[i:i+16]
    print("%04X  %s  |%s|" % (i, " ".join("%02X" % b for b in ch),
          "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))

count, dirsize = struct.unpack_from(">II", data, 0x20)
print("\ncount=%d dirsize=0x%X (expected 0x%X)"
      % (count, dirsize, 48 + 32 * count))

for i in range(min(count, 10)):
    off = 0x30 + i * 32
    name = data[off:off+16].rstrip(b"\0")
    start, length = struct.unpack_from(">II", data, off + 16)
    tail = data[off+24:off+32]
    print("%d  name=%-18s off=0x%08X len=0x%08X tail=%s"
          % (i, name.decode("ascii", "replace"), start, length, tail.hex()))
