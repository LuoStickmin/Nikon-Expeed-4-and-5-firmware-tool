# DSLR packaging-B `K8`

> Recorded: 2026-11-15 (2026-11-20: added D5600 and the external D7500 lead)
> Targets: D850 C:1.31, D5 C:1.50, D500 C:1.40, D3400 C:1.13, D5600 C:1.20
> Nature: read-only static analysis; no firmware samples in this repository

## Results

| Model | Firmware | `K8` | index / step | Candidates | Hits |
| --- | --- | --- | --- | --- | --- |
| D850 | C:1.31 | `C5005F49CFF65525` | `45` / `E3` | 65,536 | 1 |
| D5 | C:1.50 | `1F0CE7E3DDA60907` | `3E` / `E9` | 65,536 | 1 |
| D500 | C:1.40 | `66A13EE6A8573486` | `38` / `E3` | 65,536 | 1 |
| D3400 | C:1.13 | `AF08FBDBB582B587` | `39` / `B5` | 65,536 | 1 |
| D5600 | C:1.20 | `6FA0738BE53A7DE7` | `3B` / `1D` | 65,536 | 3* |
| D7500 (external) | C:1.10–1.12 | `DC73A05066D1868C` | `44` / `3B` | — | — |

\* D5600's three hits all yield the **same K8** (`3B`/`6E`/`CE` share the same `T1`
value, so the keystreams are equivalent). The result is judged by identical K8,
not by how many parameter sets coincide.

\* The D7500 row is an external report
([issue #2](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool/issues/2)):
no 65,536 search was run here; the value only reproduces with the same generator and
`keys/t1.hex`. Its digest was not re-checked against an image.

The wrapper-B header digest is, per the upstream definition:

```text
header[0:20] == SHA1(container[0x20:] || K8)
```

## 1. In one sentence

`K8` is not an irreversible black box. It is derived from the 8-byte constant at
`0x10000080` through a byte-level keystream transform, and **that constant is the
same across models**. Given a plaintext container, `K8` falls out of a 65,536-entry
search — **no camera required**.

## 2. Generator

```text
value = T1[index]            # T1: 256-byte constant table
inc   = 0x160 * step
repeat 8:
    value = (value + inc) & 0xFF
    inc  += step
    ks[j] = value

K8 = raw ^ ks                # raw = D319A081BBF520EF
```

* `index` and `step` are one byte each: 65,536 candidates, judged by
  `SHA1(body || K8) == header[0:20]`.
* This is an **equivalent parameterisation**; it does not claim a one-to-one match
  with the firmware's internal `(seed, index)` semantics. D850's documented
  keystream `16 19 FF C8 74 03 75 CA` is reproduced exactly by `index=0x45,
  step=0xE3`.
* `raw` is the 8 bytes at `0x10000080`: `D3 19 A0 81 BB F5 20 EF`. The same
  constant reproduces all five headers, so it is shared by Expeed 4/5 DSLRs.
* `T1` exists in all five images and is **byte-identical**:

  | Image | Offset of `T1` |
  | --- | --- |
  | D850 `b1330_131.bin` | `0x17CF374` |
  | D5 `b870_150.bin` | `0x1632D00` |
  | D500 `D500_0140.dec` | `0x18CB379` |
  | D3400 `D3400_0113.dec` | `0x139019A` |

  `keys/t1.hex` holds these 256 bytes as hex text (the solver also accepts 256
  raw bytes).

## 3. Solver

`k8_solve.c` hashes the body once (SHA-1 midstate) and then finalises each of the
65,536 candidates: a few seconds per image.

```powershell
gcc -O2 -o k8_solve k8_solve.c
./k8_solve D3400_0113.dec keys/t1.hex
# MATCH index=39 step=B5 K8=AF08FBDBB582B587
```

Optional arguments: the 3rd overrides the `raw` constant (16 hex chars), the 4th
overrides the digest start offset (default `0x20`).

## 4. Evidence

1. **Unique K8**: every candidate that passes the 160-bit digest points to the same
   `K8` (usually one set, three equivalent sets for D5600); random-collision
   probability ~2⁻¹⁴⁴.
2. **Independent cross-check**: `repack_firmware.py --selftest --keep-tags`
   reports `header verified on input, recomputed (SHA1(body || K8))` and
   byte-identical output for all five models; the encrypted D500/D3400/D5600
   inputs also pass `decrypt(repack) == plaintext`.
3. **Consistency with the prior record**: D850's keystream, `raw` and
   `K8` (`C5005F49CFF65525`) match the external record exactly, anchoring the
   method.

## 5. Reproduce

```powershell
# 1) decrypt first (K8 only applies to the plaintext body)
python decrypt_firmware.py --key key_all.json --firmware D3400_0113.bin --out D3400_0113.dec

# 2) solve
gcc -O2 -o k8_solve k8_solve.c
./k8_solve D3400_0113.dec keys/t1.hex

# 3) repack and self-test with the recovered K8
python repack_firmware.py --firmware D3400_0113.bin --out out.bin ^
  --key key_all.json --k8 keys/d3400_0113_k8.json --selftest --keep-tags
```

## 6. Limits

- **`K8` is per-model**: all five values differ; do not reuse across models.
- **Cross-version reuse is unverified here**. Only one version per model was solved;
  other versions (D850 `0101`, D500 `0101`/`0111`, …) need their own 65,536 search.
  An external D7500 project reports one `K8` (`DC73A05066D1868C`, issue #2) validating
  C 1.10/1.11/1.12 — generator-consistent here, but not digest-checked by this repository; see
  [d7500-external-verification.en.md](d7500-external-verification.en.md).
- **The plaintext container is required**. An encrypted image has a different body
  and yields zero hits — the first D3400 attempt failed exactly this way.
- **Header digest only**. The 12 bytes at `header[0x14:0x20]` are not covered and
  are copied verbatim.
- **Not a security proof**. Recomputing the digest does not prove the camera will
  accept an image, nor that the image is trustworthy. This repository still ships
  no flashable artifact.
- **Other models**: any Expeed 4/5 wrapper-B image can go through the same search;
  a hit gives `K8`, zero hits mean a different branch (`raw` or generator).

## 7. Effect on repacking

`repack_firmware.py` previously refused any body change for wrapper B (exit 8)
because `K8` was unknown. All of these models are now covered:

```powershell
python repack_firmware.py --firmware stock.bin --out new.bin --k8 keys/ ...
```

`--k8` also accepts a **directory**: every `*.json` in it is tried, the one that
verifies the stock digest is used, and the matching file name is printed:

```
  header     verified (d850_0131_k8.json), recomputed (SHA1(body || K8))
  k8         d850_0131_k8.json
```

This removes the need to know the model up front. Malformed files or ones with a
bad `self_check` are skipped with `note: skipping ...` and do not hide the rest.
`--allow-stale-header` remains for CRC/QEMU testing.
