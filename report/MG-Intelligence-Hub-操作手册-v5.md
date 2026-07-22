# MG Intelligence Hub v5.x — 架构设计与操作手册
> 定位：MA-MG-HUB 医学事务 AI 变革引擎，围绕 MSL 工作流的主动赋能系统
> 本手册是当前操作依据；`report/` 中旧规划文档仅作历史参考。
> 设计与审查请先读：[网站设计与审查速览.md](网站设计与审查速览.md)。

---

## 1. 系统总览

### 1.1 MG Intelligence Hub 是什么

MG Intelligence Hub 是面向重症肌无力（MG）医学事务团队的静态情报工作站。它不是单纯文献列表，而是把 PubMed 文献、会议摘要、ClinicalTrials、监管状态、知识图谱、社区语义层和 MSL 拜访准备整合到一个 GitHub Pages 网站中。

核心原则：

- **公开网站只承载可公开前端产物**：HTML / CSS / JS / JSON；无后端、无用户数据库。
- **本地 full 底座承担重分析**：`data/literature-full.json` 与大体量中间产物留在本地，不推 GitHub。
- **前端以数据产物驱动**：所有页面通过 `window.MG_*` 全局数据对象渲染，不依赖 build step。
- **医学事务语义层优先**：社区、Living Answers、MSL action 比单纯统计数字更重要。
- **中国大陆 MSL 公开情报边界**：只提供专家证据、公开情报和拜访前材料；不记录拜访，不建设随访、CRM、互动历史、私有后端或浏览器持久化。

### 1.2 当前回答的问题

| 用户问题 | 入口 |
|---|---|
| 近 14 天有哪些值得关注的 MG 信号？ | 情报中心 / 信号板；工作台信号摘要 |
| 中国相关证据有哪些新变化？ | 情报中心 / 中国情报；诊治格局 / 中外差异 |
| MG 领域证据形成了哪些主题网络？ | 知识库 / 知识图谱、社区视图、证据矩阵 |
| 某个治疗问题现在可如何回答？ | 诊治格局 / Living Answers |
| 拜访某位专家前应准备什么？ | MSL 工作台 / 专家画像、拜访助手 |
| 数据是否更新、产物是否健康？ | 数据状态；工作台数据健康 |

### 1.3 系统角色

| 角色 | 当前职责 |
|---|---|
| GitHub Pages | 承载线上静态网站：`https://reiger-luo.github.io/MA-MG-HUB/` |
| 本地工作站 | 保存 full 文献库和中间数据；运行完整重建与推送 |
| Hermes / 本地 cron | 调度 `scripts/run-local-weekly-sync.sh`，用于本地 full 驱动周更 |
| GitHub Actions | 云端兜底：执行质量门、轻量周更、提交公开产物 |
| AI coding agent | 开发、调试、文档维护、质量审计；不直接替代医学审核 |

---

## 2. 网站页面与导航

### 2.1 当前主页面

导航栏实际为 **品牌入口 + 6 个页面链接**。6 个页面链接在所有主页面中保持一致：工作台 / 情报中心 / 诊治格局 / 知识库 / MSL工作台 / 数据状态。

| 页面 | 文件 | 当前功能 |
|---|---|---|
| 工作台 | `index.html` | 统计卡片、社区动态、近期信号、工作流状态、数据健康 |
| 情报中心 | `pages/literature.html` | 文献速览 / 信号板 / 中国情报 / 会议资讯 |
| 诊治格局 | `pages/landscape.html` | 总览（月度洞察、竞争矩阵、临床管线、中外差异）/ Living Answers |
| 知识库 | `pages/knowledge.html` | 知识图谱 / 社区视图 / 证据矩阵 / 专题 / 跨库检索 |
| MSL 工作台 | `pages/msl.html` | 专家画像 / 拜访助手 |
| 数据状态 | `pages/data-ops.html` | 数据源、公开产物、community audit、graph health、backend options |

### 2.2 历史重定向页

| 旧页面 | 当前跳转 |
|---|---|
| `pages/materials.html` | `pages/msl.html` |
| `pages/outputs.html` | `pages/msl.html` |
| `pages/progress.html` | `pages/msl.html` |
| `pages/competitive.html` | `pages/landscape.html` |

这些页面没有导航栏，只保留 meta refresh 和提示文案。

### 2.3 页面分工

```
工作台
  ├── 情报中心：增量流入，回答“最近发生了什么”
  ├── 诊治格局：战略解释，回答“这些证据怎样改变治疗判断”
  ├── 知识库：沉淀底座，回答“我们掌握了什么结构化证据”
  ├── MSL 工作台：行动转化，回答“拜访前准备什么”
  └── 数据状态：运维透明，回答“数据和管线是否健康”
```

