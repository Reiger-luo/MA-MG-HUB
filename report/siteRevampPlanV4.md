# MG Intelligence Hub 网站规划改造方案 v4.0

生成日期：2026-06-29  
项目：MA-MG-HUB / MG Intelligence Hub  
定位：从静态文献工作站升级为全 MG 知识库、医学事务图谱与动态洞察系统  
状态：开工前规划草案

---

## 0. Codex 想法记录

这部分先把当前判断记下来，作为 v4.0 的设计底线。

1. GitHub Pages 适合做展示层和交互层，不适合做实时 LLM、实时向量检索、密钥保存和长时间计算。
2. 当前网站可以承载大部分目标功能，但计算应放在本地工作站、Hermes 或 GitHub Actions；网站只读取已经生成的公开数据产物。
3. 当前知识库图谱不是 embeddings / 向量知识库，而是基于 `conceptDefs`、标题、摘要和元数据共现生成的静态 abstract-level 图谱。
4. 当前图谱每周变化小是正常现象，因为节点和关系框架稳定，周更主要增加 PMID、证据计数和局部边权。
5. 真正需要升级的不是把图谱画得更复杂，而是在图谱之上增加“医学事务语义层”，让系统回答“哪些临床/医学事务问题正在变化”。
6. `efgartigimod-wiki` 不应成为全 MG 网站知识库的 source of truth；它应该作为方法来源、策展样板、专题子集和质量评估基准。
7. 动态诊治格局不应继续依赖固定 5 类模板；它应读取社区变化、图谱变化、监管/管线变化和新增证据，由 LLM 生成可溯源的 3-7 条月度洞察。
8. 所有自动结论必须保留 PMID、证据等级、知识节点、社区归属、置信度和 abstract 局限，避免把摘要级线索包装成全文级医学结论。

---

## 1. 用户目的校准

本次 v4.0 的核心目标不是“给现有站点增加一个社区分类功能”，而是重新明确网站的知识库建设路线：

1. 搭建全 MG 知识库和全 MG 学术图谱，而不是围绕单一产品扩展页面。
2. `efgartigimod-wiki` 只是全 MG 知识体系中的一个策展子集。
3. 从 `efgartigimod-wiki` 迁移的是知识库搭建方法，包括社区发现、GraphRAG 摘要、self-audit、分层策展、内部链接图谱和人工策展机制。
4. 同时优化全 MG 图谱和 efgar 子图谱：全 MG 图谱提供广度和底座，efgar 子图谱提供深度和策展质量样板。
5. 网站最终服务医学事务工作流：情报发现、知识检索、诊治格局判断、MSL 准备、内容生成和后续行动。

---

## 2. v4.0 北极星

MG Intelligence Hub v4.0 应从“文献聚合 + 静态图谱”升级为：

> 以 PubMed 全库为原料，以可溯源图谱为底座，以医学事务社区为语义层，以策展内容和动态洞察为应用层的 MG 学术情报工作站。

它需要回答五类问题：

1. 我们掌握了哪些 MG 证据、关系、主题和缺口？
2. 本周或本月哪些医学事务社区正在发生变化？
3. 这些变化影响哪个治疗位置、竞争叙事、中国实践或 MSL 行动？
4. 哪些主题已经被本地 wiki 或人工策展消化，哪些仍只是 abstract-level 弱信号？
5. 每个结论背后有哪些 PMID、证据等级、图谱节点和局限？

---

## 3. 当前基线与关键不足

### 3.1 当前已经具备的能力

| 模块 | 当前能力 |
|---|---|
| PubMed 管线 | 抓取、证据等级、IF/CAS、full/recent 派生 |
| 情报中心 | 近一年文献、候选信号、中国情报 |
| 知识库 | abstract-level 图谱、证据矩阵、专题入口、跨库检索 |
| 诊治格局 | 固定框架的本月格局变化、竞争矩阵、管线矩阵、Living Answers |
| MSL 工作台 | 专家画像、内容模块、拜访准备雏形 |
| 数据状态 | 管线状态、产物状态、存储模式透明化 |

### 3.2 当前不足

| 不足 | 影响 |
|---|---|
| 图谱依赖固定 concept dictionary | 难以发现词典外的新兴主题 |
| 无 embeddings / 向量语义层 | 搜索和聚类仍偏关键词 |
| 图谱和诊治格局之间缺少动态解释层 | 总览容易稳定但不够“本月化” |
| `efgartigimod-wiki` 方法尚未系统迁移 | 本地深度知识和网站全库之间没有充分桥接 |
| 大文件前端加载压力上升 | 后续新增数据层前必须拆分和懒加载 |
| GitHub Pages 无实时安全 LLM 能力 | 需要坚持“后台生成，前台展示” |

