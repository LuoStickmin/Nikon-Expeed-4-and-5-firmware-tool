# Nikon Expeed 4 / 5 单反固件解包

[中文](README.md) · [English](README.en.md)

> 从官方更新包 `.bin` 出发，**只用密文本身**恢复厂商级 XOR 密钥表，解开容器、校验两级 CRC、切出模块，并留下一组静态分析探针。
>
> 仓库地址：<https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool>

**Update (2026-11-05):** 新增重打包工具（[§5.8](#58-重新封包)）与 D750 高码率修改/验证（[§5.9](#59-d750-高码率修改6460-mbps)）。

![scope](https://img.shields.io/badge/scope-Expeed%204%2F5%20DSLR-blue)
![verified](https://img.shields.io/badge/verified-12%20models%20%7C%2022%20images-brightgreen)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![numpy](https://img.shields.io/badge/numpy-required-013243?logo=numpy&logoColor=white)
![capstone](https://img.shields.io/badge/capstone-optional-lightgrey)

---

## 目录

- [1. 项目概览](#1-项目概览)
- [2. 固件容器格式](#2-固件容器格式)
- [3. 加密原理](#3-加密原理)
- [4. 适用范围](#4-适用范围)
- [5. 快速开始](#5-快速开始)
- [6. 仓库结构](#6-仓库结构)
- [7. 尝试步骤释义](#7-尝试步骤释义)
- [8. 样本复核](#8-样本复核)
- [9. 已知问题](#9-已知问题)
- [10. 安全与合规](#10-安全与合规)
- [11. 参考与延伸](#11-参考与延伸)

---

## 1. 项目概览

本仓库是一份**可复现的研究记录与工具集**：拿到 Nikon Expeed 4/5 世代单反的固件 `.bin` 后，在不借助任何已公开密钥的前提下，恢复出这一代共用的三层 XOR 密钥表，解开容器，用容器自带的 CRC 证明“解对了”，再把每个模块切出来；之后用一组探针脚本尝试做静态定位。所有结论都落在 `key_all.json` 与本地解包产物（`*.dec` / `*.modules/`，不随仓库分发）上。

三条核心结论：

1. **密钥是厂商级的静态表，而不是逐机、逐版本的秘密。** `key_all.json` 中三张 256 字节的表（`T1` / `T2` / `T3`）在 12 款机型、22 个固件版本上全部通过目录校验与两级 CRC；作者在本地的 4 份样本上也全部复核通过（样本不随仓库分发，见 [§8](#8-样本复核)）。
2. **加密是“逐字节 XOR + 16 MiB 周期”的密钥流。** 没有扩散、没有 IV、没有每台机器的密钥；镜像里大量 `0x00` / `0xFF` 填充本身就是已知明文。这等价于一个“多次一密 + 已知明文”的古典场景，密钥可以只从密文统计中恢复。
3. **容器自带一个几乎不会误判的判定器。** 大端目录的严格结构 + 每个模块的 CRC16 + 覆盖全体的包 CRC，把“密钥对不对”变成一个是非题；恢复算法的每一步都是围绕这个判定器设计的。

### 1.1 本仓库能做什么

- 识别并解密 Expeed 4/5 单反的固件更新包（两种头部包装）。
- 从密文语料中**盲恢复**密钥表，并用 CRC 全量验证后才落盘。
- 解析模块目录，切出 `a*`（Firmware A）、`b*`（Firmware B）、`_wma_*`（无线模块）等组件。
- 对解出的模块做熵、关键字、代码密度、指针表、反汇编等初步静态分析。

### 1.2 本仓库不做什么

- 不涉及 Z 系列新包装（`0x260` 标签）——工具会明确识别并拒绝，payload 加密未破。
- 不重签名、不提供刷机流程；CRC 校验只证明完整性，**不证明真实性**。上游仓库 [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) 的 Z 8/Z 9 重打包与签名密钥恢复（`repack_firmware.py`、`solve_signature_e7.py`）没有随本仓库提供。
- 不附带固件样本或完整加密语料（仓库只含 `key_all.json` 与脚本），因此无法在本仓库内重跑密钥恢复；使用需自备镜像。

---

## 2. 固件容器格式

固件文件 = 安装头（可选）+ **32 字节空格标签** + 大端目录 + 首尾相接的模块 + 16 字节尾部。代码里把“从空格标签开始”的部分称作 **body**，所有偏移都以 body 为基准。

### 2.1 body 布局

```
body 偏移        内容
────────────────────────────────────────────────────────────
0x000           32 × 0x20            空格标签（明文，不参与加密）
0x020           BE32 module_count    模块数（解析器限制 1..64）
0x024           BE32 directory_size  = 48 + 32 × count
0x028           8 × 0x00             目录保留字段（观察中恒为 0）
0x030           条目 0               16B 名称 | BE32 start | BE32 length | 8B tag
0x050           条目 1               ……
 …              ……
directory_size  模块 0 负载           length 含末尾 2 字节 CRC
 …              ……
len(body)-16    BE16 package_crc     覆盖 body[:-16]
len(body)-2     14 × 0x00            尾部填充
```

### 2.2 目录条目

| 字段 | 长度 | 说明 |
| --- | --- | --- |
| name | 16 B | ASCII，`[0-9A-Za-z_][0-9A-Za-z_.]{2,15}`，NUL 填充或占满 16 字节 |
| start | BE32 | body 相对偏移，必须等于“上一模块 end”，模块严格首尾相接 |
| length | BE32 | 含末尾 2 字节 CRC 的总长度；负载 = `length - 2` |
| tag | 8 B | 上游格式定义为保留零字节；DSLR 旧包装里也观察到 ASCII（如 D750 的 `_wma` 条目为 `crc.bin`），见 [§9.1](#91-严格校验器对-crcbin-标签误报) |

目录解析器（`decrypt_firmware.parse_table`）会强制检查：`directory_size == 48 + 32 × count`、名称字符集、保留字段为零、模块彼此衔接且最后一个模块正好结束在 `len(body) - 16`。（DSLR 旧包装的 `crc.bin` 例外见 [§9.1](#91-严格校验器对-crcbin-标签误报)。）

### 2.3 两级 CRC

- 算法：`binascii.crc_hqx(data, 0)`，即 **CRC-16/XMODEM**（多项式 `0x1021`、初值 `0`、不反射、无终异或）。
- 存储：大端。
- 第一级：每个模块的最后 2 字节 = 该模块去掉这 2 字节后内容的 CRC，即 `CRC16(module[:-2])`。
- 第二级：`body[-16:-14]` = `body[:-16]` 的 CRC，**包含**所有模块 CRC 与目录本身。
- 结果：随机错误会破坏包 CRC，模块 CRC 还能定位到具体模块。但 CRC 有 residue 性质：`CRC16(payload || CRC16(payload)) == 0`，因此“改负载 + 重算模块 CRC”不会改变包 CRC——**必须同时查模块 CRC 与包 CRC**，单靠包 CRC 不能证明负载未被修改（上游 README 的 [Checksums](https://github.com/WonderLantern/nikon-fw-key-tool#checksums-and-header-digest) 一节对此有明确说明）。

### 2.4 三种包装（头部偏移）

| 包装 | 文件头 | 空格标签位置 | body 起点 | 作者本地样本（不入库） |
| --- | --- | --- | --- | --- |
| **A** | 无 | `0x00` | `0x00` | `D750_0115.bin`（加密原镜像）、`D810_0114.bin`（明文容器） |
| **B** | 32 字节头部：20B SHA-1 摘要 + 12B 未识别 | `0x20` | `0x20` | `D850_0131.bin`、`D5__0150.bin`（均为明文容器） |
| **C** | 前缀更长（未完整分析） | `0x260` | — | 无；属于 Z 5II / Z 50II / Z 6III / ZR 的新包装，工具拒绝 |

关键点：**密钥流相位以空格标签（body 起点）为 0**，与文件头长度无关。因此同一套表可以同时处理 A 与 B 两种包装；`key_all.json` 的 `sources[].header` 记录的正是各镜像的 body 起点。

包装 B 的 32 字节头部，按上游 [Firmware format](https://github.com/WonderLantern/nikon-fw-key-tool#firmware-format) 的定义是 `[20 字节 SHA-1 摘要][12 字节未识别]`，摘要满足 `header[0:20] == SHA1(decrypted_body || K8)`；`K8` 是机型专属的 8 字节密钥，因此这是“带密钥摘要”，不是非对称签名。本仓库的工具只解密/切片，**不校验也不重算**它；实测 DSLR 样本的前缀既不等于 `SHA1(body)` 也不等于 `SHA1(body[:-16])`，符合带密钥摘要的行为，但 DSLR 的 `K8` 未知，本仓库未做验证。上游覆盖的 legacy 包装标签在 `0x20`；D750/D810 这类标签在 `0x00` 的 DSLR 旧包装是本仓库新增的适配（`decrypt_dslr*.py`）。

---

## 3. 加密原理

### 3.1 密钥流

设 `i` 为 body 内偏移（`i >= 0x20`），三张 256 字节的表按下标组合：

```
K(i)      = T1[ i        & 0xFF]
          ^ T2[(i >>  8) & 0xFF]
          ^ T3[(i >> 16) & 0xFF]

plain[i]  = cipher[i] ^ K(i)
K(i)      = K(i + 2^24)        # 周期 16 MiB
```

因为三个下标都是 `& 0xFF`，密钥流每 `256^3 = 16 MiB` 精确重复一次。`T1` 的周期是 256 字节，所以**按 256 字节扇区处理**时，每个扇区内的密钥流恰好是 `T1` 异或一个只与扇区位置有关的常数：

```
K(s + p) = T1[p] ^ C(s),   C(s) = T2[(s>>8)&0xFF] ^ T3[(s>>16)&0xFF]
```

这就是整套算法以“扇区”为最小单位的原因。

### 3.2 为什么这套加密挡不住统计恢复

| 设计特征 | 后果 | 被哪一步利用 |
| --- | --- | --- |
| 全系共用一套静态表 | 一次恢复，通刷 12 款机型 | 语料跨机型合并 |
| 周期只有 16 MiB，而镜像可达 48 MB | 密钥流被重复使用 | 越界部分直接复用 |
| 逐字节 XOR、无扩散 | 明文的统计特征原样保留 | 填充扇区 = 已知明文 |
| 大量 `0x00` / `0xFF` 填充 | 存在大量已知明文 | 恢复 T1 / T2 / T3 |
| 严格目录 + 两级 CRC | 精确的判定 oracle | 定常数、验证结果 |

换句话说，这不是“破解 AES”，而是**密钥流被重复使用且明文可预测**。厂商级静态表 + 16 MiB 周期 + 零填充，三件事凑在一起，使得只凭密文即可反推出整张表。

> 附注：D750 的主模块（`b1010_115a.bin`，20.3 MB）跨越了 16 MiB 周期边界，仍能通过包 CRC，从侧面印证了“周期 = 2^24”的判断。

### 3.3 五阶段恢复算法

`extract_key.py` 把恢复拆成五步，每一步都用 65536 个 `(a,b)` 单元中的一部分观测做统计，最后用 CRC 全量验收。

| 阶段 | 输入 | 运算 | 输出 |
| --- | --- | --- | --- |
| 1 | 全部语料密文 | 重复扇区按首字节归一化 | `T1 ^ T1[0]` |
| 2 | 首个镜像前 0x200 字节 | 256 个常数 × 目录探针打分 | 绝对 `T1` |
| 3 | 全部语料 | 恒定扇区按 `(a,b)` 多数投票 | 观测表 `T2[a]^T3[b]` |
| 4 | 观测表 | 二分图多数传播（gauge `T2[0]=0`） | `T2`、`T3`（含偏移/歧义） |
| 5 | 全部语料 | 每块字节频次重定 | 修正后的 `T3` |
| 验收 | 全部镜像 | 目录 + 模块 CRC + 包 CRC | 全过才写 `key.json` |

**阶段 1：`T1` 只差一个常数。**

对起始于 `s` 的扇区，若明文整扇区为常数填充 `f`，则密文为 `f ^ T1[p] ^ C(s)`。把每个重复出现的扇区按“首字节归一化”（每字节异或该扇区第 0 字节）：

```
norm[p] = (f ^ T1[p] ^ C(s)) ^ (f ^ T1[0] ^ C(s)) = T1[p] ^ T1[0]
```

填充常数 `f` 与扇区常数 `C(s)` 同时被消掉。语料中重复出现的扇区几乎都是填充区，统计归一化向量出现次数 ≥ 64 的那一族，就得到 `T1 ^ T1[0]`。

**阶段 2：用目录可行性定下那 8 位常数。**

对 `g = 0..255` 逐个尝试 `T1 = norm ^ g`，解密开头两个扇区并跑一个简化目录探针，按“解析出的条目数 + 首尾相接的 extent 数”打分，取最高者。错误常数会把 ASCII 模块名打乱，count / dirsize 也随之离谱，所以这个打分几乎没有歧义（要求至少 2 个条目）。

**阶段 3：收集 `(a,b)` 观测。**

`T1` 定下来后，把每个扇区异或回去。凡是全字节相等的扇区就是恒定填充扇区，其值 `v = fill ^ T2[a] ^ T3[b]`，其中 `a = (s>>8) & 0xFF`、`b = (s>>16) & 0xFF`。同一 `(a,b)` 单元在语料中会被多条镜像重复命中，按多数投票取 `v`，可压掉少量非零填充或非填充扇区的干扰。

**阶段 4：二分图多数传播。**

观测给出方程 `T2[a] ^ T3[b] = v`。所有解共享“`T2` 与 `T3` 同时异或同一个常数”的自由度，取 gauge `T2[0] = 0`。随后交替更新：

```
T3[b] = majority{ v ^ T2[a]  | a 已知 }
T2[a] = majority{ v ^ T3[b]  | b 已知 }
```

直到不再变化（最多 64 轮）。这与 LDPC 的 bit-flipping 解码思路类似，能容忍一定比例的坏单元。

**阶段 5：逐块修正 `0x00 / 0xFF` 的歧义。**

阶段 4 的 `T3[b]` 还带着“该块填充是 `0x00` 还是 `0xFF`”的不确定。对每个 `b`，取所有 `b` 索引相同的扇区（`s = b*256 + k*65536`），异或掉 `T1` 与 `T2[a]` 后做字节直方图：

```
c = argmax( cnt[c] + cnt[c ^ 0xFF] )     # 先选 0x00/0xFF 成对的峰
若 cnt[c] < cnt[c ^ 0xFF]：c ^= 0xFF      # 再选让零更多的那个
```

零填充在语料中占绝对多数，因此这一步能把 `T3` 钉死。选错的情况由最终 CRC 验收发现。

**验收。** 解密每一条镜像，跑完整目录解析 + 全部模块 CRC + 包 CRC；任何一条失败都不写密钥文件。`key.json` 还会记录每张表的 SHA-256 与每个来源镜像的 SHA-256，供回归比对。

### 3.4 覆盖要求

阶段 3 要求 **256 个 `T3` 块全部被填充扇区覆盖**（即 16 MiB 周期内每个 64 KiB 块至少有一个恒定填充扇区）。`extract_key.py` 在覆盖不足时直接报出缺失块号并退出。

上游 `nikon-fw-key-tool` 在 `extract_key.py` 的 `MINIMAL` 里记录的最小充分集是 4 条 Z 系列镜像（`Z_8_0311.bin`、`Z7_2_0170.bin`、`Z_6_0380.bin`、`Z_50_0260.bin`）；DSLR 语料最终用了 22 条镜像，且仍有 3 个块（`190`、`191`、`212`）需要后续脚本手工定值（见 [§7.5](#75-阶段-3补密钥的空洞)）。

### 3.5 为什么 CRC 可以当判定器

- 目录结构约束很硬：`count` 有范围、`dirsize == 48 + 32×count`、名称必须是 ASCII、extent 必须首尾相接并正好结束在尾部之前。随机密钥能通过的概率极低。
- 即使结构碰巧通过，包 CRC 覆盖 `body[:-16]`（含空格标签、目录与所有模块 CRC）。但 residue 性质意味着“改负载 + 修模块 CRC”不会改变包 CRC，所以验收必须同时查模块 CRC；随机错误恰好撞上包 CRC 的概率约 `1/65536`，实际远低于此。
- 两级 CRC 还提供了定位能力：模块 CRC 告诉你哪一段坏，包 CRC 告诉你整体坏。

但必须强调：**CRC 是完整性校验，不是签名**。解出的镜像“结构自洽”只说明字节与厂商镜像一致、没有损坏；它不证明来源，也不防伪造（任何人改完都能重算 CRC）。相机/更新器端是否另有验签，本仓库未涉及。

---

## 4. 适用范围

### 4.1 已验证的机型与版本

`key_all.json` 的 `sources` 记录了 12 款机型、22 个固件版本，且 22 条全部出现在 `validated` 列表中（按项目内的 CRC-only 校验口径，见 [§9.1](#91-严格校验器对-crcbin-标签误报)）：

| 机型 | 世代（公开规格） | 收录版本 | body 偏移 |
| --- | --- | --- | --- |
| D3400 | Expeed 4 | 0110、0113 | `0x20` |
| D4S | Expeed 4 | 0133 | `0x00` |
| D500 | Expeed 5 | 0101、0111、0140 | `0x20` |
| D5300 | Expeed 4 | 0103 | `0x00` |
| D5500 | Expeed 4 | 0102 | `0x00` |
| D5600 | Expeed 4 | 0120 | `0x20` |
| D5 | Expeed 5 | 0120、0150 | `0x20` |
| D7200 | Expeed 4 | 0101、0104 | `0x00` |
| D7500 | Expeed 5 | 0112 | `0x20` |
| D750 | Expeed 4 | 0101、0102、0111、0115 | `0x00` |
| D810 | Expeed 4 | 0102、0114 | `0x00` |
| D850 | Expeed 5 | 0101、0131 | `0x20` |

三张表的 SHA-256（`key_all.json` 的 `self_check`）：

```
T1  29d2e34239fc33bf0a1054fd3558536ad6429966659f5b387a75f16e9aada431
T2  6e87de5da7e42df91db31fae4a899a04bd8f0225171922cc98f74922681766e0
T3  3617957facf8b21a5a3de0f3a1f6f27ca20d72c7208b196b2a8bec3076f39b49
```

只要恢复出的表与这三行一致，即可认为与回归集同源，通常不必再逐镜像验证。

另一个佐证：这三张表的 SHA-256 前 16 字节与上游 `extract_key.py` 的 `EXPECTED_SHA` 完全一致（上游只存前缀，见 [§11](#11-参考与延伸)）。也就是说，DSLR 的 Expeed 4/5 语料恢复出的表，与上游从 Z 系列 legacy 包装恢复出的表是同一组——Nikon 在这一类包装上复用了同一套厂商密钥。

### 4.2 支持的输入类型

| 输入 | 识别方式 | 处理 | 状态 |
| --- | --- | --- | --- |
| 加密原镜像，标签在 `0x00` | `raw[0:0x20]` 全为 `0x20` | `HDR=0`，XOR body | ✅ 已验证（`D750_0115.bin`） |
| 加密原镜像，标签在 `0x20` | `raw[0x20:0x40]` 全为 `0x20` | `HDR=0x20`，XOR body | ✅ 回归集已验证（仓库无加密样本） |
| 同一结构的**明文容器** | body 的目录可直接解析 | 跳过 XOR，按目录切片 | ✅ 已验证（`D810` / `D850` / `D5` 样本） |
| Z 系列新包装 | `0x260` 处有 32 空格 | 拒绝 | ❌ 未破 |
| 裸模块 / 压缩包 / 更新器 exe | 无空格标签 | 拒绝 | ❌ 需先自行提取 |

### 4.3 边界与限制

- **未收录的机型未验证。** 与 Expeed 4/5 同世代但不在上表的机型、以及更早（Expeed 3）或更晚（Z 系列）的机型，都不能假定适用；可以拿 `extract_key_mix.py` 试，但必须先过 CRC 验收。
- **不区分机型的密钥 ≠ 不区分机型的容器。** 包装 A/B 的差异（32 字节头部）必须由 `HDR` 或自动识别处理，否则解密会整体错位。
- **明文容器不能再跑解密器。** `decrypt_dslr2.py` 会无条件 XOR，对明文容器会直接毁掉目录。
- **重打包的边界。** `repack_firmware.py` 可以重建目录、重算模块 CRC 与包 CRC、按输入重新加密，产物能通过 `validate_firmware` 的目录/CRC 校验；但包装 B 的 32 字节头部含带密钥的 SHA-1 摘要（`K8`），DSLR 的 `K8` 未知，未提供 `--k8` 时摘要只能原样保留并标记 `STALE`。**这不等于重签名，也不保证相机接受**，因此仓库仍不提供刷机产物。
- **依赖语料的统计前提。** 阶段 3/5 假定填充以 `0x00` 为主；若某个 64 KiB 块以 `0xFF` 填充为主，需人工核对（`fill_t3.py` 与 CRC 枚举就是为此准备的）。
- **方案由包装决定，不由 EXPEED 世代决定。** 上游已确认 Z 8/Z 9（EXPEED 7）仍用旧包装，而 Z f/Z 5II/Z 50II/Z 6III/ZR 是新方案；本仓库用“Expeed 4/5”只是语料范围的习惯叫法，不能据此反推机型或世代。

---

## 5. 快速开始

### 5.1 依赖

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool

pip install numpy        # 必需（解密、切模块、统计）
pip install capstone     # 可选，仅 analyze_core.py / disasm_*.py 使用
```

开发环境为 Python 3.12 + NumPy 2.3.5；纯 Python，Windows / Linux / macOS 均可运行。以下命令默认在仓库根目录执行；除一次性研究脚本外，主流程没有硬编码绝对路径。

### 5.2 一键解密 + 切模块（推荐）

`decrypt_dslr2.py` 自动识别 `HDR`（`0x00` 或 `0x20`），打印目录，写 `.dec` 与 `<out>.modules/`：

```bash
python decrypt_dslr2.py \
    --key key_all.json \
    --firmware D750_0115.bin \
    --out D750_0115.dec
```

该命令在作者的 `D750_0115.bin` 上已实测：输出与当时的 `D750_0115.dec` **逐字节一致**，三个模块也与 `D750_0115.dec.modules/` 完全一致（见 [§5.7](#57-一次实际运行)）。仓库不附带这些样本与产物，运行时需自备镜像。

### 5.3 严格校验模式

只有当镜像确实是“加密原镜像”时才适用；先校验、后写盘，不通过就什么都不写：

```bash
# 标签在 0x20 的包装（默认 HDR=0x20）
python decrypt_firmware.py --key key_all.json --firmware IMAGE.bin --out IMAGE.dec

# 标签在 0x00 的包装
python decrypt_dslr.py --key key_all.json --firmware IMAGE.bin --out IMAGE.dec
```

注意：

- 目标文件已存在时必须加 `--force`，否则以退出码 2 结束。
- 对 `D750_0115.bin` 跑 `decrypt_dslr.py` 会**误报** `module 2 ... has nonzero reserved bytes`，原因见 [§9.1](#91-严格校验器对-crcbin-标签误报)；请用 `decrypt_dslr2.py`，或改用 CRC-only 校验。

### 5.4 输入已是明文容器时

作者本地的 `D810_0114.bin`、`D850_0131.bin`、`D5__0150.bin` 已经是明文容器（样本不随仓库分发；目录与模块 CRC 无需解密即可通过）。这时不要跑 XOR，直接按目录切片并校验：

```python
import binascii, os, struct

def carve(path, body_off, out_dir):
    raw = open(path, "rb").read()
    body = memoryview(raw)[body_off:]          # 包装 A:0x00  包装 B:0x20
    count, dirsize = struct.unpack_from(">II", body, 0x20)
    assert dirsize == 48 + 32 * count
    os.makedirs(out_dir, exist_ok=True)
    for i in range(count):
        e = 0x30 + 32 * i
        name = bytes(body[e:e + 16]).rstrip(b"\0").decode("ascii")
        start, length = struct.unpack_from(">II", body, e + 16)
        payload = bytes(body[start:start + length - 2])
        stored = struct.unpack_from(">H", body, start + length - 2)[0]
        assert binascii.crc_hqx(payload, 0) == stored, name
        open(os.path.join(out_dir, name), "wb").write(payload)

carve("D850_0131.bin", 0x20, "D850_0131.bin.modules")
```

### 5.5 自己恢复密钥

需要一份**填充覆盖完整**的加密镜像语料（256 个 `T3` 块全覆盖）：

```bash
# 全部是标签在 0x20 的包装
python extract_key.py      --firmware-dir corpus --out key.json

# 全部是标签在 0x00 的包装
python extract_key_dslr.py --firmware-dir corpus --out key.json

# 两种包装混放（逐文件自动识别 HDR）
python extract_key_mix.py  --firmware-dir corpus --out key.json
```

跑完后比较 `key.json` 的 `self_check` 与 [§4.1](#41-已验证的机型与版本) 的三行哈希；一致即说明恢复正确。本仓库**没有**附带这份语料或任何固件样本（只有 `key_all.json` 与脚本），因此这一步无法在原地复现。

密钥文件字段：`scheme`（方案说明）、`period_bytes`（`1<<24`）、`T1/T2/T3`（各 256 字节 hex）、`sources`（每个镜像的 `sha256` 与 `header`）、`self_check`（三张表的 SHA-256）。由 `finalize_key.py` 产出的 `key_all.json` 另有 `validated` 列表。

### 5.6 退出码

| 退出码 | 含义 | 触发点 |
| --- | --- | --- |
| `0` | 成功，文件已写出 | — |
| `2` | 参数错误 / 输入不可读 / 输出已存在 | `--force` 未给（仅 `decrypt_firmware` / `decrypt_dslr`；`decrypt_dslr2` 无此检查） |
| `3` | 密钥文件被拒绝（缺表、长度不对、self_check 不符） | `load_key` |
| `4` | 不是本方案镜像（无空格标签，或命中 `0x260` 新方案） | `check_scheme` |
| `5` | 结构或 CRC 校验失败（未写任何文件） | `validate_firmware` |
| `7` | 补丁/替换参数无法应用（未写任何文件） | `repack_firmware.py` |
| `8` | 重建产物未通过自校验（未写盘） | `repack_firmware.py` |

`extract_key.py` 额外用返回值表达回归状态：`0` 表示三张表与内置 `EXPECTED_SHA` 一致，`1` 表示发生漂移（仍会写出 key，但打印警告）。

### 5.7 一次实际运行

```console
$ python decrypt_dslr2.py --key key_all.json --firmware D750_0115.bin --out D750_0115.dec
header=0x0 count=3 dirsize=0x90
  a1010_011100.bin     off=0x00000090 len=0x000C0002 tail=
  _wma_ver01.00.00     off=0x000C0092 len=0x0006BB37 tail=crc.bin
  b1010_115a.bin       off=0x0012BBC9 len=0x01362062 tail=
  wrote D750_0115.dec.modules\a1010_011100.bin (786432 bytes)
  wrote D750_0115.dec.modules\_wma_ver01.00.00 (441141 bytes)
  wrote D750_0115.dec.modules\b1010_115a.bin (20324448 bytes)
done
```

> `tail=crc.bin` 是**第二个**条目（`_wma_ver01.00.00`）的 8 字节标签字段，合法存在；`decrypt_dslr2.py` 不校验 CRC，所以不会报错。用 `decrypt_dslr.py` / `decrypt_firmware.py` 的严格校验则会因此误拒（[§9.1](#91-严格校验器对-crcbin-标签误报)）。

### 5.8 重新封包

`repack_firmware.py` 从原始镜像出发（明文或密文均可），可替换/修补模块负载，重建目录与两级 CRC，并按输入决定是否重新加密；写盘前会再用 `decrypt_firmware.validate_firmware` 验一遍，不通过不落盘。

```bash
# 0) 先做位级往返自检：不改任何字节，产物必须与输入逐字节相同
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --out D750_0115.self.bin --selftest

# 1) 从切出的模块目录重建（允许模块变大变小）
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --modules-dir D750_0115.dec.modules --out D750_0115.repack.bin

# 2) 原地补几个字节
python repack_firmware.py --key key_all.json --firmware D750_0115.bin \
    --patch-module b1010_115a.bin:0x1000:deadbeef --out D750_0115.patched.bin

# 3) 明文容器 → 加密形态
python repack_firmware.py --key key_all.json --firmware D850_0131.bin \
    --encrypt --out D850_0131.enc.bin
```

要点：

- **输入类型自动识别**：先按明文容器完整解析（目录 + 两级 CRC 全过才算），失败才对 body 做 XOR 再试一次；不会把明文容器二次 XOR（[§9.5](#95-明文容器会被解密器二次-xor)）。
- **目录重建**：模块顺序、16 字节名称字段与 tag 都取自原镜像；`--modules-dir` / `--replace-module` 允许改变模块长度，目录里的 `start/length` 会重排，最后一个模块仍精确结束在 `body[-16]`。
- **tag 默认清零**：D750 的 `_wma_ver01.00.00` 原本是 ASCII `crc.bin`，会让严格校验器误拒（[§9.1](#91-严格校验器对-crcbin-标签误报)）。默认把 8 字节 tag 清零，产物可直接过严格校验；要逐字节复刻原镜像时加 `--keep-tags`（此时严格校验器仍会误报）。
- **输出形态默认跟随输入**：加密进 → 加密出，明文进 → 明文出；`--encrypt` / `--plaintext` 可强制。
- **头部摘要**：包装 B 的前 20 字节是 `SHA1(body || K8)`。DSLR 的 `K8` 未知，默认原样保留；body 一变就打印 `STALE`。以后若恢复了 `K8`，用 `--k8 k8.json` 传入（`{"K8": "<16 hex>", "self_check": "<sha256>"}`），脚本会先验原镜像摘要，再为新 body 重算。
- 退出码见 [§5.6](#56-退出码)。

### 5.9 D750 高码率修改（64/60 Mbps）

`d750_bitrate_patch.py` 把 `D750_0115` 的 1080p “High quality” 行（entry 1/3/5/7/9）从 `42/35`、`24/20` 改成 64/60 Mbps；`d750_bitrate_verify.py` 独立解密、重算两级 CRC，并核对 22 个表项：

```powershell
python d750_bitrate_patch.py `
  --module D750_0115.dec.modules\b1010_115a.bin --check

python d750_bitrate_patch.py `
  --module D750_0115.dec.modules\b1010_115a.bin `
  --out D750_0115.hq64.out\b1010_115a.hq64.bin

python repack_firmware.py --key key_all.json --firmware D750_0115.bin `
  --replace-module b1010_115a.bin=D750_0115.hq64.out\b1010_115a.hq64.bin `
  --keep-tags --out D750_0115.hq64.out\D750_0115.hq64.bin

python d750_bitrate_verify.py `
  --stock D750_0115.bin `
  --patched D750_0115.hq64.out\D750_0115.hq64.bin `
  --module D750_0115.hq64.out\b1010_115a.hq64.bin `
  --key key_all.json --json D750_0115.hq64.out\verify_report.json
```

结果：模块 CRC `0x12CA → 0x4314`；包 CRC 因 CRC residue 性质仍为 `0x7EE4`；解密镜像只有 36 B 差异，字段外 0 B。以上命令在仓库根目录执行（需先用 [§5.2](#52-一键解密--切模块推荐) 解出 `D750_0115.dec.modules/`），写入 `D750_0115.hq64.out/`；仓库只保留该目录下的 `REPORT.md` 与两个 JSON 报告（`*.bin` / `*.dec` / 模块不入库）。完整报告见 [`REPORT.md`](D750_0115.hq64.out/REPORT.md)。**相机端编码器/写卡/回放尚未验证**。

---

## 6. 仓库结构

### 6.1 目录树

```text
.
├── .github/ISSUE_TEMPLATE/
│   ├── config.yml
│   └── validation-report.yml
├── README.md / README.en.md
├── CONTRIBUTING.md
├── SECURITY.md
├── VALIDATION_MATRIX.md
├── PUBLISH_CHECKLIST.md / ISSUES_TO_CREATE.md / README_TOP_SNIPPET.md
├── LICENSE                       # GPL-3.0
├── .gitignore                    # 忽略固件与派生产物
├── key_all.json                  # 22 镜像回归通过的密钥集（T1/T2/T3 + sources + self_check）
├── extract_key.py                # 密钥盲恢复（五阶段）+ 全量验收
├── extract_key_dslr.py           # 薄封装：HDR=0
├── extract_key_mix.py            # 混合 HDR 语料的密钥恢复
├── decrypt_firmware.py           # 解密 + 校验 + 目录解析（主库）
├── decrypt_dslr.py               # 薄封装：HDR=0
├── decrypt_dslr2.py              # 自动识别 HDR + 切模块
├── repack_firmware.py            # 重建目录/两级 CRC、替换或修补模块、按需重加密
├── d750_bitrate_patch.py         # D750 1080p HQ 码率表改成 64/60 Mbps
├── d750_bitrate_verify.py        # 独立验证改后容器、CRC 与码率表
├── fill_t3.py                    # 缺块：启发式打分 + 组合枚举
├── solve212.py / solve212b.py / solve212c.py   # 缺块定点暴力（三种校验器）
├── finalize_key.py               # 合并修正值，写出 key_all.json
├── tests/test_d750_bitrate_patch.py   # 码率修改单元测试（缺少样本时跳过）
├── D750_0115.hq64.out/           # REPORT.md + patch_report.json + verify_report.json（二进制不入库）
├── dump_toc.py                   # 打印 D750_0101 的解密目录
├── analyze_core.py / find_base.py / check_base.py / scan_addrs.py   # 静态分析探针
├── scan_code.py / disasm_thumb.py / disasm_vtable.py
└── search_strings.py / find_refs.py / dump_region.py / find_ptrtables.py
```

### 6.2 脚本清单

| 脚本 | 阶段 | 作用 |
| --- | --- | --- |
| `extract_key.py` | 密钥恢复 | 五阶段盲恢复 + 目录/CRC 验收 + 写 key |
| `decrypt_firmware.py` | 容器 | 解密、严格校验、目录解析（默认 `HDR=0x20`） |
| `decrypt_dslr.py` | 容器 | 把 `HDR` 固定为 0 的薄封装 |
| `extract_key_dslr.py` | 密钥恢复 | 把 `HDR` 固定为 0 的薄封装 |
| `extract_key_mix.py` | 密钥恢复 | 逐文件识别 `0x00`/`0x20`，混合语料 |
| `decrypt_dslr2.py` | 产物 | 自动识别 + 打印目录 + 落 `.modules` |
| `repack_firmware.py` | 产物 | 重建目录/两级 CRC、替换或修补模块、按需重加密，写盘前自校验 |
| `d750_bitrate_patch.py` | 修改 | 把 D750 1080p HQ 码率表改成 64/60 Mbps（带 stock 自检） |
| `d750_bitrate_verify.py` | 验证 | 独立解密、重算两级 CRC、核对 22 个表项 |
| `fill_t3.py` | 补缺 | 对缺失块按 0x00/0xFF/printable/ARM 加权打分，枚举候选组合用 CRC 判定 |
| `solve212.py` | 补缺 | 固定 190/191，暴力 212（严格校验） |
| `solve212b.py` | 补缺 | 同上，换成 CRC-only 校验（绕开误报） |
| `solve212c.py` | 补缺 | 先 `correct_t3` 再暴力 |
| `finalize_key.py` | 产物 | 合并修正值，输出最终 `key_all.json` |
| `dump_toc.py` | 观察 | 打印 `D750_0101` 解密后的目录 hexdump |
| `analyze_core.py` | 分析 | 熵、ARM 条件比例、关键字、字符串、首 64 字节反汇编 |
| `find_base.py` | 分析 | 对 8 个候选基址统计“像指针的字”的数量 |
| `check_base.py` | 分析 | 用向量表字面量反查基址并试反汇编 |
| `scan_addrs.py` | 分析 | 统计 `0x80000000-0xA0000000` 高频字 |
| `scan_code.py` | 分析 | 每 64 KiB 的 ARM/Thumb push/pop/bx 打分 |
| `disasm_thumb.py` | 分析 | 在 3 个固定偏移做 ARM/Thumb 反汇编 |
| `search_strings.py` | 分析 | 影片/菜单/驱动等功能关键字检索 |
| `find_refs.py` | 分析 | 目标字符串的绝对/相对指针交叉引用 |
| `dump_region.py` | 分析 | 指定区域 hexdump + `0x90xxxxxx` 字列表 |
| `find_ptrtables.py` | 分析 | 找连续 ≥4 个 `0x90000000..0x90200000` 且为奇数的字（Thumb 函数表） |
| `disasm_vtable.py` | 分析 | 对区域内的 vtable 槽逐个反汇编 |

> `extract_key.py` 与 `decrypt_firmware.py` **原样引自** [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)（GPL-3.0），未做修改；其余脚本是本仓库在 DSLR 语料上的适配与研究补丁。详见 [§11](#11-参考与延伸)。

---

## 7. 尝试步骤释义

本节按“当时要解决什么问题 → 做了什么 → 得到什么”的顺序，解释每个脚本存在的意义。时间线来自文件修改时间与脚本内容，属于事后还原。

### 7.1 时间线

| 时间 | 阶段 | 新增脚本 / 产物 | 要解决的问题 |
| --- | --- | --- | --- |
| 10-31 21:58 | 起点 | `extract_key.py`、`decrypt_firmware.py` | 直接沿用 [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) 的两个脚本（面向 Z 系列；`KNOWN`、`MINIMAL`、`0x260` 判断都是它的口径） |
| 10-31 21:59–22:00 | 适配 | `decrypt_dslr.py`、`extract_key_dslr.py` | DSLR 镜像没有 32 字节头，标签在 0x00，必须把 `HDR=0` |
| 11-01 09:54 | 适配 | `extract_key_mix.py` | 语料里两种头部包装混放，需要逐文件识别 |
| 11-01 10:41 | 补缺 | `fill_t3.py` | 填充覆盖不满 256 个 `T3` 块 |
| 11-01 10:45–10:57 | 补缺 | `solve212.py` / `b` / `c` | 缺口收缩到 190/191/212，逐值试；发现严格校验误报 |
| 11-01 10:49 | 观察 | `dump_toc.py` | 确认解密后目录的真实排布 |
| 11-01 11:03–11:05 | 收口 | `finalize_key.py` → `key_all.json` | 把修正值写回，产出可回归的密钥集 |
| 11-01 11:07–11:10 | 产物 | `decrypt_dslr2.py` → `D750_0115.dec(.modules)` | 自动识别头部并批量切模块 |
| 11-01 11:13–11:46 | 分析 | `analyze_core.py`、`find_base.py`、`check_base.py`、`scan_addrs.py`、`scan_code.py`、`disasm_thumb.py`、`search_strings.py`、`find_refs.py`、`dump_region.py`、`disasm_vtable.py`、`find_ptrtables.py` | 从“能解开”走向“能定位” |
| 11-04 13:00–13:30 | 新样本 | `D810` / `D850` / `D5` 的明文容器与模块 | 换机型复核容器结构与模块组成 |

### 7.2 阶段 0：先看懂容器

**问题**：`.bin` 到底是“加密的整体”，还是“有明文目录的容器”？目录字段哪些可信？

**做法**：早期用手工 hexdump 起步；密钥可用之后，再用 `dump_toc.py` 复核目录排布。两次观察一致：大端、`count/dirsize`、16 字节定长名称、body 相对偏移、模块严格首尾相接、尾部 16 字节两级 CRC。

**结果**：得到 [§2](#2-固件容器格式) 的容器模型。后续所有“解对了没有”的判断都建立在这个模型上——这是整个项目最关键的早期决定。

### 7.3 阶段 1：把密钥从密文里挤出来

**问题**：没有密钥、没有已知明文对，语料还跨机型、跨版本。

**做法**：`extract_key.py` 的五阶段（[§3.3](#33-五阶段恢复算法)）。

**结果**：得到 `T1/T2/T3`，且 22 条镜像全部通过目录 + CRC 验收。

**关键判断**：

- 用“重复填充扇区”而不是“逐字节统计”来锚定 `T1`，因为前者对填充常数和扇区常数天然免疫。
- 用“目录能否解析”来定 8 位常数，而不是靠 printable 比例——`correct_t3` 的注释专门记了一笔：用可打印字符打分会把 XORed UTF-16LE 字符串误判。
- 用二分图多数传播而不是直接解线性方程，因为观测里混有坏单元；多数传播能容忍它们。

### 7.4 阶段 2：适配 DSLR 的包装差异

**问题**：同一世代镜像有两种头部（无前缀 / 32 字节前缀），工具默认 `HDR=0x20`，直接跑 D750 会整体错位。

**做法**：

- `decrypt_dslr.py` / `extract_key_dslr.py`：把 `HDR` 固定为 0；
- `extract_key_mix.py`：逐文件检查 `0x00` 或 `0x20` 处的空格标签，混合语料也能跑；
- `decrypt_dslr2.py`：自动识别 + 直接切模块。

**结果**：`D750_0115.bin`（包装 A）解出 3 个模块，模块 CRC 与包 CRC 全过；`D810/D850/D5` 的模块与按目录直接切片得到的文件逐字节一致（本次复核实测）。

**关键判断**：相位锚在空格标签而不是文件首字节，所以两种包装共用一套表。这个判断后来被 `key_all.json` 中 22 条混合 `header: 0 / 32` 的记录验证。

### 7.5 阶段 3：补密钥的空洞

**问题**：语料的填充覆盖不满 256 个 `T3` 块；阶段 4/5 只能给出部分值，或留下 `0x00/0xFF` 的二选一。剩余缺口是 `b = 190 / 191 / 212`。

**做法与演进**：

1. `fill_t3.py`：对每个缺失块，枚举 256 个候选值，用 `zeros`、`0xFF`、`printable`、`ARM 条件字段` 加权打分取前 6，再对组合做笛卡尔积，用 CRC 选真值。
2. `solve212.py`：缩小到手头的 190/191/212 三块，固定 `190=0x57,191=0x8E`，对 212 从 `0x00` 到 `0xFF` 逐值试。用的是严格校验器。
3. `solve212b.py`：发现严格校验器会因为 `crc.bin` 标签误报（见 [§9.1](#91-严格校验器对-crcbin-标签误报)），于是内联了一个只查目录链 + CRC 的 `validate_dslr`。
4. `solve212c.py`：先把 `T3` 用 0 补齐到 256 项并跑一遍 `correct_t3`，再对 212 逐值试，避免缺失键让校验路径先撞上无关错误。
5. `finalize_key.py`：把定值写死为 `190=0x57`、`191=0x8E`、`212=0xDE`，合并 `correct_t3` 的结果，写出 `key_all.json`。

**结果**：`key_all.json` 的三张表与内置回归哈希完全一致；`T3[190]=0x57`、`T3[191]=0x8E`、`T3[212]=0xDE` 已复核。

**教训**：校验器必须与容器的真实字段语义一致。严格校验器多查了“保留字段必须为零”，而真实镜像里那个字段可以是 ASCII 标签——正确密钥因此被判死，浪费了一轮排查。

### 7.6 阶段 4：从解包到静态定位

**问题**：解出来的模块里是什么？代码在哪？字符串怎么被引用？

这一阶段没有输入输出约定，全是探针。对 `D750_0115.dec.modules/b1010_115a.bin`（20.3 MB 主镜像）的实际观察：

- **熵与指令形态**（`analyze_core.py`）：整体熵 6.30，前 2 MB 每 64 KiB 约 6.9–7.2；ARM 条件字段（`word >> 28 == 0xE`）整体只占 3.9%，前 4 MB 按 64 KiB 统计的均值约 8.6%，单块在 0 到 0.81 之间剧烈起伏——说明镜像是 **ARM / Thumb-2 / 数据混排**，不是纯 ARM。`scan_code.py` 在 `0x250000` 一带 64 KiB 内数出 755 个 `push {…, lr}`（`0xB5xx`）、631 个 `pop {…, pc}`（`0xBDxx`）、135 个 `bx lr`（`0x4770`），据此判断主体为 **Thumb-2**，异常入口保留 ARM。
- **平台关键字**：`Nikon` @ `0x38C74`（`NikonMotionDetector Ver6.0 2013.09.19`）、`T-Kernel` @ `0x1264FDA`（`SysName\0T-Kernel\0TMaxTskId...` 配置表）、FotoNation 版权 @ `0x11F3E1B`；`VxWorks` / `ThreadX` / `ITRON` / `eCos` / `Linux` / `FR-V` / `SOFTUNE` 全部未命中。→ **ARM + T-Kernel** 平台。
- **入口结构**：主镜像以 `5 × ldr pc,[pc,#0x18]` + `nop` + `b 0x54` 开头，字面量为 `0x9027D524`、`0x90291C80`、`0x90291D30`…；`0x54` 起是标准 ARM 初始化（`sub lr,lr,#4; push {r3,lr}; …`），`Ver.1.15a` 就在 `0x48`，与文件名 `D750_0115` 对得上。
- **代码分布**（`scan_code.py`）：`0x250000`、`0x1B0000`、`0x100000`、`0x1E0000` 得分最高；`0x250000` 处反汇编出连续合法的 Thumb-2（`bl 0x9020ED7C`、`bl 0x9018A098`…）。
- **基址与交叉引用**：`find_base.py` / `check_base.py` / `scan_addrs.py` 围绕 `0x90000000` 做指针密度与向量反查；`find_refs.py` 已能定位目标字符串，例如 `CMoviePlayApplicationService_RequestStartPlay` @ `0x2F1901`、`D750_MenuList_FU-02` @ `0x73464C`、`APPMENU` @ `0x10CDA0`、`HI ISO,HIGH` @ `0x12F0DC`，但**绝对指针与相对指针都没有命中**。
- **下一步假设**：既然直接指针找不到引用，就转向“连续奇数指针表”（`find_ptrtables.py`）与“vtable 槽反汇编”（`disasm_vtable.py`），即假设字符串地址是运行时重定位/查表写入的。

**结果**：确认了平台、代码形态与大量可读字符串，完成了从“能解开”到“能定位字符串”的过渡；**函数级交叉引用尚未闭环**。

### 7.7 阶段小结与未完成项

- ✅ 密钥恢复与密钥集固化（`key_all.json`，22 镜像回归）。
- ✅ 两种头部包装的自动识别与产物生成。
- ✅ 模块级解包：Firmware A / B / 无线模块 / 附属小镜像。
- ⚠️ 字符串交叉引用未闭环：字面量指针零命中，怀疑存在重定位、指针表或运行时写入。
- ⚠️ 向量表字面量折算到文件偏移后，目标处并不是标准函数序言（序言出现在其后几个字），说明字面量与函数起点未必严格对应，或镜像运行前还有一层重定位/描述符处理；这一点未闭环。
- ❌ Z 系列新包装（`0x260`）未破。
- ❌ 模块内部的压缩/加密层只做了识别（见 [§8.3](#83-复核时的新观察)），未系统展开。

---

## 8. 样本复核

以下结论是本次复核时实测的，命令与结果都可复现。

### 8.1 四个 `.bin` 的真实状态

| 文件 | 大小 (B) | 状态 | body 偏移 | 处理 | 模块 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `D750_0115.bin` | 21,552,187 | 加密原镜像 | `0x00` | XOR 解密 | 3 | 模块 CRC + 包 CRC 全过；输出与 `D750_0115.dec` 逐字节一致 |
| `D810_0114.bin` | 20,179,044 | 明文容器 | `0x00` | 直接切片 | 2 | 两级 CRC 全过 |
| `D850_0131.bin` | 27,660,549 | 明文容器 | `0x20` | 直接切片 | 4 | 两级 CRC 全过 |
| `D5__0150.bin` | 48,176,012 | 明文容器 | `0x20` | 直接切片 | 4 | 两级 CRC 全过 |

SHA-256（完整值）：

```text
D750_0115.bin  6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
D750_0115.dec  1ec77111106a67076d9e70886c6e159d29609238d96e65e70f7329be7c749bdd
D810_0114.bin  a8e00377899e4c347e9afd0a346d28f8dc8100cab41154ec9ab3861fd55b68af
D850_0131.bin  6473bba8a154cb8cb5ff27345bb84a8513593e547fbe63a9dfce7b9d288f53f4
D5__0150.bin   db8103e64d9f3c16391a5f7bde8a79cd1a59d78858e9c57871e325eb98df3ed1
```

> **重要**：`key_all.json` 的 `sources` 里，`D810_0114`、`D850_0131`、`D5__0150` 的 SHA-256 与作者本地同名文件**不同**（例如 `D850_0131` 记录的是 `4599b238…`，本地是 `6473bba8…`）。说明 `sources` 记录的是另一批**加密原镜像**；作者本地的这三份是明文容器（保留原 32 字节头部，推测为解密产物；样本不随仓库分发）。只有 `D750_0115.bin` 的哈希与 `sources` 一致，它是真正的加密输入。

因此：**不要拿明文容器样本去测解密器**——它们不需要解密，跑 XOR 只会把目录打烂。

### 8.2 切出的模块

| 镜像 | 模块 | 大小 (B) | 观察与推测角色 |
| --- | --- | --- | --- |
| D750 | `a1010_011100.bin` | 786,432 | 头部像一张偏移/描述符表；含 `D750   Firmware A Copyright Nikon Corp.` → **Firmware A**（引导/平台） |
| D750 | `_wma_ver01.00.00` | 441,141 | `WLAN1`、`wlanapi_init()`、`add_wlan_event()` → **无线/蓝牙模块固件** |
| D750 | `b1010_115a.bin` | 20,324,448 | ARM 向量表 + `Ver.1.15a` + `T-Kernel` 配置表 + FotoNation 版权 → **Firmware B**（主应用） |
| D810 | `a920_011300.bin` | 1,048,576 | `D810   Firmware A …` |
| D810 | `b920_114.bin` | 19,130,336 | 主应用 |
| D850 | `a1330_010303.bin` | 1,048,576 | `D850   Firmware A …` |
| D850 | `_wma_ver01.11.00` | 882,985 | 以 `DfuSe` 开头（ST DFU 容器），含 `wlan_init()` / `bt_init()` → **无线/蓝牙模块固件** |
| D850 | `_tpj00_0150.bin` | 57,344 | 无 ASCII 串、表状数据 → 小型附属镜像（MCU/表），未确认 |
| D850 | `b1330_131.bin` | 25,671,412 | 主应用 |
| D5 | `a870_013000.bin` | 1,048,576 | `D5     Firmware A …` |
| D5 | `_wt5160_.bin` | 23,165,550 | 开头 ` 061WT-5` + **gzip 流**；解压得 37,847,040 B，以 `fw_data.bin` 开头并含 `ARMv7 Processor`（见 §8.3） |
| D5 | `_tpcy_0009.bin` | 60,002 | 表状数据，未确认 |
| D5 | `b870_150.bin` | 23,901,652 | 主应用 |

模块命名规律：`a<平台号>_<版本>` / `b<平台号>_<版本>`。D750 的 `b1010_115a.bin` 在 `0x48` 处还有一份 `Ver.1.15a`，可与文件名互相校对（其它机型未逐一检查）。

### 8.3 复核时的新观察

- `_wt5160_.bin` 的前 32 字节是 ` 061WT-5` + 填充，`0x20` 起是标准 gzip（`1f 8b 08`）。解压得到 37,847,040 字节，开头为 `fw_data.bin`，内容里能找到 `ARMv7 Processor`。说明**容器里还套着一层压缩组件**；本仓库没有继续展开它。
- `_wma_*` 并不是 WMA 音频，而是 **WLAN/Bluetooth 模块固件**：D750 版本里有 `WLAN1`、`wlanapi_init()`；D850 版本外面还包了一层 ST 的 `DfuSe`。
- 严格校验器对 `D750_0115.bin` 的误报只发生在 `_wma` 条目的 8 字节 `tag`（值为 `crc.bin`）。其余字段（count、dirsize、模块链、模块 CRC、包 CRC）全部正确。

---

## 9. 已知问题

### 9.1 严格校验器对 `crc.bin` 标签误报

`decrypt_firmware.validate_firmware` 要求目录条目尾部的 8 字节 `tag` 全为零。D750 的 `_wma_ver01.00.00` 条目该字段是 ASCII `crc.bin`，于是正确解密会被判死：

```text
error: module 2 (_wma_ver01.00.00) has nonzero reserved bytes; nothing written.
```

**处理**：`decrypt_dslr2.py` 不做该检查；需要校验时用 `solve212c.py` / `finalize_key.py` 里那种 CRC-only 的 `validate_dslr`，或把保留字段检查放宽为“允许 ASCII 标签”。这是容器语义问题，不是密钥问题——`D750_0115.dec` 的三个模块 CRC 与包 CRC 全部正确。

### 9.2 `extract_key.py` 的目录探针是简化版

`extract_key.parse_table` 为打分而生：名称查找有意错位一个条目，count/dirsize 只用于判断可行性。真正的解析在 `decrypt_firmware.parse_table`。改代码时不要把两者混用。

### 9.3 一次性脚本硬编码了语料路径与常量

`fill_t3.py`、`solve212*.py`、`dump_toc.py`、`finalize_key.py` 都假定当前目录下有 `output/`、参照文件是 `D750_0101.bin`，并且 `finalize_key.py` 把 `{190:0x57, 191:0x8E, 212:0xDE}` 写死。它们是研究过程的快照，不是通用工具。

### 9.4 `KNOWN` / `MINIMAL` 是上游残留

`extract_key.py` 里的 `KNOWN` 哈希与 `MINIMAL` 白名单来自上游 [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) 的 Z 系列样本（`Z_5_0150.bin` 等）。拿 DSLR 语料跑会打印“unknown hash”警告，不影响恢复；只在比对 `EXPECTED_SHA` 时才有意义。

### 9.5 明文容器会被解密器二次 XOR

`decrypt_dslr2.py` 无条件对 body 做 XOR，对已是明文的容器不报错但会产出垃圾。判断依据：直接解析 body 的目录能否通过 CRC（[§5.4](#54-输入已是明文容器时)）。

### 9.6 阶段 5 的“零填充优先”假设

填充以 `0x00` 为主的语料可以直接用；若某块以 `0xFF` 为主，`correct_t3` 可能选反。最终 CRC 会拦住，但需要一个枚举/人工步骤（`fill_t3.py` 就是为此写的）。当时语料缺失的 3 个块即属此类。

### 9.7 16 MiB 周期是特性，不是 bug

超过 16 MiB 的文件会复用密钥流。这是密码学弱点，也是 `key_all.json` 里那份 48 MB 级 D5 镜像能用同一套表解开的原因；不要把“周期复用”误当成解密器的索引错误。注意作者本地的 `D5__0150.bin` 已经是明文容器，不能再跑解密器。

### 9.8 版本号警告是提示

`decrypt_firmware.main` 在文件名里的版本数字未出现在模块名时会打印警告。组件版本可能落后于发布版本，因此这是提示而非错误。

### 9.9 `capstone` 是可选依赖

`analyze_core.py` 会在导入失败时降级（不做反汇编）；`disasm_thumb.py`、`disasm_vtable.py`、`check_base.py` 则直接依赖 capstone。未安装时这些脚本不可用，但不影响解密主流程。

### 9.10 `decrypt_dslr2.py` 会静默覆盖输出

`decrypt_dslr2.py` 不做 clobber 检查，`--out` 已存在时直接覆盖；`decrypt_firmware.py` / `decrypt_dslr.py` 则要求 `--force`。批处理前先备份，或先确认目标路径。

---

## 10. 安全与合规

- **固件版权属于 Nikon。** 仓库不包含 `.bin` / `.dec` / `.modules`（`.gitignore` 已排除）；作者本地的这些文件仅作个人研究留档，不应公开分发或用于商业用途。
- **只用于自己拥有的设备。** 解包/分析属于互操作性研究；不要用于绕过版权保护、制作并传播修改版固件。
- **不要直接刷入修改后的镜像。** 容器 CRC 可重算，但相机或更新器是否另有验签/型号校验未知；错误固件可能导致设备变砖且不在保修范围。
- **CRC 不是签名。** 本文所有“校验通过”只表示镜像结构与校验和自洽，不代表来源可信。
- **许可证**：完整 **GPL-3.0** 文本见 [`LICENSE`](LICENSE)。`extract_key.py` 与 `decrypt_firmware.py` 原样来自 [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)，该仓库采用 GPL-3.0。这两个文件及其衍生物需继续按 GPL-3.0 分发并保留版权/许可声明；新增脚本若与它们构成组合作品，分发时也需满足 GPL-3.0，具体由作者确认。上游仓库本身不含固件与派生密钥；本仓库只含 `key_all.json`，不含固件样本。

---

## 11. 参考与延伸

### 上游项目

本仓库的 `extract_key.py` 与 `decrypt_firmware.py` **原样引自** [**WonderLantern/nikon-fw-key-tool**](https://github.com/WonderLantern/nikon-fw-key-tool)（[README](https://github.com/WonderLantern/nikon-fw-key-tool/blob/main/README.md)，GPL-3.0）：

- 两个文件与该仓库 `main` 分支上的版本**逐字节一致**：`extract_key.py` 14,643 B（git blob `474941036131b2388135688db86d8533e59f1b92`）、`decrypt_firmware.py` 9,754 B（git blob `14128ca1240542634554945458b128b8b93c8f26`）。
- 目录/CRC 规则、`KNOWN` / `MINIMAL` 的 Z 系列回归样本、`0x260` 新方案判断、20 字节头部摘要与 `K8` 的说明，均来自该项目的代码与 README。
- 上游适用范围为 Z 5 / Z 6 / Z 6II / Z 7 / Z 7II / Z 8 / Z 9 / Z 30 / Z 50 / Z fc；其中 `repack_firmware.py` 与 `solve_signature_e7.py`（Z 8/Z 9 的头部摘要重算与签名密钥恢复）**未随本仓库提供**。
- 上游 README 的相关小节：[Firmware format](https://github.com/WonderLantern/nikon-fw-key-tool#firmware-format)、[XOR encryption](https://github.com/WonderLantern/nikon-fw-key-tool#xor-encryption)、[Checksums and header digest](https://github.com/WonderLantern/nikon-fw-key-tool#checksums-and-header-digest)。

本仓库在该项目基础上做的事：把 `HDR` 适配到 DSLR 的两种标签位置（`0x00` / `0x20`）、合并多机型语料恢复并固化出 `key_all.json`、补齐 3 个缺失 `T3` 块、生成 `.dec` / `.modules` 产物，以及一组静态分析探针。

### 其它

- CRC-16/XMODEM 的参数定义（poly `0x1021`、init `0`、无反射）：
  <https://reveng.sourceforge.io/crc-catalogue/16.htm>
- T-Kernel / TRON 实时内核：解出的 `b*` 模块中含 `SysName → T-Kernel` 配置表，可作为平台判断依据。
- WEP/RC4 密钥流复用的经典分析，与本方案“16 MiB 周期 + 已知明文”的弱点类似，可作为理解统计恢复的参考（如 FMS 攻击与 WEP 的 known-plaintext 分析）。

### 如何补充新型号

1. 准备该型号的加密 `.bin`，用 `extract_key_mix.py` 或对应 `HDR` 脚本跑一遍；若 `self_check` 与 [§4.1](#41-已验证的机型与版本) 一致，说明同一套表适用。
2. 解密后用 `validate_firmware`（或明文容器切片）确认目录与 CRC 全过。
3. 把 `{file, sha256, header}` 追加进 `key_all.json` 的 `sources` 与 `validated`，并在本 README 的表格里补一行。
4. 如果出现新的头部包装，先扩充 `detect` / `check_scheme`，再谈密钥——不要在没有容器模型的情况下猜密钥。
