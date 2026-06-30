# 本地周更自动化方案

更新时间：2026-06-30

## 背景判断

`data/literature-full.json` 是 MG Intelligence Hub 的本地全量分析底座，已在 `.gitignore` 中排除，不会进入 GitHub。GitHub Actions 因此无法访问 full，只能在无 full 时使用 `data/literature-recent.js` 做轻量兜底。

这意味着 GitHub Actions 不适合承担主周更。主周更应由能访问本地 full 的 Hermes / 本地工作站执行，GitHub Actions 只保留手动触发和云端兜底能力。

## 推荐职责

| 组件 | 职责 |
|---|---|
| Hermes / 本地工作站 | 定时执行完整周更，更新 full，派生公开数据，提交并推送 |
| Codex | 开发、调试、抽样检查、规则优化 |
| GitHub Actions | 手动兜底，不再定时自动滚动 recent |
| GitHub Pages | 展示公开 `.js` 数据产物 |

## 本地周更入口

新增入口：

```bash
bash scripts/run-local-weekly-sync.sh
```

脚本会执行：

1. 检查 `data/literature-full.json` 是否存在。
2. 检查 tracked 工作区是否干净，避免自动提交混入开发改动。
3. `git pull --ff-only origin main`。
4. 运行 PubMed weekly pipeline 的抓取、富集和 full/recent 存储同步，使用 `--skip-downstream` 跳过下游公开产物生成。
5. 用最新证据分级规则重扫 `literature-full.json` 中的近一年窗口，并重建 `literature-recent.js` 与基础前端数据。
6. 从 full 一次性重建公开派生产物：
   - `literature-full-index.js`
   - `community*.js`
   - `knowledge-graph.js`
   - `graphHealth.js`
   - `curated-topics.js`
   - `weekly-summary.md`
   - `pipeline-status.js`
7. 校验 full 与 recent 的总数和最新日期。
8. 提交并推送公开数据产物。

当前关键原则：

- `literature-full.json` 仍只保留本地，不推 GitHub。
- `knowledge-graph.js` 和 `literature-full-index.js` 都从本地 full 派生后推送。
- GitHub Actions 没有 full，只能做手动兜底；主周更必须由本地/Hermes 入口执行。

日志写入：

```text
.hermes-audit/weekly-sync-YYYYMMDD-HHMMSS.log
```

并使用：

```text
.hermes-audit/weekly-sync.lock
```

防止重复运行。

## Hermes 接入建议

建议 Hermes 每周日 23:00 Asia/Shanghai 调用：

```bash
cd "/Users/ruiluo/Library/Mobile Documents/com~apple~CloudDocs/Hermes/project/2026-06-07-MG-Intelligence-Hub"
bash scripts/run-local-weekly-sync.sh
```

若需要先测试但不推送：

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

## GitHub Actions 调整

`.github/workflows/weekly-pipeline.yml` 已移除 `schedule`，保留 `workflow_dispatch`。这样云端不会在没有 full 的情况下自动滚动 `recent.js`，避免线上 recent 与本地 full 脱节。

## 后续可增强

1. Hermes 发送周更摘要到当前通讯渠道。
2. 周更失败时读取最新 `.hermes-audit/*.log` 并通知。
3. 每周抽样新增文献做 LLM 分级对照，发现 mismatch 后交给 Codex 优化规则。
