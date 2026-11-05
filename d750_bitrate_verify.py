#!/usr/bin/env python3
"""Independent verifier for the D750 64/60 Mbps movie bit-rate patch.

Reads the stock encrypted image, the patched/repacked encrypted image and the
patched module.  It decrypts both images with the recovered key, parses the
container directory itself, checks both CRC levels, and then checks the movie
table row by row.  It deliberately does not import d750_bitrate_patch, so a
bug in the writer is not automatically repeated in the checker.

    python d750_bitrate_verify.py \
        --stock D750_0115.bin \
        --patched D750_0115.hq64.out/D750_0115.hq64.bin \
        --module D750_0115.hq64.out/b1010_115a.hq64.bin \
        --key key_all.json \
        --json D750_0115.hq64.out/verify_report.json
"""

import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path

import decrypt_firmware as fw

TABLE_ENTRY1 = 0x2AA9AC
ENTRY_STRIDE = 0x1C
HQ_INDICES = (0, 2, 4, 6, 8)
STOCK_HQ = ((42_000_000, 35_000_000),
            (42_000_000, 35_000_000),
            (24_000_000, 20_000_000),
            (24_000_000, 20_000_000),
            (24_000_000, 20_000_000))
STOCK_NQ = ((24_000_000, 20_000_000),
            (24_000_000, 20_000_000),
            (12_000_000, 10_000_000),
            (12_000_000, 10_000_000))
TARGET = (64_000_000, 60_000_000)
TARGET_HEX = "0x03D09000/0x03938700"
TABLE_ENTRIES = 22


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def detect_hdr(raw):
    for hdr in (0, 0x20):
        if raw[hdr:hdr + 32] == b" " * 32:
            return hdr
    raise ValueError("no 32-space label at 0x00 or 0x20")


def decrypt_image(raw, hdr, key):
    fw.HDR = hdr
    return fw.decrypt(raw, *key)


def parse_container(plain, hdr):
    body = memoryview(plain)[hdr:]
    if body[:32] != b" " * 32:
        raise ValueError("bad space label")
    count, dirsize = struct.unpack_from(">II", body, 0x20)
    if count != 3 or dirsize != 0x90:
        raise ValueError("unexpected directory: count=%d dirsize=0x%X" % (count, dirsize))
    mods = []
    expected = dirsize
    for i in range(count):
        off = 0x30 + i * 32
        name = bytes(body[off:off + 16]).rstrip(b"\0").decode("ascii")
        start, length = struct.unpack_from(">II", body, off + 16)
        tag = bytes(body[off + 24:off + 32])
        if start != expected or length < 2:
            raise ValueError("bad extent for %s" % name)
        payload = bytes(body[start:start + length - 2])
        stored = struct.unpack_from(">H", body, start + length - 2)[0]
        crc = binascii.crc_hqx(payload, 0)
        if stored != crc:
            raise ValueError("module CRC mismatch for %s: 0x%04X != 0x%04X"
                             % (name, stored, crc))
        mods.append({"name": name, "start": start, "length": length,
                     "tag": tag, "payload": payload, "crc": crc})
        expected = start + length
    if expected != len(body) - fw.TRAILER:
        raise ValueError("module chain does not end at the trailer")
    if body[-14:] != b"\0" * 14:
        raise ValueError("bad trailer padding")
    pkg_stored = struct.unpack_from(">H", body, len(body) - fw.TRAILER)[0]
    pkg_crc = binascii.crc_hqx(body[:-fw.TRAILER], 0)
    if pkg_stored != pkg_crc:
        raise ValueError("package CRC mismatch: 0x%04X != 0x%04X"
                         % (pkg_stored, pkg_crc))
    return mods, pkg_crc