---

## 4. 架构决策

### 4.1 GitHub Pages 只做公开展示层

GitHub Pages 继续承担：

- 页面展示
- 已生成数据产物加载
- 筛选、排序、跳转、局部图谱交互
- provenance 展示

不承担：

- 实时 LLM
- 实时向量数据库
- API key 保存
- 私有拜访记录
- 长时间批处理

### 4.2 本地 full 是完整分析底座

`data/literature-full.json` 继续留在本地工作站，不推 GitHub。完整分析以本地 full 为准，公开站只部署派生产物。

GitHub Actions 继续作为轻量兜底：

- 抓取公开增量
- 生成 recent fallback
- 提交公开产物
- 触发 Pages

但 GitHub Actions 不承担 full 级别重分析。

### 4.3 全 MG PubMed 库是 source of truth

全 MG 知识库的 source of truth 是：

- PubMed full corpus
- PMID 元数据
- 证据等级
- IF / quartile
- ClinicalTrials 数据
- 中国监管状态
- 未来可接入的指南、共识、说明书和医保信息

`efgartigimod-wiki` 是策展层和方法样板，不替代全 MG corpus。

### 4.4 图谱层和社区层必须分离

图谱层回答：

- 哪些概念、药物、人群、结局和证据在 abstract 中有关联？
- 哪些 PMID 支撑这些关系？

社区层回答：

- 这些关系共同形成了哪些医学事务问题？
- 哪些社区正在升温、冲突、过大、陈旧或出现新兴信号？

图谱是底座，社区是解释层。社区不是简单把图谱 cluster 染色。

### 4.5 LLM 和 embeddings 作为后台生成工具

LLM 和 embeddings 的职责：

- 生成候选社区
- 设计 taxonomy
- 仲裁低置信度和冲突归类
- 生成社区摘要
- 生成动态诊治格局洞察

前台只展示结果，不直接暴露模型调用。

---

## 5. v4.0 分层知识架构

```text
数据源层
  PubMed full / weekly / ClinicalTrials / regulatory / guideline / local wiki
        ↓
原始证据层
  PMID / title / abstract / metadata / evidence level / IF / China flag
        ↓
抽取与图谱层
  entity / concept / study type / graph node / graph edge / evidence matrix
        ↓
语义社区层
  candidate community / medical affairs taxonomy / assignment / facet / audit
        ↓
策展与摘要层
  community card / wiki topic coverage / GraphRAG summary / Living Answer
        ↓
应用层
  Dashboard / Intelligence / Knowledge / Landscape / MSL / Materials / Data Ops
```

### 5.1 原始证据层

保留当前 full/recent 机制，但新增 corpus pack：

| 产物 | 用途 | 是否推前端 |
|---|---|---|
| `data/literature-full.json` | 本地完整分析底座 | 否 |
| `data/literature-recent.js` | 公开站近一年文献 | 是 |
| `data/literature-full-index.js` | 全库轻索引，供知识库检索按需加载，不含 abstract | 是 |
| `data/communityCorpusPack.jsonl` | 社区发现和 LLM 输入包 | 否 |
| `data/articleConceptTags.jsonl` | 每篇文献的概念、实体、facet 标签 | 可聚合后推 |

### 5.2 抽取与图谱层

现有 `knowledge-graph.js` 保留，但逐步升级：

- 从单纯 concept dictionary 共现，升级为 dictionary + entity normalization + evidence type + study type + LLM-assisted relation。
- 边的 `source_type` 明确区分：
  - `metadataConfirmed`
  - `abstractMentioned`
  - `coOccurrence`
  - `llmInferred`
  - `curated`
- 每条边必须保留 PMID 回链。
- 关系强度不只看文章数，还要看证据等级、新近性、中国相关性和是否被策展层确认。

### 5.3 语义社区层

社区层是 v4.0 的核心新增层。

三类对象：

| 类型 | 作用 | 前台展示 |
|---|---|---|
| 算法候选社区 | 从 abstract、concept、metadata、embedding、Leiden 中发现自然聚类 | 不直接展示 |
| 医学事务社区 | 面向临床问题、证据沟通和 MSL 场景的稳定分类体系 | 主要展示 |
| 新兴社区候选 | 近期增长但未进入稳定 taxonomy 的主题 | 在信号板和数据状态提示 |

社区层字段建议：

```json
{
  "communityId": "fcrnTargetedTherapy",
  "title": "FcRn 靶向治疗",
  "level": "primary",
  "definition": "围绕 FcRn 抑制剂疗效、安全性、用药路径和机制解释的医学事务社区。",
  "boundary": "不包含纯基础免疫学且未连接 MG 治疗问题的文献。",
  "primaryPmids": ["..."],
  "representativeNodes": ["efgartigimod", "fcrnInhibition", "generalizedMg"],
  "facets": ["drug", "mechanism", "rwe", "china"],
  "mslUseCases": ["治疗定位", "机制沟通", "竞品问答"],
  "auditFlags": ["needsBoundaryReview"]
}
```

