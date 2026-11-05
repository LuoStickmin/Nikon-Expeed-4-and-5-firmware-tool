# D750 视频高码率修改报告（64/60 Mbps）

日期：2026-11-05  
目标：Nikon D750，固件 `D750_0115`（1.15）  
修改范围：`b1010_115a.bin` 中的 1080p “High quality” 码率表项  
产物：`D750_0115.hq64.bin`（与 stock 同大小、同包装、重新加密并重算 CRC）

> 这是本地静态修改与容器级验证，不是相机实拍验证。QEMU 原型目前只覆盖
> M0 启动片段，没有 H.264 编码器、SD 写卡或视频录制通路，因此**无法在
> QEMU 中证明码率真的变成 64 Mbps**。相机端首次试录仍需自行承担风险。

> 本仓库只保留本报告与 `patch_report.json` / `verify_report.json`；
> `*.bin` / `*.dec` / `*.modules/` 不随仓库分发（见 `.gitignore`）。

---

## 1. 结论

| 项目 | 结果 |
| --- | --- |
| 1080p HQ 表项 | 5 行：entry 1 / 3 / 5 / 7 / 9 |
| 修改前 | `42/35`、`42/35`、`24/20`、`24/20`、`24/20` Mbps |
| 修改后 | 全部 `64/60` Mbps |
| 未修改 | 4 个 NQ 行、entry 10 起的低分辨率组（按上限推断为 720p/480p）、另外两个模块 |
| 模块 CRC | `0x12CA` → `0x4314`（有效） |
| 包 CRC | `0x7EE4` → `0x7EE4`（有效；见 §4 的 CRC residue 说明） |
| 解密后镜像差异 | 36 B：34 B 码率字段 + 2 B 模块 CRC，字段外 0 B |
| QEMU M0 回归 | 与 stock 完全一致（exit 0、halt 寄存器、0 MMIO、0 UART） |
| 相机实拍 | **未验证** |

---

## 2. 表项与偏移

`b1010_115a.bin` 中 1080p 组从文件偏移 `0x2AA9AC` 开始，每项 28 字节：

```
entry 1  0x2AA9AC
entry 2  0x2AA9C8
entry 3  0x2AA9E4
entry 4  0x2AAA00
entry 5  0x2AAA1C
entry 6  0x2AAA38
entry 7  0x2AAA54
entry 8  0x2AAA70
entry 9  0x2AAA8C
entry 10 0x2AAAA8   <- 上限降到约 47.2 Mbps，低分辨率组（推断 720p/480p），未改
```

每项前两个 little-endian u32 是码率字段，随后是 `flag=1`、该项的码率上限
（1080p 组为 `0x04380780` = 70,780,800 bps），以及三个时间/帧率字段。
5 个 HQ 行改后为 `0x03D09000` (64,000,000) / `0x03938700` (60,000,000)，
均低于 70,780,800 的上限。

这个“5 个 HQ 行”的映射与 Nikon Hacker 的 D810 1.14 补丁同构：D810 的
`Video 1080 HQ 64mbps` 也正好改 entry 1/3/5/7/9，写 `64,000,000 / 60,000,000`；
D810 和 D750 的表都是 28 字节一项、同样的字段顺序和同样的上限值。

---

## 3. 文件与哈希

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `D750_0115.bin`（stock，只读） | 21,552,187 | `6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859` |
| `D750_0115.hq64.bin`（最终产物） | 21,552,187 | `9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a` |
| `b1010_115a.bin`（stock 模块） | 20,324,448 | `faada7fe2bcc90fef8877fae37965ee836f867b08f5736c67c5266b1f82937fd` |
| `b1010_115a.hq64.bin`（改后模块） | 20,324,448 | `ea0c161dd8bfc7fdd7037c13005e8a4f7f3ddf98a79c9565e2c8aa973ba3f579` |
| `D750_0115.dec`（stock 解密镜像） | 21,552,187 | `1ec77111106a67076d9e70886c6e159d29609238d96e65e70f7329be7c749bdd` |
| `D750_0115.hq64.dec`（改后解密镜像） | 21,552,187 | `79e592945befed5b9702efe1ffbfa457883d11e0f052c97e747bc2c42ca1c300` |

> 更新文件名必须是 `D750_0115.bin` 才会被相机识别；上面保留了 `.hq64`
> 后缀以避免覆盖 stock。真要上机时，复制到卡上再改名为 `D750_0115.bin`。

---

## 4. 验证过程与结果

### 4.1 修改器自检

`d750_bitrate_patch.py` 在写入前强制核对：

1. 5 个 HQ 行的 stock 值必须正好是上表列出的 42/35 与 24/20；
2. 每行 `flag == 1`，上限为 70,780,800；
3. 目标 64/60 必须低于上限；
4. 改后重新解析，5 行都必须读回 64/60；
5. 4 个 NQ 行必须逐字节不变；
6. 差异只能落在 5 行 × 2 个 u32 字段内。

实际结果：模块 20,324,448 B 中有 34 B 不同，全部落在 5 个 HQ 行的两个
u32 字段内（有些字节新旧值恰好相同，所以不是 5×8=40 B）。另外
`tests/test_d750_bitrate_patch.py` 的 4 个单元测试全部通过：stock 表匹配、
只改 HQ 字段、NQ/720p 不动、错误 stock 被拒绝。

### 4.2 独立容器验证

`d750_bitrate_verify.py` 不导入修改器，独立完成：

