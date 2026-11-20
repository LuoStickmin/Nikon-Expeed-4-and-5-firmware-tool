# 不同封包方式、K8 状态与工具需求

> 记录日期：2026-11-16  
> 范围：Nikon Expeed 4 / 5 单反固件容器；Z 系列新封包只做识别与边界说明  
> 性质：只读静态分析汇总；**不包含固件、解密模块、密钥文件或可刷镜像**

## 0. 一句话结论

“Expeed 4”不等于“无头 A 包”。目前至少有三类头部布局：

| 类型 | 空格标签位置 | body 起点 | 额外校验 | 典型机型 |
| --- | --- | --- | --- | --- |
| **A** | `0x00` | `0x00` | 无 header digest | D4S/D5300/D5500/D7200/D750/D810/D810A |
| **B** | `0x20` | `0x20` | `SHA1(body ‖ K8)` 20 B | D3400/D5600（Expeed 4）；D850/D5/D500/D7500（Expeed 5） |
| **新封包** | `0x260` | `0x260` | 头部明文，payload 加密未破 | Z 5II / Z 50II / Z 6III / ZR 一类 |

判定只能看文件里的 **32 个 `0x20` 空格**，不能按“Expeed 4/5”或机型年代推断。

## 1. 判定规则

`decrypt_dslr2.py` / `repack_firmware.py` 的 `detect_header()`：

- `raw[0x00:0x20] == 32 × 0x20` → **A**；
- `raw[0x20:0x40] == 32 × 0x20` → **B**；
- `raw[0x260:0x280] == 32 × 0x20` → **新封包**，工具明确拒绝；
- 都没有 → 不是本仓库支持的 legacy 容器。

A/B 的 body 内部结构、模块 CRC、包 CRC、XOR 加密方式完全一致；差异只在文件开头
和 header digest。

## 2. Packaging A

```text
0x0000  32 × 0x20       空格标签 = body 起点
0x0020  BE32 count
0x0024  BE32 dirsize = 48 + 32 × count
0x0028  8 × 0x00
0x0030  count × [16B name | BE32 start | BE32 length | 8B tag]
...     连续模块，每个模块末尾 2B CRC16
末尾    BE16 package CRC + 14 × 0x00
```

特点与需求：

- 没有 header digest；改 body 后只需重算模块 CRC、包 CRC，并按原编码重新加密。
- A 可以是加密或明文：D810 1.14 是明文样本；D4S/D5300/D5500/D7200/D750/D810A
  是加密样本。不要用“A = 加密”或“A = 明文”判断。
- D750 的 `_wma_ver01.00.00` 目录项 tag 是 ASCII `crc.bin`，不是 8 个零；严格
  校验器会误报，重打包工具默认保留 tag（`--keep-tags`），需要时用 `--zero-tags`
  归一化。
- 修改后必须同时校验模块 CRC 与包 CRC；只改包 CRC 不能证明负载未被改。

## 3. Packaging B

```text
0x0000  20 B  header digest   SHA1(decrypted_body ‖ K8)
0x0014  12 B  未识别/保留      原样复制
0x0020  32 × 0x20             空格标签 = body 起点
0x0040  BE32 count
...
```

特点与需求：

- `K8` 是 **8 字节、按机型**的密钥，不是非对称签名；`header[0:20]` 也不等于
  `SHA1(body)`，必须把 K8 追加到 body 后再算。
- 改 body 后必须用该机型的 K8 重算 20 字节摘要；否则 header 过期。
- 没有 K8 时，`repack_firmware.py` 默认 **拒绝写盘**（exit 8），因为复制旧摘要
  只能得到 stale header；`--allow-stale-header` 只适合 CRC/QEMU 测试，不适合真刷。
- `--k8` 接受 JSON（`K8` 16 hex + `self_check` 为 8 字节 SHA-256）或目录：
  逐个尝试 `*.json`，用能验证 stock 摘要的那一把，并在输出里写命中文件名。
- 工具在写之前先验证 stock 摘要；K8 错误会 exit 3，不会静默写坏。

### 3.1 K8 状态（已恢复机型）

