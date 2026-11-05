#!/usr/bin/env python3
import sys, os, json, hashlib, struct, binascii
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

t3map = {b: t3d.get(b, 0) for b in range(256)}
ek.correct_t3(triple, t1, t2, t3map)
t3map.update({190: 0x57, 191: 0x8E, 212: 0xDE})
t3 = np.array([t3map[b] for b in range(256)], dtype=np.uint8)

def validate_dslr(body):
    count, dirsize = struct.unpack_from(">II", body, 0x20)
    mods, expected = [], dirsize
    for i in range(count):
        off = 0x30 + i * 32
        name = bytes(body[off:off+16]).split(b"\0")[0].decode("ascii", "replace")
        start, length = struct.unpack_from(">II", body, off + 16)
        if start != expected:
            raise ValueError("module %d start mismatch" % i)
        mods.append((name, start, length))
        expected = start + length
    if expected != len(body) - 16:
        raise ValueError("last end mismatch")
    for name, start, length in mods:
        module = bytes(body[start:start+length])
        stored = struct.unpack_from(">H", module, length-2)[0]
        calc = binascii.crc_hqx(module[:-2], 0)
        if calc != stored:
            raise ValueError("%s CRC calc=0x%04x stored=0x%04x" % (name, calc, stored))
    stored = struct.unpack_from(">H", body, len(body)-16)[0]
    calc = binascii.crc_hqx(bytes(body[:-16]), 0)
    if calc != stored:
        raise ValueError("package CRC calc=0x%04x stored=0x%04x" % (calc, stored))
    return mods

ok_names = []
for im in imgs:
    old = fw.HDR
    fw.HDR = im["hdr"]
    plain = fw.decrypt(im["raw"], t1, t2, t3)
    fw.HDR = old
    try:
        mods = validate_dslr(memoryview(plain)[im["hdr"]:])
        print("%-20s ok  %d modules" % (im["name"], len(mods)))
        ok_names.append(im["name"])
    except Exception as e:
        print("%-20s FAIL  %s" % (im["name"], e))

tables = {"T1": t1.tobytes(), "T2": t2.tobytes(), "T3": t3.tobytes()}
check = {k: hashlib.sha256(v).hexdigest() for k, v in tables.items()}
key = {"scheme": "nikon dsrl legacy xor",
       "period_bytes": 1 << 24,
       "T1": tables["T1"].hex(), "T2": tables["T2"].hex(), "T3": tables["T3"].hex(),
       "sources": [{"file": i["name"], "sha256": i["sha"], "header": i["hdr"]} for i in imgs],
       "validated": ok_names,
       "self_check": check}
open("key_all.json", "w").write(json.dumps(key, indent=1) + "\n")
print("\nwrote key_all.json")