---

## 3. 数据架构与当前口径

### 3.1 两套核心口径

当前网站同时存在两个数据口径，必须区分：

| 口径 | 当前数量 | 用途 |
|---|---:|---|
| **公开滚动文献层** | 2026-07-22 严格派生快照：`literature-recent.js` 903 篇，其中中国相关 216 篇；全部 MG-core 且 evidence I–V | 情报中心文献速览、公开文献门控 |
| **本地 full / 语义底座** | 2026-07-15 快照：`literature-full.json` / `literature-full-index.js` / community assignment 均为 10,672 篇 | 知识图谱、社区归类、专家画像、跨库检索 |

`pipeline-status.js` 当前声明 `public_rolling_count=903`、`semantic_full_count=10672`，并核对 raw full、full index、community index/audit 一致。`MG_TOTAL_COUNT` 与 `MG_SEMANTIC_FULL_COUNT` 表示语义 full，不等于 recent 数量。`dashboard-data.js` 与 `china-intelligence.js` 已从严格 recent 重建，当前分别显示 903 篇 recent 与 216 篇中国相关文献。

### 3.2 数据流

```
PubMed / ClinicalTrials.gov / EasyScholar / 中国监管状态 / 会议来源
    ↓
本地 full 底座：literature-full.json、communityAssignments.jsonl、communityCorpusPack.jsonl
    ↓
公开滚动层：literature-recent.js、signals-weekly.js、china-intelligence.js
    ↓
语义层：communityTaxonomy.js、communityCards.js、communityWeekly.js、communityAssignments-*.js
    ↓
图谱与策展层：knowledge-graph.js、graphHealth.js、curated-topics.js、wikiTopicCoverage.js、landscapeInsights.js
    ↓
应用层：dashboard-data.js、expert-profiles*.js、content-modules.js、conference-data.js、pipeline-status.js
```

### 3.3 本地保留文件

| 文件 | 当前状态 | 说明 |
|---|---:|---|
| `data/literature-full.json` | 10,672 篇，约 40 MB | 本地 full 文献底座，不推 GitHub |
| `data/literature-weekly.json` | 32 篇 | 当前周增量临时文件；不作为公开流权威数量 |
| `data/communityCorpusPack.jsonl` | 约 21 MB | 社区语义层输入包 |
| `data/communityAssignments.jsonl` | 约 4.1 MB | 全量 PMID 社区归类明细 |
| `data/.llm_cache/` | 本地缓存 | LLM 响应缓存 |
| `data/.llm_cost.log` | 本地日志 | LLM 成本日志 |
| `data/archive/` | 本地备份 | 历史备份，不推远程 |

### 3.4 公开前端数据产物

