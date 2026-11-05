#!/usr/bin/env python3
"""Repack a legacy Nikon DSLR firmware image and re-seal every checksum.

The container is described in the `nikon-fw-docs` documentation project (§2).
All offsets are body-relative,
where the body starts at the plaintext 32-space label:

    body 0x00   32 x 0x20            space label (never encrypted)
    body 0x20   BE32 module count
    body 0x24   BE32 directory size 48 + 32 * count
    body 0x28   8 x 0x00
    body 0x30   count x [16B name | BE32 start | BE32 length | 8B tag]
    ...         adjacent modules, each ending in BE16 CRC16(payload)
    body[-16]   BE16 package CRC over body[:-16]
    body[-14]   14 x 0x00

This tool never edits an image in place. It starts from a stock image,
optionally replaces payloads from disk, rebuilds the directory and the module
CRCs from scratch, recomputes the package CRC, and re-encrypts the body when
the input was encrypted. The rebuilt image is decrypted again and run through
decrypt_firmware.validate_firmware() before anything is written.

    # bit-identical round trip (best first check)
    python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
        --out D750_0115.selftest.bin --selftest

    # rebuild from an extracted .modules directory (sizes may change)
    python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
        --modules-dir D750_0115.dec.modules --out D750_0115.repack.bin

    # patch a few bytes in place
    python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
        --patch-module b1010_115a.bin:0x1000:deadbeef --out D750_0115.patched.bin

Header digest (packaging B only): the 32-byte header's first 20 bytes are
SHA1(decrypted_body || K8), where K8 is a per-model 8-byte key. K8 has not
been recovered for the DSLR samples, so by default the header is copied
verbatim; when the body changes the digest is reported as STALE. Pass --k8
with a JSON file ({"K8": "<16 hex chars>", "self_check": "<sha256>"} is the
format produced for the upstream Z 8/Z 9 case) to verify the stock digest and
recompute it for the output.

Directory tags: the 8 reserved bytes are zero in every DSLR sample except the
D750 `_wma_ver01.00.00` entry, whose tag is ASCII `crc.bin`. A strict
decrypt_firmware.py rejects that image even though its CRCs are correct
(documentation §9.1). By default this tool zeroes the tag so the output passes the
strict validator; --keep-tags preserves it byte for byte.

Exit codes: 2 usage, 3 bad key, 4 wrong scheme, 5 invalid input container,
7 a requested edit could not be applied, 8 self-verification failed.

Requires NumPy via decrypt_firmware.
"""

import argparse
import binascii
import hashlib
import json
import os
import struct
import sys

import numpy as np

import decrypt_firmware as fw

HDR_A = 0x00        # packaging A: no header, space label at file offset 0
HDR_B = 0x20        # packaging B: 32-byte header, space label at 0x20
NEW_SCHEME = 0x260  # space-label offset of the unbroken Z 5II / Z 50II scheme
ZERO8 = b"\0" * 8
ZERO14 = b"\0" * 14
TAG_KEEP, TAG_ZERO = "keep", "zero"

EX_EDIT = 7         # a --replace-module / --patch-module could not be applied
EX_VERIFY = 8       # the rebuilt image failed its own verification


# --------------------------------------------------------------------------
# Input handling
# --------------------------------------------------------------------------

def detect_header(raw, path):
    """Return 0x00 or 0x20 for the body start, or exit with a scheme error."""
    if raw[NEW_SCHEME:NEW_SCHEME + 32] == b" " * 32:
        fw.die(fw.EX_SCHEME,
               "%s uses the newer Nikon scheme (32 spaces at 0x%x, not 0x%x).\n"
               "       The header is plaintext but the payload cipher is not broken;\n"
               "       nothing here can repack it."
               % (path, NEW_SCHEME, HDR_B))
    for hdr in (HDR_A, HDR_B):
        if raw[hdr:hdr + 32] == b" " * 32:
            return hdr
    fw.die(fw.EX_SCHEME,
           "%s is not a recognised legacy Nikon image (no 32-space label at "
           "0x00 or 0x20)." % path)


