# D7500 外部复核记录（第三方案例）

> 记录日期：2026-11-20  
> 来源：[noahengelking/nikon-d7500-firmware-notes](https://github.com/noahengelking/nikon-d7500-firmware-notes)  
> 性质：交叉比对记录，不是新的密钥/固件工作。该仓库与本仓库一样**不含**固件、
> 解密模块、XOR 表与 `K8`，只发布方法、偏移与校验值。

## 0. 结论

对方在 D7500（EXPEED 5，C 1.12）上独立走了一遍容器、两级 CRC、`K8` 与重打包验证，
结论与本仓库一致；其中有一条正好补上本仓库在
[k8-dslr.md](k8-dslr.md#6-边界) 里标成“未验证”的问题：
**D7500 的 `K8` 在 C 1.10 / 1.11 / 1.12 三个版本上通用**（值未公开）。

这份材料适合当 **D7500 的第三方旁证**，不适合当独立密钥来源：表哈希与上游回归值
同源，`K8` 和固件都不发布。

## 1. 逐项对照

| 项目 | 对方（D7500 C 1.12） | 本仓库 | 判定 |
| --- | --- | --- | --- |
| 容器布局 | B 包装；空格标签在文件 `0x20`；`count=3`、`dirsize=144`；16 B 名称 + BE32 start/len + 8 B tag；模块末尾 BE16 CRC；包 CRC + 14 × `0x00` | 同（README §2），偏移相对 body，`dirsize = 48 + 32 × count` | ✅ 一致（对方用文件偏移：`count` 在 `0x40`；本仓库写 body 偏移 `0x20`，差 `0x20` 不是矛盾） |
| 模块组成 | 3 个：`a1450_011100.bin`（~1.0 MB）、`_wma_ver01.11.00`（~0.84 MB）、`b1450_112.bin`（~23 MB） | 命名规则同（`a*` = Firmware A、`b*` = Firmware B、`_wma_*` = 无线）；D7500 的具体模块名本仓库未记录 | ✅ 规则一致，细节新增 |
| CRC | CRC-16/XMODEM（`0x1021`、初值 0、不反射、无终异或）；模块 CRC 与包 CRC 全过 | 同（§2.3） | ✅ 一致 |
| 加密 | 3 张 256 B 表、16 MiB 周期、phase 相对 body | 同（§3.1） | ✅ 一致 |
| 表哈希 | `self_check` 三行与上游 `EXPECTED_SHA` 相同 | `key_all.json` 的 `self_check` 逐字相同 | ✅ 已在本机核对 |
| 跨机型 | `T1` 在 15 个镜像上逐字节相同（D500 / D5600 / D7500 / D780 / D850 + Z 系列） | 22 个镜像、12 机型共用一套表（§4.1） | ✅ 方向一致；对方多覆盖 D780 与 Z 系列 |
| 头部摘要 | `header[0:20] == SHA1(body ‖ K8)`，B 包装 | 同（§2.4、[k8-dslr.md](k8-dslr.md)） | ✅ 一致 |
| `K8` 恢复方法 | `0x10000080` 的 8 字节常数 + 字节级 keystream，65,536 组候选 | `k8_solve.c` 同一思路（`raw = D319A081BBF520EF`） | ✅ 方法一致 |
| `K8` 版本稳定性 | 同一个 `K8` 通过 1.10 / 1.11 / 1.12 | 未验证（每个机型只解一个版本） | 🆕 补充（值未公开，本仓库未独立复核） |
| 重打包 | `b1450_112.bin` → `b1450_113.bin`（版本号提升）+ 改填充字节 + 重算两级 CRC 与摘要；离线全过，**未刷机** | `repack_firmware.py` 同能力，同样不保证相机接受 | ✅ 一致 |
| 功能面 | D7500 无 peaking / focus shift 等 UI 文本，D850 有 | 本仓库未做该对比 | ➖ 不重叠，可作参考 |
| 模拟 | 模块在 `0x10000000` 载入执行；缺外部库，不能冷启动 | 属 D750-QEMU / D850-QEMU 线 | ➖ 不重叠 |

## 2. 需要注意的三点

1. **表哈希“相同”不算两次独立恢复。** 对方明确写了这三行“also the upstream
   regression values”，即与上游 `EXPECTED_SHA` 同源。真正的独立性在于他们对
   D7500 镜像的目录 / CRC / 模块名观察，以及 `K8` 版本稳定性的结论。
2. **`K8` 仍然拿不到。** 对方出于合规只发方法，值需私下联系；本仓库因此仍不能对
   D7500 做“body 改了还重算摘要”的重打包——`repack_firmware.py` 需要
   `--allow-stale-header` 才肯写盘。这只影响头部摘要，不影响容器、CRC 与模块级补丁。
3. **双方的边界一样。** 都没刷机，“相机是否接受版本号提升的镜像”仍未验证；
   `header[0x14:0x20]` 的 12 字节仍未解释（对方称 “nonce-like”）。

## 3. 可复现的核对

**只用本机数据（本次已做）：**

```powershell
python -c "import json,hashlib;d=json.load(open('key_all.json',encoding='utf-8'));print({k:hashlib.sha256(bytes.fromhex(d[k])).hexdigest() for k in ('T1','T2','T3')})"
```

三行应与 [README §4.1](../README.md#41-已验证的机型与版本) 以及对方 `FINDINGS.md` §2
的表格逐字相同。

**如果手上有官方 D7500 C 1.12 镜像**（`key_all.json` 记录的 SHA-256 是
`47e795e1164d4fcd45d53db48d618979053b57d757ec5d213e1bb211809ba0ee`）：

```bash
python decrypt_dslr2.py --key key_all.json --firmware D7500_0112.bin --out D7500_0112.dec
```

期望：`header=0x20 count=3`、`dirsize=144`，模块 `a1450_011100.bin` /
`_wma_ver01.11.00` / `b1450_112.bin`，两级 CRC 全过。这一步能同时验证对方 §1 的结构
描述和本仓库的密钥集。本次记录**没有**做这一步：作者本机当前没有该镜像。

## 4. 仍然开放的问题

- 相机是否接受版本号提升的镜像（双方都未刷机）。
- `header[0x14:0x20]` 12 字节的语义。
- 模块内部是否还有压缩/加密层（本仓库只在 D5 的 `_wt5160_.bin` 里见过 gzip 包装）。
- peaking 等 D850 功能能否移植到 D7500（对方认为依赖不同的处理管线）。

## 5. 参考

- [noahengelking/nikon-d7500-firmware-notes](https://github.com/noahengelking/nikon-d7500-firmware-notes)（README / FINDINGS / METHOD / LEGAL）
- [docs/k8-dslr.md](k8-dslr.md) — `K8` 生成器与 65,536 组候选
- [docs/different_packaging_models.md](different_packaging_models.md) — A/B 包装与跨项目证据
