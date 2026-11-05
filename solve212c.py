import sys, struct, binascii
import numpy as np
import extract_key as ek
import decrypt_firmware as fw
from fill_t3 import load

imgs = load("output")
norm = ek.recover_family(imgs[0]["sec"])
t1, _ = ek.fix_constant(imgs[0]["sec"], norm)
triple = [(i["name"], i["sha"], i["sec"]) for i in imgs]
obs = ek.collect_observations(triple, t1)
t2d, t3d = ek.solve_tables(obs)
t2 = np.array([t2d[i] for i in range(256)], dtype=np.uint8)

# 补齐 256 个键，跑 stage 5 修正
t3 = {b: t3d.get(b, 0) for b in range(256)}
changed = ek.correct_t3(triple, t1, t2, t3)
print("correct_t3 changed %d entries" % len(changed))

rep = [i for i in imgs if i["name"] == "D750_0101.bin"][0]

def validate_dslr(body):
    count, dirsize = struct.unpack_from(">II", body, 0x20)
    if dirsize != 48 + 32 * count:
        raise ValueError("bad dirsize")
    mods, expected = [], dirsize
    for i in range(count):
        off = 0x30 + i * 32
        name = bytes(body[off:off+16]).split(b"\0")[0].decode("ascii", "replace")
        start, length = struct.unpack_from(">II", body, off + 16)
        if start != expected:
            raise ValueError("module %d start 0x%x != 0x%x" % (i, start, expected))
        mods.append((name, start, length))
        expected = start + length
    if expected != len(body) - 16:
        raise ValueError("last end 0x%x != 0x%x" % (expected, len(body)-16))
    for name, start, length in mods:
        module = bytes(body[start:start+length])
        stored = struct.unpack_from(">H", module, length-2)[0]
        calc = binascii.crc_hqx(module[:-2], 0)
        if calc != stored:
            raise ValueError("module %s CRC calc=0x%04x stored=0x%04x" % (name, calc, stored))
    stored = struct.unpack_from(">H", body, len(body)-16)[0]
    calc = binascii.crc_hqx(bytes(body[:-16]), 0)
    if calc != stored:
        raise ValueError("package CRC calc=0x%04x stored=0x%04x" % (calc, stored))
    return mods

def check(vals):
    arr = np.array([t3[b] for b in range(256)], dtype=np.uint8)
    for b, v in vals.items():
        arr[b] = v
    old = fw.HDR
    fw.HDR = rep["hdr"]
    plain = fw.decrypt(rep["raw"], t1, t2, arr)
    fw.HDR = old
    try:
        return True, validate_dslr(memoryview(plain)[rep["hdr"]:])
    except ValueError as e:
        return False, str(e)

print("reference:", check({190: 0x57, 191: 0x8E, 212: 0xBE}))
for c in range(256):
    ok, info = check({190: 0x57, 191: 0x8E, 212: c})
    if ok:
        print("FOUND 212=0x%02X" % c)
        sys.exit(0)
    if c % 32 == 31:
        print("tried to 0x%02X" % c)
print("none; last:", info)
