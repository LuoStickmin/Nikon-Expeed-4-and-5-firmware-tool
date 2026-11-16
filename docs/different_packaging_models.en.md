# Packaging Variants, K8 Status and Tooling Requirements

> Recorded: 2026-11-16  
> Scope: Nikon Expeed 4/5 DSLR firmware containers; Z-series packaging is only
> identified and rejected  
> Read-only analysis summary; **no firmware, decrypted modules, key files or
> flashable images are included**

## 0. Summary

“Expeed 4” does **not** mean “headerless A”. At least three header layouts exist:

| Type | 32-space label | Body starts | Extra check | Examples |
| --- | --- | --- | --- | --- |
| **A** | `0x00` | `0x00` | none | D4S/D5300/D5500/D7200/D750/D810/D810A |
| **B** | `0x20` | `0x20` | `SHA1(body ‖ K8)` in 20 B | D3400/D5600 (Expeed 4); D850/D5/D500 (Expeed 5) |
| **new** | `0x260` | `0x260` | plaintext header, payload cipher unbroken | Z 5II / Z 50II / Z 6III / ZR class |

Detect from the **32 `0x20` spaces** in the file, never from the generation or
model year.

## 1. Detection

`detect_header()` in `decrypt_dslr2.py` / `repack_firmware.py`:

- `raw[0x00:0x20] == 32 × 0x20` → **A**;
- `raw[0x20:0x40] == 32 × 0x20` → **B**;
- `raw[0x260:0x280] == 32 × 0x20` → **new scheme**, explicitly rejected;
- otherwise → not a supported legacy container.

A/B share the same body layout, module CRCs, package CRC and XOR cipher; only the
file prefix and header digest differ.

## 2. Packaging A

```text
0x0000  32 × 0x20       space label = body start
0x0020  BE32 count
0x0024  BE32 dirsize = 48 + 32 × count
0x0028  8 × 0x00
0x0030  count × [16B name | BE32 start | BE32 length | 8B tag]
...     adjacent modules, each ending in 2B CRC16
end     BE16 package CRC + 14 × 0x00
```

- No header digest: changing the body only needs module CRC/package CRC and
  re-encryption.
- A may be encrypted or plaintext: D810 1.14 is a plaintext sample; D4S/D5300/
  D5500/D7200/D750/D810A are encrypted samples. Do not equate A with either.
- D750's `_wma_ver01.00.00` tag is ASCII `crc.bin`, not eight zero bytes; strict
  validators may complain. Preserve tags with `--keep-tags`, or normalize with
  `--zero-tags` only when intended.
- Recompute **both** module CRC and package CRC; a package CRC alone does not prove
  the payload was untouched.

## 3. Packaging B

```text
0x0000  20 B  header digest   SHA1(decrypted_body ‖ K8)
0x0014  12 B  unidentified    copied verbatim
0x0020  32 × 0x20            space label = body start
0x0040  BE32 count
...
```

- `K8` is an **8-byte, per-model** key, not an asymmetric signature.
  `header[0:20]` is not `SHA1(body)`; K8 must be appended first.
- Changing the body requires recomputing the digest with that model's K8.
- Without K8, `repack_firmware.py` refuses to write by default (exit 8); copying
  the old digest produces a stale header. `--allow-stale-header` is for CRC/QEMU
  tests only, not real flashing.
- `--k8` accepts a JSON file (`K8` 16 hex chars + `self_check` SHA-256 of the 8
  bytes) or a directory of `*.json` files. The tool verifies the stock digest,
  picks the matching key and reports its filename.

### 3.1 Recovered K8 values

| Model | Firmware | K8 | Source |
| --- | --- | --- | --- |
| D850 | C:1.31 | `C5005F49CFF65525` | [docs/k8-dslr.en.md](k8-dslr.en.md) |
| D5 | C:1.50 | `1F0CE7E3DDA60907` | [docs/k8-dslr.en.md](k8-dslr.en.md) |
| D500 | C:1.40 | `66A13EE6A8573486` | [docs/k8-dslr.en.md](k8-dslr.en.md) |
| D3400 | C:1.13 | `AF08FBDBB582B587` | [docs/k8-dslr.en.md](k8-dslr.en.md) |
| D5600 | C:1.20 | `6FA0738BE53A7DE7` | [docs/k8-dslr.en.md](k8-dslr.en.md) |

Boundaries:

- K8 is per-model; never reuse it across models.
- Whether different firmware versions of the same model share K8 is unverified.
- A matching digest proves container consistency, **not** camera acceptance or
  image trust.
- D3400's trailing 12 header bytes are non-zero; the tool copies them verbatim.

