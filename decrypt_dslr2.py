#!/usr/bin/env python3
"""Decrypt (or accept plaintext) and split a legacy Nikon firmware image.

The module directory and both CRC levels are validated before anything is
written, so a wrong key or a damaged image exits with an error instead of
leaving a silently corrupt .modules directory behind.

    python decrypt_dslr2.py --key key_all.json --firmware D750_0115.bin \
        --out D750_0115.dec

Pair it with repack_firmware.py --modules-dir ... --selftest to prove that an
unpack/repack cycle reproduces the input image byte for byte.
"""

import argparse
import os
import sys

import decrypt_firmware as fw
from repack_firmware import read_directory


def detect(raw):
    if raw[0:32] == b" " * 32:
        return 0
    if raw[0x20:0x40] == b" " * 32:
        return 0x20
    raise SystemExit("no 32-space label")


def main():
    ap = argparse.ArgumentParser(
        description="Decrypt/validate a legacy Nikon image and split its modules.")
    ap.add_argument("--key", required=True)
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true",
                    help="replace --out and its .modules directory if they exist")
    a = ap.parse_args()

    fw.refuse_clobber(a.out, a.force)
    fw.refuse_clobber(a.out + ".modules", a.force)
    t1, t2, t3 = fw.load_key(a.key)
    try:
        with open(a.firmware, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        fw.die(fw.EX_USAGE, str(exc))
    if len(raw) <= 0x40:
        fw.die(fw.EX_SCHEME, "%s is only %d bytes" % (a.firmware, len(raw)))
    hdr = detect(raw)
    fw.HDR = hdr

    # Validate as plaintext first; only XOR if that fails, so an already
    # decrypted container is never damaged by a second XOR.
    plain_error = None
    try:
        plain = raw
        mods = read_directory(memoryview(raw)[hdr:])
        mode = "plaintext"
    except ValueError as exc:
        plain_error = str(exc)
        plain = fw.decrypt(raw, t1, t2, t3)
        try:
            mods = read_directory(memoryview(plain)[hdr:])
        except ValueError as exc2:
            fw.die(fw.EX_SANITY,
                   "%s fails as plaintext (%s) and after decrypting with the given "
                   "key (%s); nothing written." % (a.firmware, plain_error, exc2))
        mode = "encrypted"

    print("header=0x%X count=%d mode=%s" % (hdr, len(mods), mode))
    start = 48 + 32 * len(mods)
    for m in mods:
        tail = m["tag"].split(b"\0")[0].decode("ascii", "replace")
        print("  %-20s off=0x%08X len=0x%08X tail=%s"
              % (m["name"], start, len(m["payload"]) + 2, tail))
        start += len(m["payload"]) + 2

    with open(a.out, "wb") as fh:
        fh.write(plain)
    moddir = a.out + ".modules"
    os.makedirs(moddir, exist_ok=True)
    for m in mods:
        path = os.path.join(moddir, m["name"])
        with open(path, "wb") as fh:
            fh.write(m["payload"])
        print("  wrote %s (%d bytes)" % (path, len(m["payload"])))
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