| 文件 | 当前大小 / 数量 | 用途 | 加载方式 |
|---|---:|---|---|
| `data/dashboard-data.js` | 约 55 KB；2026-07-22 重建 | 工作台统计、section、top signals、工作流；recent 903 / China 216 | 首页同步加载 |
| `data/literature-recent.js` | 903 篇 | 严格 MG-core + evidence I–V 主文献数据 | 情报中心同步加载 |
| `data/signals-weekly.js` | 13 条父级 Signal / 19 条 talking point / 28 个 PMID | Signal → gap → Evidence → KOL key points；严格 recent 重建 | 同步加载 |
| `data/china-intelligence.js` | 中国相关 216 篇；展示最新 120 条摘要 | 严格 MG-core + evidence I–V 的 recent 中国情报 | 按需加载 |
| `data/literature-full-index.js` | 10,672 篇轻索引 | 知识库跨库检索 | 懒加载 |
| `data/knowledge-graph.js` | 6.8 MB；55 节点 / 334 核心边 / 180 矩阵行 | 知识库图谱与证据矩阵 | 知识库同步加载 |
| `data/graphHealth.js` | 7 KB | 图谱健康度 | 知识库、数据状态同步加载 |
| `data/communityTaxonomy.js` | 9 KB；10 个业务社区 | 社区定义 | 多页面同步加载 |
| `data/communityCards.js` | 45 KB；10 张社区卡片 | 社区摘要、代表证据 | 首页、知识库同步加载 |
| `data/communityWeekly.js` | 23 KB；10 个社区周更 | 社区动态 | 首页、知识库同步加载 |
| `data/communityAssignmentIndex.js` | 7 KB；10 个业务社区 + unassigned 分片索引 | 社区归类入口 | 同步加载 |
| `data/communityAssignments-*.js` | 分片 | 某一社区 PMID 明细 | 懒加载 |
| `data/communityAssignmentsRecent.js` | 1,158 条近一年归类 | 上次 full 社区构建快照；与严格公开 recent 分属不同口径 | 按需加载 |
| `data/communityAudit.js` | 28 KB | 社区 assignment 质量摘要 | 知识库、数据状态同步加载 |
| `data/expert-profiles.js` | 2.4 KB manifest | 专家画像入口、分片路径 | MSL 同步加载 |
| `data/expert-profiles-china.js` | 8,958 位 | 中国作者-机构索引 | MSL 同步加载 |
| `data/expert-profiles-international.js` | 43,626 位 | 国外作者-机构索引，仅供离线分析 | 前端不加载 |
| `data/source-signals.js` | 5 个来源频道 / 386 条频道项 | 文献、指南/共识、监管、注册、会议的独立信号摘要 | 情报中心同步加载 |
| `data/guideline-consensus-cache.json` | 9 篇 | MG-core 且具有指南/共识主来源标志的独立缓存；不进入 I–V 文献流 | 构建脚本使用 |
| `data/chictr-trials-cache.json` | tracked cache | ChiCTR 官方公开研究字段；人工官方导出刷新 | 构建脚本使用 |
| `data/release-manifest.js` | 当前不存在 | 仅真实 required-step 管线完整成功后生成 coherent run id 与产物哈希 | 数据状态/发布审计 |
| `data/content-modules.js` | 28 KB；6 个模块 | MSL 拜访助手信息模块 | MSL 同步加载 |
| `data/landscape-data.js` | 254 KB | 竞争矩阵、临床管线、Living Answers | 诊治格局同步加载 |
| `data/landscapeInsights.js` | 27 KB；6 条动态洞察 | 月度格局洞察、MSL action | 诊治格局 / MSL 同步加载 |
| `data/curated-topics.js` | 117 KB；27 个专题 | 知识库专题层 | 知识库 / 诊治格局同步加载 |
| `data/wikiTopicCoverage.js` | 64 KB；27 个专题覆盖 | wiki 专题与 PubMed 社区映射 | 多页面同步加载 |
| `data/conference-data.js` / `.json` | 195 条摘要 | 会议资讯；含 meetingNarratives、coverageAudits 和逐条 deepInsight。MGFA / AANEM 已清空，待新数据源链接后再接入 | 情报中心同步加载 |
| `data/pipeline-status.js` | 6 KB | 数据状态页 | 数据状态同步加载 |
| `data/backendOptions.js` | 5 KB | Phase 6 后端选项评估 | 数据状态同步加载 |
| `data/china-regulatory-status.json` | — | NMPA/CDE/准入状态 | 构建脚本与诊治格局使用 |
| `data/clinicaltrials-pipeline-cache.json` | — | ClinicalTrials 管线缓存 | 构建脚本与诊治格局使用 |
| `assets/journal_metrics.json` | — | IF / CAS 分区缓存 | 构建脚本使用 |

---

## 4. 医学事务社区层

社区层是当前网站的核心语义层。2026-07-15 快照将 10,672 篇 full corpus 文献映射到医学事务可行动主题，用于工作台、知识库、情报中心筛选和后续 MSL action。

### 4.1 社区结构

当前有 **10 个业务社区**，另有 `unassigned` 作为低置信度/未归类桶，不属于 taxonomy 展示社区。

| ID | 名称 | 文献数 | 高等级证据 | 中国相关 |
|---|---|---:|---:|---:|
| `clinicalSubtypesStratification` | 临床亚型与人群分层 | 2,058 | 57 | 322 |
| `safetyMedicationManagement` | 安全性与用药管理 | 1,656 | 121 | 269 |
| `diagnosisMonitoringPrediction` | 诊断、监测与预测 | 1,184 | 27 | 183 |
| `mechanismTranslationalMedicine` | 机制与转化医学 | 1,042 | 13 | 420 |
| `rweClinicalPathway` | 真实世界证据与临床路径 | 721 | 25 | 156 |
| `efficacyBurdenOutcomes` | 疗效终点与疾病负担 | 557 | 69 | 128 |
| `complementAndNovelTargets` | 补体与其他新靶点 | 293 | 19 | 32 |
| `fcrnTargetedTherapy` | FcRn 靶向治疗 | 251 | 38 | 76 |
| `guidelineHeorAccess` | 指南、共识与卫生经济 | 109 | 4 | 17 |
| `competitiveLandscapeIndirectComparison` | 竞争格局与间接比较 | 51 | 18 | 14 |
| `unassigned` | 未归类桶（非展示社区） | 2,750 | — | — |

