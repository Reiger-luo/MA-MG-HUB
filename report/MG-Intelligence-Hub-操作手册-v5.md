# MG Intelligence Hub v5.x — 架构设计与操作手册
> 定位：MA-MG-HUB 医学事务 AI 变革引擎，围绕 MSL 工作流的主动赋能系统
> 本手册是当前操作依据；`report/` 中旧规划文档仅作历史参考。

---

## 1. 系统总览

### 1.1 MG Intelligence Hub 是什么

MG Intelligence Hub 是面向重症肌无力（MG）医学事务团队的静态情报工作站。它不是单纯文献列表，而是把 PubMed 文献、会议摘要、ClinicalTrials、监管状态、知识图谱、社区语义层和 MSL 拜访准备整合到一个 GitHub Pages 网站中。

核心原则：

- **公开网站只承载可公开前端产物**：HTML / CSS / JS / JSON；无后端、无用户数据库。
- **本地 full 底座承担重分析**：`data/literature-full.json` 与大体量中间产物留在本地，不推 GitHub。
- **前端以数据产物驱动**：所有页面通过 `window.MG_*` 全局数据对象渲染，不依赖 build step。
- **医学事务语义层优先**：社区、Living Answers、MSL action 比单纯统计数字更重要。

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
| **公开滚动文献层** | 近一年 `literature-recent.js` 1,154 篇；其中中国相关 323 篇；候选信号 38 条 | 情报中心、Dashboard、信号板、中国情报 |
| **本地 full / 语义底座** | `literature-full.json` / `literature-full-index.js` / community assignment 为 10,635 篇 | 知识图谱、社区归类、专家画像、跨库检索 |

注意：当前 `dashboard-data.js.stats.total_articles` 与 `window.MG_TOTAL_COUNT` 显示 1,165，属于公开前端统计口径，并不等同于社区语义层使用的 10,635 篇 full 底座。这个口径差异已列入已知问题。

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
| `data/literature-full.json` | 10,635 篇，约 40 MB | 本地 full 文献底座，不推 GitHub |
| `data/literature-weekly.json` | 38 篇，约 274 KB | 当前周增量临时文件 |
| `data/communityCorpusPack.jsonl` | 约 21 MB | 社区语义层输入包 |
| `data/communityAssignments.jsonl` | 约 4.1 MB | 全量 PMID 社区归类明细 |
| `data/.llm_cache/` | 本地缓存 | LLM 响应缓存 |
| `data/.llm_cost.log` | 本地日志 | LLM 成本日志 |
| `data/archive/` | 本地备份 | 历史备份，不推远程 |

### 3.4 公开前端数据产物

| 文件 | 当前大小 / 数量 | 用途 | 加载方式 |
|---|---:|---|---|
| `data/dashboard-data.js` | 99 KB；生成时间 2026-07-12 01:16:57 | 工作台统计、section、top signals、工作流 | 首页同步加载 |
| `data/literature-recent.js` | 4.8 MB；1,151 篇 | 情报中心主文献数据 | 情报中心同步加载 |
| `data/signals-weekly.js` | 146 KB；8 条父级 Signal / 20 条 talking point / 26 个 PMID | Signal → Talking Points → Evidence | 同步加载 |
| `data/china-intelligence.js` | 127 KB；120 条中国情报摘要 | 中国情报 tab | 按需加载 |
| `data/literature-full-index.js` | 5.4 MB；10,635 篇轻索引 | 知识库跨库检索 | 懒加载 |
| `data/knowledge-graph.js` | 6.8 MB；55 节点 / 334 核心边 / 180 矩阵行 | 知识库图谱与证据矩阵 | 知识库同步加载 |
| `data/graphHealth.js` | 7 KB | 图谱健康度 | 知识库、数据状态同步加载 |
| `data/communityTaxonomy.js` | 9 KB；10 个业务社区 | 社区定义 | 多页面同步加载 |
| `data/communityCards.js` | 45 KB；10 张社区卡片 | 社区摘要、代表证据 | 首页、知识库同步加载 |
| `data/communityWeekly.js` | 23 KB；10 个社区周更 | 社区动态 | 首页、知识库同步加载 |
| `data/communityAssignmentIndex.js` | 7 KB；10 个业务社区 + unassigned 分片索引 | 社区归类入口 | 同步加载 |
| `data/communityAssignments-*.js` | 分片 | 某一社区 PMID 明细 | 懒加载 |
| `data/communityAssignmentsRecent.js` | 505 KB；1,155 条近一年归类 | 近一年社区过滤 | 按需加载 |
| `data/communityAudit.js` | 28 KB | 社区 assignment 质量摘要 | 知识库、数据状态同步加载 |
| `data/expert-profiles.js` | 2.4 KB manifest | 专家画像入口、分片路径 | MSL 同步加载 |
| `data/expert-profiles-china.js` | 5.2 MB；8,926 位 | 中国作者-机构索引 | MSL 同步加载 |
| `data/expert-profiles-international.js` | 24 MB；43,485 位 | 国外作者-机构索引 | MSL 按需加载 |
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