### 5.4 策展与摘要层

这一层迁移 `efgartigimod-wiki` 的成功方法，但不搬全部内容结构。

迁移机制：

- Leiden / 图谱社区发现
- GraphRAG 社区摘要
- self-audit state
- 分层标签体系
- 内部链接图谱
- 人工策展 + 算法辅助
- 版本化元数据

在网站中对应为：

- `communityCards.js`
- `communityWeekly.js`
- `communityAudit.js`
- `wikiTopicCoverage.js`
- `livingAnswers.js`
- `landscapeInsights.js`

---

## 6. 全 MG 图谱与 efgar 子图谱的关系

### 6.1 全 MG 图谱

全 MG 图谱负责广度：

- 疾病亚型
- 药物和机制
- 人群
- 结局指标
- 研究类型
- 证据等级
- 中国相关证据
- 真实世界和指南共识
- 临床管线和监管状态

它的目标是成为全站知识底座。

### 6.2 efgar 子图谱

efgar 子图谱负责深度：

- 作为全 MG 图谱中的产品/机制子图
- 显示 efgartigimod 相关证据链、RWE、真实世界路径、安全性、竞品比较和 steroid-sparing 等策展主题
- 作为 GraphRAG、社区摘要、self-audit 和策展质量的 benchmark

efgar 子图谱不应单独平行于全 MG 图谱，而应从全 MG 图谱中切出：

```text
full MG graph
  └── efgartigimod subgraph
        ├── PubMed evidence
        ├── curated wiki topics
        ├── community coverage
        ├── MSL use cases
        └── gaps / conflicts / update needs
```

### 6.3 wiki 的角色

`efgartigimod-wiki` 在 v4.0 中有三个角色：

1. 方法来源：迁移社区发现、摘要、audit 和策展机制。
2. 策展子集：提供高质量专题、claims 和 MSL 使用场景。
3. 覆盖率基准：判断全 MG PubMed 社区中哪些主题已被人工策展，哪些仍是缺口。

---

## 7. 新数据产物规划

新文件采用英文 camelCase 命名。

### 7.1 本地中间产物

| 文件 | 作用 |
|---|---|
| `data/communityCorpusPack.jsonl` | 每篇 PMID 的压缩输入包 |
| `data/communityCandidates.json` | 算法候选社区 |
| `data/communityReviewQueue.json` | 低置信度、冲突、新兴主题待审队列 |
| `data/communityAssignments.jsonl` | full 级别 PMID 归类明细 |
| `data/embeddingIndex.local.json` | 本地 embedding 索引或索引元数据 |

这些文件默认不推 GitHub。

### 7.2 前端公开产物

| 文件 | 页面用途 |
|---|---|
| `data/communityTaxonomy.js` | 社区定义、边界、层级、facet |
| `data/communityAssignmentIndex.js` | 社区归类轻量索引、recent assignments 和分片清单 |
| `data/communityAssignmentsRecent.js` | 近一年社区归类明细，情报中心按需加载 |
| `data/communityAssignments-*.js` | 按社区拆分的全量归类分片，必须懒加载 |
| `data/communityCards.js` | 社区摘要、代表证据、MSL use case |
| `data/communityWeekly.js` | 本周新增、升温、强信号、社区 drift |
| `data/communityAudit.js` | audit 摘要，供数据状态页展示 |
| `data/wikiTopicCoverage.js` | wiki 专题与 PubMed 社区覆盖关系 |
| `data/landscapeInsights.js` | 动态诊治格局洞察，可合并进 `landscape-data.js` |
| `data/graphHealth.js` | 图谱健康度、过大节点、弱边、陈旧关系 |
| `data/literature-full-index.js` | 全库 PMID 轻索引，知识库跨库检索首次输入时懒加载 |

---

## 8. 动态诊治格局 v4.0

当前诊治格局的“本月格局变化”是固定 5 类框架。v4.0 改为动态生成。

### 8.1 输入

- 本月或近 45 天新增 PMID
- `communityWeekly.js`
- `knowledge-graph.js`
- `communityCards.js`
- `curated-topics.js`
- 中国监管状态
- ClinicalTrials 管线
- 竞争矩阵

### 8.2 生成逻辑