### 4.2 质量状态

`communityAudit.js` 当前摘要：

| 指标 | 数量 |
|---|---:|
| total_articles | 10,672 |
| assigned_articles | 7,922 |
| unassigned_articles | 2,750 |
| low_confidence_articles | 1,100 |
| conflict_articles | 1,519 |
| recent_unassigned_articles | 4 |

当前状态为 `needsReview`。这不是运行失败，而是提示 taxonomy 和 assignment 仍需医学事务 review。

### 4.3 方法

- 当前 assignment 方法：`ruleBasedMedicalAffairsReview`
- 数据源模式：`local_full_first`
- 版本：`2026.07-v4e-medical-affairs-signal`
- 核心逻辑：`buildCommunityData.py` 中每个 community spec 定义 strong / normal / weak terms，通过 title / abstract / metadata 规则归类。
- 前端策略：首屏只加载 taxonomy/cards/weekly/audit；全量 assignments 按社区分片懒加载。

---

## 5. 知识库与图谱

### 5.1 知识图谱

当前 `knowledge-graph.js`：

| 指标 | 数量 |
|---|---:|
| 图谱节点 | 55 |
| 核心展示边 | 337 |
| 全量合格边 | 1,261 |
| 证据矩阵行 | 180 |
| abstract-level 命中文献 | 9,191 |

图谱关系来自 title / abstract / metadata 层面的证据线索，不代表全文级因果关系。页面中已保留 PMID 回链。

### 5.2 Graph Health

`graphHealth.js` 当前状态为 `needsReview`：

- 55 个节点均已映射到社区
- 337 条展示边均有社区映射
- oversized_nodes = 6
- weak_edges = 88
- isolated_nodes = 0
- semantic_bridge_gaps = 0

含义：图谱结构完整，但仍需要对过大节点和弱边做医学事务语义 review。

### 5.3 知识库 5 个 tab

| Tab | 用途 |
|---|---|
| 知识图谱 | 图谱浏览、节点筛选、社区染色、核心/桥接/全部边切换 |
| 社区视图 | 10 个医学事务社区的定义、代表证据、本周动态和 audit 信息 |
| 证据矩阵 | 180 行摘要级关系，用于定位 PMID 证据 |
| 专题 | 本地 wiki/专题层与 PubMed 证据桥接 |
| 跨库检索 | 同时检索 full 文献轻索引与专家画像 |

---

## 6. 情报中心与会议资讯

### 6.1 情报中心 4 个 tab

| Tab | 数据来源 | 用途 |
|---|---|---|
| 文献速览 | `literature-recent.js` | 近一年文献浏览、筛选、分页、证据等级展示 |
| 信号板 | `signals-weekly.js` | 近 14 天 MG-core 聚合 Signal → Talking Points → Evidence |
| 中国情报 | `china-intelligence.js` | 中国相关文献、方向、机构/作者线索 |
| 会议资讯 | `conference-data.js` + `conference.js` | AAN / EAN 会议模块；MGFA / AANEM 仅保留待接入占位 |

### 6.2 会议数据

当前结构化会议摘要共 195 条。会议资讯不是新闻列表，而是面向医学事务（medical affairs, MA）和 MSL briefing 的摘要级情报工作台。MGFA / AANEM 后台数据已清空，等待新的稳定摘要链接后再接入。

| 来源 | 数量 | 当前状态 |
|---|---:|---|
| AAN 2026 | 91 | 已接入；MiraSmart 检索命中 109 条，MG 摘要 91 条，规则剔除 18 条；前端显示 NEW |
| EAN 2026 | 104 | 已接入；已纳入 acronym-only MG 标题条目；前端显示 NEW |
| MGFA | — | 后台清空；待提供会议摘要链接后重新接入 |
| AANEM | — | 后台清空；待提供会议摘要链接后重新接入 |

分析维度包括国家/地区、研究类型、主题、药物/机制、中国相关、高优先级、行动标签、证据边界和 KOL 问题。

### 6.3 AAN / EAN 会议资讯口径

会议数据由 `scripts/build-conference-data.py` 生成。不要手改 `data/conference-data.js` 或 `data/conference-data.json`。

