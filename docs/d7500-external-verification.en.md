# D7500 external verification record (third-party case)

> Recorded: 2026-11-20  
> Source: [noahengelking/nikon-d7500-firmware-notes](https://github.com/noahengelking/nikon-d7500-firmware-notes)  
> Nature: a cross-check record, not new key or firmware work. Like this repository,
> that project ships **no** firmware, decrypted modules, XOR tables or `K8` — only
> method, offsets and check values.

## 0. Bottom line

The other project walked the D7500 (EXPEED 5, C 1.12) container, both CRC levels,
`K8` and the repack path independently, and reached the same conclusions as this
repository. One of its results fills a question this repository explicitly marks as
unverified in [k8-dslr.en.md](k8-dslr.en.md#6-limits):
**the D7500 `K8` is the same for C 1.10, 1.11 and 1.12** (the value is not published).

Use it as **third-party corroboration for the D7500**, not as an independent key
source: the table hashes are the same upstream regression values, and neither `K8`
nor firmware is published.

## 1. Item-by-item comparison

| Item | Their D7500 C 1.12 | This repository | Verdict |
| --- | --- | --- | --- |
| Container layout | Wrapper B; space label at file `0x20`; `count=3`, `dirsize=144`; 16 B name + BE32 start/len + 8 B tag; BE16 module CRC; package CRC + 14 × `0x00` | Same (README §2), offsets relative to body, `dirsize = 48 + 32 × count` | ✅ Agrees (they use file offsets — `count` at `0x40`; body-relative is `0x20`, a `0x20` shift, not a conflict) |
| Modules | 3: `a1450_011100.bin` (~1.0 MB), `_wma_ver01.11.00` (~0.84 MB), `b1450_112.bin` (~23 MB) | Same naming rules (`a*` = Firmware A, `b*` = Firmware B, `_wma_*` = wireless); D7500 module names were not recorded here | ✅ Rules agree, new detail |
| CRC | CRC-16/XMODEM (`0x1021`, init 0, no reflection, no final XOR); module and package CRCs pass | Same (§2.3) | ✅ Agrees |
| Obfuscation | 3 × 256 B tables, 16 MiB period, phase relative to body | Same (§3.1) | ✅ Agrees |
| Table hashes | `self_check` lines equal the upstream `EXPECTED_SHA` | `key_all.json`'s `self_check` is byte-identical | ✅ Verified locally |
| Cross-model | `T1` byte-identical across 15 images (D500 / D5600 / D7500 / D780 / D850 + Z series) | 22 images, 12 models, one table set (§4.1) | ✅ Same direction; they additionally cover D780 and Z |
| Header digest | `header[0:20] == SHA1(body ‖ K8)`, wrapper B | Same (§2.4, [k8-dslr.en.md](k8-dslr.en.md)) | ✅ Agrees |
| `K8` method | 8-byte constant at `0x10000080` + byte-level keystream, 65,536 candidates | `k8_solve.c`, same idea (`raw = D319A081BBF520EF`) | ✅ Agrees |
| `K8` stability | one `K8` validates 1.10, 1.11 and 1.12 | not verified here (one version per model) | 🆕 Fills a gap (value withheld; not re-checked here) |
| Repack | `b1450_112.bin` → `b1450_113.bin` (version bump) + one padding byte + recomputed CRCs and digest; passes offline, **never flashed** | `repack_firmware.py` does the same; camera acceptance equally unknown | ✅ Agrees |
| Feature surface | no peaking / focus shift UI text on D7500, present on D850 | not compared here | ➖ No overlap, reference only |
| Emulation | module loads at `0x10000000`; missing libraries block cold boot | belongs to the D750-QEMU / D850-QEMU line | ➖ No overlap |

## 2. Three cautions

1. **Matching hashes are not two independent recoveries.** The other project states
   those three lines are "also the upstream regression values", i.e. the same
   `EXPECTED_SHA`. The real independence lies in their directory / CRC / module-name
   observations on the D7500 image, and in the `K8` stability result.
2. **`K8` still is not available.** It is withheld for legal reasons; this repository
   therefore still cannot repack a D7500 body change with a fresh digest —
   `repack_firmware.py` requires `--allow-stale-header`. This only affects the header
   digest, not the container, CRCs or module-level patches.
3. **Same boundaries on both sides.** Neither flashed a camera, so "does the body
   accept a version-bumped image" is still unknown; `header[0x14:0x20]` (12 bytes)
   remains unexplained (they call it "nonce-like").

## 3. Reproducible checks

**Local data only (done this time):**

```powershell
python -c "import json,hashlib;d=json.load(open('key_all.json',encoding='utf-8'));print({k:hashlib.sha256(bytes.fromhex(d[k])).hexdigest() for k in ('T1','T2','T3')})"
```

The three lines must match [README §4.1](../README.en.md#41-verified-models-and-versions)
and their `FINDINGS.md` §2 table exactly.

**With an official D7500 C 1.12 image** (SHA-256 recorded in `key_all.json`:
`47e795e1164d4fcd45d53db48d618979053b57d757ec5d213e1bb211809ba0ee`):

```bash
python decrypt_dslr2.py --key key_all.json --firmware D7500_0112.bin --out D7500_0112.dec
```

Expect `header=0x20 count=3`, `dirsize=144`, modules `a1450_011100.bin` /
`_wma_ver01.11.00` / `b1450_112.bin`, and both CRC levels passing. That single step
would confirm their §1 layout and this repository's key set at once. It was **not**
done here: the image is not present on the author's machine right now.

## 4. Still open

- Does the body accept a version-bumped image (neither project flashed one)?
- Semantics of the 12 header bytes at `header[0x14:0x20]`.
- Is there an inner compression/encryption layer in modules (seen only as a gzip
  wrapper inside the D5 `_wt5160_.bin` here)?
- Can peaking and friends be ported from the D850 (they believe a different pipeline
  is involved)?

## 5. References

- [noahengelking/nikon-d7500-firmware-notes](https://github.com/noahengelking/nikon-d7500-firmware-notes) (README / FINDINGS / METHOD / LEGAL)
- [docs/k8-dslr.en.md](k8-dslr.en.md) — the `K8` generator and its 65,536 candidates
- [docs/different_packaging_models.en.md](different_packaging_models.en.md) — A/B wrappers and cross-project evidence