1. 从社区层识别升温、冲突、高证据冲击和新兴主题。
2. 从图谱层识别新增强边、新增高等级 PMID 和被策展主题影响的节点。
3. 从监管/管线层识别治疗选择或竞争态势变化。
4. 用 LLM 生成 3-7 条月度洞察。
5. 用脚本校验 PMID、节点、社区、证据等级和置信度。
6. 若 LLM 失败，回退到当前固定框架。

### 8.3 输出结构

```json
{
  "id": "fcrnResponseHeterogeneity202606",
  "title": "FcRn 疗效异质性正在从经验观察走向机制解释",
  "changeType": "机制与疗效",
  "selectionReason": "本月新增抗体功能和反应预测相关研究，并强化既有 FcRn 社区证据链。",
  "whatIsNew": "新增证据从 RWE 疗效观察转向 response mechanism。",
  "communityIds": ["fcrnTargetedTherapy", "diagnosisMonitoringPrediction"],
  "knowledgeNodes": ["fcrnInhibition", "efgartigimod", "achrPositive"],
  "treatmentPosition": "AChR+ gMG、疗效预测、专家深访",
  "competitiveNarrative": "机制沟通、精准用药、FcRn 内部差异化",
  "mslAction": "准备抗体功能、response biomarker 和 efgartigimod 机制相关 PMID。",
  "references": ["42242900", "42308456"],
  "confidence": "medium",
  "limitations": "基于 abstract 和元数据；不替代阅读全文。"
}
```

---

## 9. 页面改造方案

### 9.1 Dashboard

从静态概览升级为“本周行动入口”：

- 本周升温社区
- 高证据冲击
- 低置信度待审
- 中国证据变化
- 本月格局变化入口
- MSL 待准备材料入口

### 9.2 情报中心

从文献列表升级为“文献 + 社区信号”：

- 文献卡显示 primary community
- 增加 community filter
- 信号板从单篇排序升级为社区聚合
- 中国情报改为 geo facet 叠加，而不是孤立页面逻辑

#### 9.2.1 会议资讯：会后 MG 摘要情报分析

会议资讯仍然放在情报中心内，名称保持“会议资讯”。它不是参会指南，不回答“去哪里开会、怎么参会、日程怎么安排”，而是在会议摘要公开后回答医学事务问题：

1. 这次会议中 MG 领域发生了什么变化？
2. 哪些摘要改变了治疗、诊断、患者旅程或竞争叙事的判断？
3. 哪些 late-breaking / 重点会话需要会后第一时间复盘？
4. 哪些国家、机构和 KOL 在 MG 领域更活跃？
5. 哪些内容可以进入 MSL briefing、KOL 拜访问题、内部 slide 和后续证据追踪？

核心定位：

> 会议资讯 = 会议摘要公开后的 MG 医学事务情报复盘页。摘要是原料，结构化洞察和行动建议才是页面主体。

收录边界：

- 只收录 MG / myasthenia gravis / gMG / ocular MG / AChR MG / MuSK MG / LRP4 MG / myasthenic crisis 等 MG 相关内容。
- LEMS、CMS、先天性肌无力综合征、泛神经肌肉疾病不作为独立收录对象。
- 如果 LEMS/CMS 只是在 MG 主研究中作为背景或对照出现，可以保留该 MG 主研究，但标签和解读必须说明主语是 MG。
- 所有自动判断必须保留摘要来源、会议来源、presentation type 和官网链接，不把摘要级信息包装成全文级结论。

##### 9.2.1.1 信息架构

会议资讯采用“总览页 + 单会议工作区”的结构，但仍在同一个情报中心 tab 内完成，不额外变成参会型 microsite。

总览层：

| 区块 | 目的 | 当前可复用内容 |
|---|---|---|
| 四会议固定模块 | 固定展示 MGFA、AANEM、AAN、EAN 的收录状态和摘要量 | `conferenceMeetingCards` |
| 会后信号摘要 | 用 5-8 条信号概括本轮会议中 MG 领域变化 | `conferenceHighlights` 可升级 |
| Late-breaking / 重点会话 | 会议后优先复盘 late-breaking、late abstract 和高影响 oral | `conferenceLateBreakers`、AAN LS1/LS2 |
| 源状态 / 待扫描 | 告诉用户哪些摘要源已抓取、哪些仍待补扫 | `conferenceSourceMonitor` |
| 未来会议小窗 | 只作为摘要源预监控，不做参会指南 | `conferenceFutureMeetings` |

单会议工作区：

