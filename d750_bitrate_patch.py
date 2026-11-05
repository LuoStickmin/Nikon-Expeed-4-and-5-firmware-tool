#!/usr/bin/env python3
"""Raise the D750 1080p movie bit-rate table from stock to a 64/60 Mbps profile.

The D750 `b1010_115a.bin` module contains a 28-byte-per-entry movie quality
table.  The first two little-endian u32 fields of each entry are the two
bit-rate slots for that profile; the next u32 is a validity flag and the
following u32 is the profile's bit-rate ceiling.  The tenth entry starts the
lower-ceiling group at 0x2AAAA8 (inferred 720p/480p), so only the nine 1080p
rows (and of those, the five HQ rows listed below) are touched here.

Nikon Hacker's D810 1.14 patch uses the same table layout.  Its five
"1080 HQ" entries are entry numbers 1, 3, 5, 7 and 9 (1-based), i.e. the
42/35 and 24/20 pairs; the 12/10 pairs are the normal-quality entries.  This
tool applies the equivalent mapping to the D750:

    entry 1  (0x2AA9AC)  42/35 -> 64/60   (1080 60p HQ)
    entry 3  (0x2AA9E4)  42/35 -> 64/60   (1080 50p HQ)
    entry 5  (0x2AAA1C)  24/20 -> 64/60   (1080 30p HQ)
    entry 7  (0x2AAA54)  24/20 -> 64/60   (1080 25p HQ)
    entry 9  (0x2AAA8C)  24/20 -> 64/60   (1080 24p HQ)

Everything else, including the 12/10 normal-quality rows and the lower-ceiling
720p/480p group, is left byte-for-byte unchanged.  The tool refuses to patch
unless all nine 1080p stock rows match the expected values, so it cannot
silently corrupt a different firmware revision.

Usage:
    python d750_bitrate_patch.py --module b1010_115a.bin --out b1010_115a.hq64.bin
    python d750_bitrate_patch.py --module b1010_115a.bin --check
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

TABLE_ENTRY1 = 0x2AA9AC
ENTRY_STRIDE = 0x1C
# 0-based indices inside the 1080p group (entries 1..9 in the table dump).
HQ_INDICES = (0, 2, 4, 6, 8)
STOCK_HQ = (
    (42_000_000, 35_000_000),
    (42_000_000, 35_000_000),
    (24_000_000, 20_000_000),
    (24_000_000, 20_000_000),
    (24_000_000, 20_000_000),
)
STOCK_ROWS = (
    (42_000_000, 35_000_000),
    (24_000_000, 20_000_000),
    (42_000_000, 35_000_000),
    (24_000_000, 20_000_000),
    (24_000_000, 20_000_000),
    (12_000_000, 10_000_000),
    (24_000_000, 20_000_000),
    (12_000_000, 10_000_000),
    (24_000_000, 20_000_000),
)
TARGET = (64_000_000, 60_000_000)  # D810 1.14 64 Mbps patch: 0x03D09000 / 0x03938700
MAX_RATE_FIELD = 0x04380780  # 70,780,800 bps, the 1080p ceiling in the table


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_entry(data, index):
    off = TABLE_ENTRY1 + index * ENTRY_STRIDE
    if off + ENTRY_STRIDE > len(data):
        raise ValueError("table entry %d at 0x%X is outside the module" % (index + 1, off))
    rate_a, rate_b, flag, ceiling, tb_num, tb_den, fps = struct.unpack(
        "<7I", data[off:off + ENTRY_STRIDE]
    )
    return {
        "entry": index + 1,
        "offset": off,
        "rate_a": rate_a,
        "rate_b": rate_b,
        "flag": flag,
        "ceiling": ceiling,
        "tb_num": tb_num,
        "tb_den": tb_den,
        "fps_field": fps,
    }


def read_hq(data):
    return [(parse_entry(data, i)["rate_a"], parse_entry(data, i)["rate_b"])
            for i in HQ_INDICES]


def check_stock(data):
    got_rows = [(parse_entry(data, i)["rate_a"], parse_entry(data, i)["rate_b"])
                for i in range(9)]
    if got_rows != list(STOCK_ROWS):
        raise ValueError(
            "the nine 1080p rows do not match D750_0115 stock values\n"
            "  expected %s\n  got      %s" % (STOCK_ROWS, got_rows)
        )
    if read_hq(data) != list(STOCK_HQ):
        raise ValueError("the five 1080 HQ rows do not match the expected subset")
    for i in HQ_INDICES:
        entry = parse_entry(data, i)
        if entry["flag"] != 1:
            raise ValueError("entry %d has flag %#x, expected 1"
                             % (entry["entry"], entry["flag"]))
        if entry["ceiling"] != MAX_RATE_FIELD:
            raise ValueError("entry %d has ceiling %#x, expected %#x"
                             % (entry["entry"], entry["ceiling"], MAX_RATE_FIELD))
        if not (TARGET[0] < entry["ceiling"] and TARGET[1] < entry["ceiling"]):
            raise ValueError("target %s exceeds entry %d ceiling %d"
                             % (TARGET, entry["entry"], entry["ceiling"]))


def patch_module(data):
    check_stock(data)
    out = bytearray(data)
    changes = []
    for i in HQ_INDICES:
        entry = parse_entry(data, i)
        off = entry["offset"]
        old = data[off:off + 8]
        out[off:off + 8] = struct.pack("<II", *TARGET)
        changes.append({
            "entry": entry["entry"],
            "offset": off,
            "old": list(struct.unpack("<II", old)),
            "new": list(TARGET),
        })
    return bytes(out), changes


def verify_patch(original, patched, changes):
    if len(original) != len(patched):
        raise ValueError("module size changed: %d -> %d" % (len(original), len(patched)))
    diffs = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    expected_offsets = set()
    for change in changes:
        expected_offsets.update(range(change["offset"], change["offset"] + 8))
    if not set(diffs).issubset(expected_offsets):
        raise ValueError(
            "patched bytes escaped the expected table fields: %d diff(s), "
            "%d expected field bytes" % (len(diffs), len(expected_offsets))
        )
    if len(changes) != len(HQ_INDICES):
        raise ValueError("expected %d HQ changes, found %d"
                         % (len(HQ_INDICES), len(changes)))
    for change in changes:
        entry = parse_entry(patched, change["entry"] - 1)
        if (entry["rate_a"], entry["rate_b"]) != TARGET:
            raise ValueError("entry %d did not read back as %s"
                             % (change["entry"], TARGET))
    # Every other row must still match the stock pattern.
    for i in range(9):
        off = TABLE_ENTRY1 + i * ENTRY_STRIDE
        if i not in HQ_INDICES and patched[off:off + 8] != original[off:off + 8]:
            raise ValueError("non-HQ entry %d was modified" % (i + 1))


def report(original, patched, changes):
    return {
        "module": {
            "size": len(original),
            "sha256_stock": sha256(original),
            "sha256_patched": sha256(patched),
            "changed_bytes": sum(1 for a, b in zip(original, patched) if a != b),
        },
        "table": {
            "entry1_offset": TABLE_ENTRY1,
            "stride": ENTRY_STRIDE,
            "hq_entry_numbers": [i + 1 for i in HQ_INDICES],
            "stock_hq_rates": [list(x) for x in STOCK_HQ],
            "target_rates": list(TARGET),
            "target_hex_le": ["0x%08X" % x for x in TARGET],
            "ceiling": MAX_RATE_FIELD,
        },
        "changes": changes,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", required=True, help="extracted b1010_115a.bin")
    ap.add_argument("--out", help="patched module to write")
    ap.add_argument("--json", help="write a JSON report here")
    ap.add_argument("--check", action="store_true",
                    help="only validate the stock table and print its rows")
    args = ap.parse_args(argv)

    data = Path(args.module).read_bytes()
    try:
        check_stock(data)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.check:
        for i in range(9):
            e = parse_entry(data, i)
            tag = "HQ" if i in HQ_INDICES else "NQ"
            print("%d %s 0x%06X  %10d / %10d  max=%d  tb=%d/%d fps=%d"
                  % (e["entry"], tag, e["offset"], e["rate_a"], e["rate_b"],
                     e["ceiling"], e["tb_num"], e["tb_den"], e["fps_field"]))
        print("stock table OK; HQ targets would be %d / %d" % TARGET)
        return 0

    if not args.out:
        ap.error("--out is required unless --check is used")
    if Path(args.out).resolve() == Path(args.module).resolve():
        print("error: --out must not be the stock module", file=sys.stderr)
        return 2
    patched, changes = patch_module(data)
    verify_patch(data, patched, changes)
    Path(args.out).write_bytes(patched)
    doc = report(data, patched, changes)
    doc["output"] = str(Path(args.out))
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    print("stock  %s  %s" % (args.module, doc["module"]["sha256_stock"]))
    print("patched %s  %s" % (args.out, doc["module"]["sha256_patched"]))
    for c in changes:
        print("  entry %d @0x%06X  %d/%d -> %d/%d"
              % (c["entry"], c["offset"], c["old"][0], c["old"][1],
                 c["new"][0], c["new"][1]))
    print("changed bytes: %d across %d HQ rows (two u32 fields each)"
          % (doc["module"]["changed_bytes"], len(changes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
