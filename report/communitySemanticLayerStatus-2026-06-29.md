# MA-MG-HUB v4.0 社区语义层状态记录

记录时间：2026-06-29
补充更新时间：2026-06-30

## 当前结论

v4.0 社区语义层的可用基础闭环已经完成并合入 `main`。

当前版本可以视为 **Phase 2 Core 完成**：

- 后台能从全 MG PubMed full 库生成社区语义层。
- 前端能展示社区、审计社区质量、按社区筛文献、按需下钻全量 PMID。
- 首屏仍保持静态站轻量加载，不预加载全量 assignment。

但如果把“信号板社区聚合”和“MSL 行动映射”也算入广义 Phase 2，则 Phase 2 Advanced 尚未完成。

2026-06-30 补充：

- 知识图谱已从 recent 口径切换为本地 full 口径：`knowledge-graph.js` 由 `data/literature-full.json` 派生；没有 full 时才 fallback `literature-recent.js`。
- 新增 `data/literature-full-index.js` 作为全库轻索引，不包含 abstract，知识库跨库检索首次输入时按需加载。
- 本地周更已去重：先 upsert full/recent，再重扫 full 的近一年窗口，最后一次性生成 full-derived 公开产物。

## 已完成

### Phase 0 / 规划收敛

- 明确 v4.0 方向：全 MG PubMed full 是 source of truth，`efgartigimod-wiki` 是方法样板和覆盖校验，不是全站知识库主体。
- 明确社区层不是图谱 cluster，而是医学事务语义层。
- 明确第一版不做实时 LLM、实时向量检索和轻后端。
- 输出规划文档：`report/siteRevampPlanV4.md`。

### Phase 1 / 后台社区语义层

- 新增 `scripts/buildCommunityData.py`。
- 生成 10 个主社区的规则基线 taxonomy。
- 生成公开前端产物：
  - `data/communityTaxonomy.js`
  - `data/communityCards.js`
  - `data/communityWeekly.js`
  - `data/communityAudit.js`
  - `data/communityAssignmentIndex.js`
  - `data/communityAssignmentsRecent.js`
  - `data/communityAssignments-*.js`
- 全量 assignment 按社区分片，避免首屏加载大文件。
- `communityAssignmentIndex.js` 从约 520 KB 缩小到约 7.4 KB。
- 社区层接入周更管线和 pipeline status。
- 本地中间产物加入 `data/.gitignore`。

当前基线指标：

- 全库文献：10,635
- 已归类：8,979
- 未归类：1,656
- 低置信度：3,030
- 冲突归类：2,280
- 近 14 天未归类：0
- 主社区：10
- assignment 分片：11

### Phase 2 Core / 前端接入

- 数据状态页：
  - 展示 community audit 摘要。
  - 展示总文献、已归类、未归类、低置信度、冲突、近 14 天未归类、审计状态。
  - audit 卡片可跳转到知识库社区视图。
  - 过大社区可跳转到具体社区。

- 知识库：
  - 新增“社区视图”tab。
  - 展示社区列表、社区详情、定义、边界、MSL use case、facet、关键词、证据结构、代表 PMID、本周动态。
  - 支持 `knowledge.html?tab=communities`。
  - 支持 `knowledge.html?community=<communityId>`。
  - 社区详情支持按需加载 `communityAssignments-<id>.js`。
  - 全量 PMID 面板展示 PMID、confidence、entry date、evidence level、China、lowConfidence、crossCommunityConflict。
  - 默认不加载 assignment shard，点击“加载全量 PMID”后才加载单个分片。

- 情报中心：
  - 新增“医学事务社区”多选筛选。
  - 默认不加载任何 assignment shard。
  - URL 支持 `literature.html?community=<communityId>` 和多社区逗号分隔。
  - 勾选社区后按需加载对应分片，用 primary community PMID set 与近一年 `MG_LITERATURE_DATA` 求交集。
  - 文献卡片在社区筛选状态下显示 primary community badge。

### Phase 2.5 / Full 图谱底座与全库轻索引