| 区块 | 应展示的问题 | 设计口径 |
|---|---|---|
| 会后速读 | 本会议 MG 内容一句话结论、摘要数、主导主题、关键药物/机制、中国相关数量 | 首屏 brief，不做长列表 |
| 结构分析 | 国家/地区投稿排名、研究类型结构、主题与药物机制地图 | 使用图表/排行/标签，不用大段解释 |
| 医学事务洞察 | 对治疗格局、诊断分型、安全性、中国机会、患者旅程、KOL 线索的解释 | 每张卡必须有“为什么重要”和“可用于什么” |
| Late-breaking 复盘 | 是否有 MG late-breaking；若未公开，展示会话入口和待抓取状态 | 独立高优先级区，不和普通摘要混排 |
| 摘要池下钻 | 给用户核查来源，支持关键词、国家、研究类型、药物/机制、中国相关筛选 | 放在后半屏，作为证据核查区 |

##### 9.2.1.2 四个会议的差异化口径

MGFA：

- 定位：MG 疾病专题会议，会后复盘应看领域内部结构。
- 重点：治疗机制、患者旅程、PRO/生活质量、真实世界、MGFA 专题趋势、中国机构线索。
- 解读方式：更像疾病领域年度快照，不只看新药。

AAN：

- 定位：综合神经大会中的高影响 MG 信号。
- 重点：late-breaking、phase 2/3、FcRn、补体、seronegative gMG、真实世界、安全性、竞争格局。
- 解读方式：优先识别会后需要进入内部 briefing 的治疗和竞争信号。

EAN：

- 定位：欧洲多中心与 ePoster 体系中的 MG 证据池。
- 重点：国家/地区协作网络、登记研究、治疗路径、安全性、真实世界和公开摘要完整度。
- 解读方式：强调欧洲实践差异和多中心合作线索。

AANEM：

- 定位：神经肌肉临床实践会议。
- 重点：诊断、电生理、危象管理、病例/真实世界经验、神经肌肉实践相关 MG 内容。
- 解读方式：如果摘要集尚不能稳定结构化，先作为“源已定位 / 待结构化”的监控模块，不强行混入其他会议摘要。

##### 9.2.1.3 与当前上线版本的关系

当前已上线的会议资讯已经具备第一版骨架：

| 已有资产 | 当前能力 | 下一步改造 |
|---|---|---|
| `data/conference-data.json` | 458 条 MG 摘要；MGFA 2025、AAN 2026、EAN 2026 已结构化；AANEM 2025 留监控口 | 增加 per-meeting brief、会后信号、MSL action、source limitation 字段 |
| `assets/conference.js` | 四会议模块、KPI、国家/研究类型排行、主题药物、late-breaking、结构化解读、下钻筛选 | 把 `conferenceHighlights` 从摘要推荐升级为“医学事务洞察卡” |
| `pages/literature.html` | 情报中心第四个 tab，标题仍为会议资讯 | 保留 tab 与浅色工作台风格，调整信息层级：洞察在前，摘要下钻在后 |
| `conferenceSourceMonitor` | 展示 MGFA/AANEM/AAN/EAN 源状态 | 改名语义为“摘要源状态 / 待补扫”，避免像参会信息 |
| `conferenceFutureMeetings` | 展示未来会议时间地点和官网 | 压缩为右侧小窗，仅用于摘要源预监控和后台扫描提醒 |

当前数据也可直接支持第一轮会后分析：

- 总结构化摘要：458 条。
- 已结构化会议：MGFA 2025、AAN 2026、EAN 2026。
- 待结构化监控：AANEM 2025 Abstract Guide。
- 已知 AAN 2026 late-breaking 入口：LS1 / LS2。
- 已有分析维度：国家/地区、研究类型、主题、药物/机制、中国相关、高优先级。

##### 9.2.1.4 下一版前端改造方案

第一步，不推倒现有页面，只重排信息优先级：

1. 保留四张固定会议模块，继续作为会议切换入口。
2. 将当前 `conference-brief` 升级为“会后速读”，展示 3 条自动生成的会议结论。
3. 将当前 `conferenceHighlights` 改成“医学事务洞察”，每张卡包含：
   - 洞察标题
   - 对 MG 领域意味着什么
   - MSL 可用场景
   - 关联摘要数量
   - 代表摘要链接
   - 局限说明
4. 将 `conferenceLateBreakers` 固定放在结构分析之前或紧随会后速读之后，保证 late-breaking 不被摘要列表淹没。
5. 将 `conferenceResults` 明确命名为“摘要池下钻 / 来源核查”，视觉上弱于洞察区。
6. 将未来会议小窗改为“会议源预监控”，只显示摘要集状态、预计公开节点和官网链接。

第二步，补数据 schema：

