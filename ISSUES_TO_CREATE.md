# 待创建 issue 草稿 / Issue drafts to create

按顺序用 `gh issue create` 创建，或手动复制到 GitHub。
Create in order with `gh issue create`, or copy manually to GitHub.

```bash
# 先确保标签存在 / ensure labels exist
gh label create "good first issue" --color "7057ff" --description "适合第一次贡献 / suitable for first contribution"
gh label create "validation"       --color "0e8a16" --description "第三方固件验证回报 / third-party firmware validation"
gh label create "analysis"         --color "1d76db" --description "静态分析探针 / static analysis probe"
gh label create "tooling"          --color "fbca04" --description "脚本 / 校验器改进 / script / validator improvement"

# 逐个创建（body 用本文件对应段落）/ create one by one (body from the matching section)
gh issue create --title "..." --label "..." --body "..."
```

---

## Issue 1 — 为 `CMoviePlayApplicationService_RequestStartPlay` 寻找指针引用 / Find pointer references to `CMoviePlayApplicationService_RequestStartPlay`

**labels**: `analysis`

### 背景 / Background

`find_refs.py` 已能定位字符串，但绝对指针与相对指针均未命中（README §7.6）。怀疑字符串地址是运行时重定位或查表写入。

`find_refs.py` already locates the string, but neither absolute nor relative pointers hit (README §7.6). Suspect runtime relocation or table lookup writes.

### 输入 / Input

- `D750_0115.dec.modules/b1010_115a.bin`
- 目标字符串偏移 `0x2F1901` · target string offset `0x2F1901`

### 期望产出 / Expected output

在 issue 中回报 / Report in the issue:

1. 扫描过的区域与判据（`find_ptrtables.py` / `disasm_vtable.py` 的参数）
   Regions scanned and criteria (`find_ptrtables.py` / `disasm_vtable.py` params)
2. 是否找到候选引用；若找到，贴出所在偏移与上下文反汇编
   Whether candidate references were found; if so, paste offset and context disassembly
3. 若仍无命中，记录已排除的假设
   If still no hit, record excluded hypotheses

### 成功标准 / Success criteria

- [ ] 至少排除或确认一种引用方式（绝对 / 相对 / Thumb 函数表 / vtable / 运行时写入）
      At least one reference method excluded or confirmed (absolute / relative / Thumb function table / vtable / runtime write)
- [ ] 结论可被他人用相同命令复现
      Conclusion reproducible by others with the same commands

### 不需要做的事 / Out of scope

不需要反编译出完整函数，不需要理解该服务的业务逻辑。
No need to decompile the whole function or understand the service's business logic.

---

## Issue 2 — 对 `_tpj00_0150.bin` 与 `_tpcy_0009.bin` 做初步画像 / Preliminary profiling of `_tpj00_0150.bin` and `_tpcy_0009.bin`

**labels**: `good first issue`, `analysis`

### 背景 / Background

这两个小型附属镜像角色未确认（README §8.2），无 ASCII 串、呈表状数据。
These two small auxiliary images have unconfirmed roles (README §8.2): no ASCII strings, table-like data.

### 输入 / Input

- `D850_0131.bin.modules/_tpj00_0150.bin`（57,344 B）
- `D5__0150.bin.modules/_tpcy_0009.bin`（60,002 B）

### 期望产出 / Expected output

在 issue 中回报每个文件的 / Report for each file:

