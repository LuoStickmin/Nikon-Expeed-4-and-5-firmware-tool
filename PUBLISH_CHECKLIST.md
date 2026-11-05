# 发布前检查清单 / Pre-publish checklist

## 合规 / Compliance

- [ ] `.gitignore` 已生效：`git status` 中不再出现 `*.bin` / `*.dec` / `*.modules/`
      `.gitignore` effective: no `*.bin` / `*.dec` / `*.modules/` in `git status`
- [ ] 已确认仓库内不含完整固件二进制（含历史提交；必要时用 `git filter-repo` 清理）
      Confirmed no full firmware binaries in repo (including history; use `git filter-repo` if needed)
- [ ] `SECURITY.md` 已填写真实联系方式 · Real contact filled in `SECURITY.md`
- [ ] README 顶部已插入免责声明（见 `README_TOP_SNIPPET.md`）
      Disclaimer inserted at README top (see `README_TOP_SNIPPET.md`)
- [ ] GPL-3.0 文件保留了原版权与许可声明（`extract_key.py`、`decrypt_firmware.py`）
      GPL-3.0 files preserve original copyright/license notices
- [ ] 确认 `key_all.json` 的公开不违反你的判断（README §10 已提示需自行确认）
      Confirmed public `key_all.json` is within your judgment (README §10 flags this)

## 可参与性 / Contributability

- [ ] `CONTRIBUTING.md` 已就位 · in place
- [ ] `VALIDATION_MATRIX.md` 已就位并在 README 中链接 · in place and linked from README
- [ ] 已创建至少 4 个 `good first issue`（见 `ISSUES_TO_CREATE.md`）
      At least 4 `good first issue` created (see `ISSUES_TO_CREATE.md`)
- [ ] 已创建 `validation` 标签与验证回报模板 · `validation` label and report template created
- [ ] 已启用 GitHub Discussions（可选，用于开放式讨论）
      GitHub Discussions enabled (optional, for open-ended discussion)

## 可运行性 / Runnability

- [ ] 从 `https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git` clone 后，`pip install numpy` + README §5.2 的命令能跑通（用你自己的样本验证）
      Fresh clone from `https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool.git` + `pip install numpy` + README §5.2 command works (verified with your sample)
- [ ] 无加密样本时，README §5.4 的切片代码能直接跑通明文容器
      Without encrypted sample, README §5.4 carving runs on plaintext container
- [ ] `CONTRIBUTING.md` 的「第一次运行」两步都实测过
      Both steps in `CONTRIBUTING.md`'s "First run" measured
- [ ] 仓库 README 中所有链接（含锚点）无 404
      No 404 in any README link (including anchors)

## 推广（发布后第一周）/ Promotion (week 1 after release)

- [ ] r/ReverseEngineering 发帖：讲「从密文统计盲恢复 + 两级 CRC 当 oracle + 22 镜像回归」，不只丢链接
      Post to r/ReverseEngineering: tell the story (blind recovery + two-level CRC oracle + 22-image regression), not just a link
- [ ] NikonHacker / `simeonpilgrim/nikon-firmware-tools` 相关讨论区
      NikonHacker / related `simeonpilgrim/nikon-firmware-tools` discussion
- [ ] 向 `AL-255/Awesome-Camera-Hacking` 提 PR · PR to `AL-255/Awesome-Camera-Hacking`
- [ ] 中文侧：看雪固件/物联网逆向板块、V2EX
      Chinese side: Kanxue firmware/IoT reverse section, V2EX
- [ ] 每条评论都回复；根据反馈修正 issue 列表后再考虑第二轮
      Reply to every comment; revise the issue list from feedback before a second round

## 度量 / Metrics

短期不要看 star。看这三个数 / Do not look at stars short-term. Watch these three:

- [ ] 验证矩阵新增条目数 · New rows in validation matrix
- [ ] `good first issue` 被认领数 · Claimed `good first issue` count
- [ ] 外部提交的 PR 数（含文档修正）· External PR count (docs included)