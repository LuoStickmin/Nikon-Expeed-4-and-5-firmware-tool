#!/usr/bin/env python3
import sys, os, struct, argparse
import decrypt_firmware as fw

def detect(raw):
    if raw[0:32] == b" " * 32:
        return 0
    if raw[0x20:0x40] == b" " * 32:
        return 0x20
    raise SystemExit("no 32-space label")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    t1, t2, t3 = fw.load_key(a.key)
    raw = open(a.firmware, "rb").read()
    hdr = detect(raw)
    fw.HDR = hdr
    plain = fw.decrypt(raw, t1, t2, t3)
    body = memoryview(plain)[hdr:]

    count, dirsize = struct.unpack_from(">II", body, 0x20)
    print("header=0x%X count=%d dirsize=0x%X" % (hdr, count, dirsize))
    mods, expected = [], dirsize
    for i in range(count):
        off = 0x30 + i * 32
        name = bytes(body[off:off+16]).split(b"\0")[0].decode("ascii", "replace")
        start, length = struct.unpack_from(">II", body, off + 16)
        tail = bytes(body[off+24:off+32]).split(b"\0")[0].decode("ascii", "replace")
        print("  %-20s off=0x%08X len=0x%08X tail=%s"
              % (name, start, length, tail))
        mods.append((name, start, length))

    open(a.out, "wb").write(plain)
    moddir = a.out + ".modules"
    os.makedirs(moddir, exist_ok=True)
    for name, start, length in mods:
        safe = name.replace("/", "_")
        payload = bytes(body[start:start+length-2])
        path = os.path.join(moddir, safe)
        open(path, "wb").write(payload)
        print("  wrote %s (%d bytes)" % (path, len(payload)))
    print("done")

if __name__ == "__main__":
    main()