1. 整体熵与 4 KiB 分块的熵曲线（可用 `analyze_core.py` 的统计部分）
   Overall entropy and 4 KiB block entropy curve (can use `analyze_core.py`'s statistics part)
2. 非零字节频率 top-10 · Nonzero byte frequency top-10
3. 是否存在 4 字节对齐的递增序列 / 重复步长（暗示表结构）
   Whether 4-byte-aligned increasing sequences / repeating strides exist (suggesting table structure)
4. 你的角色猜测及依据 · Your role guess and evidence

### 成功标准 / Success criteria

- [ ] 两个文件各有画像 · Each file has a profile
- [ ] 结论有数据支撑，不只凭“看起来像” · Data-backed, not just "looks like"

### 不需要做的事 / Out of scope

不需要反汇编，不需要确定具体功能。
No disassembly, no need to determine specific function.

---

## Issue 3 — 展开 `_wt5160_.bin` 内嵌的 gzip 层 / Expand the embedded gzip layer in `_wt5160_.bin`

**labels**: `good first issue`, `analysis`

### 背景 / Background

`_wt5160_.bin` 前 32 字节为 ` 061WT-5` + 填充，`0x20` 起是标准 gzip（`1f 8b 08`），解压得 37,847,040 B，开头为 `fw_data.bin`（README §8.3）。未继续展开。

`_wt5160_.bin`'s first 32 bytes are ` 061WT-5` + padding; from `0x20` is standard gzip (`1f 8b 08`), decompressing to 37,847,040 B starting with `fw_data.bin` (README §8.3). Not further expanded.

### 输入 / Input

- `D5__0150.bin.modules/_wt5160_.bin`

### 期望产出 / Expected output

1. 解压产物的完整开头 hexdump（前 0x200 字节）
   Full opening hexdump of the decompressed output (first 0x200 bytes)
2. `fw_data.bin` 之后的结构：是目录？是定长头？给出字段猜测
   Structure after `fw_data.bin`: directory? fixed header? Give field guesses
3. `ARMv7 Processor` 字符串所在偏移 · Offset of the `ARMv7 Processor` string
4. 判断这是否又是一层容器；若是，给出大小 / 偏移 / CRC 的观察
   Judge whether this is another container layer; if so, give size / offset / CRC observations

### 成功标准 / Success criteria

- [ ] 给出可复现的解压命令 · Reproducible decompression command
- [ ] 对 `fw_data.bin` 之后的结构给出至少一种可验证的假设
      At least one verifiable hypothesis about the structure after `fw_data.bin`

### 不需要做的事 / Out of scope

不需要完整解析这一层，不需要解密。
No need to fully parse this layer, no need to decrypt.

---

## Issue 4 — 放宽 `validate_firmware` 的保留字段检查 / Relax the reserved-field check in `validate_firmware`

**labels**: `good first issue`, `tooling`

### 背景 / Background

严格校验器要求目录条目尾部 8 字节 `tag` 全为零，但 D750 的 `_wma_ver01.00.00` 条目该字段是 ASCII `crc.bin`，导致正确解密被判死（README §9.1）。

The strict validator requires the directory entry's trailing 8-byte `tag` to be all zero, but D750's `_wma_ver01.00.00` entry has ASCII `crc.bin` there, so correct decryption is judged dead (README §9.1).

### 期望产出 / Expected output

1. 把检查改为「允许全零 **或** 合法 ASCII 标签」
   Change the check to "allow all-zero **or** legitimate ASCII tag"
2. 补一个针对 D750 `_wma` 条目的回归断言
   Add a regression assertion for the D750 `_wma` entry
3. 确认改动后 `D750_0115.bin` 用 `decrypt_dslr.py` 不再误报，且其余样本行为不变
   Confirm `D750_0115.bin` with `decrypt_dslr.py` no longer false-reports, and other samples unchanged

### 成功标准 / Success criteria

- [ ] `decrypt_dslr.py --key key_all.json --firmware D750_0115.bin` 通过 · passes
- [ ] `D810_0114.bin` / `D850_0131.bin` / `D5__0150.bin` 的切片结果不变 · carving results unchanged
- [ ] PR 中贴出前后对比输出 · Before/after output in PR

### 不需要做的事 / Out of scope

不要顺手重构整个 `validate_firmware`。
Do not refactor the whole `validate_firmware` along the way.

---

## Issue 5 — 把 `D750_0115.dec` 的复现做成回归脚本 / Turn `D750_0115.dec` reproduction into a regression script

**labels**: `good first issue`, `tooling`

### 背景 / Background

README §5.7 声称 `decrypt_dslr2.py` 的输出与仓库内 `D750_0115.dec` 逐字节一致，但目前没有自动化的回归检查。

README §5.7 claims `decrypt_dslr2.py`'s output matches the repository's `D750_0115.dec` byte-for-byte, but there is currently no automated regression check.

### 期望产出 / Expected output

一个 `regress.py`（或等价脚本），行为 / A `regress.py` (or equivalent) that:

1. 检查输入与产物的 SHA-256，与 README §8.1 的完整值比对
   Checks input and artifact SHA-256 against README §8.1's full values
2. 校验三个模块的大小与 CRC · Validates the three modules' sizes and CRC
3. 全部通过退出 0，任一失败退出非 0 并打印差异
   Exits 0 if all pass, nonzero with diff printed on any failure

**注意 / Note**：仓库不附带二进制（`.gitignore`），脚本应在文件缺失时给出明确提示而不是崩溃。
The repo does not ship binaries (`.gitignore`); the script should give a clear message on missing files rather than crash.

### 成功标准 / Success criteria

- [ ] 文件存在时全绿，缺失时给出可读提示 · Green when files exist, readable hint when missing
- [ ] 不引入新依赖 · No new dependencies

---

## Issue 6 — 补充 README 的「明文容器」识别说明 / Add "plaintext container" identification notes to README

**labels**: `good first issue`

### 背景 / Background

README §9.5 提到明文容器会被 `decrypt_dslr2.py` 二次 XOR，但「如何判断一个文件是明文容器」只散落在 §5.4 与 §8.1。

README §9.5 mentions plaintext containers get double-XORed by `decrypt_dslr2.py`, but "how to tell a file is a plaintext container" is scattered only across §5.4 and §8.1.

### 期望产出 / Expected output

在 README 中新增一小节（或扩写 §5.4），给出 / Add a new subsection to README (or expand §5.4) giving:

1. 一条不依赖密钥的判断命令（直接解析 body 目录并检查 CRC）
   A key-independent detection command (parse body directory directly and check CRC)
2. 判断结果与应选脚本的对照表 · A mapping from detection result to script to use
3. 误跑一次 XOR 后会看到什么现象 · What you see after running XOR by mistake

### 成功标准 / Success criteria

- [ ] 命令可复制即跑 · Command copy-paste runnable
- [ ] 与现有章节不重复、不矛盾 · No duplication or contradiction with existing sections

---

## Issue 7 — 扩大验证矩阵（长期，可重复认领）/ Expand the validation matrix (long-running, repeatable)

**labels**: `validation`

### 背景 / Background

`key_all.json` 的回归集覆盖 12 机型 22 版本，但全部来自维护者语料。见 `VALIDATION_MATRIX.md`。

`key_all.json`'s regression set covers 12 models 22 versions, but all from the maintainer's corpus. See `VALIDATION_MATRIX.md`.

### 期望产出 / Expected output

用你手上的加密固件跑 `extract_key_mix.py`，按验证回报模板贴出 `self_check`。一致就并入矩阵；不一致就开新 issue 讨论密钥变体。

Run `extract_key_mix.py` on your encrypted firmware and post `self_check` per the validation report template. Match → add to matrix; mismatch → open a new issue to discuss the key variant.

### 成功标准 / Success criteria

- [ ] 每一条回报都能被 `VALIDATION_MATRIX.md` 收录
      Every report can be recorded in `VALIDATION_MATRIX.md`