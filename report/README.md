# MA-MG-HUB 文档入口

`report/` 只保存需要长期阅读和维护的文档。网站运行数量、生成时间和发布状态不在这里重复维护，统一以网站“数据状态”页、`data/pipeline-status.js` 和 `data/release-manifest.js` 为准。

## 当前权威文档

| 文档 | 作用 | 更新触发条件 |
| --- | --- | --- |
| [架构设计与操作手册](current/operationsManual.md) | 系统边界、页面、数据流、周更和维护操作 | 架构、管线或运维方式变化 |
| [网站设计与审查速览](current/designReview.md) | 五分钟产品和设计审查入口 | 产品边界或审查顺序变化 |
| [医学事务决策情报升级计划](roadmap/decisionIntelligencePlan.md) | 当前 R1–R6 实施路线 | Release 状态或范围变化 |
| [临床试验数据维护](runbooks/clinicalTrialsMaintenance.md) | ClinicalTrials.gov、ChiCTR、ChinaDrugTrials 维护流程 | 数据源或导入流程变化 |
| [Oxford CEBM 证据等级参考](reference/evidenceGrading.md) | 证据等级的方法学和脚本映射 | 分类规则或正式依据变化 |

## 架构决定

| 文档 | 决定 |
| --- | --- |
| [医学事务社区语义层](decisions/communitySemanticLayer.md) | 图谱、社区、策展和审计的职责边界 |
| [中国作者医院网络](decisions/chinaAuthorNetwork.md) | 中国机构、作者、合作边和药物线索口径 |

## 自动产物规则

- 周更、审计和 Agent 自动生成的 Markdown 写入 `.hermes-audit/reports/`。
- 默认文件名使用 `*Latest.md` 并覆盖更新，避免按日期无限增长。
- 日期快照只在明确审计需要时生成，并由 `.hermes-audit/` 的保留策略管理。
- `report/` 根目录新增 Markdown 会触发测试失败。

历史规划、代码审查和已完成方案保留在 Git 历史中，不在当前目录重复保存。