### 3.2 Common B mistakes

- Reading B with `HDR=0`, or A with `HDR=0x20`, shifts the whole directory.
- Comparing `SHA1(body)` will never match; that is not the definition.
- Solving K8 against the encrypted body yields zero matches; use the decrypted
  body.
- Changing a module without recomputing the header digest yields “all CRCs OK but
  camera rejects”.

## 4. New scheme (`0x260`)

Recognized and rejected, not supported for repacking:

- 32-space label at `0x260`, not `0x00`/`0x20`;
- header is plaintext, but the payload cipher is unbroken;
- examples: Z 5II / Z 50II / Z 6III / ZR class;
- do not apply A/B body offsets, CRCs or K8 logic.

## 5. Other platforms

Not part of the legacy DSLR container:

- Nikon 1: different platform/menu/container;
- Coolpix / KeyMission: different platform;
- lens firmware (`lens-fw`): different container and checksums;
- phone/software updates: not camera firmware containers.

## 6. Cross-project evidence

| Project/document | Finding |
| --- | --- |
| [docs/k8-dslr.en.md](k8-dslr.en.md) | Static recovery of D850/D5/D500/D3400/D5600 wrapper-B K8; the `0x10000080` 8-byte constant is shared; no camera needed |
| [docs/d3400-wrapper-b.en.md](d3400-wrapper-b.en.md) | D3400 is Expeed 4 but packaging B; first record that E4 can be B |
| local `D850-K8` workspace | K8 solving for D850/D5/D500 and `keys/` evidence |
| [LuoStickmin/D750-QEMU](https://github.com/LuoStickmin/D750-QEMU) | D750 packaging A, encryption/repack, QEMU validation and LCD dump |
| [LuoStickmin/E4_HQ_VID](https://github.com/LuoStickmin/E4_HQ_VID) | Expeed 4 movie profiles; D3400/D5600 B; eight stock-checked profiles and container-level repack tests |
| [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) | Early container/checksum/header-digest documentation and tools |

## 7. Tooling requirements

- [ ] Detect A/B/`0x260` from the 32-space labels; never hard-code by model.
- [ ] All offsets body-relative (A: 0; B: 0x20).
- [ ] Validate `dirsize == 48 + 32 × count`, adjacent modules, names/reserved bytes.
- [ ] Recompute module CRC16 and package CRC; never only one layer.
- [ ] Preserve/handle tags (D750 `crc.bin`); separate strict and relaxed validators.
- [ ] Preserve header and 32-space label during XOR; body cipher must round-trip.
- [ ] Support `--k8` (file or directory); verify stock digest before writing and
      recompute for output.
- [ ] Refuse stale headers by default; `--allow-stale-header` is test-only.
- [ ] `--selftest` decrypts/compares the result; output should be bit-identical on
      a no-op edit.
- [ ] Ship no firmware, keys or flashable images; document methods and checksums only.

## 8. Quick reference

| Model | Packaging | K8 | Notes |
| --- | --- | --- | --- |
| D4S 1.33 | A | — | encrypted |
| D5300 1.03 | A | — | encrypted; movie UI differs from D5500 |
| D5500 1.02 | A | — | encrypted |
| D7200 1.01/1.04 | A | — | encrypted; 22×0x1C movie table |
| D750 1.01/1.02/1.11/1.15 | A | — | encrypted; `_wma` tag `crc.bin` |
| D810 1.02/1.14 | A | — | 1.14 is a plaintext sample |
| D810A 1.03 | A | — | encrypted |
| D3400 1.10/1.13 | **B** | `AF08FBDBB582B587` (1.13) | Expeed 4; trailing 12 header bytes non-zero |
| D5600 1.20 | **B** | `6FA0738BE53A7DE7` | Expeed 4; K8 recovered |
| D850 1.31 | **B** | `C5005F49CFF65525` | Expeed 5 |
| D5 1.50 | **B** | `1F0CE7E3DDA60907` | Expeed 5 |
| D500 1.40 | **B** | `66A13EE6A8573486` | Expeed 5 |
| Z 5II / Z 50II / Z 6III / ZR | new `0x260` | — | identify/reject only |

> “Encrypted” means the body is XORed; the header and space label remain plaintext.
> A/B and encrypted/plaintext are independent properties.

## 9. References

- [docs/k8-dslr.en.md](k8-dslr.en.md)
- [docs/d3400-wrapper-b.en.md](d3400-wrapper-b.en.md)
- [README.en.md](../README.en.md) container and repacking sections
- [LuoStickmin/E4_HQ_VID](https://github.com/LuoStickmin/E4_HQ_VID)
- [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)
