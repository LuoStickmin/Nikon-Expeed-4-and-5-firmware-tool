# The D3400 wrapper-B variant

> Recorded: 2026-11-14
> Target: Nikon D3400, `D3400_0113.bin`, main module `b1480_113.bin`
> Nature: read-only static analysis; **no firmware, keys, or flashable images**

## Conclusion

D3400 is not wrapper A. Its image carries the standard 32-space label only
after a 32-byte header:

| Item | Value |
| --- | --- |
| File | `D3400_0113.bin` (24,139,012 B) |
| Wrapper | **B** (body offset `0x20`) |
| Space label | `0x20..0x3F` (32 × `0x20`) |
| Directory | at `0x40`: `count=2`, `dirsize=0x70` |
| Modules | `a1480_011001.bin` (786,434 B), `b1480_113.bin` (23,352,418 B) |
| Header | `0x00..0x13`: 20-byte digest; `0x14..0x1F`: 12 unidentified non-zero bytes |
| Body encryption | yes (header and space label are plaintext) |

This is more than "another B body": D3400 is **Expeed 4**, and the Expeed 4
D7200 / D750 / D810 are all A. **The wrapper is not a generation property.**

## 1. How it was found

While adding the D3400 movie-mode profile, the usual space-label probe was run:

| Image | `raw[0:4]` | `raw[0:0x20]` all spaces | `raw[0x20:0x40]` all spaces |
| --- | --- | --- | --- |
| `D7200_0104.bin` | `20 20 20 20` | ✅ | ❌ |
| `D750_0115.bin` | `20 20 20 20` | ✅ | ❌ |
| `D810_0114.bin` | `20 20 20 20` | ✅ | ❌ |
| `D3400_0113.bin` | not spaces | ❌ | ✅ |

`detect_header()` in `decrypt_dslr2.py` / `repack_firmware.py` uses exactly this
rule:

- 32 spaces at `0x00` → **A**;
- 32 spaces at `0x20` → **B**;
- 32 spaces at `0x260` → newer wrapper (Z 5II / Z 50II / Z 6III / ZR class,
  refused by the tool).

So the tool does not hard-code models, but a human must not infer A from
"Expeed 4".

## 2. Layout

```text
A (D7200 / D750 / D810):
0x0000  32 × 0x20        space label = body start
0x0020  BE32 count
0x0024  BE32 dirsize
0x0028  8 × 0x00
0x0030  entry 0
...

B (D3400):
0x0000  20-byte digest   SHA1(decrypted_body || K8), keyed
0x0014  12 unidentified  non-zero; copied verbatim by the tool
0x0020  32 × 0x20        space label = body start
0x0040  BE32 count       D3400: 2
0x0044  BE32 dirsize     D3400: 0x70
0x0048  8 × 0x00
0x0050  entry 0          a1480_011001.bin
0x0070  entry 1          b1480_113.bin
...
```

The body layout, module CRC16, package CRC, and XOR encryption are identical
between A and B; only the file prefix and the 20-byte digest differ.

## 3. The digest is not `SHA1(body)`

Measured on `D3400_0113.dec` (the decrypted container):

| Computation | Equals `header[0:20]`? |
| --- | --- |
| `SHA1(body)` | ❌ |
| `SHA1(body[:-16])` | ❌ |

This matches the upstream wrapper-B definition:
`header[0:20] == SHA1(body || K8)`, where `K8` is an **8-byte model-specific
key**, not an asymmetric signature.

Negative results: appending any of the following as `K8` to `body` or
`body[:-16]` never reproduces `header[0:20]`:

- any 8 consecutive bytes inside the 32-byte header (25 windows);
- eight zero bytes;
- the two 8-byte paddings of `D3400` (`D3400\0\0\0`, `D3400␠␠␠`).

So `K8` is not stored in the header, and it is not a simple model-name padding.
The trailing 12 bytes are non-zero; their meaning is unidentified and the tool
copies them verbatim.

## 4. Why this matters

### 4.1 The wrapper is not a generation property

Both are Expeed 4:

- A: D4S (0133), D5300 (0103), D5500 (0102), D7200 (0101/0104),
  D750 (0101/0102/0111/0115), D810 (0102/0114);
- B: D3400 (0110/0113), D5600 (0120).

"E4 = no header" is wrong. Any code that picks `HDR=0` / `HDR=0x20` from the
generation will misalign on D3400 / D5600.

### 4.2 It defines the repack boundary

D3400 module-level patches (for example movie bitrate) remain valid: module and
package CRCs can be recomputed. But once the body changes, a full image needs:

```text
edit module → recompute module CRC → recompute package CRC → re-encrypt
            → recompute SHA1(body || K8) with K8
```

Without K8, `repack_firmware.py` **refuses to write** (exit 8), because copying
the old digest can only produce a stale header. `--allow-stale-header` forces
the write but is only suitable for CRC / QEMU tests, not real flashing. With
`--k8`, the tool first verifies the stock digest, then recomputes it for the
output.

## 5. Tool behaviour

| Tool | Behaviour |
| --- | --- |
| `decrypt_dslr2.py` | auto-detects `HDR=0x00/0x20`; validates directory and both CRCs before writing |
| `repack_firmware.py` | `detect_header()` classifies A/B/C by the space label; for B it copies `raw[:0x20]`; exits 8 if the body changes and K8 is absent |
| `repack_firmware.py --allow-stale-header` | keeps the old digest deliberately (tests only) |
| `repack_firmware.py --k8 k8.json` | verifies the stock digest and recomputes for the new body; JSON has `K8` (16 hex) and `self_check` (SHA-256 of the 8 bytes) |
| `repack_firmware.py` (A) | no header digest; after a body edit it only recomputes CRCs / re-encrypts |

## 6. Reproduce

You need your own `D3400_0113.bin` and a `key_all.json` that covers it:

```powershell
python decrypt_dslr2.py --key key_all.json `
  --firmware D3400_0113.bin --out D3400_0113.dec

python -c "d=open('D3400_0113.dec','rb').read(); print(d[0:4].hex(), d[0x20:0x40]==b' '*32)"
# expect: first 4 bytes are not 20202020; the second value is True
```

Digest check (without printing firmware content):

```python
import hashlib
d = open("D3400_0113.dec", "rb").read()
body = d[0x20:]
print(hashlib.sha1(body).digest() == d[:20])        # False
print(hashlib.sha1(body[:-16]).digest() == d[:20])  # False
```

## 7. Boundaries

- Only `D3400_0113` was byte-checked locally; `D3400_0110` is also recorded as
  `0x20` in `key_all.json` sources but was not re-tested here;
- `K8` is not recovered; whether the camera/updater checks the digest was not
  hardware-verified, and the tool assumes it does;
- the 12 trailing header bytes are unidentified; they may relate to model,
  version, or the digest scheme;
- no firmware samples are included; every conclusion is reproducible from a
  legally obtained image.

## 8. One sentence

**D3400 extends wrapper B from E5 into E4: it proves the wrapper is not a
generation property, and it makes `K8` the hard boundary for full-image
repacking.**