```json
{
  "conferenceInsights": [
    {
      "meetingId": "aan-2026",
      "title": "FcRn 与补体仍是 AAN 2026 MG 治疗信号核心",
      "dimension": "治疗格局",
      "whyItMatters": "提示会后 briefing 应优先比较机制、适用人群和安全性叙事。",
      "mslUseCase": "用于 KOL 拜访前准备和内部 slide 选题。",
      "representativeAbstractIds": ["..."],
      "relatedDrugs": ["efgartigimod", "ravulizumab"],
      "relatedTopics": ["FcRn", "补体", "安全性"],
      "confidence": "medium",
      "limitations": "基于会议摘要；需等待全文或 presentation material 核查。"
    }
  ]
}
```

摘要级字段建议补充：

- `meetingModule`
- `sessionType`
- `sessionTitle`
- `presentationDate`
- `lateBreakerSessionId`
- `medicalAffairsDimension`
- `mslUseCase`
- `sourceLimitation`
- `communityId`
- `representativeForInsight`

第三步，与现有网站语义层打通：

| 现有模块 | 会议资讯如何复用 |
|---|---|
| 文献速览 | 会议摘要转化为后续 PubMed/全文追踪清单 |
| 信号板 | 会后重要摘要可以生成“会议来源信号”，但标明不是 PubMed 证据 |
| 中国情报 | 会议中的中国机构/中国患者/中国作者作为 geo facet 进入中国线索 |
| 知识库社区 | 会议摘要按医学事务社区归类，形成会后社区热度 |
| 诊治格局 | 只有高置信度、可溯源的会议信号进入月度格局变化 |
| MSL 工作台 | 输出 KOL 问题、拜访前 briefing、slide 选题和后续文献追踪 |

##### 9.2.1.5 验收标准

会议资讯下一版验收不以“展示多少摘要”为核心，而以是否支持医学事务会后复盘为核心：

1. 用户进入会议资讯后，30 秒内能看懂本次会议 MG 领域的主要变化。
2. 每个会议都有独立分析口径，不把 MGFA、AAN、EAN、AANEM 混成一个摘要列表。
3. 国家/地区排名、研究类型结构、主题/药物机制、late-breaking、中国相关都能按会议单独查看。
4. Late-breaking / 重点会话必须有独立模块；未公开 MG 摘要时显示“会话已定位、摘要待抓取”。
5. 摘要池只作为下钻核查区，不作为页面主体。
6. AANEM 等尚未结构化的会议必须显示源状态和后续扫描口，而不是空白或混入其他会议内容。
7. 所有会后洞察必须能回链到摘要、会议源和自动判断局限。

### 9.3 知识库

知识库成为 v4.0 核心页面：

- 图谱视图：节点按 dominant community 染色
- 社区视图：展示 community cards
- 证据矩阵：支持按社区过滤
- 专题覆盖：展示 wiki 主题覆盖哪些社区
- 图谱健康：显示弱边、过大节点、陈旧社区、未归类文献

### 9.4 诊治格局

诊治格局从固定框架升级为动态解释层：

- 首屏展示动态月度洞察
- 每条洞察关联社区、知识节点、PMID 和 MSL action
- 竞争矩阵继续保留，但作为背景，不作为首屏主体
- 中外差异只在指南、说明书、准入和全文证据接入后形成正式结论

### 9.5 MSL 工作台

MSL 工作台读取社区状态：

- 专家画像显示专家活跃社区
- 拜访前简报按社区组装
- objection handling 关联社区证据链
- follow-up 任务按社区缺口生成

### 9.6 数据状态

数据状态新增知识库健康面板：

- 社区数
- 未归类 PMID
- 低置信度归类
- 冲突归类
- 新兴主题候选
- wiki 覆盖缺口
- 图谱弱边 / 过大节点 / 陈旧社区

---

## 10. 周更管线 v4.0

推荐顺序：

```text
1. PubMed weekly fetch
2. weekly enrichment：证据等级、IF/CAS、China flag
3. merge full / derive recent
4. reclassify full 中的近一年窗口
5. split recent / frontend base data build
6. full literature index rebuild
7. community assignment / weekly diff / audit
8. knowledge graph rebuild from full
9. wiki topic coverage update
10. dynamic landscape generation
11. weekly summary and pipeline status
12. commit public artifacts
```

模型调用策略：

- 常规周更不让高级模型读全库。
- 高级模型只处理 taxonomy 版本、低置信度、冲突、新兴主题和关键洞察。
- 普通模型处理批量归类和模板化社区摘要。
- embedding 和 Leiden 在本地批处理，结果以静态文件发布。

---

## 11. 可行性评估

| 能力 | 纯 GitHub Pages | 本地工作站 / Hermes | GitHub Actions |
|---|---|---|---|
| 文献展示和筛选 | 可行 | 生成数据 | 轻量生成 |
| 全 MG 图谱展示 | 可行 | 完整生成 | 无 full 时兜底 |
| 社区卡片展示 | 可行 | 完整生成 | 可提交产物 |
| embedding 聚类 | 不建议前端跑 | 推荐 | 可小规模兜底 |
| 实时语义搜索 | 不适合 | 可本地服务 | 需外部后端 |
| LLM 动态洞察 | 不在前端跑 | 推荐 | 可用 secrets 做轻量 |
| 私有拜访数据 | 不适合公开站 | 推荐 | 不推荐 |

