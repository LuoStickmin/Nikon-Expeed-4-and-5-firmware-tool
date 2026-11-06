# Nikon Expeed 4 / 5 DSLR Firmware Unpacking

[中文](README.md) · [English](README.en.md)

> Starting from the official update package `.bin`, **using only the ciphertext itself**, recover the vendor-level XOR key tables, open the container, verify the two-level CRC, carve out the modules, and leave behind a set of static-analysis probes.
>
> Repository: <https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool>
>
> **Related project:** the D750 high-bitrate video modification (64/60 Mbps), QEMU validation, and LCD dump have moved to [LuoStickmin/D750-QEMU](https://github.com/LuoStickmin/D750-QEMU); this repository focuses on the firmware container, key recovery, and repacking.

**Update (2026-11-05):** added the repacking tool ([§5.8](#58-repacking)).

![scope](https://img.shields.io/badge/scope-Expeed%204%2F5%20DSLR-blue)
![verified](https://img.shields.io/badge/verified-12%20models%20%7C%2022%20images-brightgreen)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![numpy](https://img.shields.io/badge/numpy-required-013243?logo=numpy&logoColor=white)
![capstone](https://img.shields.io/badge/capstone-optional-lightgrey)

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Firmware Container Format](#2-firmware-container-format)
- [3. Encryption Principles](#3-encryption-principles)
- [4. Scope](#4-scope)
- [5. Quick Start](#5-quick-start)
- [6. Repository Layout](#6-repository-layout)
- [7. Attempt Log](#7-attempt-log)
- [8. Sample Review](#8-sample-review)
- [9. Known Issues](#9-known-issues)
- [10. Security and Compliance](#10-security-and-compliance)
- [11. References](#11-references)

---

## 1. Project Overview

This repository is a **reproducible research record and toolkit**: given an Expeed 4/5-generation DSLR firmware `.bin`, it recovers the three-layer XOR key tables shared by this generation *without any previously published key*, opens the container, uses the container's own CRC to prove "we decrypted it correctly", then carves each module out; a set of probe scripts then attempt static localization. All conclusions land in `key_all.json` and local unpacking artifacts (`*.dec` / `*.modules/`, not shipped with the repository).

Three core conclusions:

1. **The key is a vendor-level static table, not a per-camera or per-version secret.** The three 256-byte tables (`T1` / `T2` / `T3`) in `key_all.json` pass directory validation and both CRC levels on 12 models and 22 firmware versions; the author's four local samples also all re-validate (the samples are not shipped with this repository; see [§8](#8-sample-review)).
2. **The encryption is a "byte-wise XOR + 16 MiB periodic" keystream.** No diffusion, no IV, no per-device key; the large runs of `0x00` / `0xFF` padding in the image are themselves known plaintext. This is equivalent to a classical "many-time pad + known plaintext" scenario, and the key can be recovered from ciphertext statistics alone.
3. **The container ships an almost-never-wrong oracle.** The strict big-endian directory structure + per-module CRC16 + package-wide CRC turns "is the key right?" into a yes/no question; every step of the recovery algorithm is designed around this oracle.

### 1.1 What this repository can do

- Identify and decrypt Expeed 4/5 DSLR firmware update packages (two header wrappers).
- **Blindly recover** key tables from a ciphertext corpus, and only write them to disk after full CRC validation.
- Parse the module directory and carve out `a*` (Firmware A), `b*` (Firmware B), `_wma_*` (wireless module), and other components.
- Run preliminary static analysis — entropy, keywords, code density, pointer tables, disassembly — on the carved modules.

### 1.2 What this repository does not do

- It does not cover the new Z-series wrapper (`0x260` tag) — the tool explicitly recognizes and refuses it; payload encryption is unbroken.
- It does not re-sign or provide any flashing workflow; CRC validation only proves integrity, **not authenticity**. The upstream repository [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)'s Z 8/Z 9 repacking and signing-key recovery (`repack_firmware.py`, `solve_signature_e7.py`) is not included here.
- It does not ship firmware samples or the full encrypted corpus (only `key_all.json` and the scripts), so key recovery cannot be rerun inside this repository; bring your own image.

---

## 2. Firmware Container Format

A firmware file = installation header (optional) + **32-byte space tag** + big-endian directory + concatenated modules + 16-byte trailer. In code, the part starting from the space tag is called the **body**, and all offsets are relative to the body.

### 2.1 Body Layout

```
body offset       content
────────────────────────────────────────────────────────────
0x000           32 × 0x20            space tag (plaintext, not encrypted)
0x020           BE32 module_count    module count (parser limits 1..64)
0x024           BE32 directory_size = 48 + 32 × count
0x028           8 × 0x00            directory reserved field (always 0 in observations)
0x030           entry 0             16B name | BE32 start | BE32 length | 8B tag
0x050           entry 1             ...
 ...            ...
directory_size  module 0 payload    length includes trailing 2-byte CRC
 ...            ...
len(body)-16    BE16 package_crc    covers body[:-16]
len(body)-2     14 × 0x00           trailer padding
```

### 2.2 Directory Entry

| Field | Length | Notes |
| --- | --- | --- |
| name | 16 B | ASCII, `[0-9A-Za-z_][0-9A-Za-z_.]{2,15}`, NUL-padded or full 16 bytes |
| start | BE32 | body-relative offset, must equal "previous module's end"; modules are strictly concatenated |
| length | BE32 | total length including trailing 2-byte CRC; payload = `length - 2` |
| tag | 8 B | Upstream format defines it as reserved zero bytes; the DSLR old wrapper has also been observed with ASCII (e.g., D750's `_wma` entry carries `crc.bin`), see [§9.1](#91-strict-validator-false-positive-on-crcbin-tag) |

The directory parser (`decrypt_firmware.parse_table`) enforces: `directory_size == 48 + 32 × count`, the name character set, reserved fields being zero, modules being contiguous, and the last module ending exactly at `len(body) - 16`. (See [§9.1](#91-strict-validator-false-positive-on-crcbin-tag) for the DSLR old-wrapper `crc.bin` exception.)

### 2.3 Two-Level CRC

- Algorithm: `binascii.crc_hqx(data, 0)`, i.e., **CRC-16/XMODEM** (poly `0x1021`, init `0`, no reflection, no final XOR).
- Storage: big-endian.
- Level 1: the last 2 bytes of each module = CRC of that module with those 2 bytes removed, i.e., `CRC16(module[:-2])`.
- Level 2: `body[-16:-14]` = CRC of `body[:-16]`, **including** all module CRCs and the directory itself.
- Result: random errors break the package CRC, and module CRC pinpoints which module. But CRC has the residue property: `CRC16(payload || CRC16(payload)) == 0`, so "modify payload + recompute module CRC" does not change the package CRC — **you must check both module CRC and package CRC**; the package CRC alone cannot prove the payload was not modified (the upstream README's [Checksums](https://github.com/WonderLantern/nikon-fw-key-tool#checksums-and-header-digest) section is explicit about this).

### 2.4 Three Wrappers (Header Offsets)

| Wrapper | File header | Space tag position | Body start | Author's local samples (not shipped) |
| --- | --- | --- | --- | --- |
| **A** | none | `0x00` | `0x00` | `D750_0115.bin` (encrypted original), `D810_0114.bin` (plaintext container) |
| **B** | 32-byte header: 20B SHA-1 digest + 12B unidentified | `0x20` | `0x20` | `D850_0131.bin`, `D5__0150.bin` (both plaintext containers) |
| **C** | longer prefix (not fully analyzed) | `0x260` | — | none; belongs to Z 5II / Z 50II / Z 6III / ZR new wrapper, tool refuses |

Key point: **the keystream phase is anchored at the space tag (body start) as 0**, independent of the header length. Hence the same tables handle both wrappers A and B; `key_all.json`'s `sources[].header` records each image's body start.

Wrapper B's 32-byte header, per the upstream [Firmware format](https://github.com/WonderLantern/nikon-fw-key-tool#firmware-format) definition, is `[20-byte SHA-1 digest][12-byte unidentified]`, with the digest satisfying `header[0:20] == SHA1(decrypted_body || K8)`; `K8` is a model-specific 8-byte key, so this is a "keyed digest", not an asymmetric signature. The tools here only decrypt/carve and **do not verify or recompute** it; the measured DSLR sample's prefix equals neither `SHA1(body)` nor `SHA1(body[:-16])`, consistent with keyed-digest behavior, but the DSLR `K8` is unknown and this repository has not verified it. The upstream covers the legacy wrapper with the tag at `0x20`; the DSLR old-wrapper with the tag at `0x00` (D750/D810-class) is the adaptation added by this repository (`decrypt_dslr*.py`).

---

## 3. Encryption Principles

### 3.1 Keystream

Let `i` be the offset inside the body (`i >= 0x20`); the three 256-byte tables combine as follows:

```
K(i)      = T1[ i        & 0xFF]
          ^ T2[(i >>  8) & 0xFF]
          ^ T3[(i >> 16) & 0xFF]

plain[i]  = cipher[i] ^ K(i)
K(i)      = K(i + 2^24)        # period 16 MiB
```

Since all three indices are `& 0xFF`, the keystream repeats exactly every `256^3 = 16 MiB`. `T1` has a period of 256 bytes, so **when processing in 256-byte sectors**, the keystream within each sector is exactly `T1` XOR a sector-position-only constant:

```
K(s + p) = T1[p] ^ C(s),   C(s) = T2[(s>>8)&0xFF] ^ T3[(s>>16)&0xFF]
```

This is why the whole algorithm uses "sector" as its minimum unit.

### 3.2 Why this encryption cannot resist statistical recovery

| Design property | Consequence | Exploited by which step |
| --- | --- | --- |
| Single static table shared by the whole generation | Recover once, works on 12 models | Corpus merged across models |
| Period only 16 MiB while images reach 48 MB | Keystream reused | Reuse directly beyond the period |
| Byte-wise XOR, no diffusion | Plaintext statistics preserved | Fill sectors = known plaintext |
| Large runs of `0x00` / `0xFF` padding | Abundant known plaintext | Recover T1 / T2 / T3 |
| Strict directory + two-level CRC | Precise yes/no oracle | Determine constants, validate results |

In other words, this is not "breaking AES" — it is **keystream reuse with predictable plaintext**. Vendor-level static table + 16 MiB period + zero fill: three things together make it possible to recover the whole table from ciphertext alone.

> Note: D750's main module (`b1010_115a.bin`, 20.3 MB) crosses the 16 MiB period boundary and still passes the package CRC, corroborating "period = 2^24".

### 3.3 Five-Stage Recovery Algorithm

`extract_key.py` splits recovery into five steps; each step uses part of the 65536 `(a,b)` cells' observations for statistics, and finally validates in full with CRC.

| Stage | Input | Operation | Output |
| --- | --- | --- | --- |
| 1 | All ciphertext corpus | Normalize repeated sectors by first byte | `T1 ^ T1[0]` |
| 2 | First 0x200 bytes of first image | 256 constants × directory-probe scoring | Absolute `T1` |
| 3 | All corpus | Majority vote on constant sectors by `(a,b)` | Observation table `T2[a]^T3[b]` |
| 4 | Observation table | Bipartite graph majority propagation (gauge `T2[0]=0`) | `T2`, `T3` (with offset/ambiguity) |
| 5 | All corpus | Per-block byte frequency re-fix | Corrected `T3` |
| Acceptance | All images | Directory + module CRC + package CRC | Write `key.json` only if all pass |

**Stage 1: `T1` only misses one constant.**

For a sector starting at `s`, if the entire sector's plaintext is a constant fill `f`, the ciphertext is `f ^ T1[p] ^ C(s)`. Normalizing each repeated sector by "first byte" (XOR each byte with the sector's byte 0):

```
norm[p] = (f ^ T1[p] ^ C(s)) ^ (f ^ T1[0] ^ C(s)) = T1[p] ^ T1[0]
```

The fill constant `f` and the sector constant `C(s)` cancel simultaneously. Repeated sectors in the corpus are almost always fill regions, so taking the family whose normalized vector occurs ≥ 64 times yields `T1 ^ T1[0]`.

**Stage 2: use directory feasibility to pin down the 8-bit constant.**

For `g = 0..255`, try `T1 = norm ^ g`, decrypt the first two sectors, run a simplified directory probe, score by "number of entries parsed + number of contiguous extents", and pick the highest. A wrong constant garbles the ASCII module names, making count/dirsize absurd, so this score is almost unambiguous (requires at least 2 entries).

**Stage 3: collect `(a,b)` observations.**

With `T1` fixed, XOR each sector back. Any sector where all bytes are equal is a constant fill sector, with value `v = fill ^ T2[a] ^ T3[b]`, where `a = (s>>8) & 0xFF`, `b = (s>>16) & 0xFF`. The same `(a,b)` cell is hit repeatedly across the corpus; majority vote the `v`, suppressing rare nonzero-fill or non-fill sectors.

**Stage 4: bipartite graph majority propagation.**

Observations give equations `T2[a] ^ T3[b] = v`. All solutions share the freedom "`T2` and `T3` simultaneously XOR the same constant"; set gauge `T2[0] = 0`. Then alternate:

```
T3[b] = majority{ v ^ T2[a]  | a known }
T2[a] = majority{ v ^ T3[b]  | b known }
```

until unchanged (up to 64 rounds). This resembles LDPC bit-flipping decoding and tolerates bad cells.

**Stage 5: per-block disambiguation of the `0x00 / 0xFF` ambiguity.**

Stage 4's `T3[b]` still carries the "is this block's fill `0x00` or `0xFF`" uncertainty. For each `b`, take all sectors with the same `b` index (`s = b*256 + k*65536`), XOR out `T1` and `T2[a]`, and build a byte histogram:

```
c = argmax( cnt[c] + cnt[c ^ 0xFF] )     # first pick the 0x00/0xFF peak
if cnt[c] < cnt[c ^ 0xFF]: c ^= 0xFF     # then pick whichever gives more zeros
```

Zero fill dominates the corpus, so this step nails down `T3`. A wrong choice is caught by final CRC validation.

**Acceptance.** Decrypt every image, run full directory parsing + all module CRCs + package CRC; if any fails, do not write the key file. `key.json` also records each table's SHA-256 and each source image's SHA-256 for regression comparison.

### 3.4 Coverage Requirements

Stage 3 requires **all 256 `T3` blocks to be covered by fill sectors** (i.e., every 64 KiB block within a 16 MiB period has at least one constant-fill sector). `extract_key.py` reports the missing block numbers and exits if coverage is insufficient.

Upstream `nikon-fw-key-tool` records the minimal sufficient set in `extract_key.py`'s `MINIMAL` as 4 Z-series images (`Z_8_0311.bin`, `Z7_2_0170.bin`, `Z_6_0380.bin`, `Z_50_0260.bin`); the DSLR corpus finally used 22 images, and still had 3 blocks (`190`, `191`, `212`) requiring follow-up scripts to set manually (see [§7.5](#75-stage-3-fill-key-holes)).

### 3.5 Why CRC can serve as an oracle

- The directory structural constraints are rigid: `count` is range-bounded, `dirsize == 48 + 32×count`, names must be ASCII, extents must be contiguous and end exactly before the trailer. The probability a random key passes is extremely low.
- Even if the structure happens to pass, the package CRC covers `body[:-16]` (including the space tag, directory, and all module CRCs). However, the residue property means "modify payload + fix module CRC" does not change the package CRC, so validation must also check module CRC; the probability a random error hits the package CRC is ~`1/65536`, actually far lower.
- The two-level CRC also provides localization: module CRC tells which segment is bad, package CRC tells the whole thing is bad.

But it must be emphasized: **CRC is an integrity check, not a signature.** "Structurally self-consistent" only means the bytes match the vendor image without corruption; it does not prove origin and does not prevent forgery (anyone can recompute CRC after modifying). Whether the camera/updater performs signature verification is not covered by this repository.

---

## 4. Scope

### 4.1 Verified Models and Versions

`key_all.json`'s `sources` records 12 models and 22 firmware versions, all 22 appearing in the `validated` list (per the project's CRC-only validation criterion, see [§9.1](#91-strict-validator-false-positive-on-crcbin-tag)):

| Model | Generation (public spec) | Versions included | body offset |
| --- | --- | --- | --- |
| D3400 | Expeed 4 | 0110, 0113 | `0x20` |
| D4S | Expeed 4 | 0133 | `0x00` |
| D500 | Expeed 5 | 0101, 0111, 0140 | `0x20` |
| D5300 | Expeed 4 | 0103 | `0x00` |
| D5500 | Expeed 4 | 0102 | `0x00` |
| D5600 | Expeed 4 | 0120 | `0x20` |
| D5 | Expeed 5 | 0120, 0150 | `0x20` |
| D7200 | Expeed 4 | 0101, 0104 | `0x00` |
| D7500 | Expeed 5 | 0112 | `0x20` |
| D750 | Expeed 4 | 0101, 0102, 0111, 0115 | `0x00` |
| D810 | Expeed 4 | 0102, 0114 | `0x00` |
| D850 | Expeed 5 | 0101, 0131 | `0x20` |

SHA-256 of the three tables (`key_all.json`'s `self_check`):

```
T1  29d2e34239fc33bf0a1054fd3558536ad6429966659f5b387a75f16e9aada431
T2  6e87de5da7e42df91db31fae4a899a04bd8f0225171922cc98f74922681766e0
T3  3617957facf8b21a5a3de0f3a1f6f27ca20d72c7208b196b2a8bec3076f39b49
```

As long as the recovered tables match these three lines, they are considered sourced from the same regression set, and per-image validation is usually unnecessary.

Anyone with any Expeed 4/5 encrypted firmware can run `extract_key_mix.py` and compare against these three hashes to independently determine whether it is the same table set — no original corpus required. Results welcome in the validation matrix.

Another corroboration: the first 16 bytes of these three tables' SHA-256 match the upstream `extract_key.py`'s `EXPECTED_SHA` exactly (upstream stores only the prefix, see [§11](#11-references)). That is, the tables recovered from the DSLR Expeed 4/5 corpus are the same set recovered by upstream from the Z-series legacy wrapper — Nikon reused the same vendor keys on this class of wrapper.

### 4.2 Supported Input Types

| Input | Detection | Handling | Status |
| --- | --- | --- | --- |
| Encrypted original, tag at `0x00` | `raw[0:0x20]` all `0x20` | `HDR=0`, XOR body | ✅ Verified (`D750_0115.bin`) |
| Encrypted original, tag at `0x20` | `raw[0x20:0x40]` all `0x20` | `HDR=0x20`, XOR body | ✅ Regression-verified (no encrypted sample shipped) |
| **Plaintext container** of the same structure | body directory parses directly | Skip XOR, carve by directory | ✅ Verified (D810 / D850 / D5 samples) |
| Z-series new wrapper | 32 spaces at `0x260` | Refuse | ❌ Unbroken |
| Bare module / archive / updater exe | No space tag | Refuse | ❌ Extract first |

### 4.3 Boundaries and Limitations

- **Models not included are unverified.** Models of the same Expeed 4/5 generation but not in the table above, as well as earlier (Expeed 3) or later (Z-series) models, cannot be assumed applicable; try `extract_key_mix.py`, but must pass CRC validation first.
- **Key not distinguishing models ≠ container not distinguishing models.** The wrapper A/B difference (32-byte header) must be handled by `HDR` or auto-detection, otherwise decryption is globally misaligned.
- **Plaintext containers must not be re-decrypted.** `decrypt_dslr2.py` unconditionally XORs; on a plaintext container this destroys the directory.
- **Limits of repacking.** `repack_firmware.py` can rebuild the directory, recompute module and package CRCs, and re-encrypt according to the input; the result passes `validate_firmware`'s directory/CRC checks. But wrapper B's 32-byte header carries a keyed SHA-1 digest (`K8`); the DSLR `K8` is unknown, so without `--k8` the digest is preserved as-is and marked `STALE`. **This is not re-signing and does not guarantee the camera accepts it**, so the repository still ships no flashable artifact.
- **Depends on corpus statistics.** Stages 3/5 assume fill is predominantly `0x00`; if a 64 KiB block is predominantly `0xFF`, manual verification is needed (`fill_t3.py` and CRC enumeration exist for this).
- **Scheme is determined by wrapper, not by EXPEED generation.** Upstream confirmed Z 8/Z 9 (EXPEED 7) still use the old wrapper, while Z f/Z 5II/Z 50II/Z 6III/ZR use the new scheme; "Expeed 4/5" here is just the customary corpus-scope label and cannot be used to infer model or generation.

---

## 5. Quick Start

### 5.1 Dependencies

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool

pip install numpy        # required (decrypt, carve, statistics)
pip install capstone     # optional, only for analyze_core.py / disasm_*.py
```

Dev environment is Python 3.12 + NumPy 2.3.5; pure Python, runs on Windows / Linux / macOS. The commands below assume the repository root; except for one-off research scripts, the main flow has no hardcoded absolute paths.

### 5.2 One-Click Decrypt + Carve (recommended)

`decrypt_dslr2.py` auto-detects `HDR` (`0x00` or `0x20`), prints the directory, writes `.dec` and `<out>.modules/`:

```bash
python decrypt_dslr2.py \
    --key key_all.json \
    --firmware D750_0115.bin \
    --out D750_0115.dec
```

This command was measured on the author's `D750_0115.bin`: the output matched the then-current `D750_0115.dec` **byte-for-byte**, and all three modules matched `D750_0115.dec.modules/` exactly (see [§5.7](#57-an-actual-run)). The repository does not ship those samples or artifacts; bring your own image.

### 5.3 Strict Validation Mode

Only applicable when the image really is an "encrypted original"; validate first, write second:

```bash
# Wrapper with tag at 0x20 (default HDR=0x20)
python decrypt_firmware.py --key key_all.json --firmware IMAGE.bin --out IMAGE.dec

# Wrapper with tag at 0x00
python decrypt_dslr.py --key key_all.json --firmware IMAGE.bin --out IMAGE.dec
```

Note:

- If the target exists, `--force` must be given, otherwise exits with code 2.
- Running `decrypt_dslr.py` on `D750_0115.bin` will **falsely report** `module 2 ... has nonzero reserved bytes`, see [§9.1](#91-strict-validator-false-positive-on-crcbin-tag); use `decrypt_dslr2.py` instead, or switch to CRC-only validation.

### 5.4 When Input Is Already a Plaintext Container

The author's local `D810_0114.bin`, `D850_0131.bin`, `D5__0150.bin` are already plaintext containers (samples are not shipped; directory and module CRC pass without decryption). Do not XOR; carve by directory and validate directly:

```python
import binascii, os, struct

def carve(path, body_off, out_dir):
    raw = open(path, "rb").read()
    body = memoryview(raw)[body_off:]          # wrapper A:0x00  wrapper B:0x20
    count, dirsize = struct.unpack_from(">II", body, 0x20)
    assert dirsize == 48 + 32 * count
    os.makedirs(out_dir, exist_ok=True)
    for i in range(count):
        e = 0x30 + 32 * i
        name = bytes(body[e:e + 16]).rstrip(b"\0").decode("ascii")
        start, length = struct.unpack_from(">II", body, e + 16)
        payload = bytes(body[start:start + length - 2])
        stored = struct.unpack_from(">H", body, start + length - 2)[0]
        assert binascii.crc_hqx(payload, 0) == stored, name
        open(os.path.join(out_dir, name), "wb").write(payload)

carve("D850_0131.bin", 0x20, "D850_0131.bin.modules")
```

### 5.5 Recovering Keys Yourself

Requires an encrypted corpus with **full fill coverage** (all 256 `T3` blocks):

```bash
# All wrapper with tag at 0x20
python extract_key.py      --firmware-dir corpus --out key.json

# All wrapper with tag at 0x00
python extract_key_dslr.py --firmware-dir corpus --out key.json

# Mixed wrappers (auto-detect HDR per file)
python extract_key_mix.py  --firmware-dir corpus --out key.json
```

After running, compare `key.json`'s `self_check` against the three hash lines in [§4.1](#41-verified-models-and-versions); matching means correct recovery. The repository **does not ship** that corpus or any firmware sample (only `key_all.json` and scripts), so this step must be run with your own images.

Key file fields: `scheme` (scheme description), `period_bytes` (`1<<24`), `T1/T2/T3` (each 256 bytes hex), `sources` (each image's `sha256` and `header`), `self_check` (SHA-256 of the three tables). The `key_all.json` produced by `finalize_key.py` additionally has a `validated` list.

### 5.6 Exit Codes

| Exit code | Meaning | Trigger |
| --- | --- | --- |
| `0` | Success, files written | — |
| `2` | Argument error / unreadable input / output exists | `--force` missing (only `decrypt_firmware` / `decrypt_dslr`; `decrypt_dslr2` lacks this check) |
| `3` | Key file rejected (missing table, wrong length, self_check mismatch) | `load_key` |
| `4` | Not this scheme's image (no space tag, or hits `0x260` new scheme) | `check_scheme` |
| `5` | Structure or CRC validation failed (no files written) | `validate_firmware` |
| `7` | Patch/replace argument could not be applied (no files written) | `repack_firmware.py` |
| `8` | Rebuilt output failed self-validation (nothing written) | `repack_firmware.py` |

`extract_key.py` additionally expresses regression status via return value: `0` means all three tables match built-in `EXPECTED_SHA`, `1` means drift (still writes the key, but prints a warning).

### 5.7 An Actual Run

```console
$ python decrypt_dslr2.py --key key_all.json --firmware D750_0115.bin --out D750_0115.dec
header=0x0 count=3 dirsize=0x90
  a1010_011100.bin     off=0x00000090 len=0x000C0002 tail=
  _wma_ver01.00.00     off=0x000C0092 len=0x0006BB37 tail=crc.bin
  b1010_115a.bin       off=0x0012BBC9 len=0x01362062 tail=
  wrote D750_0115.dec.modules\a1010_011100.bin (786432 bytes)
  wrote D750_0115.dec.modules\_wma_ver01.00.00 (441141 bytes)
  wrote D750_0115.dec.modules\b1010_115a.bin (20324448 bytes)
done
```

> `tail=crc.bin` is the 8-byte tag field of the **second** entry (`_wma_ver01.00.00`), legitimately present; `decrypt_dslr2.py` does not validate CRC, so it does not error. The strict validation in `decrypt_dslr.py` / `decrypt_firmware.py` falsely rejects it ([§9.1](#91-strict-validator-false-positive-on-crcbin-tag)).

### 5.8 Repacking

`repack_firmware.py` starts from the original image (plaintext or encrypted), can replace/patch module payloads, rebuilds the directory and both CRC levels, and decides whether to re-encrypt based on the input; before writing to disk it validates again with `decrypt_firmware.validate_firmware` and refuses to write if validation fails.

```bash
# 0) Bit-level round-trip self-test first: modify nothing, output must match input byte-for-byte
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --out D750_0115.self.bin --selftest

# 1) Rebuild from a carved module directory (modules may grow or shrink)
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --modules-dir D750_0115.dec.modules --out D750_0115.repack.bin

# 2) Patch a few bytes in place
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --patch-module b1010_115a.bin:0x1000:deadbeef --out D750_0115.patched.bin

# 3) Plaintext container -> encrypted form
python repack_firmware.py --key key_all.json --firmware D850_0131.bin \
    --encrypt --out D850_0131.enc.bin
```

Key points:

- **Input type auto-detected**: first attempts full parsing as a plaintext container (directory + both CRC levels must pass); only on failure does it XOR the body and try again; it will not double-XOR a plaintext container ([§9.5](#95-plaintext-containers-get-double-xored)).
- **Directory rebuild**: module order, 16-byte name fields, and tags are taken from the original image; `--modules-dir` / `--replace-module` allow changing module length, directory `start/length` are recalculated, and the last module still ends exactly at `body[-16]`.
- **Tag zeroed by default**: D750's `_wma_ver01.00.00` originally has ASCII `crc.bin`, which would cause the strict validator to falsely reject ([§9.1](#91-strict-validator-false-positive-on-crcbin-tag)). By default the 8-byte tag is zeroed, so the output passes strict validation directly; to replicate the original image byte-for-byte add `--keep-tags` (the strict validator will still falsely reject it).
- **Output form follows input by default**: encrypted in → encrypted out, plaintext in → plaintext out; `--encrypt` / `--plaintext` can force otherwise.
- **Header digest**: Wrapper B's first 20 bytes are `SHA1(body || K8)`. DSLR's `K8` is unknown, so it is kept as-is by default; if the body changes, `STALE` is printed. If `K8` is recovered in the future, pass it with `--k8 k8.json` (`{"K8": "<16 hex>", "self_check": "<sha256>"}`); the script will first verify the original image's digest, then recompute for the new body.
- See [§5.6](#56-exit-codes) for exit codes.

---

## 6. Repository Layout

### 6.1 Directory Tree

```text
.
├── .github/ISSUE_TEMPLATE/
│   ├── config.yml
│   └── validation-report.yml
├── README.md / README.en.md
├── CONTRIBUTING.md
├── SECURITY.md
├── VALIDATION_MATRIX.md
├── PUBLISH_CHECKLIST.md / ISSUES_TO_CREATE.md / README_TOP_SNIPPET.md
├── LICENSE                       # GPL-3.0
├── .gitignore                    # firmware/derived artifacts excluded
├── key_all.json                  # 22-image regression-passing key set (T1/T2/T3 + sources + self_check)
├── extract_key.py                # blind key recovery (five stages) + full validation
├── extract_key_dslr.py           # thin wrapper: HDR=0
├── extract_key_mix.py            # mixed-HDR corpus key recovery
├── decrypt_firmware.py           # decrypt + validate + directory parse (main library)
├── decrypt_dslr.py               # thin wrapper: HDR=0
├── decrypt_dslr2.py              # auto-detect HDR + carve modules
├── repack_firmware.py            # rebuild directory/CRCs, patch/replace modules, re-encrypt
├── fill_t3.py                    # missing blocks: heuristic scoring + combinatorial enumeration
├── solve212.py / solve212b.py / solve212c.py   # missing-block pinpoint brute force
├── finalize_key.py               # merge corrections, write key_all.json
├── dump_toc.py                   # print D750_0101 decrypted directory
├── analyze_core.py / find_base.py / check_base.py / scan_addrs.py   # static-analysis probes
├── scan_code.py / disasm_thumb.py / disasm_vtable.py
└── search_strings.py / find_refs.py / dump_region.py / find_ptrtables.py
```

### 6.2 Script Inventory

| Script | Stage | Purpose |
| --- | --- | --- |
| `extract_key.py` | key recovery | five-stage blind recovery + directory/CRC validation + write key |
| `decrypt_firmware.py` | container | decrypt, strict validate, directory parse (default `HDR=0x20`) |
| `decrypt_dslr.py` | container | thin wrapper fixing `HDR` to 0 |
| `extract_key_dslr.py` | key recovery | thin wrapper fixing `HDR` to 0 |
| `extract_key_mix.py` | key recovery | detect `0x00`/`0x20` per file, mixed corpus |
| `decrypt_dslr2.py` | artifact | auto-detect + print directory + write `.modules` |
| `repack_firmware.py` | artifact | rebuild directory/CRC, replace/patch modules, re-encrypt, validate |
| `fill_t3.py` | fill | for missing blocks, score by 0x00/0xFF/printable/ARM weights, enumerate candidate combos with CRC oracle |
| `solve212.py` | fill | fix 190/191, brute 212 (strict validation) |
| `solve212b.py` | fill | same, switched to CRC-only validation (to bypass false positive) |
| `solve212c.py` | fill | `correct_t3` first, then brute |
| `finalize_key.py` | artifact | merge corrections, output final `key_all.json` |
| `dump_toc.py` | observation | print `D750_0101` decrypted directory hexdump |
| `analyze_core.py` | analysis | entropy, ARM condition ratio, keywords, strings, first-64-byte disassembly |
| `find_base.py` | analysis | count "pointer-like words" across 8 candidate base addresses |
| `check_base.py` | analysis | reverse-lookup base from vector-table literals and attempt disassembly |
| `scan_addrs.py` | analysis | frequency of `0x80000000-0xA0000000` words |
| `scan_code.py` | analysis | per-64 KiB ARM/Thumb push/pop/bx scoring |
| `disasm_thumb.py` | analysis | ARM/Thumb disassembly at 3 fixed offsets |
| `search_strings.py` | analysis | feature keyword search (movie/menu/driver/etc.) |
| `find_refs.py` | analysis | absolute/relative pointer cross-reference of target strings |
| `dump_region.py` | analysis | region hexdump + `0x90xxxxxx` word list |
| `find_ptrtables.py` | analysis | find ≥4 contiguous `0x90000000..0x90200000` odd words (Thumb function table) |
| `disasm_vtable.py` | analysis | disassemble vtable slots in a region one by one |

> `extract_key.py` and `decrypt_firmware.py` are **copied verbatim** from [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) (GPL-3.0) without modification; the rest are adaptations and research patches by this repository on the DSLR corpus. See [§11](#11-references).

---

## 7. Attempt Log

This section, in "what problem were we solving → what was done → what resulted" order, explains the purpose of each script. Timeline reconstructed post-hoc from file modification times and script contents.

### 7.1 Timeline

| Time | Stage | New script / artifact | Problem being solved |
| --- | --- | --- | --- |
| 10-31 21:58 | start | `extract_key.py`, `decrypt_firmware.py` | Directly reuse [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)'s two scripts (Z-series-oriented; `KNOWN`, `MINIMAL`, `0x260` checks are its conventions) |
| 10-31 21:59–22:00 | adapt | `decrypt_dslr.py`, `extract_key_dslr.py` | DSLR images have no 32-byte header, tag at 0x00, must set `HDR=0` |
| 11-01 09:54 | adapt | `extract_key_mix.py` | Corpus mixes both header wrappers, need per-file detection |
| 11-01 10:41 | fill | `fill_t3.py` | Fill coverage does not reach all 256 `T3` blocks |
| 11-01 10:45–10:57 | fill | `solve212.py` / `b` / `c` | Gap narrowed to 190/191/212, try per value; discovered strict-validator false positive |
| 11-01 10:49 | observe | `dump_toc.py` | Confirm real directory layout after decryption |
| 11-01 11:03–11:05 | finalize | `finalize_key.py` → `key_all.json` | Write corrections back, produce regression-capable key set |
| 11-01 11:07–11:10 | artifact | `decrypt_dslr2.py` → `D750_0115.dec(.modules)` | Auto-detect header and batch-carve modules |
| 11-01 11:13–11:46 | analysis | `analyze_core.py`, `find_base.py`, `check_base.py`, `scan_addrs.py`, `scan_code.py`, `disasm_thumb.py`, `search_strings.py`, `find_refs.py`, `dump_region.py`, `disasm_vtable.py`, `find_ptrtables.py` | From "can open" to "can localize" |
| 11-04 13:00–13:30 | new samples | D810 / D850 / D5 plaintext containers and modules | Cross-model re-validation of container structure and module composition |

### 7.2 Stage 0: Understand the container first

**Problem**: Is the `.bin` an "encrypted whole", or a "container with plaintext directory"? Which directory fields are trustworthy?

**Approach**: Early manual hexdump; once keys were available, `dump_toc.py` to re-verify the directory layout. Both observations agreed: big-endian, `count/dirsize`, 16-byte fixed-length names, body-relative offsets, strictly contiguous modules, 16-byte trailer with two-level CRC.

**Result**: The container model in [§2](#2-firmware-container-format). All subsequent "did we decrypt correctly" judgments build on this model — this is the single most critical early decision of the project.

### 7.3 Stage 1: Squeeze the key out of the ciphertext

**Problem**: No key, no known plaintext pair, and corpus spans multiple models and versions.

**Approach**: The five stages of `extract_key.py` ([§3.3](#33-five-stage-recovery-algorithm)).

**Result**: `T1/T2/T3` obtained, and all 22 images pass directory + CRC validation.

**Key judgments**:

- Use "repeated fill sectors" rather than "per-byte statistics" to anchor `T1`, because the former is naturally immune to fill constant and sector constant.
- Use "can the directory parse" to fix the 8-bit constant, rather than printable ratio — `correct_t3` has a comment specifically noting that printable-character scoring misjudges XORed UTF-16LE strings.
- Use bipartite graph majority propagation rather than directly solving linear equations, because the observations contain bad cells; majority propagation tolerates them.

### 7.4 Stage 2: Adapt DSLR wrapper differences

**Problem**: Same-generation images have two headers (no prefix / 32-byte prefix); the tool defaults to `HDR=0x20`, so D750 is globally misaligned.

**Approach**:

- `decrypt_dslr.py` / `extract_key_dslr.py`: fix `HDR` to 0;
- `extract_key_mix.py`: check the space tag at `0x00` or `0x20` per file, so mixed corpus works;
- `decrypt_dslr2.py`: auto-detect + carve modules directly.

**Result**: `D750_0115.bin` (wrapper A) decrypts to 3 modules, all module CRC and package CRC pass; D810/D850/D5 modules match direct directory carving byte-for-byte (verified in this review).

**Key judgment**: Phase anchored at the space tag, not the file's first byte, so the two wrappers share one table set. This judgment was later validated by `key_all.json`'s 22 mixed `header: 0 / 32` records.

### 7.5 Stage 3: Fill key holes

**Problem**: Corpus fill coverage does not reach all 256 `T3` blocks; stage 4/5 can only give partial values or leave `0x00/0xFF` binary choices. Remaining gaps are `b = 190 / 191 / 212`.

**Approach and evolution**:

1. `fill_t3.py`: for each missing block, enumerate 256 candidates, weight-score by `zeros`, `0xFF`, `printable`, `ARM condition field`, take top 6, then Cartesian-product the combinations, pick truth with CRC.
2. `solve212.py`: narrow to the 190/191/212 three blocks at hand, fix `190=0x57,191=0x8E`, brute 212 from `0x00` to `0xFF`. Uses strict validator.
3. `solve212b.py`: found that the strict validator falsely rejects due to the `crc.bin` tag (see [§9.1](#91-strict-validator-false-positive-on-crcbin-tag)), so inlined a `validate_dslr` that only checks directory chain + CRC.
4. `solve212c.py`: first fill `T3` with 0 to 256 entries and run `correct_t3` once, then brute 212, avoiding missing keys hitting unrelated errors on the validation path first.
5. `finalize_key.py`: hardcode `190=0x57`, `191=0x8E`, `212=0xDE`, merge `correct_t3` results, write `key_all.json`.

**Result**: `key_all.json`'s three tables exactly match built-in regression hashes; `T3[190]=0x57`, `T3[191]=0x8E`, `T3[212]=0xDE` re-verified.

**Lesson**: Validators must match the real field semantics of the container. The strict validator additionally checked "reserved field must be zero", but real images can carry ASCII tags there — a correct key was thus killed, wasting a round of investigation.

### 7.6 Stage 4: From unpacking to static localization

**Problem**: What is inside the decrypted modules? Where is the code? How are strings referenced?

This stage has no I/O contract, it is all probes. Actual observations on `D750_0115.dec.modules/b1010_115a.bin` (20.3 MB main image):

- **Entropy and instruction shape** (`analyze_core.py`): overall entropy 6.30, first 2 MB roughly 6.9–7.2 per 64 KiB; ARM condition field (`word >> 28 == 0xE`) overall only 3.9%, first 4 MB mean per 64 KiB ~8.6%, per-block varying wildly from 0 to 0.81 — indicating the image is **ARM / Thumb-2 / data mixed**, not pure ARM. `scan_code.py` counts 755 `push {…, lr}` (`0xB5xx`), 631 `pop {…, pc}` (`0xBDxx`), 135 `bx lr` (`0x4770`) within 64 KiB around `0x250000`, judging the body to be **Thumb-2**, with ARM reserved for exception entry.
- **Platform keywords**: `Nikon` @ `0x38C74` (`NikonMotionDetector Ver6.0 2013.09.19`), `T-Kernel` @ `0x1264FDA` (`SysName\0T-Kernel\0TMaxTskId...` config table), FotoNation copyright @ `0x11F3E1B`; `VxWorks` / `ThreadX` / `ITRON` / `eCos` / `Linux` / `FR-V` / `SOFTUNE` all miss. → **ARM + T-Kernel** platform.
- **Entry structure**: main image starts with `5 × ldr pc,[pc,#0x18]` + `nop` + `b 0x54`, literals are `0x9027D524`, `0x90291C80`, `0x90291D30`…; from `0x54` is standard ARM init (`sub lr,lr,#4; push {r3,lr}; …`), `Ver.1.15a` is at `0x48`, matching the filename `D750_0115`.
- **Code distribution** (`scan_code.py`): `0x250000`, `0x1B0000`, `0x100000`, `0x1E0000` score highest; `0x250000` disassembles to consecutive legal Thumb-2 (`bl 0x9020ED7C`, `bl 0x9018A098`…).
- **Base and cross-reference**: `find_base.py` / `check_base.py` / `scan_addrs.py` revolve around `0x90000000` for pointer density and vector reverse-lookup; `find_refs.py` already locates target strings, e.g. `CMoviePlayApplicationService_RequestStartPlay` @ `0x2F1901`, `D750_MenuList_FU-02` @ `0x73464C`, `APPMENU` @ `0x10CDA0`, `HI ISO,HIGH` @ `0x12F0DC`, but **neither absolute nor relative pointers hit**.
- **Next hypothesis**: since direct pointers find no references, turn to "contiguous odd pointer table" (`find_ptrtables.py`) and "vtable slot disassembly" (`disasm_vtable.py`), i.e., assume string addresses are written at runtime by relocation or table lookup.

**Result**: Confirmed platform, code shape, and many readable strings, completing the transition from "can open" to "can localize strings"; **function-level cross-reference not yet closed**.

### 7.7 Stage summary and open items

- ✅ Key recovery and key-set finalization (`key_all.json`, 22-image regression).
- ✅ Auto-detection and artifact generation for two header wrappers.
- ✅ Module-level unpacking: Firmware A / B / wireless module / auxiliary small images.
- ⚠️ String cross-reference not closed: literal pointers all miss, suspect relocation, pointer table, or runtime write.
- ⚠️ Vector-table literals mapped to file offsets do not land on standard function prologues (prologues appear a few words later), indicating literals and function starts do not strictly correspond, or the image undergoes a relocation/descriptor layer before running; this is not closed.
- ❌ Z-series new wrapper (`0x260`) unbroken.
- ❌ Inner compression/encryption layer of modules only identified (see [§8.3](#83-new-observations-during-review)), not systematically expanded.

---

## 8. Sample Review

The following conclusions were measured in this review; commands and results are reproducible.

### 8.1 Actual State of the Four `.bin` Files

| File | Size (B) | State | body offset | Handling | Modules | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `D750_0115.bin` | 21,552,187 | encrypted original | `0x00` | XOR decrypt | 3 | module CRC + package CRC all pass; output matches `D750_0115.dec` byte-for-byte |
| `D810_0114.bin` | 20,179,044 | plaintext container | `0x00` | direct carve | 2 | both CRC levels pass |
| `D850_0131.bin` | 27,660,549 | plaintext container | `0x20` | direct carve | 4 | both CRC levels pass |
| `D5__0150.bin` | 48,176,012 | plaintext container | `0x20` | direct carve | 4 | both CRC levels pass |

SHA-256 (full values):

```text
D750_0115.bin  6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
D750_0115.dec  1ec77111106a67076d9e70886c6e159d29609238d96e65e70f7329be7c749bdd
D810_0114.bin  a8e00377899e4c347e9afd0a346d28f8dc8100cab41154ec9ab3861fd55b68af
D850_0131.bin  6473bba8a154cb8cb5ff27345bb84a8513593e547fbe63a9dfce7b9d288f53f4
D5__0150.bin   db8103e64d9f3c16391a5f7bde8a79cd1a59d78858e9c57871e325eb98df3ed1
```

> **Important**: In `key_all.json`'s `sources`, the SHA-256 of `D810_0114`, `D850_0131`, `D5__0150` **differ** from the author's local same-named files (e.g., `D850_0131` records `4599b238…`, local is `6473bba8…`). This means `sources` records another batch of **encrypted originals**; the author's three local files are plaintext containers (original 32-byte header retained, presumably decryption products; the samples are not shipped with this repository). Only `D750_0115.bin`'s hash matches `sources` — it is the true encrypted input.

Therefore: **do not test the decryptor with plaintext-container samples** — they do not need decryption, and running XOR only destroys the directory.

### 8.2 Carved Modules

| Image | Module | Size (B) | Observation and inferred role |
| --- | --- | --- | --- |
| D750 | `a1010_011100.bin` | 786,432 | header looks like an offset/descriptor table; contains `D750   Firmware A Copyright Nikon Corp.` → **Firmware A** (boot/platform) |
| D750 | `_wma_ver01.00.00` | 441,141 | `WLAN1`, `wlanapi_init()`, `add_wlan_event()` → **wireless/Bluetooth module firmware** |
| D750 | `b1010_115a.bin` | 20,324,448 | ARM vector table + `Ver.1.15a` + `T-Kernel` config table + FotoNation copyright → **Firmware B** (main application) |
| D810 | `a920_011300.bin` | 1,048,576 | `D810   Firmware A …` |
| D810 | `b920_114.bin` | 19,130,336 | main application |
| D850 | `a1330_010303.bin` | 1,048,576 | `D850   Firmware A …` |
| D850 | `_wma_ver01.11.00` | 882,985 | starts with `DfuSe` (ST DFU container), contains `wlan_init()` / `bt_init()` → **wireless/Bluetooth module firmware** |
| D850 | `_tpj00_0150.bin` | 57,344 | no ASCII string, table-like data → small auxiliary image (MCU/table), unconfirmed |
| D850 | `b1330_131.bin` | 25,671,412 | main application |
| D5 | `a870_013000.bin` | 1,048,576 | `D5     Firmware A …` |
| D5 | `_wt5160_.bin` | 23,165,550 | starts with ` 061WT-5` + **gzip stream**; decompresses to 37,847,040 B, begins with `fw_data.bin` and contains `ARMv7 Processor` (see §8.3) |
| D5 | `_tpcy_0009.bin` | 60,002 | table-like data, unconfirmed |
| D5 | `b870_150.bin` | 23,901,652 | main application |

Module naming pattern: `a<platform>_<version>` / `b<platform>_<version>`. D750's `b1010_115a.bin` additionally carries `Ver.1.15a` at `0x48`, cross-checkable with the filename (other models not checked individually).

### 8.3 New Observations During Review

- `_wt5160_.bin`'s first 32 bytes are ` 061WT-5` + padding; from `0x20` is standard gzip (`1f 8b 08`). Decompression yields 37,847,040 bytes, starting with `fw_data.bin`, containing `ARMv7 Processor`. This indicates **another compression layer nested in the container**; this repository does not expand it further.
- `_wma_*` is not WMA audio, it is **WLAN/Bluetooth module firmware**: D750 version has `WLAN1`, `wlanapi_init()`; D850 version is additionally wrapped in ST's `DfuSe`.
- The strict validator's false positive on `D750_0115.bin` occurs only on the `_wma` entry's 8-byte `tag` (value `crc.bin`). All other fields (count, dirsize, module chain, module CRC, package CRC) are all correct.

---

## 9. Known Issues

### 9.1 Strict Validator False Positive on `crc.bin` Tag

`decrypt_firmware.validate_firmware` requires the directory entry's trailing 8-byte `tag` to be all zero. D750's `_wma_ver01.00.00` entry has ASCII `crc.bin` there, so correct decryption is judged dead:

```text
error: module 2 (_wma_ver01.00.00) has nonzero reserved bytes; nothing written.
```

**Handling**: `decrypt_dslr2.py` does not perform this check; when validation is needed, use the CRC-only `validate_dslr` from `solve212c.py` / `finalize_key.py`, or relax the reserved-field check to "allow ASCII tags". This is a container-semantics issue, not a key issue — `D750_0115.dec`'s three module CRCs and package CRC all pass.

### 9.2 `extract_key.py`'s Directory Probe Is Simplified

`extract_key.parse_table` exists for scoring: its name lookup is intentionally off by one entry, and count/dirsize are only used to judge feasibility. Real parsing is in `decrypt_firmware.parse_table`. Do not mix the two when editing code.

### 9.3 One-Off Scripts Hardcode Corpus Paths and Constants

`fill_t3.py`, `solve212*.py`, `dump_toc.py`, `finalize_key.py` all assume `output/` in the current directory, reference file `D750_0101.bin`, and `finalize_key.py` hardcodes `{190:0x57, 191:0x8E, 212:0xDE}`. They are snapshots of the research process, not general-purpose tools.

### 9.4 `KNOWN` / `MINIMAL` Are Upstream Leftovers

`extract_key.py`'s `KNOWN` hashes and `MINIMAL` whitelist come from upstream [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)'s Z-series samples (`Z_5_0150.bin` etc.). Running on DSLR corpus prints "unknown hash" warnings, does not affect recovery; only meaningful when comparing `EXPECTED_SHA`.

### 9.5 Plaintext Containers Get Double-XORed

`decrypt_dslr2.py` unconditionally XORs the body; on an already-plaintext container it does not error but produces garbage. Detection: whether parsing the body directory directly passes CRC ([§5.4](#54-when-input-is-already-a-plaintext-container)).

### 9.6 Stage 5's "Zero-Fill Priority" Assumption

Corpus with predominantly `0x00` fill works directly; if some block is predominantly `0xFF`, `correct_t3` may pick the wrong one. Final CRC catches it, but requires an enumeration/manual step (`fill_t3.py` exists for this). The 3 blocks missing at the time are of this kind.

### 9.7 The 16 MiB Period Is a Feature, Not a Bug

Files beyond 16 MiB reuse the keystream. This is a cryptographic weakness and the reason the 48 MB-class D5 image in `key_all.json` opens with the same tables; do not mistake "period reuse" for a decryptor index error. Note that the author's local `D5__0150.bin` is already a plaintext container and must not be re-decrypted.

### 9.8 Version-Number Warning Is a Hint

`decrypt_firmware.main` prints a warning when the version number in the filename does not appear in module names. Component versions may lag the release version, so this is a hint, not an error.

### 9.9 `capstone` Is an Optional Dependency

`analyze_core.py` degrades on import failure (no disassembly); `disasm_thumb.py`, `disasm_vtable.py`, `check_base.py` depend directly on capstone. Without it, those scripts are unavailable but the main decryption flow is unaffected.

### 9.10 `decrypt_dslr2.py` Silently Overwrites Output

`decrypt_dslr2.py` does no clobber check; `--out` existing is overwritten directly; `decrypt_firmware.py` / `decrypt_dslr.py` require `--force`. Back up before batch processing, or confirm the target path first.

---

## 10. Security and Compliance

- **Firmware copyright belongs to Nikon.** The repository contains no `.bin` / `.dec` / `.modules` (`.gitignore` excludes them); the author's local copies are for personal research archival only and must not be publicly distributed or used commercially.
- **Use only on devices you own.** Unpacking/analysis is interoperability research; do not use it to bypass copyright protection, produce, and distribute modified firmware.
- **Do not flash modified images directly.** Container CRC can be recomputed, but whether the camera or updater performs signature verification or model checks is unknown; wrong firmware may brick the device and void the warranty.
- **CRC is not a signature.** All "validation passed" here only means structure and checksums are self-consistent, not that the source is trustworthy.
- **License**: the full **GPL-3.0** text is in [`LICENSE`](LICENSE). `extract_key.py` and `decrypt_firmware.py` are copied verbatim from [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool), which uses GPL-3.0. These two files and their derivatives must continue to be distributed under GPL-3.0 with copyright/license notices preserved; new scripts that form a combined work with them must also satisfy GPL-3.0 when distributed — confirm with the author. The upstream repository itself contains no firmware or derived keys; this repository contains only `key_all.json`, not firmware samples.

---

## 11. References

### Upstream project

The `extract_key.py` and `decrypt_firmware.py` in this repository are **copied verbatim** from [**WonderLantern/nikon-fw-key-tool**](https://github.com/WonderLantern/nikon-fw-key-tool) ([README](https://github.com/WonderLantern/nikon-fw-key-tool/blob/main/README.md), GPL-3.0):

- Both files are byte-identical to the version on that repo's `main` branch: `extract_key.py` 14,643 B (git blob `474941036131b2388135688db86d8533e59f1b92`), `decrypt_firmware.py` 9,754 B (git blob `14128ca1240542634554945458b128b8b93c8f26`).
- The directory/CRC rules, the Z-series regression samples in `KNOWN` / `MINIMAL`, the `0x260` new-scheme check, and the 20-byte header digest and `K8` explanation all come from that project's code and README.
- Upstream's scope is Z 5 / Z 6 / Z 6II / Z 7 / Z 7II / Z 8 / Z 9 / Z 30 / Z 50 / Z fc; of these, `repack_firmware.py` and `solve_signature_e7.py` (Z 8/Z 9 header-digest recomputation and signing-key recovery) are **not included** here.
- Upstream README sections: [Firmware format](https://github.com/WonderLantern/nikon-fw-key-tool#firmware-format), [XOR encryption](https://github.com/WonderLantern/nikon-fw-key-tool#xor-encryption), [Checksums and header digest](https://github.com/WonderLantern/nikon-fw-key-tool#checksums-and-header-digest).

What this repository adds on top: adapting `HDR` to the two DSLR tag positions (`0x00` / `0x20`), merging multi-model corpus to recover and finalize `key_all.json`, filling the 3 missing `T3` blocks, producing `.dec` / `.modules` artifacts, and a set of static-analysis probes.

### Others

- CRC-16/XMODEM parameters (poly `0x1021`, init `0`, no reflection): <https://reveng.sourceforge.io/crc-catalogue/16.htm>
- T-Kernel / TRON real-time kernel: the decrypted `b*` module contains a `SysName → T-Kernel` config table, usable as platform evidence.
- Classic analysis of WEP/RC4 keystream reuse, similar to this scheme's "16 MiB period + known plaintext" weakness, useful as a reference for understanding statistical recovery (e.g., FMS attack and WEP known-plaintext analysis).

### How to add a new model

1. Prepare the encrypted `.bin` for that model, run `extract_key_mix.py` or the corresponding `HDR` script; if `self_check` matches [§4.1](#41-verified-models-and-versions), the same table applies.
2. After decryption, confirm the directory and CRC all pass with `validate_firmware` (or plaintext-container carving).
3. Append `{file, sha256, header}` to `key_all.json`'s `sources` and `validated`, and add a row to this README's table.
4. If a new header wrapper appears, extend `detect` / `check_scheme` first, then discuss the key — do not guess the key without a container model.