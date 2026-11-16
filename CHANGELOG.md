# 更新日志

简短记录仓库层面的变化；细节见对应文档。

> 惯例：`README.md` / `README.en.md` 顶部保留最近 3–5 条摘要，本文件记录完整历史（见 CONTRIBUTING「更新日志惯例」）。

## 2026-11-16

- 新增 [docs/different_packaging_models.md](docs/different_packaging_models.md)（[EN](docs/different_packaging_models.en.md)）：汇总 packaging A/B/`0x260` 新封包、K8 状态、跨项目证据和工具需求。
- README / README.en 顶部加入该文档的链接和短更新日志。
- 明确“Expeed 4 ≠ A 包”：D3400/D5600 是 Expeed 4 的 B 包；A/B 与加密/明文互相独立。
- 更新 D5600 的 K8 记录为 `6FA0738BE53A7DE7`（与 `docs/k8-dslr.md` 一致）。

## 2026-11-15

- 新增 [docs/k8-dslr.md](docs/k8-dslr.md)（[EN](docs/k8-dslr.en.md)）：恢复 D850 C:1.31、D5 C:1.50、D500 C:1.40、D3400 C:1.13、D5600 C:1.20 的 packaging B `K8`。
- 新增 `k8_solve.c` 与 `keys/`（五个机型的 `K8` JSON、`t1.hex`/`t2.hex`）。
- 方法要点：`0x10000080` 的 8 字节常数跨机型通用，`K8` 可在 65,536 组候选里静态解出，不需要相机。
- README / README.en：包装 B 的 `K8` 不再是未知量；`--k8` 可用于上述五个机型。
- [docs/d3400-wrapper-b.md](docs/d3400-wrapper-b.md)：D3400 的 `K8` 记为 `AF08FBDBB582B587`，原文的“K8 未恢复”已更新。
- `repack_firmware.py --k8` 现在也接受目录：逐个试 `*.json`，用能验证 stock 摘要的那把，并在输出里写明命中的文件；格式损坏或 `self_check` 不符的 key 会被跳过。
- 边界：`K8` 机型专属；同机型跨版本是否共用未验证；只解决头部摘要，不构成刷机可行性结论。

## 2026-11-14

- 记录 D3400 的 packaging B 变体（Expeed 4 也可以是 B），见 [docs/d3400-wrapper-b.md](docs/d3400-wrapper-b.md)。

## 2026-11-05

- 新增重打包工具 `repack_firmware.py`（§5.8）。