| 字段 | 用途 |
|---|---|
| `meetingNarratives.chapters` | 会议级线索，回答“本次会议说明 MG 领域什么方向正在变化” |
| `meetingNarratives.chapters[].talkingPoints` / `kolFocus` | KOL 交流点，回答“拿哪条证据去和 KOL 说什么/问什么”；前者嵌套在线索下，后者作为优先清单扁平排序 |
| `coverageAudits` | 展示检索命中、MG 摘要、剔除数量和剔除原则 |
| `deepInsight` | 每条摘要的临床读数、MA 转化、证据边界、关键数字、KOL 问题 |
| `abstractZh` | LLM 生成的真实中文摘要翻译；不要用 `analysisZh` 冒充摘要全文 |
| `deepInsight.kolKeyMessageZh` | 摘要级 KOL key message，供会议级交流点调用 |

AAN 2026 的会议资讯保留可核查工作流口径：MiraSmart `myasthenia` 检索命中 109 条，MG 摘要 91 条，剔除 18 条 CMS / LEMS / mimic / 非 MG 误命中。每条入库摘要保留原始链接，并增加 MA 转化与证据边界。

EAN 2026 已完成外部文章引用核查。被引用的 31 条 EAN 摘要均已纳入本库并生成分析字段。当前 104 条包含 acronym-only MG 标题条目 `EPV-1203`。

#### Signal-to-KOL 生成原则

会议资讯不是把“线索”和“交流点”并排罗列，而是采用三层链条：`摘要证据 → 会议线索 → KOL 交流点`。

- 会议线索（signal）是父层：回答“会议说明什么变化”，必须说明 `whySignal` 和 `evidenceBoundary`，由多摘要趋势、证据格局变化、未满足需求或 MA 机会支撑。
- KOL 交流点（talking point）挂在线索下：回答“拿哪条证据去和 KOL 说什么/问什么”，必须有 `parentSignalId`、`whyKol`、`keyMessages` 和证据 locator chips。
- 同一摘要可以同时支撑线索和交流点；线索解释结构变化，交流点承载可传递的具体数据或追问。
- 交流点排序：`efgar` 数据优先传递；竞品/其他治疗数据从与 efgar 的机制、人群、终点、给药、安全性、证据成熟度区隔角度解读；与产品或治疗无直接关系但重要的疾病进展最后补充。
- 复刻到 MGFA / AANEM 时，先把稳定摘要链接加入 `SOURCES` / `SOURCE_MONITOR`，保证摘要正文与 locator 可靠，再运行 `enrich-conference-zh.py` 和 `enrich-conference-narrative.py --conference "会议名" --force`。

#### 文献 Signal-to-KOL 生成原则

文献信号与会议信号来源不同，但复用同一语义链条：`PubMed evidence → literature Signal → KOL talking point → PMID evidence`。

- `scripts/build-frontend-data.py` 先做 MG-core 相关性过滤，再按 efgartigimod / 其他靶向机制 / 抗体分型 / 安全性 / 患者负担 / 临床路径等主题聚合。
- 仅把 MG 作为比较组或背景的 CIDP、stiff-person、MS 等文章不会进入文献 Signal；会议摘要仍严格排除在 `signals-weekly.js` 之外。
- `scripts/enrich-literature-narrative.py` 只负责证据边界内的语义归纳；所有 `refPmids` 必须来自输入记录，程序写入前会去重并核查公开引用覆盖率。
- 每个 talking point 必须包含 `parentSignalId`、`priorityTier`、`whyKol`、`keyMessages` 和 `refs`；优先级为 `efgar → competitor_response → disease_progress`。
- 无 API key 或 LLM 返回不合格 JSON 时，保留确定性 MG-core 聚合回退，不阻断基础周更。
- 2026-07-22 的严格 recent 重建产物为 13 条父级 Signal、19 条 talking point、28 个唯一 PMID；每条 Signal 逐篇保存 finding、gapContribution 与 boundary，PMID 只在证据项中展示一次。该数量随近 14 天 PubMed 窗口变化，不应硬编码到前端逻辑。
- 手动重建顺序：`python3 scripts/build-frontend-data.py` → `python3 scripts/enrich-literature-narrative.py` → `python3 scripts/generate-weekly-summary.py` → `python3 scripts/generate-pipeline-status.py`。只重建基础数据时，前两步中的第二步可跳过，但发布前必须确认 `signals-weekly.js` 的 `source_policy` 与 PMID 覆盖率。

---

## 7. 诊治格局

诊治格局不是单独的“竞品页”，而是把近期证据、知识图谱、监管状态和临床管线转成 MSL 可扫描的治疗格局判断。

### 7.1 总览 tab

包含：

- 动态月度洞察（`landscapeInsights.js`，当前 6 条）
- 中国已获批治疗选择竞争矩阵
- ClinicalTrials Phase II+ 临床开发管线矩阵
- 中外证据与诊治差异

