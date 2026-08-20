# MG Intelligence Hub：网站设计与审查速览

> 五分钟入口。详细操作见 [operationsManual.md](operationsManual.md)，实时状态见网站“数据状态”页。

## 产品边界

MG Intelligence Hub 是面向医学事务与中国大陆 MSL 的**公开证据决策支持和拜访准备来源**。它把 PubMed、指南/共识、监管、试验注册、会议来源和公开作者机构线索组织成可追溯的准备材料。

它**不是拜访记录、CRM、follow-up、互动历史或私有数据存储**。网站不采集拜访笔记、团队反馈、内部专家标签或需要登录保存的个人数据。

## 设计原则

1. 证据先于叙事：公开文献先通过 MG-core 与证据等级 I–V 门控。
2. 来源分频道：指南/共识、监管、注册和会议不能冒充 Oxford 文献证据。
3. 可追溯：Signal、talking point 和判断尽量回链 PMID、注册号或官方来源。
4. 公开最小化：full、中间数据、日志和详细审计留在本地。
5. 云端发布只读：没有 full 的发布验证 workflow 不执行生成或提交，保留 last-good release；PR 代码图 workflow 只输出 advisory 评论，post-push workflow 只重建 Graph 并留证。
6. 决策支持而非自动结论：abstract-level 结果不替代全文医学审核。
7. 动态状态单一来源：数量、生成时间和发布一致性只从数据状态产物读取。
8. 简报跟随当前上下文：复制内容必须反映当前标签、筛选条件和来源边界。
9. 周更口径显式：公开 rolling 以 `literature-recent.js` 为权威，社区 recent 使用相同 PMID 集合，周信号只来自 ingest `added_pmids`。
10. 发布不可混版：公开文件必须满足显式白名单与 hash 契约，活动页面资源统一使用 release run id。
11. 代码图只作辅助：CRG 的影响半径和测试关系必须回到实际 diff、动态数据契约与仓库测试验证，低风险分数不等于安全；获批源码上线后本地与 `main` 云端两次完整重建共同闭环。
12. 后台发布 fail closed：周更只自动提交声明的数据/HTML 产物，源码或其他路径漂移先转人工 review；单次 push 后条件刷新 Graph，数据更新不制造空提交。
13. 试验信号双门控：先判断试验本身是否关键，再判断本次更新是否实质；LLM 只能解释确定性字段，不能突破强度上限或把注册里程碑写成疗效结果。

## 页面任务

| 页面 | 核心任务 |
| --- | --- |
| 工作台 | 在全宽统一信号板内分别扫描本周文献信号与临床试验信号，再看数据状态 |
| 情报中心 | 回答“最近发生了什么”，区分文献与其他来源，并按当前上下文生成可复制简报；信号板已迁移到首页工作台 |
| 诊治格局 | 回答“证据怎样影响治疗判断” |
| 知识库 | 浏览社区、图谱、证据矩阵、专题和中国作者网络 |
| MSL 工作台 | China-only 专家检索、话题建议和 PMID 材料 |
| 数据状态 | 审查数量口径、产物时间、来源和管线健康 |

## 证据与来源频道层级

```text
PubMed MG-core + 证据等级 I–V
  → 公开文献流与文献信号

MG-core 指南/共识
  → 指南共识频道，不显示 Oxford 等级

监管 / 临床试验注册（ClinicalTrials.gov、ChiCTR、ChinaDrugTrials）/ 会议主来源
  → 各自独立频道，不显示 Oxford 等级

三源临床试验注册差分
  → 严格 MG-core + 试验重要性 × 更新实质性
  → 来源内强/中/弱试验信号（不与文献强度比较）
```

未知、非指南且没有证据等级 I–V 的 PubMed 记录不进入公开证据流。

## MSL 建议工作流

1. 在首页信号板按“文献 / 临床试验”分组确认 Signal 及其 PMID 或官方登记来源。
2. 在 MSL 工作台先输入中国作者、机构或学术兴趣关键词，再用筛选项细化公开画像。
3. 组合内容模块并生成拜访前话题建议。
4. 回到全文、指南、注册页或官方监管来源核查关键结论。
5. 网站之外的获批系统承担实际业务记录。