| 机型 | 固件 | K8 | 来源 |
| --- | --- | --- | --- |
| D850 | C:1.31 | `C5005F49CFF65525` | [docs/k8-dslr.md](k8-dslr.md) |
| D5 | C:1.50 | `1F0CE7E3DDA60907` | [docs/k8-dslr.md](k8-dslr.md) |
| D500 | C:1.40 | `66A13EE6A8573486` | [docs/k8-dslr.md](k8-dslr.md) |
| D3400 | C:1.13 | `AF08FBDBB582B587` | [docs/k8-dslr.md](k8-dslr.md) |
| D5600 | C:1.20 | `6FA0738BE53A7DE7` | [docs/k8-dslr.md](k8-dslr.md) |
| D7500 | C:1.10–1.12 | `DC73A05066D1868C` | [d7500-external-verification.md](d7500-external-verification.md)、issue [#2](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool/issues/2) |

边界：

- K8 **按机型不同**；不要跨机型复用。
- 同机型不同固件版本是否共用 K8：本仓库**未验证**（目前每个机型只解了一个版本）；
  外部 D7500 项目（issue #2）报告 C 1.10/1.11/1.12 共用同一个 `K8`（`DC73A05066D1868C`），见
  [d7500-external-verification.md](d7500-external-verification.md)。
- 重算摘要只证明容器一致，**不证明相机接受**，也不证明镜像可信。
- D3400 的 12 B 头尾是非零的；工具原样复制，不解释其语义。

### 3.2 为什么 B 容易踩坑

- 用固定 `HDR=0x20` 的旧代码读 A，或固定 `HDR=0` 读 B，整个目录会错位。
- 直接 `SHA1(body)` 永远对不上，误以为“K8 无法恢复”。
- 用加密原包的 body 去解 K8 会得到 0 命中；必须用解密后的 body。
- 只改模块、不重算 header digest，会得到“CRC 全对但相机拒刷”的镜像。

## 4. 新封包（`0x260`）

当前工具能识别并拒绝，但不支持重打包：

- 32 个空格标签在 `0x260`，不是 `0x00`/`0x20`；
- 头部是明文，但 payload 的加密方式未破；
- 代表：Z 5II / Z 50II / Z 6III / ZR 一类；
- 不要把 A/B 的 body 偏移、CRC 或 K8 逻辑套到这类镜像上。

## 5. 其他平台

以下不属于本仓库的 legacy DSLR 容器，不能套 A/B：

- Nikon 1 系列：不同平台/菜单/容器；
- Coolpix、KeyMission：不同平台；
- 镜头固件（如 `lens-fw`）：不同容器和校验；
- 手机/软件更新包：不是相机固件容器。

需要单独逆向，不能按“Expeed 4/5”直接归类。

## 6. 跨项目证据

| 项目/文档 | 发现 |
| --- | --- |
| [docs/k8-dslr.md](k8-dslr.md) | D850/D5/D500/D3400/D5600 的 packaging B K8 静态恢复；`0x10000080` 8 字节常数跨机型通用；K8 是等价参数，不需要相机 |
| [docs/d3400-wrapper-b.md](d3400-wrapper-b.md) | D3400 是 Expeed 4 但为 B；首次记录“Expeed 4 也可为 B” |
| 本地 `D850-K8` 工作区 | D850/D5/D500 K8 求解与 `keys/` 证据 |
| [LuoStickmin/D750-QEMU](https://github.com/LuoStickmin/D750-QEMU) | D750 packaging A、加密/重打包、QEMU 验证与 LCD dump |
| [LuoStickmin/E4_HQ_VID](https://github.com/LuoStickmin/E4_HQ_VID) | Expeed 4 电影模式 profile；D3400/D5600 B 包；8 个 profile 的 stock 校验与容器层重打包验证 |
| [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) | 容器格式、两级 CRC、header digest 的早期文档与工具 |
| [noahengelking/nikon-d7500-firmware-notes](https://github.com/noahengelking/nikon-d7500-firmware-notes) | D7500（EXPEED 5）独立复核：B 包装、3 模块、两级 CRC 全过；`K8` 在 C 1.10–1.12 通用（`DC73A05066D1868C`）；见 [d7500-external-verification.md](d7500-external-verification.md) |

## 7. 工具需求清单

新增/修改容器工具时，至少满足：

- [ ] 按 32 空格标签自动判定 A/B/`0x260`，不按机型/世代写死。
- [ ] 所有目录与模块偏移都相对 body（A: 0；B: 0x20）。
- [ ] 校验 `dirsize == 48 + 32 × count`、模块首尾相接、模块名/保留字节。
- [ ] 模块 CRC16 与包 CRC 都重算；不要只改其中一层。
- [ ] 保留/正确处理 tag（D750 `crc.bin`）；严格校验器与宽松校验器分开。
- [ ] 加密/解密保留 header 与 32 空格标签；body XOR 可逆。
- [ ] B 包支持 `--k8`（单文件或目录）；写前验证 stock 摘要，写后重算。
- [ ] 无 K8 时默认拒绝 stale header；`--allow-stale-header` 仅测试用。
- [ ] `--selftest` 做解密回读/逐字节比对；输出与输入应可 bit-identical。
- [ ] 不附带固件、密钥或可刷镜像；文档只给方法和校验值。

## 8. 封装/状态速查

| 机型 | 封装 | K8 | 备注 |
| --- | --- | --- | --- |
| D4S 1.33 | A | — | 加密；无 header digest |
| D5300 1.03 | A | — | 加密；电影 UI 布局与 D5500 不同 |
| D5500 1.02 | A | — | 加密 |
| D7200 1.01/1.04 | A | — | 加密；电影模式表 22×0x1C |
| D750 1.01/1.02/1.11/1.15 | A | — | 加密；`_wma` tag `crc.bin` |
| D810 1.02/1.14 | A | — | D810 1.14 是明文样本 |
| D810A 1.03 | A | — | 加密 |
| D3400 1.10/1.13 | **B** | `AF08FBDBB582B587`（1.13） | Expeed 4 也可是 B；12 B 头尾非零 |
| D5600 1.20 | **B** | `6FA0738BE53A7DE7` | Expeed 4；K8 已恢复 |
| D850 1.31 | **B** | `C5005F49CFF65525` | Expeed 5 |
| D5 1.50 | **B** | `1F0CE7E3DDA60907` | Expeed 5 |
| D500 1.40 | **B** | `66A13EE6A8573486` | Expeed 5 |
| D7500 1.12 | **B** | `DC73A05066D1868C` | Expeed 5；模块 `a1450` / `_wma_ver01.11.00` / `b1450_112`；摘要未在本机复核 |
| Z 5II / Z 50II / Z 6III / ZR | 新封包 `0x260` | — | 仅识别/拒绝，payload 未破 |

> “加密”指 body 被 XOR；header 和空格标签始终明文。A/B 与加密/明文是两回事。

## 9. 参考

- [docs/k8-dslr.md](k8-dslr.md) / [EN](k8-dslr.en.md)
- [docs/d3400-wrapper-b.md](d3400-wrapper-b.md) / [EN](d3400-wrapper-b.en.md)
- [README.md](../README.md) 的容器格式与重打包章节
- [LuoStickmin/E4_HQ_VID](https://github.com/LuoStickmin/E4_HQ_VID)
- [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)