### 7.2 Living Answers tab

- 当前 Dashboard 统计为 6 个 landscape questions
- 每个问题保留回答姿态、要点、证据锚点和 PMID 回链
- 当前定位是 abstract-level 提纲，不替代全文级综述或正式医学声明

---

## 8. MSL 工作台

### 8.1 专家画像

专家画像已拆成 manifest + 区域分片：

| 文件 | 数量 | 加载方式 |
|---|---:|---|
| `expert-profiles.js` | manifest，0 位实际专家 | 同步加载，用于声明分片路径 |
| `expert-profiles-china.js` | 8,958 位 | MSL 页面同步加载，默认中国视图 |
| `expert-profiles-international.js` | 43,626 位 | 每次完整重建仍生成，仅供离线分析；网站不加载 |

完整重建生成总计 52,584 位作者-机构画像和轻量 manifest，但 `pages/msl.html` / `assets/msl.js` 是 China-only：默认、搜索和拜访准备只使用中国作者索引，没有国际分片加载路径。前端徽标只报告中国作者索引和快速候选。无 full 的云端构建会保留这两个 last-good 分片，不会以 recent 数据清空或缩小它们。

### 8.2 拜访助手

当前已实现：

- 选择专家
- 选择 6 个内容模块中的学术/产品信息
- 读取近期信号与本月诊治格局 action
- 在页面内生成“拜访话题建议”和对应 PMID 文献清单

范围边界：本站只生成拜访前话题和公开 PMID 材料，不记录拜访、不保存随访、不维护 CRM 或互动历史，也不把这些能力列入未来范围。

### 8.3 内容模块

当前 6 个模块：

1. 抗体分型与发病机制
2. 中国真实世界与患者价值
3. 诊疗路径与共识问题
4. Efgartigimod 疗效与适用人群
5. Efgartigimod 安全性与用药管理
6. 靶向治疗格局与竞品定位

---

## 9. 周更与构建流程

### 9.1 本地完整周更入口

生产级本地入口是：

```bash
bash scripts/run-local-weekly-sync.sh
```

它以本地 `data/literature-full.json` 为源头，执行完整下游刷新、校验、commit 和 push。支持 dry-run：

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

### 9.2 `run-local-weekly-sync.sh` 实际步骤

```
1. 校验 full 文件存在、Git tracked 改动干净、当前分支为 main
2. git fetch / pull --ff-only origin main
3. `run-weekly-pipeline.py --local-full --run-id local-<timestamp>`：抓取/富集/合并后执行 MG-core `--apply`、归档排除记录、近一年重分类及完整下游重建
4. 生成 source signals、pipeline status 与 release manifest
5. 执行 full/recent 同步校验
6. 非 dry-run 时 git add → commit → push
```

### 9.3 `run-weekly-pipeline.py` 检查点执行

每步记录到 `.hermes-audit/pipeline-runs/<run-id>.json`：step id、命令、起止时间、耗时、状态、optional、错误码、声明输出和哈希。标准流依次执行 fetch、MG-core/证据富集、merge、前端构建、可选 narrative、full index、community、knowledge、中国作者网络、专题、格局、ChiCTR cache、source signals、周报和状态。`--local-full` 会在 merge 后加入 `filter-mg-core-literature.py --apply` 与近一年重分类。

恢复命令：

```bash
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume --from-step build-source-signals
```

步骤默认有可配置超时；required 超时为硬失败，optional 超时只记 warning。resume 仅跳过“此前成功且声明输出哈希仍匹配”的步骤。仅所有 required 步骤成功后更新 `data/release-manifest.js`，部分运行不会宣称成功发布。

默认 `build-frontend-data.py` 会重建 recent-derived 的 signals、China、dashboard、landscape 与 content modules，同时加载并逐字节保留现有专家 manifest 和 China/international 分片，即使本地 full 存在也不改写专家文件。`run-weekly-pipeline.py` 仅在检测到 full 时为该步骤传入 `--rebuild-experts-from-full`，此显式模式固定生成两个区域分片。

当 `data/literature-full.json` 不存在时，管线进入 cloud-safe mode：继续 recent、前端 recent/signals/China/dashboard、source signals、周报和状态流程，但不运行 `build-full-index`、`build-community`、`build-knowledge`、`build-china-author-network`，从而保留 tracked last-good full-derived 产物。cloud-safe mode 不传专家重建 flag，因此专家 manifest 和两个区域分片同样保持 last-good 字节不变。

### 9.4 MG-core、证据门控与来源频道