## 非目标

- 不建设拜访记录、follow-up、CRM 或互动历史。
- 不保存私有材料、内部专家标签、团队反馈或用户画像。
- 不把摘要级关联包装成全文级因果结论。
- 不在无 full 的云端运行中重建或缩小 full-derived 产物。
- 不在部分管线运行后伪造完整发布证明。
- 不把自动报告写入长期文档目录。
- 不把浏览器内生成的简报视为已保存记录或医学审核结论。

## 权威产物

| 判断 | 权威产物 |
| --- | --- |
| 严格公开文献 | `data/literature-recent.js` |
| 当前周文献信号 | `data/signals-weekly.js` |
| 当前三源临床试验信号 | `data/trial-signals-weekly.js` |
| 本周真实新增 PMID 口径 | 本地 `data/literature-ingest-latest.json` → `signals-weekly.js`、`communityWeekly.js`、`curated-topics.js`、`wikiTopicCoverage.js` |
| 语义 full 状态 | `data/literature-full-index.js`、community index、`pipeline-status.js` |
| 指南/共识 | `data/guideline-consensus-cache.json` |
| 来源频道 | `data/source-signals.js`（试验注册频道覆盖三源原始 `items` 与独立的已裁决 `weekly_signals`） |
| 会议摘要 | `data/conference-data.js` |
| 多源临床试验 | `data/clinical-trials-data.js` |
| China-only MSL 专家 | `data/expert-profiles-china.js` |
| 管线与数量状态 | `data/pipeline-status.js` |
| 完整发布证明 | `data/release-manifest.js`；其哈希一致性结论由 `pipeline-status.js` 展示 |
| 详细自动审计 | `.hermes-audit/` |

## 5 分钟审查顺序

1. 读“产品边界”和“非目标”。
2. 打开情报中心，确认来源频道彼此独立。
3. 依次切换文献、中国、会议和临床试验，确认简报跟随当前标签与筛选条件；首页信号简报必须分成文献与试验两节，并分别说明强/中/弱口径。
4. 打开知识库社区，确认“本周新证据”带有社区级新增数量；进入专题后仍保留社区筛选，且本周新入库证据排在长期专题 PMID 之前。
5. 打开 MSL 工作台，确认只加载中国专家分片且不保存行为。
6. 打开数据状态，核对公开滚动层、语义底座和完整发布哈希一致性；漂移时首页不得显示“完整发布成功”。
7. 运行快速验证，确认门控、分片和发布边界。

代码变更另按 [Code Review Graph 审查流程](../runbooks/codeReviewGraph.md) 执行 findings-first review。图谱只覆盖可解析源码，不替代本页的产品、来源、发布和医学边界检查。

## 验证命令

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
for file in assets/*.js; do node --check "$file" || exit 1; done
bash scripts/build-sites-static.sh
git diff --check
```

## 已知限制

- 文献、图谱、社区和 Living Answers 主要基于 title/abstract/metadata，正式医学使用前需阅读全文。
- MG-core 与证据分级是规则系统，需要持续抽样审计。
- 社区 `unassigned` 和冲突状态表示需要复核，不表示管线失败。
- “本周新证据”表示相对周更前基线真实新增的 PMID，不等于滚动 14 天，也不包含专题长期 PMID；社区标签只在该 PMID 的 primary/secondary 社区出现。
- 来源新鲜度读取产物语义时间而非文件 mtime；黄色表示过期或待核对，红色表示缺失或错误。
- ChiCTR 自动访问可能受 WAF 影响，失败时使用 last-good 官方缓存。
- 国际专家分片不被页面加载，但仍是 GitHub Pages 可公开访问的 tracked 文件，不能存放私有数据。
- 当前数量、分片规模、会议覆盖和发布时间会随周更变化，应在数据状态页查看，不在本文档中固定。
