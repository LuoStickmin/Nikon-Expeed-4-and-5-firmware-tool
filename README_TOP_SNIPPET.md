# README 顶部建议插入片段 / Suggested README top snippet

**插入位置 / Insertion point**：现有 badge 行之后、`---` 与「目录」之前。
After the existing badge lines, before the `---` and "Table of Contents".

**同时建议在目录上方加一行语言切换 / Also add a language switch above the TOC**：

```markdown
[中文](README.md) · [English](README.en.md)
```

---

## 片段 1：免责声明 + 参与入口（插在 badge 下方）

```markdown
> **免责声明 / Disclaimer**：本项目是 Nikon Expeed 4/5 固件容器的**互操作性研究记录**。
> 本项目与 Nikon Corporation 无关联，未获其授权、赞助或背书。
> 不提供可刷写镜像，不重签名；`repack_firmware.py` 仅用于研究性容器重建，不绕过设备验签，也不保证相机接受。
> 所有「校验通过」仅表示完整性自洽，**不证明真实性**。
> 请仅对自己拥有的设备与合法获取的固件使用。详见 [LEGAL.md](LEGAL.md)、[SECURITY.md](SECURITY.md) 与 [§10](#10-安全与合规)。
>
> **Disclaimer**: This project is an **interoperability research record** for Nikon Expeed 4/5 firmware containers.
> It is not affiliated with, authorized by, sponsored by, or endorsed by Nikon Corporation.
> It does not provide flashable images or re-sign firmware; `repack_firmware.py` is for research-grade container rebuilding only, does not bypass device signature checks, and does not guarantee camera acceptance.
> Every "validation passed" statement only means structural integrity — it **does not prove authenticity**.
> Use only on devices you own, with firmware you obtained legally. See [SECURITY.md](SECURITY.md) and [§10](#10-security-and-compliance).

> **想参与？/ Want to contribute?** 你不需要理解五阶段恢复算法——
> 只要手上有一份 Expeed 4/5 的加密 `.bin`，跑一条 `extract_key_mix.py`，
> 把 `self_check` 的三行 SHA-256 贴到 [验证回报](.github/ISSUE_TEMPLATE/validation-report.yml) 即可。
> 贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，已验证机型见 [VALIDATION_MATRIX.md](VALIDATION_MATRIX.md)。
>
> You do not need to understand the five-stage recovery algorithm —
> if you have any encrypted Expeed 4/5 `.bin`, run `extract_key_mix.py` once and post the three `self_check` SHA-256 lines to a [validation report](.github/ISSUE_TEMPLATE/validation-report.yml).
> See [CONTRIBUTING.md](CONTRIBUTING.md); verified models are in [VALIDATION_MATRIX.md](VALIDATION_MATRIX.md).
```

---

## 片段 2：目录里加两项（插在「目录」列表末尾）

```markdown
- [验证矩阵](VALIDATION_MATRIX.md)
- [参与贡献](CONTRIBUTING.md)
```

---

## 片段 3：§4.1 三行 SHA-256 下方补一句

插在中文 README 的三行哈希代码块之后、「另一个佐证」段落之前；英文 `README.en.md` 的对应位置加英文句。

```markdown
> 任何人拿到任意一款 Expeed 4/5 的加密固件，跑 `extract_key_mix.py` 后对照这三行哈希，
> 即可独立判断是否同一套表——无需原始语料。欢迎把结果回报到 [验证矩阵](VALIDATION_MATRIX.md)。

> Anyone with any Expeed 4/5 encrypted firmware can run `extract_key_mix.py` and compare against these three hashes to independently determine whether it is the same table set — no original corpus required. Results welcome in the [validation matrix](VALIDATION_MATRIX.md).
```

> 注：`README.en.md` 中这句已经直接写进了 §4.1（不带 blockquote 前缀），无需重复插入；中文 README 需要手动加。