结论：

1. v4.0 的主体功能可以在当前 GitHub 网站架构上实现。
2. 关键是坚持“后台智能生成，前台静态展示”。
3. 如果未来需要实时问答、实时语义搜索、多人协作或私有记录，再引入轻量后端。

---

## 12. 风险与护栏

| 风险 | 护栏 |
|---|---|
| LLM 生成无 PMID 结论 | schema 强制 PMID，脚本校验 |
| abstract 线索被误包装为医学结论 | 每条卡保留 limitation 和 evidence level |
| 社区 taxonomy 漂移 | 版本化 taxonomy、audit、人工确认 |
| China 被误设为平行社区 | China 默认作为 geo facet |
| efgar-wiki 过度主导全 MG | wiki 只作策展层和 benchmark |
| 前端数据文件过大 | 拆分数据、按需加载、分页索引 |
| 图谱越来越复杂但不可用 | 强制局部视图、社区视图、证据矩阵联动 |
| GitHub Actions 无 full 导致口径不一致 | 状态页明确 storage mode，本地 full 为完整口径 |

---

## 13. 实施路线

### Phase 0：规划确认和口径锁定

交付：

- 确认 v4.0 架构
- 明确 full MG 为 source of truth
- 明确 efgar-wiki 只迁移方法和策展子集
- 确认新文件命名和是否推前端

验收标准：

- 形成一页架构图和数据产物清单
- 不开始页面改造，先开后台数据层

### Phase 1：社区语义层后台数据

交付：

- `communityCorpusPack.jsonl`
- `communityCandidates.json`
- 初版 `communityTaxonomy.js`
- 初版 `communityAssignments.jsonl`
- 初版 `communityAssignmentIndex.js` 和 `communityAssignments-*.js` 分片
- `communityAudit.js`

验收标准：

- 每篇文献可归入 primary community 或进入 unassigned queue
- 每个社区有定义、边界、代表 PMID 和 audit flags
- China 作为 facet 生效

### Phase 2：全 MG 图谱升级

交付：

- enrich 后的 `knowledge-graph.js`
- 图谱节点 dominant community
- 关系 source_type 更细
- 图谱健康指标
- efgar subgraph view 的数据准备

验收标准：

- 图谱可按社区染色
- 每条关系仍能回链 PMID
- efgar 主题能作为全 MG 图谱子图被切出

### Phase 3：前台轻量接入

交付：

- Dashboard 社区动态
- 情报中心 community filter
- 知识库社区视图
- 数据状态 community audit 摘要

验收标准：

- 用户能从社区进入文献、图谱、证据矩阵和专题
- 页面性能不因新增数据明显下降

### Phase 4：动态诊治格局

交付：

- `landscapeInsights.js` 或新版 `landscape-data.js`
- 动态 3-7 条月度洞察
- 洞察关联社区、PMID、知识节点、置信度和 MSL action
- 失败时回退固定规则

验收标准：

- 不再固定展示 5 个角度
- 每条洞察能说明“为什么被选中”和“相比既有知识新在哪里”

### Phase 5：MSL 与内容工坊深化

交付：

- 专家活跃社区
- 拜访前简报按社区组装
- 内容模块按社区和证据强度映射
- objection handling 关联社区证据链

验收标准：

- 社区状态能转化为 MSL 可执行动作
- 内容产物保留 PMID 和限制说明

### Phase 6：后端选项评估

仅当出现以下需求时启动：

- 实时 LLM 问答
- 实时语义搜索
- 用户私有笔记
- 多人协作
- 权限管理

可选技术：

- Cloudflare Worker
- Vercel Function
- Supabase Edge Function
- 本地 Hermes API

---

## 14. 开干建议

不要先改前台页面。第一步应该开后台数据层：

1. 从 `literature-full.json` 生成 `communityCorpusPack.jsonl`。
2. 基于 concept co-occurrence + metadata 生成第一版 `communityCandidates.json`。
3. 用 v2 建议中的 8-10 个顶层社区作为 seed taxonomy，但不写死，交给候选社区和人工 review 校正。
4. 生成 `communityTaxonomy.js`、`communityCards.js`、`communityWeekly.js`、`communityAudit.js` 的最小可用版本。
5. 生成轻量 `communityAssignmentIndex.js`、按需 `communityAssignmentsRecent.js` 和按社区拆分的 `communityAssignments-*.js`，避免首屏加载全量归类。
6. 再把知识库页面接入社区视图。
7. 最后改诊治格局，让它读取社区变化和图谱变化生成动态洞察。

