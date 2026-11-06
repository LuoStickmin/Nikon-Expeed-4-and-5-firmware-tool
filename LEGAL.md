# 法律声明 / Legal Notice

> **本文件是项目维护者的合规说明，不构成法律意见，也不保证任何具体使用合法。**
> 使用本项目前，请咨询你所在司法辖区的律师，并自行判断你的行为是否合法。
>
> **This document is the maintainers' compliance note. It is not legal advice and does not guarantee that any particular use is lawful.**
> Consult a lawyer in your jurisdiction and make your own legal assessment before use.

本声明适用于本仓库的代码、文档、`key_all.json` 以及由本项目产生的任何分析结果。
This notice applies to the code, documentation, `key_all.json`, and any analysis output of this repository.

---

## 1. 非官方项目与商标 / Non-affiliation and trademarks

本项目是独立的互操作性研究项目，**与 Nikon Corporation 无关联，未获其授权、赞助或背书**。
"Nikon"、"EXPEED" 以及各相机型号名称是其各自权利人的商标，仅用于描述兼容性与研究对象的说明性目的。
本项目不声称拥有上述商标，也不暗示任何官方关系。
**本仓库不授予任何 Nikon 固件、商标或专利的许可。**

This is an independent interoperability research project. It is **not affiliated with, authorized by,
sponsored by, or endorsed by Nikon Corporation**. "Nikon", "EXPEED", and camera model names are
trademarks of their respective owners and are used only descriptively to identify the studied
hardware and compatibility. No trademark ownership or official relationship is claimed.
**Nothing in this repository grants any license to Nikon firmware, trademarks, or patents.**

## 2. 固件版权、EULA 与获取 / Firmware copyright, EULA, and acquisition

相机固件镜像的版权归 Nikon Corporation 或其许可方所有，并可能受最终用户许可协议（EULA）、
更新服务条款或其他合同约束。**本仓库不包含任何固件镜像或解密后的镜像**；`.gitignore`
排除了 `*.bin`、`*.dec` 与 `*.modules/`。请仅使用你合法获取、且你有权研究的镜像，
不要公开分发固件、解密产物或修改后的镜像。

Camera firmware images are copyrighted by Nikon Corporation or its licensors and may be subject
to end-user license agreements (EULA), update-service terms, or other contracts. **This repository
contains no firmware images or decrypted images**; `.gitignore` excludes `*.bin`, `*.dec`, and
`*.modules/`. Use only images you obtained lawfully and are entitled to study, and do not publicly
redistribute firmware, decrypted images, or modified images.

## 3. 逆向工程与反规避 / Reverse engineering and anti-circumvention

固件解密、修改与重新封装可能涉及你所在辖区的反规避、计算机访问、版权或其他法律。
例如：

- 美国《数字千年版权法》（DMCA）第 1201 条及其中的互操作性例外（17 U.S.C. §1201(f)）；
- 欧盟《软件指令》2009/24/EC 第 6 条（为互操作性进行的反编译）；
- 其他国家和地区的类似规定。

以上仅为示例，**不是穷举**，也不表示这些例外一定适用于你的具体情形。本项目用于
互操作性研究、格式分析与你自有设备上的研究；维护者不对任何具体使用的合法性作出
陈述或保证。若你不确定，请先咨询律师。

Firmware decryption, modification, and repacking may implicate anti-circumvention, computer-access,
copyright, or other laws in your jurisdiction. Examples include:

- Section 1201 of the U.S. Digital Millennium Copyright Act (DMCA) and its interoperability
  exception (17 U.S.C. §1201(f));
- Article 6 of the EU Software Directive 2009/24/EC (decompilation for interoperability);
- similar provisions in other countries and regions.

These are examples only, **not an exhaustive list**, and do not imply that any exception applies to
your situation. This project is for interoperability research, format analysis, and study on devices
you own; the maintainers make no representation or guarantee about the legality of any particular
use. If in doubt, consult a lawyer first.