社区层是当前网站的核心语义层。它把 10,635 篇 full corpus 文献映射到医学事务可行动主题，用于工作台、知识库、情报中心筛选和后续 MSL action。

### 4.1 社区结构

当前有 **10 个业务社区**，另有 `unassigned` 作为低置信度/未归类桶，不属于 taxonomy 展示社区。

| ID | 名称 | 文献数 | 高等级证据 | 中国相关 |
|---|---|---:|---:|---:|
| `clinicalSubtypesStratification` | 临床亚型与人群分层 | 2,055 | 58 | 323 |
| `safetyMedicationManagement` | 安全性与用药管理 | 1,647 | 121 | 267 |
| `diagnosisMonitoringPrediction` | 诊断、监测与预测 | 1,150 | 26 | 169 |
| `mechanismTranslationalMedicine` | 机制与转化医学 | 1,064 | 13 | 424 |
| `rweClinicalPathway` | 真实世界证据与临床路径 | 723 | 25 | 158 |
| `efficacyBurdenOutcomes` | 疗效终点与疾病负担 | 553 | 69 | 127 |
| `complementAndNovelTargets` | 补体与其他新靶点 | 290 | 19 | 31 |
| `fcrnTargetedTherapy` | FcRn 靶向治疗 | 248 | 37 | 76 |
| `guidelineHeorAccess` | 指南、共识与卫生经济 | 109 | 4 | 17 |
| `competitiveLandscapeIndirectComparison` | 竞争格局与间接比较 | 51 | 18 | 14 |
| `unassigned` | 未归类桶（非展示社区） | 2,745 | — | — |

### 4.2 质量状态

`communityAudit.js` 当前摘要：

| 指标 | 数量 |
|---|---:|
| total_articles | 10,635 |
| assigned_articles | 7,890 |
| unassigned_articles | 2,745 |
| low_confidence_articles | 1,120 |
| conflict_articles | 1,481 |
| recent_unassigned_articles | 3 |

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
| 核心展示边 | 334 |
| 全量合格边 | 1,261 |
| 证据矩阵行 | 180 |
| abstract-level 命中文献 | 9,162 |

图谱关系来自 title / abstract / metadata 层面的证据线索，不代表全文级因果关系。页面中已保留 PMID 回链。

### 5.2 Graph Health

`graphHealth.js` 当前状态为 `needsReview`：

- 55 个节点均已映射到社区
- 334 条展示边均有社区映射
- oversized_nodes = 6
- weak_edges = 92
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
- 当前公开产物为 8 条父级 Signal、20 条 talking point、26 个唯一 PMID，`published_reference_coverage = 1.0`；该数量随近 14 天 PubMed 窗口变化，不应硬编码到前端逻辑。
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
| `expert-profiles-china.js` | 8,926 位 | MSL 页面同步加载，默认中国视图 |
| `expert-profiles-international.js` | 43,485 位 | 用户切换到国外/全部或搜索时按需加载 |

