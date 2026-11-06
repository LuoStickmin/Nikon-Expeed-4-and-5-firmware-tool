# 安全策略 / Security Policy

## 项目定位

本仓库是 **Nikon Expeed 4/5 单反固件容器的互操作性研究记录**。产出是：

- 从密文统计中恢复的三层 XOR 密钥表（`key_all.json`）
- 解密 / 目录解析 / 模块切片脚本
- 一组静态分析探针

本仓库 **不产出** 可刷写镜像，**不重签名**，**不涉及** 绕过相机或更新器的验签机制。仓库中的 `repack_firmware.py` 仅用于研究性重建容器（重算模块/包 CRC、可选重新加密）；包装 B 的头部摘要依赖机型专属 `K8`，未知时只能原样保留并标记 `STALE`，因此重打包产物**不保证被相机接受**。

`key_all.json` 中的三张表只用于解开官方更新包、复现容器结构。CRC 通过只证明完整性，不证明真实性。

完整的法律声明（非官方项目、反规避、无担保与责任限制等）见 [LEGAL.md](LEGAL.md)。

## 报告问题

如果你认为仓库中的内容存在以下问题，请 **先联系维护者**，而不是直接向 GitHub 提交 abuse 报告：

- 违反了某项许可证（特别是 GPL-3.0 相关文件，见 README §10）
- 包含了不应公开的第三方版权材料
- 存在被直接用于非授权用途的风险

联系方式：**<IvanStickmin@163.com>** **<luostickmin@foxmail.com>**

维护者在收到后会尽快回应；确认有问题的内容会删除或调整。我们希望先内部解决，再走平台流程。

## 不在支持范围

- 相机 / 更新器的实际验签机制（本仓库未研究）
- Z 系列 `0x260` 新包装的密钥（未破）
- 刷机、变砖、保修相关的支持请求
- 任何“帮我解某个具体固件”的定制需求

## 使用者的责任

使用者应仅对自己拥有的设备与合法获取的固件使用本工具，并自行承担由此产生的一切后果。详见 README §10。

---

# Security Policy

## Project positioning

This repository is an **interoperability research record for Nikon Expeed 4/5 firmware containers**. Its outputs are:

- The three-layer XOR key tables recovered from ciphertext statistics (`key_all.json`)
- Decryption / directory parsing / module carving scripts
- A set of static-analysis probes

This repository **does not** produce flashable images, **does not** re-sign firmware, and **does not** involve bypassing camera or updater signature verification. `repack_firmware.py` exists only for research-grade container rebuilding (recompute module/package CRCs, optional re-encryption); wrapper B's header digest depends on the model-specific `K8`, so without it the digest is preserved and marked `STALE`, and the rebuilt image is **not guaranteed to be accepted by a camera**.

The three tables in `key_all.json` are only for opening official update packages and reproducing the container structure. Passing CRC only proves integrity, not authenticity.

See [LEGAL.md](LEGAL.md) for the full legal notice (non-affiliation, anti-circumvention, no warranty, and limitation of liability).

## Reporting issues

If you believe repository content has any of the following problems, please **contact the maintainer first** rather than filing a GitHub abuse report directly:

- Violates a license (especially GPL-3.0 files, see README §10)
- Contains third-party copyrighted material that should not be public
- Poses a risk of being used directly for unauthorized purposes

Contact: **<IvanStickmin@163.com>** **<luostickmin@foxmail.com>**

The maintainer will respond as soon as possible; confirmed problematic content will be removed or adjusted. We prefer to resolve internally before involving platform processes.

## Out of scope

- The actual signature verification mechanism of cameras / updaters (not studied here)
- Keys for the Z-series `0x260` new wrapper (unbroken)
- Flashing, bricking, or warranty support requests
- Any "help me decrypt a specific firmware" custom request

## User responsibility

Users should use this tool only on devices they own, with firmware obtained legally, and bear all consequences. See README §10.