- 新增 `scripts/buildFullLiteratureIndex.py`。
- 新增公开产物 `data/literature-full-index.js`：
  - 来源为本地 `literature-full.json`。
  - 保留 PMID、标题、期刊、日期、证据等级、研究类型、关键词、前三作者等轻字段。
  - 不包含 abstract、affiliation、grant 等大字段。
  - 知识库跨库检索首次输入时按需加载。
- `data/knowledge-graph.js` 已由 full 派生：
  - 全库文献：10,635
  - 图谱命中文献：9,127
  - 节点：44
  - 关系：241
  - 社区映射节点：44
- `scripts/run-local-weekly-sync.sh` 已优化为 canonical 周更入口：
  - `run-weekly-pipeline.py --skip-status --skip-downstream` 只做抓取/富集/存储同步。
  - `reclassify-existing-iii.py --recent-days 365` 重扫 full 中的近一年窗口。
  - 随后一次性重建 full index、community、graph、curated topics、weekly summary 和 pipeline status。

## 尚未完成

### 1. Taxonomy 和规则质量优化

当前规则基线可用，但仍需 review：

- `clinicalSubtypesStratification` 过大。
- low confidence 偏高。
- cross-community conflict 偏高。
- FcRn、complement、safety、efficacy、competitive landscape 之间存在边界重叠。

后续要做：

- 抽样 review `communityReviewQueue.json`。
- 修订 taxonomy 边界和关键词权重。
- 必要时引入 LLM / 人工仲裁，但不放到前台实时运行。

### 2. Phase 2 Advanced / 信号板社区聚合

尚未做：

- 信号板按社区聚合。
- 每个社区展示 top signals / high evidence impact / China signal。
- 社区动态从“单篇信号列表”升级为“社区变化视角”。

### 3. Phase 2 Advanced / MSL 工作台 community 到 action 映射

尚未做：

- 社区状态映射到 MSL 行动。
- 拜访前简报按社区组装。
- objection handling 关联社区证据链。
- 内容模块按社区、证据强度和专家兴趣匹配。

### 4. 动态诊治格局 v4.0

尚未做：

- “本月格局变化”仍未完全改成基于社区变化、图谱变化、监管/管线变化和新增证据的动态生成。
- 后续需要从固定 5 类模板升级为可溯源的 3-7 条月度洞察。

### 5. Wiki 覆盖关系和 GraphRAG / embedding

尚未做：

- `efgartigimod-wiki` topic 与全 MG PubMed 社区覆盖关系。
- embedding / vector retrieval。
- GraphRAG 社区摘要。
- 多模型协作的批量仲裁和摘要生成。

这些都不是当前静态站稳定版的前置条件。

## 什么时候再考虑

### 立即不建议继续加大功能

当前主干已经有完整可用闭环。短期应先观察稳定性，不建议立刻继续把信号板、MSL、动态诊治格局全部塞进同一轮。

### 1-2 次周更后

如果周更产物稳定，优先考虑：

- 抽样 review taxonomy 边界。
- 检查 `clinicalSubtypesStratification` 是否需要拆分。
- 检查 low confidence / conflict 样本。
- 观察 community audit 是否每周稳定。

### 2-4 周后

如果社区层在真实周更中稳定，再考虑：

- 信号板社区聚合。
- Dashboard / 工作台的本周社区动态。
- data-ops 增加更细的 audit drilldown。

### Taxonomy 稳定后

再考虑：

- MSL 工作台 community 到 action 映射。
- 专家画像按社区聚合。
- 拜访前简报按社区生成。

### 有明确检索/问答需求时

再考虑：

- embedding / vector retrieval。
- GraphRAG 社区摘要。
- LLM 仲裁低置信度和冲突归类。

这些需要先定义评估标准，否则容易变成复杂但不可验收的后台系统。

## 当前推荐下一步

先运行 1-2 次真实周更，观察：

- 社区产物是否稳定生成。
- audit 指标是否异常波动。
- 情报中心社区筛选是否够用。
- 知识库全量 PMID 下钻是否会造成浏览器卡顿。

之后再决定是否进入 **Phase 2 Advanced** 或改名为 **Phase 3：社区驱动的信号与行动层**。