- 用 `key_all.json` 解密 stock 与改后镜像；
- 自己解析大端目录，核对 3 个模块的名称、顺序、start/length、tag；
- 逐模块重算 CRC-16/XMODEM，并重算包 CRC；
- 确认改后 `b1010` 模块与单独交给它的 `b1010_115a.hq64.bin` 完全一致；
- 确认 `a1010` 与 `_wma` 逐字节未变；
- 解析全部 22 个表项，确认 5 个 HQ 行命中 64/60，NQ 与低分辨率组（推断
  720p/480p）未变；
- 对比 stock/改后解密镜像，确认字段外 0 B 差异。

结果：

```
stock   6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
patched 9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a
module  ea0c161dd8bfc7fdd7037c13005e8a4f7f3ddf98a79c9565e2c8aa973ba3f579
package CRC 0x7EE4 -> 0x7EE4
b1010 CRC   0x12CA -> 0x4314
changed decrypted bytes: 36 (fields+CRCs), outside: 0
HQ rows at target:
  entry 1 @0x2AA9AC  64000000 / 60000000
  entry 3 @0x2AA9E4  64000000 / 60000000
  entry 5 @0x2AAA1C  64000000 / 60000000
  entry 7 @0x2AAA54  64000000 / 60000000
  entry 9 @0x2AAA8C  64000000 / 60000000
all checks passed
```

**为什么包 CRC 没变：** CRC-16 的 residue 性质使
`CRC16(payload || CRC16(payload)) == 0`。每个模块末尾都带着自己的 CRC，
包 CRC 对“模块 payload 变化 + 模块 CRC 重算”不敏感；本次 stock 与改后
包 CRC 都是 `0x7EE4`，这是格式性质，不是“没有改到”。真正证明 payload
变化的是模块 CRC 从 `0x12CA` 变成 `0x4314`，以及 36 B 的差异。

### 4.3 QEMU M0 回归

用现有 `nikon-d750` 机器分别跑 stock 与改后 `b1010` 模块：

| 运行 | exit | timed_out | UART | MMIO | halt |
| --- | ---: | --- | ---: | ---: | --- |
| stock `runs/20261105-084449` | 0 | False | 0 B | 0 | `pc=0xFF0 r0=0x80002000 r1=0 sp=0x97FFFF00 lr=0xFF0` |
| patched `runs/20261105-084416` | 0 | False | 0 B | 0 | 同上 |

这说明改表没有破坏已知的 M0 入口路径。它**不**说明视频编码器会接受
64 Mbps；这一段执行本来就不访问编码器或 SD 卡。

---

## 5. 复现命令

```powershell
cd C:\Users\23795\Downloads\DSLR

# 1) 只检查 stock 表
python d750_bitrate_patch.py `
  --module D750_0115.dec.modules\b1010_115a.bin --check

# 2) 生成改后模块
python d750_bitrate_patch.py `
  --module D750_0115.dec.modules\b1010_115a.bin `
  --out D750_0115.hq64.out\b1010_115a.hq64.bin `
  --json D750_0115.hq64.out\patch_report.json

# 3) 重打包 + 重算两级 CRC + 重新加密（保留 stock 的 crc.bin tag）
python repack_firmware.py --key key_all.json --firmware D750_0115.bin `
  --replace-module b1010_115a.bin=D750_0115.hq64.out\b1010_115a.hq64.bin `
  --keep-tags --out D750_0115.hq64.out\D750_0115.hq64.bin

# 4) 独立验证
python d750_bitrate_verify.py `
  --stock D750_0115.bin `
  --patched D750_0115.hq64.out\D750_0115.hq64.bin `
  --module D750_0115.hq64.out\b1010_115a.hq64.bin `
  --key key_all.json `
  --json D750_0115.hq64.out\verify_report.json
```

---

## 6. 未验证项与风险

1. **编码器/写卡/回放未验证。** 64 Mbps 对 1080p30 是 stock 24 Mbps 的
   约 2.7 倍；对 1080p60 是 42→64 Mbps。相机可能：
   - 在慢卡上提前停止录制；
   - 录出电脑可播、相机不能回放的文件；
   - 因发热或编码器上限而降码率/报警。
2. **没有签名验证结论。** 本工具只保证容器 CRC 自洽；D750 更新器是否
   另有型号/签名检查未知。改后镜像**不保证被相机接受**。
3. **不要在唯一一台工作机上直接试。** 保留 stock 镜像；确认相机电量、
   使用已知良好的 UHS-I 卡、先短录 10–30 秒，再检查文件码率与回放。
4. 本次只提高了 1080p 的 5 个 HQ 行。NQ 仍是 stock 的 24/20 与 12/10；
   entry 10 起的低分辨率组（推断 720p/480p）完全未动。

---

## 7. 产物清单

```
D750_0115.hq64.out/
├── D750_0115.hq64.bin          # 最终加密镜像（上机前改名为 D750_0115.bin）
├── D750_0115.hq64.dec          # 改后明文容器（验证用）
├── D750_0115.hq64.dec.modules/ # 改后切出的三个模块
├── b1010_115a.hq64.bin         # 改后 b1010 模块
├── patch_report.json           # 修改器报告
├── verify_report.json          # 独立验证报告
└── REPORT.md                   # 本文件
```

---

## 8. 参考

- Nikon Hacker 补丁定义（D810 1.14 的 1080 HQ 行与 64 Mbps 写法）：
  [simeonpilgrim/nikon-firmware-tools · patches.c](https://github.com/simeonpilgrim/nikon-firmware-tools/blob/main/Nikon-Patch-JS/src/nikon_patch/patches.c)
- Nikon Hacker 高码率说明：
  [High Bit-rate recording now solved](https://simeonpilgrim.com/blog/2014/02/23/high-bit-rate-recording-now-solved/)
- D750 官方规格/评测中的 42 Mbps 上限：
  [色影无忌 D750 评测](https://info.xitek.com/reviews/201410/20-296442_15.html)

