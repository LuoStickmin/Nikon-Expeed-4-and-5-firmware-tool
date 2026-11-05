import sys
import numpy as np
import extract_key as ek
import decrypt_firmware as fw
from fill_t3 import load

imgs = load("output")

norm = ek.recover_family(imgs[0]["sec"])
t1, table = ek.fix_constant(imgs[0]["sec"], norm)
obs = ek.collect_observations(
    [(i["name"], i["sha"], i["sec"]) for i in imgs], t1)
t2d, t3d = ek.solve_tables(obs)
t2 = np.array([t2d[i] for i in range(256)], dtype=np.uint8)

rep = [i for i in imgs if i["name"] == "D750_0101.bin"][0]

def check(vals):
    t3 = np.zeros(256, dtype=np.uint8)
    for b, v in t3d.items():
        t3[b] = v
    for b, v in vals.items():
        t3[b] = v
    old = fw.HDR
    fw.HDR = rep["hdr"]
    plain = fw.decrypt(rep["raw"], t1, t2, t3)
    fw.HDR = old
    try:
        fw.validate_firmware(memoryview(plain)[rep["hdr"]:])
        return True, ""
    except ValueError as e:
        return False, str(e)

print("checking top candidates for reference...")
ok, err = check({190: 0x57, 191: 0x8E, 212: 0xBE})
print("reference result:", ok, err)

print("brute-forcing block 212...")
for c in range(256):
    ok, err = check({190: 0x57, 191: 0x8E, 212: c})
    if ok:
        print("FOUND: 190=0x57 191=0x8E 212=0x%02X" % c)
        sys.exit(0)
    if c % 32 == 31:
        print("  tried 0x%02X.." % c)
print("none passed; last error:", err)
