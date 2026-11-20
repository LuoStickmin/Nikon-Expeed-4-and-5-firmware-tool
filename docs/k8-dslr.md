# DSLR packaging B 的 K8

> 记录日期：2026-11-15（2026-11-20 补 D5600 与外部 D7500 线索）
> 对象：D850 C:1.31、D5 C:1.50、D500 C:1.40、D3400 C:1.13、D5600 C:1.20
> 性质：只读静态分析；本仓库不含任何固件样本

## 结论

| 机型 | 固件 | `K8` | index / step | 候选数 | 命中 |
| --- | --- | --- | --- | --- | --- |
| D850 | C:1.31 | `C5005F49CFF65525` | `45` / `E3` | 65,536 | 1 |
| D5 | C:1.50 | `1F0CE7E3DDA60907` | `3E` / `E9` | 65,536 | 1 |
| D500 | C:1.40 | `66A13EE6A8573486` | `38` / `E3` | 65,536 | 1 |
| D3400 | C:1.13 | `AF08FBDBB582B587` | `39` / `B5` | 65,536 | 1 |
| D5600 | C:1.20 | `6FA0738BE53A7DE7` | `3B` / `1D` | 65,536 | 3* |
| D7500（外部） | C:1.10–1.12 | `DC73A05066D1868C` | `44` / `3B` | — | — |

\* D5600 的 3 组命中给出的是**同一个 K8**（`3B`/`6E`/`CE` 的 `T1` 值相同，keystream
等价）。判定标准是 K8 相同，而不是参数组合数。

\* D7500 一行来自外部回报（[issue #2](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool/issues/2)）：
本仓库没有跑 65,536 搜索，只用 `keys/t1.hex` 与同一生成器复算，K8 一致；摘要未用镜像复核。

包装 B 的头部摘要按上游定义：

```text
header[0:20] == SHA1(container[0x20:] || K8)
```

## 1. 一句话

`K8` 不是不可逆的黑盒。它由 `0x10000080` 的 8 字节常数经过一个字节级 keystream
变换得到，而**该常数跨机型通用**；于是只要拿到明文容器，就能在 65,536 组候选里
把 `K8` 解出来——**不需要连相机**。

## 2. 生成器

```text
value = T1[index]            # T1：256 字节常量表
inc   = 0x160 * step
repeat 8:
    value = (value + inc) & 0xFF
    inc  += step
    ks[j] = value

K8 = raw ^ ks                # raw = D319A081BBF520EF
```

* `index`、`step` 各 1 字节，共 65,536 组；用 `SHA1(body || K8) == header[0:20]`
  判定，命中即唯一。
* 这是**等价参数化**：不承诺与固件内部 `(seed, index)` 语义一一对应。D850 的
  keystream `16 19 FF C8 74 03 75 CA` 由 `index=0x45, step=0xE3` 精确复现。
* `raw` 即 `0x10000080` 的 8 字节：`D3 19 A0 81 BB F5 20 EF`。这个常数在五个
  机型上都能复现各自的头部摘要，说明它是 Expeed 4/5 DSLR 的共用常数。
* `T1` 在五份镜像里都能找到，且**字节完全相同**。D850 的取址：

  | 镜像 | 文件中 `T1` 偏移 |
  | --- | --- |
  | D850 `b1330_131.bin` | `0x17CF374` |
  | D5 `b870_150.bin` | `0x1632D00` |
  | D500 `D500_0140.dec` | `0x18CB379` |
  | D3400 `D3400_0113.dec` | `0x139019A` |

  `keys/t1.hex` 是这 256 字节的十六进制文本（求解器也接受 256 字节原始二进制）。

## 3. 求解工具

`k8_solve.c`：一次遍历只哈希正文一遍（SHA-1 中途状态），再对 65,536 组候选
各做一次收尾，单机几秒完成。

```powershell
gcc -O2 -o k8_solve k8_solve.c
./k8_solve D3400_0113.dec keys/t1.hex
# MATCH index=39 step=B5 K8=AF08FBDBB582B587
```

可选参数：第 3 个覆盖 `raw` 常数（16 位十六进制），第 4 个覆盖摘要起点（默认
`0x20`）。

## 4. 证据

1. **K8 唯一**：每个机型 65,536 组里通过 160 位摘要的都指向同一个 `K8`（多数为
   1 组，D5600 为 3 组等价参数），随机碰撞概率约 2⁻¹⁴⁴。
2. **独立交叉验证**：用本仓库 `repack_firmware.py --selftest --keep-tags`
   重打包，五个机型全部 `header verified on input, recomputed (SHA1(body || K8))`
   且输出与输入逐字节相同；D500/D3400/D5600 的加密原包另通过
   `decrypt(repack) == plaintext`。
3. **与既有记录一致**：D850 的 keystream、`raw`、`K8` 与外部记录（`C5005F49CFF65525`）
   完全吻合，可作为方法的基准点。

## 5. 复现

```powershell
# 1) 先解密（K8 只对明文 body 成立）
python decrypt_firmware.py --key key_all.json --firmware D3400_0113.bin --out D3400_0113.dec

# 2) 求解
gcc -O2 -o k8_solve k8_solve.c
./k8_solve D3400_0113.dec keys/t1.hex

# 3) 用解出的 K8 重打包并自检
python repack_firmware.py --firmware D3400_0113.bin --out out.bin ^
  --key key_all.json --k8 keys/d3400_0113_k8.json --selftest --keep-tags
```

## 6. 边界

- **K8 是机型专属的**，五个值互不相同；不要跨机型使用。
- **同机型不同版本是否共用 K8：本仓库未验证**。本表每个机型只解了一个版本；D850 的
  `0101`、D500 的 `0101/0111` 等需要各自再跑一次 65,536 搜索。外部 D7500 项目报告
  同一个 `K8` 通过 C 1.10/1.11/1.12（`DC73A05066D1868C`，见 issue #2），见
  [d7500-external-verification.md](d7500-external-verification.md)——生成器复算一致，但摘要不是本仓库复核的。
- **必须用明文容器**。加密原包的 body 与明文不同，直接跑会得到 0 命中
  （D3400 第一次就是这么失败的）。这是最容易踩的坑。
- **只有头部摘要**。`header[0x14:0x20]` 的 12 字节不参与校验，仍按原样复制。
- **不证明安全性**。能重算摘要不代表相机接受、不代表镜像可信。本仓库仍不提供
  刷机产物。
- **其他机型**：任何 Expeed 4/5 的包装 B 镜像都可以照同样流程跑一遍；命中即得
  `K8`，零命中说明它属于另一支（`raw` 或生成器不同）。

## 7. 对重打包的影响

`repack_firmware.py` 之前因 `K8` 未知而对 body 变更默认拒绝写盘（exit 8）。
现在这些机型都可以：

```powershell
python repack_firmware.py --firmware stock.bin --out new.bin --k8 keys/ ...
```

`--k8` 也接受**目录**：工具会逐个试目录里的 `*.json`，用能验证 stock 头部摘要的
那一把，并把命中的文件名写进输出；都不匹配时 exit 3 并列出试过的 key。这样不
需要事先知道机型，也不会拿错 key：

```
  header     verified (d850_0131_k8.json), recomputed (SHA1(body || K8))
  k8         d850_0131_k8.json
```

格式损坏或 `self_check` 不符的文件会被跳过并打印 `note: skipping ...`，不影响其余
key。`--allow-stale-header` 仍保留给 CRC/QEMU 测试。
