# MA-MG-HUB v4.0 Phase 2 收尾与 Phase 3 连接层记录

更新时间：2026-06-30

## 当前状态

- Phase 2 全 MG 图谱升级已快进合入 `main`，并已推送远程。
- 当前开发分支：`codex/community-connection-layer-v4`。
- Phase 3 连接层最小闭环已完成：社区可以进入文献、图谱、证据矩阵和 wiki 专题。

## 已完成

1. 确认图谱底座已改为 full 派生：
   - `data/literature-full-index.js` 作为全库轻索引，知识库跨库检索时懒加载。
   - `data/knowledge-graph.js` 节点与关系已带 community profile。
   - `data/graphHealth.js` 已纳入数据状态页。

2. 确认周更逻辑已切换为 full-first：
   - `scripts/run-weekly-pipeline.py` 支持 `--skip-downstream`。
   - `scripts/run-local-weekly-sync.sh` 先 upsert full/recent，再重扫近一年窗口，并重建 full-derived 公开产物。

3. 新增专题社区覆盖后台产物：
   - 新脚本：`scripts/buildWikiTopicCoverage.py`
   - 新数据：`data/wikiTopicCoverage.js`
   - 方法：wiki topic `anchor_nodes` + 图谱 dominant community + PMID assignment + taxonomy 关键词校正。
   - 当前结果：27 个专题，覆盖 10/10 个主社区，未映射专题 0。

4. 前台接入：
   - 工作台新增“本周社区动态”。
   - 知识库专题 tab 新增“覆盖社区”筛选。
   - 专题详情显示覆盖社区，并可跳转社区。
   - 社区详情显示相关专题，并可跳转专题。
   - 数据状态页新增“专题社区覆盖”审计。

5. 管线接入：
   - `run-weekly-pipeline.py` 和 `run-local-weekly-sync.sh` 已加入 `buildWikiTopicCoverage.py`。
   - `generate-pipeline-status.py` 已将 `wikiTopicCoverage.js` 纳入公开产物清单。

## 已验证

- `python3 -m py_compile scripts/*.py`
- `node --check assets/knowledge.js`
- `node --check assets/dashboard.js`
- `wikiTopicCoverage.js` 数据结构校验：27 个专题，10/10 社区覆盖。
- jsdom 页面挂载校验：
  - 知识库 `?community=fcrnTargetedTherapy` 可打开社区详情。
  - 社区详情出现相关专题。
  - 专题筛选有 11 个选项（全部 + 10 个社区）。
  - 工作台渲染 4 条社区动态。
  - 数据状态页渲染 6 张专题覆盖卡片。
- 本地 HTTP 预览路径可访问：`http://127.0.0.1:8765/MA-MG-HUB/`

## 还没做

1. 社区语义层质量审计：
   - review `clinicalSubtypesStratification` 过大问题。
   - review `fcrnTargetedTherapy`、`complementAndNovelTargets`、`competitiveLandscapeIndirectComparison` 的边界和漏归类。
   - 降低 low-confidence 与 conflict 比例。

2. Phase 4 动态诊治格局：
   - 等社区质量审计后再启动。
   - 目标是不再固定展示 5 个角度，而是由社区变化、图谱变化、wiki 覆盖变化和新文献证据共同选出 3-7 条动态洞察。

## 后续顺序

1. 合并 Phase 3 连接层。
2. 开新分支做社区语义层质量审计。
3. 质量审计稳定后，再进入 Phase 4 动态诊治格局。
