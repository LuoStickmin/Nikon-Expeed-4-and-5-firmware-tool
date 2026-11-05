# 参与贡献 / Contributing

感谢你愿意参与。这是一个 **研究型** 项目，贡献不限于写代码。

## 这个项目需要什么

按门槛从低到高：

1. **验证回报（最低门槛，最有价值）**
   你手上只要有任意一款 Expeed 4/5 单反的加密 `.bin`，就能参与：

   ```bash
   python extract_key_mix.py --firmware-dir <你的目录> --out key_check.json
   ```

   把 `key_check.json` 里的 `self_check` 三行 SHA-256 贴到
   [验证回报 issue](../../issues/new?template=validation-report.yml) 里。

   - 与 README §4.1 的三行一致 → 你的机型可以加入验证矩阵
   - 不一致 → 你可能发现了新的密钥变体，这本身就是有价值的发现

   不需要你理解五阶段恢复算法，也不需要你提交代码。

2. **小型附属模块画像**
   `_tpj00_0150.bin`、`_tpcy_0009.bin`、`_wt5160_.bin` 内嵌 gzip 等，
   做熵 / 字符串 / 字节频率的初步观察并回报，见标有 `good first issue` 的 issue。

3. **文档修正**
   README 里的偏移、命令、哈希写错了，直接提 PR，不需要先开 issue。

4. **脚本改进 / 新探针**
   修 bug、加校验、补回归测试、写新的静态定位脚本。

5. **新包装 / 新世代的容器建模**
   门槛最高。请先开 issue 讨论容器模型，再谈密钥——不要在没有容器模型的情况下猜密钥。

## 第一次运行

仓库 **不附带固件二进制或样本**（见 `.gitignore`）。先拉取仓库；如果本地已有明文容器样本，可以先用它们跑通切片与静态分析：

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool
```

```python
# 见 README §5.4，直接对本地明文容器切片（示例文件名为 D810_0114.bin 等）
```

注意：明文容器不要跑 `decrypt_dslr2.py`（会二次 XOR 打烂目录，见 README §9.5）。

有加密镜像时：

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool
pip install numpy
python decrypt_dslr2.py --key key_all.json --firmware <image>.bin --out <image>.dec
```

## 提交 PR 的标准

- **涉及解密 / 密钥的改动**：必须附带对应镜像的「目录解析 + 每个模块 CRC + 包 CRC」全部通过的证明（贴命令输出即可）。
- **纯分析脚本的改动**：至少在现有样本上跑通，并在 PR 描述里贴输出摘要。
- **README / 文档改动**：直接提。
- **新增依赖**：请说明为什么不能只用标准库 + numpy。capstone 保持可选（见 README §9.9）。

## 请不要提交

- 固件 `.bin`、解密产物 `.dec`、切出的 `*.modules/`
- 从厂商镜像中提取的完整模块文件
- 任何可刷写的重打包产物
- 大体积二进制、压缩包、语料目录

## 关于一次性脚本

`fill_t3.py`、`solve212*.py`、`dump_toc.py`、`finalize_key.py` 是研究过程的快照，硬编码了路径与常量（README §9.3）。**不建议**把它们改造成通用工具，除非先开 issue 讨论。保留它们作为过程记录是有意的。

## 许可证

`extract_key.py` 与 `decrypt_firmware.py` 原样来自
[WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)（GPL-3.0）。
对这两个文件的修改及其衍生物需继续按 GPL-3.0 分发并保留版权声明。提交 PR 即表示你同意你的贡献按仓库相应许可证分发。

## 响应节奏

维护者会尽量在一周内回应 issue。如果两周没有回复，可以 @ 维护者。

不需要承诺完美，但请把「你试过什么、看到什么」写清楚——这是研究型 issue 最有价值的部分。

---

# Contributing

Thanks for your interest. This is a **research** project; contributions are not limited to code.

## What this project needs

From lowest to highest barrier:

1. **Validation reports (lowest barrier, highest value)**
   If you have any encrypted Expeed 4/5 `.bin`, you can participate:

   ```bash
   python extract_key_mix.py --firmware-dir <your-dir> --out key_check.json
   ```

   Post the three `self_check` SHA-256 lines from `key_check.json` to a
   [validation report issue](../../issues/new?template=validation-report.yml).

   - Matches the three lines in README §4.1 → your model can join the validation matrix
   - Does not match → you may have found a new key variant, a valuable finding in itself

   You do not need to understand the five-stage recovery algorithm, and you do not need to submit code.

2. **Small auxiliary module profiling**
   Initial observations of `_tpj00_0150.bin`, `_tpcy_0009.bin`, `_wt5160_.bin`'s embedded gzip, etc. — entropy / strings / byte frequency. See issues labeled `good first issue`.

3. **Documentation fixes**
   Wrong offset, command, or hash in README — submit a PR directly, no issue needed first.

4. **Script improvements / new probes**
   Fix bugs, add validation, add regression tests, write new static-localization scripts.

5. **New wrapper / new generation container modeling**
   Highest barrier. Open an issue to discuss the container model first, then the key — do not guess the key without a container model.

## First run

The repository **does not ship firmware binaries or samples** (see `.gitignore`). Clone it first; if you already have plaintext container samples locally, use them to exercise carving and static analysis:

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool
```

```python
# See README §5.4, carve directly on local plaintext containers (example names: D810_0114.bin, ...)
```

Note: do not run `decrypt_dslr2.py` on plaintext containers (it double-XORs and destroys the directory, see README §9.5).

With an encrypted image:

```bash
git clone https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git
cd Nikon-Expeed-4-and-5-firmware-tool
pip install numpy
python decrypt_dslr2.py --key key_all.json --firmware <image>.bin --out <image>.dec
```

## PR criteria

- **Changes touching decryption / keys**: must attach proof that the corresponding image's "directory parse + every module CRC + package CRC" all pass (paste command output).
- **Pure analysis-script changes**: at least run on existing samples and paste an output summary in the PR description.
- **README / documentation changes**: submit directly.
- **New dependencies**: explain why standard library + numpy is insufficient. capstone stays optional (see README §9.9).

## Please do not submit

- Firmware `.bin`, decrypted `.dec`, carved `*.modules/`
- Complete module files extracted from vendor images
- Any flashable repacked artifact
- Large binaries, archives, corpus directories

## About one-off scripts

`fill_t3.py`, `solve212*.py`, `dump_toc.py`, `finalize_key.py` are snapshots of the research process with hardcoded paths and constants (README §9.3). **Not recommended** to generalize them into tools unless an issue is opened first. Keeping them as a process record is intentional.

## License

`extract_key.py` and `decrypt_firmware.py` are copied verbatim from
[WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool) (GPL-3.0).
Modifications to these two files and their derivatives must continue to be distributed under GPL-3.0 with copyright notices preserved. Submitting a PR means you agree your contribution is distributed under the repository's corresponding license.

## Response cadence

The maintainer will try to respond to issues within a week. If two weeks pass with no reply, you may @ the maintainer.

No need to promise perfection, but please write clearly "what you tried, what you saw" — that is the most valuable part of a research issue.