总计 52,411 位作者-机构画像。检索字段包括姓名、拼音/英文名、机构、国家/地区、研究方向、发文量和近期活跃度。

### 8.2 拜访助手

当前已实现：

- 选择专家
- 选择 6 个内容模块中的学术/产品信息
- 读取近期信号与本月诊治格局 action
- 在页面内生成“拜访话题建议”和对应 PMID 文献清单

当前未实现：

- 拜访记录持久化
- follow-up 闭环
- 一键导出/下载简报
- 团队协作或权限控制

这些能力需要后续引入本地存储方案或轻量后端后再建设。

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
3. python3 scripts/run-weekly-pipeline.py --skip-status --skip-downstream
4. python3 scripts/reclassify-existing-iii.py --modes ALL --recent-days 365
5. python3 scripts/buildFullLiteratureIndex.py
6. python3 scripts/buildCommunityData.py
7. python3 scripts/build-knowledge-data.py
8. python3 scripts/build-curated-topic-data.py
9. python3 scripts/buildWikiTopicCoverage.py
10. python3 scripts/generate-weekly-summary.py
11. python3 scripts/generate-pipeline-status.py
12. 执行 full/recent 同步校验
13. 非 dry-run 时 git add → commit → push
```

### 9.3 `run-weekly-pipeline.py` 内部 15 步

```
1. fetch-pubmed-weekly.py
2. enrich-weekly-literature.py
3. merge-weekly-literature.py
4. build-frontend-data.py
5. enrich-literature-narrative.py（可选；失败回退确定性聚合）
6. buildFullLiteratureIndex.py
7. buildCommunityData.py
8. build-knowledge-data.py
9. buildChinaAuthorNetwork.py
10. build-curated-topic-data.py
11. buildWikiTopicCoverage.py
12. buildLandscapeInsights.py
13. buildBackendOptions.py
14. generate-weekly-summary.py
15. generate-pipeline-status.py
```

### 9.4 GitHub Actions 兜底

Workflow：`.github/workflows/weekly-pipeline.yml`

- 触发：手动 `workflow_dispatch` + 每周日 23:00 Asia/Shanghai
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
- 大文件使用分片或懒加载：full index、国际专家、community assignment shards。
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
python3 -m py_compile scripts/*.py
node --check assets/*.js
```

---

## 11. 当前已知问题

| 优先级 | 问题 | 当前影响 | 建议处理 |
|---|---|---|---|
| P0 | 公开统计口径与 full 语义底座口径并存：Dashboard / `MG_TOTAL_COUNT` 为 1,165，而 full/index/community 为 10,635 | 用户可能误以为“全库”只有 1,165 篇；本地 sync 校验也可能因 full/recent 口径变化失败 | 明确定义 public rolling count 与 semantic full count；同步修改展示文案与校验逻辑 |
| P1 | `pipeline-status.js` 生成时间早于部分 2026-07-02 数据产物，且 expert split 后状态页仍把 manifest + shards 当成单文件 | 数据状态页个别 expert/size 信息不完全可信 | 让 `generate-pipeline-status.py` 识别 expert shards，并在所有前端产物重建后最后运行 |
| P1 | 证据矩阵仍是 abstract-level 自动关系，可能混入跨疾病或弱相关 PMID | MSL 使用时需回到 PMID 原文核对 | 增加跨疾病排除规则和人工抽样 review |
| P2 | MSL 拜访助手尚无持久化、导出和 follow-up 闭环 | 目前只能页面内生成建议，不能形成团队工作流 | 后续再设计本地存储或轻量后端 |
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

---

## 14. 后续建设方向

1. 统一 public rolling count 与 semantic full count 的展示和校验逻辑。
2. 修复 pipeline-status 对 expert shards、community shards、生成时间的识别。
3. 把 MSL 拜访助手从页面生成器升级为可保存、可导出、可 follow-up 的工作流。
4. 补齐 AANEM 结构化会议数据。
5. 在真正需要多人协作、权限和持久记录时，再评估轻量后端。