def load_k8(path):
    """Load and self-check the eight-byte header digest key."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        fw.die(fw.EX_KEY, "cannot read signature key %s: %s" % (path, exc))
    if "K8" not in doc:
        fw.die(fw.EX_KEY, "%s has no K8 field" % path)
    try:
        k8 = bytes.fromhex(doc["K8"])
    except ValueError:
        fw.die(fw.EX_KEY, "K8 in %s is not valid hex" % path)
    if len(k8) != 8:
        fw.die(fw.EX_KEY, "K8 is %d bytes, expected 8" % len(k8))
    if "self_check" in doc:
        got = hashlib.sha256(k8).hexdigest()
        if doc["self_check"] != got:
            fw.die(fw.EX_KEY,
                   "K8 fails its own self_check\n  recorded %s\n  actual   %s"
                   % (doc["self_check"], got))
    return k8


def xor_stream(data, hdr, tables):
    """XOR the body from its space label onwards; decryption == encryption.

    The 32-byte space label is excluded, exactly like decrypt_firmware.decrypt:
    the key stream is still indexed from the body start, so both directions use
    the same call. The header and label are returned unchanged.
    """
    t1, t2, t3 = tables
    body = data[hdr:]
    pad = -len(body) % fw.SEC
    sectors = np.frombuffer(body + b"\0" * pad, dtype=np.uint8).reshape(-1, fw.SEC)
    j = np.arange(sectors.shape[0], dtype=np.int64)
    key = t1 ^ (t2[j & 0xFF] ^ t3[(j >> 8) & 0xFF])[:, None]
    mixed = (sectors ^ key).tobytes()[:len(body)]
    return data[:hdr] + data[hdr:hdr + 32] + mixed[32:]


def read_directory(body):
    """Validate one plaintext body and return its module records.

    This mirrors decrypt_firmware.parse_table/validate_firmware but accepts
    non-zero tag bytes so a stock D750 image can be read; the reserved
    directory bytes and both CRC levels are still enforced. Each record keeps
    the raw 16-byte name field and the 8-byte tag for a faithful rebuild.
    """
    body = memoryview(body)
    if len(body) < fw.TABLE + 32 + fw.TRAILER:
        raise ValueError("body is too short for a directory and checksum trailer")
    if body[:fw.TABLE] != b" " * fw.TABLE:
        raise ValueError("invalid space label")

    count, dirsize = struct.unpack_from(">II", body, fw.TABLE)
    if not 0 < count <= 64:
        raise ValueError("invalid module count %d (expected 1..64)" % count)
    if dirsize != 48 + 32 * count:
        raise ValueError("directory size %d does not match module count %d"
                         % (dirsize, count))
    if body[fw.TABLE + 8:fw.TABLE + 16] != ZERO8:
        raise ValueError("nonzero directory reserved bytes")

    payload_end = len(body) - fw.TRAILER
    if dirsize + 2 * count > payload_end:
        raise ValueError("directory/modules extend beyond the checksum trailer")

    mods = []
    expected = dirsize
    for i in range(count):
        off = fw.TABLE + 16 + i * 32
        name_field = bytes(body[off:off + 16])
        name_raw = name_field.rstrip(b"\0")
        if not fw.NAME_RE.fullmatch(name_raw):
            raise ValueError("module %d has an invalid name or NUL padding" % (i + 1))
        name = name_raw.decode("ascii")
        start, length = struct.unpack_from(">II", body, off + 16)
        tag = bytes(body[off + 24:off + 32])
        if start != expected:
            raise ValueError("module %d (%s) starts at 0x%x, expected 0x%x"
                             % (i + 1, name, start, expected))
        if length < 2:
            raise ValueError("module %d (%s) is too short for its CRC" % (i + 1, name))
        if start + length > payload_end:
            raise ValueError("module %d (%s) extends beyond the checksum trailer"
                             % (i + 1, name))
        payload = bytes(body[start:start + length - 2])
        stored = struct.unpack_from(">H", body, start + length - 2)[0]
        actual = binascii.crc_hqx(payload, 0)
        if stored != actual:
            raise ValueError("module %d (%s) CRC mismatch: stored 0x%04x, "
                             "computed 0x%04x" % (i + 1, name, stored, actual))
        mods.append({"name": name, "name_field": name_field, "tag": tag,
                     "payload": payload})
        expected = start + length
    if expected != payload_end:
        raise ValueError("last module ends at 0x%x, expected 0x%x"
                         % (expected, payload_end))
    if body[-fw.TRAILER + 2:] != ZERO14:
        raise ValueError("nonzero checksum trailer padding")
    stored = struct.unpack_from(">H", body, len(body) - fw.TRAILER)[0]
    actual = binascii.crc_hqx(body[:-fw.TRAILER], 0)
    if stored != actual:
        raise ValueError("package CRC mismatch: stored 0x%04x, computed 0x%04x"
                         % (stored, actual))
    return mods


def decode(raw, hdr, tables, path):
    """Return (plain image, module records, 'plaintext'|'encrypted').

    Plaintext is tried first: the directory and both CRC levels have to pass.
    Only if that fails is the body XORed and the same test repeated, so a
    plaintext container is never damaged by a second XOR (documentation §9.5).
    """
    plain_error = None
    try:
        return raw, read_directory(memoryview(raw)[hdr:]), "plaintext"
    except ValueError as exc:
        plain_error = str(exc)
        if tables is None:
            fw.die(fw.EX_SANITY,
                   "%s is not a valid plaintext container: %s\n"
                   "       If this is an encrypted .bin, pass --key." % (path, plain_error))
    plain = xor_stream(raw, hdr, tables)
    try:
        return plain, read_directory(memoryview(plain)[hdr:]), "encrypted"
    except ValueError as exc:
        fw.die(fw.EX_SANITY,
               "%s fails as plaintext (%s) and after decrypting with the given key "
               "(%s); refusing to repack a container whose checksums do not pass."
               % (path, plain_error, exc))


# --------------------------------------------------------------------------
# Rebuild
# --------------------------------------------------------------------------

def seal(mods, zero_tags):
    """Build body bytes: fresh directory, module CRCs and package CRC."""
    count = len(mods)
    dirsize = 48 + 32 * count
    parts = [b" " * 32, struct.pack(">II", count, dirsize), ZERO8]
    entries, blobs = [], []
    start = dirsize
    for mod in mods:
        payload = mod["payload"]
        blob = payload + struct.pack(">H", binascii.crc_hqx(payload, 0))
        tag = ZERO8 if zero_tags else mod["tag"]
        entries.append(mod["name_field"] + struct.pack(">II", start, len(blob)) + tag)
        blobs.append(blob)
        start += len(blob)
    body = b"".join(parts) + b"".join(entries) + b"".join(blobs)
    body += struct.pack(">H", binascii.crc_hqx(body, 0)) + ZERO14
    return body


def sign(body, k8):
    """SHA1(body || K8); body may be a bytes-like object."""
    h = hashlib.sha1()
    h.update(body)
    h.update(k8)
    return h.digest()


def find_module(mods, want):
    """Resolve an exact module name or an unambiguous prefix, or exit 7."""
    hit = [i for i, m in enumerate(mods) if m["name"] == want]
    if not hit:
        hit = [i for i, m in enumerate(mods) if m["name"].startswith(want)]
    if not hit:
        fw.die(EX_EDIT, "no module named %r; have %s"
               % (want, ", ".join(m["name"] for m in mods)))
    if len(hit) > 1:
        fw.die(EX_EDIT, "%r matches %d modules: %s"
               % (want, len(hit), ", ".join(mods[i]["name"] for i in hit)))
    return hit[0]


def take_modules_dir(mods, dirpath):
    """Replace every payload from a directory named after the module table."""
    if not os.path.isdir(dirpath):
        fw.die(fw.EX_USAGE, "%s is not a directory" % dirpath)
    edits = []
    for mod in mods:
        path = os.path.join(dirpath, mod["name"])
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            fw.die(EX_EDIT, "cannot read %s for module %s: %s"
                   % (path, mod["name"], exc))
        edits.append((mod["name"], "modules-dir", len(mod["payload"]), len(data)))
        mod["payload"] = data
    known = {m["name"] for m in mods}
    extra = sorted(name for name in os.listdir(dirpath)
                   if name not in known
                   and os.path.isfile(os.path.join(dirpath, name)))
    if extra:
        print("warning: ignoring %d file(s) in %s that are not in the module "
              "table: %s" % (len(extra), dirpath, ", ".join(extra)))
    return edits


def apply_replace(mods, spec):
    """Apply MODULE=PATH; any size is allowed because extents are rebuilt."""
    if "=" not in spec:
        fw.die(EX_EDIT, "--replace-module wants MODULE=PATH, got %r" % spec)
    want, path = spec.split("=", 1)
    idx = find_module(mods, want)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        fw.die(EX_EDIT, "cannot read %s: %s" % (path, exc))
    old = len(mods[idx]["payload"])
    mods[idx]["payload"] = data
    return [(mods[idx]["name"], "replace", old, len(data))]


def apply_patch(mods, spec):
    """Apply MODULE:OFFSET:HEXBYTES in place; the offset is payload-relative."""
    parts = spec.split(":", 2)
    if len(parts) != 3:
        fw.die(EX_EDIT, "--patch-module wants MODULE:OFFSET:HEXBYTES, got %r" % spec)
    want, off_s, hex_s = parts
    try:
        off = int(off_s, 0)
    except ValueError:
        fw.die(EX_EDIT, "%r is not a number" % off_s)
    try:
        data = bytes.fromhex(hex_s)
    except ValueError:
        fw.die(EX_EDIT, "%r is not valid hex" % hex_s)
    if not data:
        fw.die(EX_EDIT, "empty patch for %r" % want)
    idx = find_module(mods, want)
    payload = bytearray(mods[idx]["payload"])
    if off < 0:
        fw.die(EX_EDIT, "patch offset into %s is negative (%d)" % (mods[idx]["name"], off))
    if off + len(data) > len(payload):
        fw.die(EX_EDIT,
               "patch at %s+0x%x..0x%x leaves the payload (0x0..0x%x; its last "
               "two bytes are the CRC)" % (mods[idx]["name"], off, off + len(data),
                                           len(payload)))
    payload[off:off + len(data)] = data
    mods[idx]["payload"] = bytes(payload)
    return [(mods[idx]["name"], "patch +0x%x" % off, len(payload), len(payload))]


# --------------------------------------------------------------------------
# Reporting helpers
# --------------------------------------------------------------------------

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def count_diffs(a, b):
    """Number of differing bytes, counting a tail as a difference."""
    n = min(len(a), len(b))
    va = np.frombuffer(memoryview(a)[:n], dtype=np.uint8)
    vb = np.frombuffer(memoryview(b)[:n], dtype=np.uint8)
    return int(np.count_nonzero(va != vb)) + abs(len(a) - len(b))


def packaging(hdr):
    return "A (header 0x00)" if hdr == HDR_A else "B (header 0x20)"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Rebuild a legacy Nikon DSLR firmware container and re-seal "
                    "module and package CRCs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit codes: 2 usage, 3 bad key, 4 wrong scheme, 5 invalid input, "
               "7 bad edit, 8 self-verification failed.")
    ap.add_argument("--firmware", required=True,
                    help="stock image: encrypted or plaintext, packaging A or B")
    ap.add_argument("--out", required=True, help="repacked image to write")
    ap.add_argument("--force", action="store_true",
                    help="replace --out if it already exists")
    ap.add_argument("--key",
                    help="key JSON from extract_key.py; needed for encrypted input "
                         "or --encrypt")
    ap.add_argument("--k8",
                    help="signature key JSON with K8; verifies and recomputes the "
                         "packaging B header digest")
    ap.add_argument("--modules-dir", metavar="DIR",
                    help="replace every payload with the same-named file in DIR")
    ap.add_argument("--replace-module", action="append", default=[], metavar="MODULE=PATH",
                    help="replace one module payload from a file; size may change")
    ap.add_argument("--patch-module", action="append", default=[],
                    metavar="MODULE:OFF:HEX",
                    help="patch bytes inside a payload; repeatable")
    out_enc = ap.add_mutually_exclusive_group()
    out_enc.add_argument("--encrypt", action="store_true",
                         help="write an encrypted image even if the input was plaintext")
    out_enc.add_argument("--plaintext", action="store_true",
                         help="write a plaintext container even if the input was encrypted")
    tags = ap.add_mutually_exclusive_group()
    tags.add_argument("--zero-tags", dest="tags", action="store_const", const=TAG_ZERO,
                      help="canonicalise the 8 reserved tag bytes to zero")
    tags.add_argument("--keep-tags", dest="tags", action="store_const", const=TAG_KEEP,
                      help="preserve stock tag bytes (D750 keeps 'crc.bin')")
    ap.add_argument("--selftest", action="store_true",
                    help="no edits; the repacked image must be bit-identical to the input")
    args = ap.parse_args(argv)

    fw.refuse_clobber(args.out, args.force)
    if os.path.realpath(args.out) == os.path.realpath(args.firmware):
        fw.die(fw.EX_USAGE,
               "output is the same file as --firmware; keep the stock image, it is "
               "the only baseline a bad repack can be compared against.")

    if args.selftest and (args.modules_dir or args.replace_module or args.patch_module):
        fw.die(fw.EX_USAGE, "--selftest makes no edits; drop --modules-dir, "
               "--replace-module and --patch-module")

    # Tag policy: strict-validator-clean by default, byte fidelity on request.
    if args.tags is None:
        zero_tags = not args.selftest
    else:
        zero_tags = args.tags == TAG_ZERO
    if args.selftest and zero_tags:
        fw.die(fw.EX_USAGE, "--selftest compares bytes, so it needs --keep-tags; "
               "drop --zero-tags.")

    try:
        with open(args.firmware, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        fw.die(fw.EX_USAGE, str(exc))
    hdr = detect_header(raw, args.firmware)
    if len(raw) <= hdr + 32:
        fw.die(fw.EX_SANITY, "%s is only %d bytes" % (args.firmware, len(raw)))

    tables = fw.load_key(args.key) if args.key else None
    k8 = None
    if args.k8:
        k8 = load_k8(args.k8)
        if hdr != HDR_B:
            print("note: --k8 ignored; packaging %s has no header digest" % packaging(hdr))
            k8 = None

    plain_in, mods, encoding = decode(raw, hdr, tables, args.firmware)
    body_in = memoryview(plain_in)[hdr:]
    legacy_tags = [m for m in mods if m["tag"] != ZERO8]

    # Edits are applied to the in-memory module payloads, then re-sealed.
    edits = []
    if args.modules_dir:
        edits += take_modules_dir(mods, args.modules_dir)
    for spec in args.replace_module:
        edits += apply_replace(mods, spec)
    for spec in args.patch_module:
        edits += apply_patch(mods, spec)

    encrypted_out = encoding == "encrypted"
    if args.encrypt:
        encrypted_out = True
    if args.plaintext:
        encrypted_out = False
    if encrypted_out and tables is None:
        fw.die(fw.EX_USAGE, "encrypted output needs --key")
    if args.selftest and encrypted_out != (encoding == "encrypted"):
        fw.die(fw.EX_USAGE, "--selftest requires the output encoding to match the "
               "input; drop --encrypt/--plaintext.")

    # Packaging B's digest is keyed; verify the stock one before touching it.
    digest_state = "n/a (packaging A has no header digest)"
    if hdr == HDR_B:
        if k8 is not None:
            want = sign(body_in, k8)
            if want != raw[:20]:
                fw.die(fw.EX_KEY,
                       "this K8 does not verify %s\n  header   %s\n  computed %s\n"
                       "       Wrong camera, or the image is already modified."
                       % (args.firmware, raw[:20].hex(), want.hex()))
        else:
            digest_state = "not verified (K8 unknown)"

    body_out = seal(mods, zero_tags)
    body_same = sha256(body_out) == sha256(body_in)

    header_out = raw[:hdr]
    if hdr == HDR_B:
        if k8 is not None:
            header_out = sign(body_out, k8) + raw[20:32]
            digest_state = "verified on input, recomputed (SHA1(body || K8))"
        elif body_same:
            digest_state = "preserved (body unchanged)"
        else:
            digest_state = ("STALE: body changed and K8 is unknown; the digest "
                            "cannot be recomputed")

    plain_out = header_out + body_out
    image_out = xor_stream(plain_out, hdr, tables) if encrypted_out else plain_out

    # ---- verify the exact bytes that are about to be written -----------------
    if encrypted_out:
        back = xor_stream(image_out, hdr, tables)
        if back != plain_out:
            fw.die(EX_VERIFY, "re-encryption did not round-trip; nothing written.")
        check_plain = back
    else:
        check_plain = image_out
    check_body = memoryview(check_plain)[hdr:]
    try:
        read_directory(check_body)
        fw.validate_firmware(check_body)
        strict_note = "strict: directory, trailer, module CRCs and package CRC OK"
    except ValueError as exc:
        if "nonzero reserved bytes" in str(exc) and not zero_tags and legacy_tags:
            # The only expected failure: stock tag bytes kept on request.
            strict_note = ("strict tag check skipped: legacy tag preserved (%s)"
                           % ", ".join("%s=%r" % (m["name"], m["tag"]) for m in legacy_tags))
        else:
            fw.die(EX_VERIFY, "the rebuilt image fails validation (%s); nothing "
                   "written." % exc)
    if hdr == HDR_B and k8 is not None and sign(check_body, k8) != header_out[:20]:
        fw.die(EX_VERIFY, "the rebuilt image fails its header digest; nothing written.")
    if args.selftest:
        if image_out != raw:
            fw.die(EX_VERIFY, "selftest: output differs from the input in %d byte(s)."
                   % count_diffs(image_out, raw))
        if legacy_tags:
            strict_body = seal(mods, True)
            try:
                fw.validate_firmware(memoryview(strict_body))
            except ValueError as exc:
                fw.die(EX_VERIFY, "selftest: the zero-tag variant fails the strict "
                       "validator (%s)." % exc)

    # ---- atomic write --------------------------------------------------------
    tmp = args.out + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(image_out)
        os.replace(tmp, args.out)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        fw.die(fw.EX_USAGE, "cannot write %s: %s; nothing left behind." % (args.out, exc))

    # ---- report --------------------------------------------------------------
    print("input        %s (%s bytes)" % (args.firmware, format(len(raw), ",")))
    print("  packaging  %s, %s" % (packaging(hdr), encoding))
    print("  modules    %d" % len(mods))
    print("output       %s (%s bytes)" % (args.out, format(len(image_out), ",")))
    print("  image      %s" % ("encrypted" if encrypted_out else "plaintext"))
    if edits:
        print("  edits")
        for name, what, old, new in edits:
            if what == "modules-dir":
                print("    %-22s %-13s %s -> %s bytes"
                      % (name, what, format(old, ","), format(new, ",")))
            elif what.startswith("patch"):
                print("    %-22s %-13s %s bytes (size unchanged)"
                      % (name, what, format(new, ",")))
            else:
                print("    %-22s %-13s %s -> %s bytes"
                      % (name, what, format(old, ","), format(new, ",")))
    if zero_tags and legacy_tags:
        print("  tags       zeroed: %s (strict validator clean)"
              % ", ".join("%s=%r" % (m["name"], m["tag"]) for m in legacy_tags))
    elif legacy_tags:
        print("  tags       preserved: %s"
              % ", ".join("%s=%r" % (m["name"], m["tag"]) for m in legacy_tags))
    else:
        print("  tags       already zero")
    print("  header     %s" % digest_state)
    print("  checksums  %d module CRC(s) + package CRC" % len(mods))
    print("  verify     %s" % strict_note)
    if encrypted_out:
        print("             decrypt(repack) == plaintext (bit-identical)")
    if args.selftest:
        print("  selftest   output is bit-identical to the input")
        if legacy_tags:
            print("             zero-tag variant also passes the strict validator")
    print("  sha256     %s" % sha256(image_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
