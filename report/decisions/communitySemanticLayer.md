# 架构决定：医学事务社区语义层

状态：已采用

生效日期：2026-06-29

## 背景

PubMed 文献图谱适合表达摘要级节点、共现关系和 PMID 溯源，但不能直接回答医学事务团队关心的治疗定位、证据缺口、安全性、临床路径和中国实践问题。因此网站在图谱与页面之间保留一层稳定、可审计的医学事务社区语义层。

## 决定

1. 图谱和社区分离。图谱负责证据关系，社区负责医学事务问题域和行动语义。
2. 社区 taxonomy 保持少量稳定业务主题；产品、人群、地域和证据等级作为 facets，不无限扩张为新社区。
3. 每篇文献最多有一个 primary community，可有 secondary community；低置信度文献进入 `unassigned`，不强行归类。
4. 规则程序负责可复现的候选、分配、冲突和质量指标；LLM 只作为可选语义增强，不成为发布单点故障。
5. `communityAudit.js` 是网站可展示的当前质量状态；详细抽样报告属于审计产物，写入 `.hermes-audit/reports/`。
6. 工作台、情报中心、知识库、诊治格局和 MSL 工作台消费同一套社区产物，不各自维护平行分类。
7. 当前数量和质量状态由数据产物生成，不写入本决定文档。

## 权威实现

- taxonomy：`data/communityTaxonomy.js`
- 卡片与周更：`data/communityCards.js`、`data/communityWeekly.js`
- 分配与分片：`data/communityAssignmentIndex.js`、`data/communityAssignments-*.js`
- 当前审计：`data/communityAudit.js`
- 构建入口：`scripts/buildCommunityData.py`
- 详细审计：`scripts/auditCommunityQuality.py`

## 结果

- 社区可以长期演进而不破坏图谱 schema。
- 未归类与冲突是可见的质量状态，不被当作管线失败。
- 页面可以共享相同语义，但所有医学结论仍需回到 PMID、正式来源和全文审核。