周增量先执行 MG-core，再调用证据分类器。明确 MG 题名、可靠 MG MeSH/关键词或重复 MG-core 提及可保留；非 MG 疾病主导题名和单次背景提及排除。之后仅证据等级 I–V 进入 PubMed 文献库。合并脚本对合并后的完整历史候选流再次执行两道门控，而不是只检查 weekly incoming。

历史和 weekly 的 MG-core 指南/共识使用同一检测：研究类型标签之外，还要求 `Practice Guideline` / `Consensus Statement` 等 publication type，或题名中的明确指南/共识主来源标志，避免把正文中提到 guideline 的普通研究误路由。缓存按 PMID 原子、幂等更新，不进入证据文献流。未知、非指南且无 I–V 等级的记录不会进入任何公开证据频道。`source-signals.js` 分为文献证据、指南/共识、中国监管、试验注册和会议五个频道。会议频道只给摘要级信号，完整会议工作区仍留在会议 tab。

只重建严格 recent、指南缓存、来源频道和状态，不合并 weekly、不写 full：

```bash
python3 scripts/merge-weekly-literature.py --derive-only
python3 scripts/build-source-signals.py
python3 scripts/generate-pipeline-status.py
```

ChiCTR 使用 `chictr-trials-cache.json` 的官方公开字段种子。自动访问被 Aliyun WAF 阻断时保持最后良好缓存并标记 `mode=cache`；运营人员可运行 `refresh-chictr-cache.py --input <official.json|csv>`。不得使用第三方抓取数据或重新分发 WHO ICTRP 数据。ChiCTR / ClinicalTrials.gov 注册记录没有 Oxford 证据等级。

### 9.5 GitHub Actions 兜底

Workflow：`.github/workflows/weekly-pipeline.yml`

- 触发：仅手动 `workflow_dispatch`；当前 YAML 没有 `schedule`
- 环境：Ubuntu + Python 3.11
- 质量门：`python -m py_compile scripts/*.py`、`node --check assets/*.js`、禁止旧 EasyScholar key / SSL bypass pattern
- 测试：`python -m pytest -q`
- 执行：`python scripts/run-weekly-pipeline.py`
- 提交：`data/*.js`、`data/weekly-summary.md`、监管/管线缓存、assets/pages/index

GitHub Actions 没有本地 full 文件，因此只能作为公开 recent 数据的兜底路径；完整语义层仍以本地工作站为准。

---

## 10. 开发与维护约定

### 10.1 项目结构

```
MG-Intelligence-Hub/
├── index.html
├── pages/
│   ├── literature.html
│   ├── landscape.html
│   ├── knowledge.html
│   ├── msl.html
│   ├── data-ops.html
│   ├── materials.html      # redirect → msl.html
│   ├── outputs.html        # redirect → msl.html
│   ├── progress.html       # redirect → msl.html
│   └── competitive.html    # redirect → landscape.html
├── assets/
│   ├── common.js
│   ├── main.css
│   ├── dashboard.js
│   ├── literature.js
│   ├── conference.js
│   ├── landscape.js
│   ├── knowledge.js
│   ├── msl.js
│   ├── dataOps.js
│   └── dataOps.css
├── data/
├── scripts/
├── tests/
├── .github/workflows/
├── requirements.txt
├── requirements-dev.txt
└── report/
```

### 10.2 前端约定

- 零构建：直接加载 HTML / CSS / JS。
- 数据全局变量统一使用 `window.MG_*`。
- 共用工具在 `window.MgHub`：base path、escape、safeUrl、loadScriptOnce、tabs 等。
- 大文件使用分片或懒加载：full index、community assignment shards；国际专家分片只离线生成，MSL 前端不加载。
- 动态 HTML 必须 escape；外链 URL 必须走 safe helper。
- 页面导航修改必须同步 6 个主页面；redirect 页不算主导航。

### 10.3 证据等级

- `scripts/studyClassifier.py`：Oxford CEBM 2011-informed I–V 自动筛选标签。
- 规则来源：`report/Oxford-CEBM-2011-证据等级规则参考.md`
- I：Systematic Review / Meta-Analysis；II：RCT / Prognostic Inception Cohort；
  III：Non-randomized controlled cohort / Adjusted Retrospective Cohort / Post-marketing Controlled Follow-up；
  IV：Case Control / Historical Control / Case Series / Case Report / Cross-Sectional / Single Arm / Pharmacovigilance / Genetic/Omics Association / Biomarker Association；
  V：Mechanism-based Reasoning。
- Narrative Review / Protocol / HEOR / Guideline / Consensus / Editorial / Letter / Comment / Animal / In Vitro 为未分类，无 evidence_level。