## 4. 派生密钥与数据 / Derived keys and data

`key_all.json` 中的 XOR 表是从固件密文统计中恢复的派生数据。派生数据的可版权性、可分发性
以及是否受固件许可条款约束，因司法辖区而异。维护者对其法律状态**不作任何保证**，
也不保证其适用于你的用途。请自行评估公开或再分发 `key_all.json` 的后果。

The XOR tables in `key_all.json` are derived data recovered from firmware ciphertext statistics.
The copyright status, redistributability, and contractual treatment of derived data vary by
jurisdiction. The maintainers make **no warranty** about its legal status or fitness for your use.
Assess the consequences of publishing or redistributing `key_all.json` yourself.

## 5. 无担保与责任限制 / No warranty and limitation of liability

本项目的代码按 **GPL-3.0** 的免责条款以“AS IS”提供，不附带任何明示或默示担保。
**在法律允许的最大范围内**，维护者与贡献者不对以下事项承担责任：设备损坏、变砖、
数据丢失、保修失效、更新失败、法律后果、第三方索赔，以及任何间接、附带或后果性损失。

修改固件、刷入修改后的镜像或依赖本项目的分析结论均**风险自负**。本项目不提供
可刷写镜像，也不保证任何重建产物会被相机接受。

The code is provided "AS IS" under the GPL-3.0 warranty disclaimer, without any express or implied
warranty. **To the maximum extent permitted by law**, the maintainers and contributors are not liable
for device damage, bricking, data loss, voided warranties, failed updates, legal consequences,
third-party claims, or any indirect, incidental, or consequential damages.

Modifying firmware, flashing modified images, or relying on this project's analysis is **at your own
risk**. This project provides no flashable images and does not guarantee that any rebuilt artifact
will be accepted by a camera.

## 6. 出口管制与制裁 / Export control and sanctions

密码分析、逆向工程与固件工具可能受出口管制、进口限制或制裁法规约束。你应自行确认
下载、使用或再分发本项目不违反适用于你的法律。

Cryptanalysis, reverse-engineering, and firmware tools may be subject to export controls, import
restrictions, or sanctions. You are responsible for confirming that downloading, using, or
redistributing this project does not violate laws applicable to you.

## 7. 许可证与第三方组件 / License and third-party components

- 本仓库的代码按 **GPL-3.0** 分发，完整文本见 [`LICENSE`](LICENSE)。
- `extract_key.py` 与 `decrypt_firmware.py` 原样来自
  [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)
  （GPL-3.0），其版权归原作者/贡献者。
- 第三方依赖：NumPy（BSD-3-Clause）、Capstone（BSD-3-Clause）；它们的许可证归各自作者。
- 本法律声明不改变、也不对 GPL-3.0 代码附加任何额外限制；若本声明与 `LICENSE` 就代码
  发生冲突，以 `LICENSE` 为准。对固件、派生数据与商标的限制独立于代码许可证。

- The code in this repository is distributed under **GPL-3.0**; see [`LICENSE`](LICENSE).
- `extract_key.py` and `decrypt_firmware.py` are copied verbatim from
  [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)
  (GPL-3.0); copyright remains with its authors/contributors.
- Third-party dependencies: NumPy (BSD-3-Clause), Capstone (BSD-3-Clause); their licenses belong
  to their respective authors.
- This notice does not change or add restrictions to code licensed under GPL-3.0; if this notice
  conflicts with `LICENSE` regarding code, `LICENSE` controls. The restrictions on firmware,
  derived data, and trademarks are independent of the code license.

## 8. 联系 / Contact

如对许可证、版权或本声明有疑问，请先联系维护者（见 [`SECURITY.md`](SECURITY.md)），
而不是直接向平台提交滥用报告。

For license, copyright, or notice questions, contact the maintainers first (see
[`SECURITY.md`](SECURITY.md)) rather than filing a platform abuse report directly.
