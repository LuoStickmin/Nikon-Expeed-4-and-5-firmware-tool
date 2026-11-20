# 验证矩阵 / Validation Matrix

本表记录 **独立第三方** 用 `key_all.json` 验证过的机型与版本。
维护者自己的 22 条回归记录见 README §4.1，不重复列入。

**如何加一行**：按 [验证回报模板](../../issues/new?template=validation-report.yml) 提交 issue，
`self_check` 三行与 README §4.1 一致即可。

| 机型 / Model | 固件版本 / Version | body 偏移 / offset | self_check 一致 / match | 回报者 / Reporter | issue |
| --- | --- | --- | --- | --- | --- |
| D7500 | C:1.12 | `0x20` | ✅ 一致 / match | [noahengelking](https://github.com/noahengelking) | [#2](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool/issues/2) |
| D7500 | C:1.11 | `0x20` | ✅ 一致 / match | noahengelking | #2 |
| D7500 | C:1.10 | `0x20` | ✅ 一致 / match | noahengelking | #2 |

> D7500 的 `K8` 为 `DC73A05066D1868C`（index `0x44` / step `0x3B`），1.13 重打包验证也通过
> CRC 与摘要（未刷机）。细节见 [docs/d7500-external-verification.md](docs/d7500-external-verification.md)。

## 不一致记录 / Mismatch records

如果 `self_check` 与 README §4.1 不一致，也请记录在这里——这可能是新的密钥变体。
If `self_check` differs from README §4.1, record it here too — this may be a new key variant.

| 机型 / Model | 固件版本 / Version | body 偏移 / offset | 差异摘要 / Diff summary | 回报者 / Reporter | issue |
| --- | --- | --- | --- | --- | --- |
| _（暂无）/ (none yet)_ | | | | | |

---

# Validation Matrix

This table records models and versions **independently verified by third parties** against `key_all.json`.
The maintainer's own 22 regression records are in README §4.1 and are not repeated here.

**How to add a row**: submit an issue using the
[validation report template](../../issues/new?template=validation-report.yml);
if the three `self_check` lines match README §4.1, it is eligible.

| Model | Firmware version | body offset | self_check match | Reporter | issue |
| --- | --- | --- | --- | --- | --- |
| D7500 | C:1.12 | `0x20` | ✅ match | [noahengelking](https://github.com/noahengelking) | [#2](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool/issues/2) |
| D7500 | C:1.11 | `0x20` | ✅ match | noahengelking | #2 |
| D7500 | C:1.10 | `0x20` | ✅ match | noahengelking | #2 |

> The D7500 `K8` is `DC73A05066D1868C` (index `0x44` / step `0x3B`); a validation-only 1.13
> repack also passes every CRC and the digest (not flashed). Details in
> [docs/d7500-external-verification.en.md](docs/d7500-external-verification.en.md).

## Mismatch records

If `self_check` differs from README §4.1, please record it here too — this may be a new key variant.

| Model | Firmware version | body offset | Diff summary | Reporter | issue |
| --- | --- | --- | --- | --- | --- |
| _(none yet)_ | | | | | |