def table_rows(data):
    rows = []
    for i in range(TABLE_ENTRIES):
        off = TABLE_ENTRY1 + i * ENTRY_STRIDE
        if off + ENTRY_STRIDE > len(data):
            raise ValueError("table truncated at entry %d" % (i + 1))
        a, b, flag, ceiling, tb_num, tb_den, fps = struct.unpack(
            "<7I", data[off:off + ENTRY_STRIDE])
        rows.append({"entry": i + 1, "offset": off, "a": a, "b": b,
                     "flag": flag, "ceiling": ceiling, "tb": (tb_num, tb_den),
                     "fps": fps})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", required=True)
    ap.add_argument("--patched", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args(argv)

    key = fw.load_key(args.key)
    stock_raw = Path(args.stock).read_bytes()
    patched_raw = Path(args.patched).read_bytes()
    module = Path(args.module).read_bytes()
    stock_hdr = detect_hdr(stock_raw)
    patched_hdr = detect_hdr(patched_raw)
    if stock_hdr != patched_hdr:
        raise ValueError("packaging changed")
    stock_plain = decrypt_image(stock_raw, stock_hdr, key)
    patched_plain = decrypt_image(patched_raw, patched_hdr, key)

    stock_mods, stock_pkg = parse_container(stock_plain, stock_hdr)
    patched_mods, patched_pkg = parse_container(patched_plain, patched_hdr)
    if [m["name"] for m in stock_mods] != [m["name"] for m in patched_mods]:
        raise ValueError("module name/order changed")
    if [m["length"] for m in stock_mods] != [m["length"] for m in patched_mods]:
        raise ValueError("module size changed")
    if [m["tag"] for m in stock_mods] != [m["tag"] for m in patched_mods]:
        raise ValueError("directory tag changed")

    # Other two modules must be byte-identical.
    for a, b in zip(stock_mods, patched_mods):
        if a["name"] != "b1010_115a.bin" and a["payload"] != b["payload"]:
            raise ValueError("%s changed unexpectedly" % a["name"])
    patched_b = next(m for m in patched_mods if m["name"] == "b1010_115a.bin")
    if patched_b["payload"] != module:
        raise ValueError("repacked b1010 payload does not match the patched module")

    stock_rows = table_rows(next(m for m in stock_mods if m["name"] == "b1010_115a.bin")["payload"])
    patched_rows = table_rows(patched_b["payload"])

    # Stock table shape.
    for n, idx in enumerate(HQ_INDICES):
        r = stock_rows[idx]
        if (r["a"], r["b"]) != STOCK_HQ[n]:
            raise ValueError("stock HQ row %d is %s, expected %s"
                             % (idx + 1, (r["a"], r["b"]), STOCK_HQ[n]))
    for n, idx in enumerate((1, 3, 5, 7)):
        r = stock_rows[idx]
        if (r["a"], r["b"]) != STOCK_NQ[n]:
            raise ValueError("stock NQ row %d is %s, expected %s"
                             % (idx + 1, (r["a"], r["b"]), STOCK_NQ[n]))

    # Patched HQ rows and untouched NQ / 720 / 480 rows.
    for idx in HQ_INDICES:
        r = patched_rows[idx]
        if (r["a"], r["b"]) != TARGET:
            raise ValueError("patched HQ row %d is %s, expected %s"
                             % (idx + 1, (r["a"], r["b"]), TARGET))
        if TARGET[0] >= r["ceiling"] or TARGET[1] >= r["ceiling"]:
            raise ValueError("row %d target exceeds ceiling" % (idx + 1))
    for idx in (1, 3, 5, 7):
        if (patched_rows[idx]["a"], patched_rows[idx]["b"]) != (stock_rows[idx]["a"], stock_rows[idx]["b"]):
            raise ValueError("NQ row %d changed" % (idx + 1))
    for idx in range(9, TABLE_ENTRIES):
        if patched_rows[idx] != stock_rows[idx]:
            raise ValueError("720/480 row %d changed" % (idx + 1))

    # Exact byte-level diff of the whole decrypted image.
    diffs = [i for i, (a, b) in enumerate(zip(stock_plain, patched_plain)) if a != b]
    expected = set()
    module_start = patched_b["start"] + patched_hdr
    for idx in HQ_INDICES:
        off = module_start + TABLE_ENTRY1 + idx * ENTRY_STRIDE
        expected.update(range(off, off + 8))
    # Module CRC and package CRC are expected to change too.
    expected.update(range(module_start + patched_b["length"] - 2,
                          module_start + patched_b["length"]))
    expected.update(range(len(patched_plain) - fw.TRAILER,
                          len(patched_plain) - fw.TRAILER + 2))
    outside = [i for i in diffs if i not in expected]
    if outside:
        raise ValueError("%d byte(s) changed outside the bitrate fields/CRCs; first 0x%X"
                         % (len(outside), outside[0]))

    doc = {
        "stock": {
            "path": str(Path(args.stock)),
            "sha256": sha256(stock_raw),
            "packaging": stock_hdr,
            "modules": [{"name": m["name"], "start": m["start"], "length": m["length"],
                         "crc": "0x%04X" % m["crc"], "tag_hex": m["tag"].hex()}
                        for m in stock_mods],
            "package_crc": "0x%04X" % stock_pkg,
            "movie_rows": [{"entry": r["entry"], "offset": "0x%X" % r["offset"],
                            "a": r["a"], "b": r["b"], "ceiling": r["ceiling"]}
                           for r in stock_rows[:9]],
        },
        "patched": {
            "path": str(Path(args.patched)),
            "sha256": sha256(patched_raw),
            "module_sha256": sha256(module),
            "modules": [{"name": m["name"], "start": m["start"], "length": m["length"],
                         "crc": "0x%04X" % m["crc"], "tag_hex": m["tag"].hex()}
                        for m in patched_mods],
            "package_crc": "0x%04X" % patched_pkg,
            "movie_rows": [{"entry": r["entry"], "offset": "0x%X" % r["offset"],
                            "a": r["a"], "b": r["b"], "ceiling": r["ceiling"]}
                           for r in patched_rows[:9]],
        },
        "table": {
            "entry1_offset": "0x%X" % TABLE_ENTRY1,
            "stride": ENTRY_STRIDE,
            "hq_rows": [i + 1 for i in HQ_INDICES],
            "target": list(TARGET),
            "target_hex_le": TARGET_HEX,
        },
        "diff": {
            "decrypted_bytes_changed": len(diffs),
            "expected_field_bytes": len(expected),
            "outside_expected": len(outside),
            "module_crc_before": "0x%04X" % next(m for m in stock_mods if m["name"] == "b1010_115a.bin")["crc"],
            "module_crc_after": "0x%04X" % patched_b["crc"],
            "package_crc_before": "0x%04X" % stock_pkg,
            "package_crc_after": "0x%04X" % patched_pkg,
        },
        "checks": {
            "directory": "3 modules, same names/sizes/tags",
            "module_crcs": "all pass",
            "package_crc": "pass",
            "b1010_matches_patched_module": True,
            "other_modules_identical": True,
            "hq_rows_at_target": True,
            "nq_and_720_480_rows_unchanged": True,
            "differences_confined_to_fields_and_crcs": True,
        },
    }
    Path(args.json).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")

    print("stock    %s" % doc["stock"]["sha256"])
    print("patched  %s" % doc["patched"]["sha256"])
    print("module   %s" % doc["patched"]["module_sha256"])
    print("package CRC 0x%04X -> 0x%04X" % (stock_pkg, patched_pkg))
    print("b1010 CRC   0x%04X -> 0x%04X"
          % (next(m for m in stock_mods if m["name"] == "b1010_115a.bin")["crc"],
             patched_b["crc"]))
    print("changed decrypted bytes: %d (fields+CRCs), outside: %d"
          % (len(diffs), len(outside)))
    print("HQ rows at target:")
    for idx in HQ_INDICES:
        r = patched_rows[idx]
        print("  entry %d @0x%X  %d / %d" % (r["entry"], r["offset"], r["a"], r["b"]))
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