### 10.4 Python 约定

- 共用读写工具：`scripts/common/io.py`
- EasyScholar：`scripts/easyscholar_api.py`，只从 `EASYSCHOLAR_KEY` 环境变量读取密钥
- PubMed / NCBI：`NCBI_API_KEY` 作为可选加速参数
- 写前端 JS 数据优先用 `atomic_write_js_global`

### 10.5 Git 与安全纪律

- `data/literature-full.json`、`data/literature-weekly.json`、`data/archive/`、LLM cache/cost 不推 GitHub。
- 公开数据产物在 `data/*.js`。
- API key 不写入脚本、报告或前端数据。
- CI 已扫描旧硬编码 key 与 SSL bypass pattern。
- 拜访记录、内部专家标签、团队反馈不进入公开仓库。

### 10.6 验证命令

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
node --check assets/*.js
```

---

## 11. 当前已知问题

| 优先级 | 问题 | 当前影响 | 建议处理 |
|---|---|---|---|
| P2 | `communityAssignmentsRecent.js` 仍是 full 社区构建口径，与严格公开 recent 分属不同快照 | 社区 recent 数量不能替代公开 rolling 数量 | 继续在状态页分开显示两套口径；需要时运行完整 community 构建 |
| P1 | `data/release-manifest.js` 当前不存在 | 当前局部派生不构成 coherent 完整发布证明 | 仅在真实 required-step 管线完整成功后生成，不手工补造 |
| P1 | 证据矩阵仍是 abstract-level 自动关系，可能混入跨疾病或弱相关 PMID | MSL 使用时需回到 PMID 原文核对 | 增加跨疾病排除规则和人工抽样 review |
| P2 | ChiCTR 自动访问可能被 Aliyun WAF 阻断 | 无法保证每周 live 刷新 | 使用官方字段 tracked cache 与运营人员官方 JSON/CSV 导出刷新 |
| P3 | `data/china-manual.json` 不存在 | 中国情报缺少手动补充入口，但不影响 PubMed 自动部分 | 需要人工维护中国政策/指南时再创建 |
| P3 | AANEM 仅有监控口，尚未进入结构化会议摘要库 | AAN / EAN / MGFA 已结构化，AANEM 仍缺摘要级情报 | 后续补结构化抓取/录入 |

---

## 12. 快速操作指南

### 12.1 查看当前网站

- 线上：`https://reiger-luo.github.io/MA-MG-HUB/`
- 本地：直接打开 `index.html`，或使用任意静态 server。

### 12.2 本地完整 dry-run

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

### 12.3 本地完整周更并推送

```bash
bash scripts/run-local-weekly-sync.sh
```

### 12.4 仅跑内部周更管线

```bash
python3 scripts/run-weekly-pipeline.py
```

恢复指定运行：

```bash
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume --from-step build-source-signals
```

### 12.5 仅重建社区语义层

```bash
python3 scripts/buildCommunityData.py
```

### 12.6 仅重建知识图谱

```bash
python3 scripts/build-knowledge-data.py
```

### 12.7 仅重建会议资讯

```bash
python3 scripts/build-conference-data.py
```

需要刷新远端会议源时使用：

```bash
python3 scripts/build-conference-data.py --refresh
```

重建后至少运行：

```bash
python3 -m py_compile scripts/build-conference-data.py
node --check assets/conference.js
python3 -m pytest -q
```

### 12.8 手动触发 GitHub Actions

GitHub 仓库 → Actions → `MA-MG-HUB Weekly Pipeline` → `Run workflow`

---

## 13. 旧文档关系

以下旧文档保留为历史记录，不再作为当前操作依据：

| 文件 | 当前状态 |
|---|---|
| `report/项目规划-v3.2.md` | 规划蓝图，已被当前 v5 实现超越 |
| `report/siteRevampPlanV4.md` | 改版草案，部分已实现、部分已修订 |
| `report/知识库社区分类精细化建议-2026-06-29.md` | 思路已融入社区层实现 |
| `report/codexSecondOpinionReview2026-07-01.md` | 审查意见中仍有效的部分已纳入“当前已知问题” |

当前设计审查入口为 `report/网站设计与审查速览.md`；建议新审查者先读该文件，再按需进入本手册。

---

## 14. 后续建设方向

1. 统一 public rolling count 与 semantic full count 的展示和校验逻辑。
2. 修复 pipeline-status 对 expert shards、community shards、生成时间的识别。
3. 补齐 AANEM 结构化会议数据。
4. 持续扩展公开来源频道的覆盖率、缓存审计与来源核查。