---

## 15. 执行角色分工与修订建议

这一节是对 v4.0 的收敛修订：v4.0 方向可行且必要，但第一版实现必须降低复杂度，避免同时引入多模型、多后端、多页面大改。

### 15.1 是否必要

必要。原因有三点：

1. 当前图谱是稳定底座，但缺少语义解释层，无法自然回答“本周哪些医学事务问题在变化”。
2. 当前诊治格局仍偏固定模板，不能充分利用 full MG 知识库、wiki 策展和社区变化。
3. `efgartigimod-wiki` 已经验证了社区发现、摘要、audit 和策展机制；把这些方法迁移到全 MG 是下一阶段的核心价值。

### 15.2 是否可行

可行，但不应一口气做成实时智能后端。推荐先做“离线智能 + 静态发布”：

```text
Codex 开发脚本和页面
        ↓
本地 / Hermes 定时运行后台管线
        ↓
生成公开 JS 数据产物
        ↓
GitHub Pages 展示结果
```

第一阶段不做网页实时 LLM、不做实时向量检索、不做登录和私有数据。

### 15.3 多模型协作的收敛版本

不要一开始设计成很多模型协作。先收敛为三层：

| 层级 | 工具 | 任务 |
|---|---|---|
| 规则和统计层 | Python 脚本 | concept tags、co-occurrence、evidence score、weekly diff、audit |
| 轻量模型层 | 普通 LLM 或可替代规则 | 批量归类、社区卡片草稿、低风险摘要 |
| 高级模型层 | DeepSeek Pro / 强推理模型 / 人工 | taxonomy 设计、边界仲裁、低置信度 review、关键诊治格局洞察 |

实施原则：

- 能用规则解决的，不交给 LLM。
- 能批量低风险处理的，不用高级模型。
- 高级模型只处理“结构决策”和“高风险解释”。
- 每次模型输出都必须有 JSON schema、PMID 校验和 fallback。

### 15.4 Codex 与 Hermes 分工

| 工作 | Codex | Hermes |
|---|---|---|
| 架构方案落成文档 | 主责 | 参与校准 |
| 脚本开发 | 主责 | 运行和调度 |
| 前端页面改造 | 主责 | 验收反馈 |
| 数据 schema 设计 | 主责 | 参与规则确认 |
| 周更定时任务 | 支持 | 主责 |
| 长期监控和提醒 | 支持 | 主责 |
| full 本地数据维护 | 支持 | 主责 |
| 多轮策略记忆和项目节奏 | 支持 | 主责 |
| 单次代码实现和验证 | 主责 | 不主责 |

结论：

- Codex 能搞定复杂开发，不需要把任务拆成过度简单的小票。
- Hermes 更适合做长期管理者：定时、监控、记忆、运行管线、汇总状态。
- 最佳协作方式是：在 Hermes 里定方向和节奏，在 Codex 里完成具体工程实现；重大方案可以继续在 Codex 中沉淀为 repo 文档。

### 15.5 讨论应该放在哪里

建议采用双轨：

1. **架构和阶段性决策**：可以继续在 Codex 讨论，前提是讨论结果要沉淀到 `report/` 文档，避免只留在聊天里。
2. **长期节奏和每周运营**：交给 Hermes 管理，包括何时跑管线、何时 review audit、何时提醒你确认 taxonomy。
3. **具体开发任务**：交给 Codex，并且可以是完整任务，例如“实现 Phase 1 社区数据层”，不必只给很小的开发任务。

### 15.6 建议对 v4.0 的执行修改

原 v4.0 愿景保持，但落地顺序修改为：

1. 先不做 embeddings，先做 concept co-occurrence + evidence metadata 的社区候选基线。
2. 先不做多模型自动协作，先做一个可审计的 LLM taxonomy 生成脚本。
3. 先不改所有页面，只新增社区数据产物和数据状态 audit。
4. 再接入知识库社区视图。
5. 再接入情报中心和 Dashboard。
6. 最后改造诊治格局动态洞察。
7. 等静态智能层跑通后，再评估 embeddings、Leiden、实时语义搜索和轻后端。

---

## 16. 一句话版本

v4.0 的核心不是“多做一个社区页面”，而是把 `efgartigimod-wiki` 已经证明有效的知识构建方法，迁移成全 MG 网站的语义中间层：全 MG PubMed 库提供原料，图谱提供可溯源关系，社区层提供医学事务解释，wiki 提供策展样板和覆盖校验，诊治格局和 MSL 工作台负责把这些知识转成行动。
