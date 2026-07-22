# MA-MG-HUB 医学事务决策情报升级实施计划

> **For Hermes:** 实施时按“讨论 → 决定 → 构建 → 验收 → 下一模块”串行推进；每个模块先加载 `software-development:mg-hub-website`、`software-development:test-driven-development` 和 `software-development:requesting-code-review`。复杂前端实现满足 Codex 强制条件时交由 Codex CLI，Machine 负责架构、数据合约、医学逻辑、Git 和验收。

**Goal:** 在不引入 CRM、拜访记录、互动历史、私有后端或浏览器持久化的前提下，把 MA-MG-HUB 从“公开证据浏览站”升级为“围绕 EFG 学术推广策略、可追溯的医学问题导航、判断建议和拜访前准备来源”。本计划只处理纯学术与医学策略，不覆盖政务、支付、市场准入或 Health Economics and Outcomes Research（HEOR）。

**Architecture:** 保留 GitHub Pages + 静态 `window.MG_*` 数据架构。新增“医学策略问题 → Decision Brief → Claim–Evidence → Evidence Delta → 中国证据与临床实践 → Confidence/Review Labels”派生链。核心输入来自 PubMed、指南/共识、临床试验、会议、MG-wide 图谱、efgar-wiki 策展层、社区层和公开专家数据。监管来源继续留在情报中心，用于必要的适用人群或说明书边界核查，不作为 Decision Brief 的默认主轴或 `Why now` 触发器。确定性程序负责候选、引用、门控、变化检测和降级；LLM 只做可选的证据边界内叙事增强，输出引用必须回验。

**Tech Stack:** Python 3.11、原生 HTML/CSS/JavaScript、GitHub Pages、现有 `scripts/common/io.py` 原子写入、`PipelineRunner`、pytest、可选 `llm_client.py`。

### 已确认的 R1 设计决定（2026-07-20）

1. 原网站 6 个 Living Answers 只作为迁移输入，不再直接充当首批战略问题。
2. 首批问题必须从 MG-wide 证据框架与 efgar-wiki 医学策略问题库共同推导，围绕路径定位、治疗目标、长期管理、优先患者、学术差异化和中国证据生成。
3. Decision Brief 采用纯学术结构。中国部分聚焦患者证据、临床实践、证据迁移性和研究缺口，弱化监管，排除政务、支付、市场准入和 HEOR。
4. `Decision state` 固定为四档：明确、条件、探索、不支持结论。
5. 六大页面和顶级导航不变。R1 只改造现有 `pages/landscape.html` 的 Living Answers 区域；工作台、知识库和 MSL 工作台只消费该数据，不维护平行 Brief。

---

## 0. 当前基础与不可突破的边界

### 0.1 当前可直接复用的权威产物

| 现有产物 | 当前接口 | 本计划用途 |
|---|---|---|
| `data/literature-recent.js` | `window.MG_LITERATURE_DATA` | 严格 MG-core + Evidence I–V 文献证据；问题检索、Claim 支持、Delta 新文献 |
| `data/signals-weekly.js` | `window.MG_SIGNALS_DATA` | 近 14 天 Signal、talkingPoints、evidenceBoundary、PMID、KOL/机构公开线索 |
| `data/source-signals.js` | `window.MG_SOURCE_SIGNALS` | 文献、指南/共识、中国监管、试验注册、会议五频道统一入口 |
| `data/guideline-consensus-cache.json` | JSON `records[]` | 指南/共识来源；不赋 Oxford 等级 |
| `data/landscape-data.js` | `window.MG_LANDSCAPE_DATA` | 6 个现有 Living Answers、竞争矩阵、临床管线、中国差异框架 |
| `data/landscapeInsights.js` | `window.MG_LANDSCAPE_INSIGHTS` | 动态格局洞察、confidence、limitations、MSL action、PMID |
| `data/knowledge-graph.js` | `window.MG_KNOWLEDGE_GRAPH` | 节点、关系、evidence matrix、PMID、社区映射 |
| `data/communityTaxonomy.js` | `window.MG_COMMUNITY_TAXONOMY` | 10 个医学事务问题域和边界 |
| `data/communityCards.js` | `window.MG_COMMUNITY_CARDS` | 社区摘要、代表证据、MSL use cases |
| `data/communityWeekly.js` | `window.MG_COMMUNITY_WEEKLY` | 14 天社区增量、高等级证据、中国证据 |
| `data/curated-topics.js` | `window.MG_CURATED_TOPICS` | 已策展 Claims、PMID、confidence、impact |
| `data/wikiTopicCoverage.js` | `window.MG_WIKI_TOPIC_COVERAGE` | 专题与社区/图谱桥接及 coverage gaps |
| `data/content-modules.js` | `window.MG_CONTENT_MODULES` | 现有 6 个 MSL 内容模块、claims、references、boundary |
| `data/china-intelligence.js` | `window.MG_CHINA_DATA` | 严格 recent 的中国文献、机构、期刊和证据结构 |
| `data/china-author-network.js` | `window.MG_CHINA_AUTHOR_NETWORK` | 中国机构合作、作者、主题、药物和 PMID |
| `data/expert-profiles-china.js` | `window.MG_EXPERT_PROFILE_CHINA` | China-only 公开作者画像、机构、兴趣和时间线 |
| `data/china-regulatory-status.json` | JSON `drugs[]` | 保留为情报中心独立频道；仅在适用人群、剂量或说明书边界必须核查时被 Brief 引用 |
| `data/clinicaltrials-pipeline-cache.json` | ClinicalTrials.gov API v2 cache | 识别未来将产生的科学证据、研究设计和终点，不讨论审批进度 |
| `data/chictr-trials-cache.json` | JSON `records[]` | 识别中国正在生成的科学证据与研究缺口 |
| `data/conference-data.js/json` | `window.MG_CONFERENCE_DATA` / JSON | 会议摘要、deepInsight、signal-to-kol |
| `data/pipeline-status.js` | `window.MG_PIPELINE_STATUS` | 来源和产物健康、新鲜度 |
| `data/release-manifest.js` | `window.MG_RELEASE_MANIFEST` | coherent run、产物 hash、发布时间 |

### 0.2 当前可直接复用的代码接口

- `scripts/common/mg_relevance.py::assess_mg_core()`：MG-core 门控。
- `scripts/common/source_channels.py::build_source_signals()`：五来源频道规范化。
- `scripts/common/clinical_registry.py`：ClinicalTrials.gov / ChiCTR 规范化、去重和管线矩阵。
- `scripts/common/io.py`：`load_js_global()`、`atomic_write_js_global()`、JSON/文本原子写入。
- `scripts/common/pipeline_runner.py`：step timeout、audit、resume、output hash、release manifest。
- `scripts/build-frontend-data.py::build_landscape()`：现有 Living Answers 和竞争/管线数据。
- `scripts/buildLandscapeInsights.py`：社区 + 图谱 + wiki 的动态洞察。
- `scripts/build-curated-topic-data.py::extract_claims()`：wiki Claim 初始抽取。
- `scripts/enrich-literature-narrative.py`：LLM 输出 JSON、PMID 回验、中文叙事和 fallback 模式。
- `assets/common.js`：escape、safe URL、script loading、tabs。
- `assets/landscape.js::renderAnswers()`：现有 Living Answer 展示入口。
- `assets/msl.js::generateBrief()`：现有无状态拜访前建议生成器。

### 0.3 永久边界

1. 不增加拜访记录、follow-up、互动历史、任务状态、用户画像、内部专家评级或联系方式库。
2. 不使用 `localStorage`、IndexedDB、cookie 或后端数据库保存用户选择。
3. URL 参数只表达当前公开视图；不表达内部关系、反馈或未公开标签。
4. 导出只在浏览器内瞬时生成，由用户自行下载；网站不保留导出历史。
5. PubMed 文献继续执行 MG-core + Evidence I–V 双门；指南、监管、注册、会议不冒充 Oxford 文献证据。
6. Abstract-level 推断必须明确标识，不能替代全文、说明书、指南原文或医学审核。
7. 云端缺少 full 时，不重建或覆盖 full-derived 产物。
8. Decision Brief 不讨论政务、支付、市场准入或 HEOR；监管信息不进入默认学术叙事。

---

## 1. 医学问题导航与 Decision Brief

### 1.1 改造目标

将当前 6 个基础 Living Answers 改造成 6 个影响 EFG 学术推广策略的决策问题。每张 Decision Brief 必须回答：

- EFG 应位于哪一段治疗路径
- 哪类患者最有理由优先考虑
- 应以哪条患者轨迹和终点链形成学术主张
- 首周期以后如何讨论再治疗、序贯和长期管理
- 没有 head-to-head 时，哪些差异可以防守，哪些不能比较
- 中国证据下一步应补哪一段，才能改变临床判断

原有 Living Answers 只保留为兼容输入和回归基线，不直接决定新问题目录。

### 1.2 问题来源与首批 6 个战略问题

首批问题由两层证据共同推导：

1. **MG-wide 层**：现有 PubMed 全量/rolling 文献、社区 taxonomy、知识图谱、证据矩阵和治疗格局。
2. **EFG 策展层**：`efgartigimod-wiki` 的产品、研究、比较、终点和医学策略问题库。

实施前必须读取以下权威输入：

- `efgartigimod-wiki/wiki-outputs/meta/expert-question-bank.yaml`：12 个维度、48 个专家问题，其中医学策略问题覆盖治疗路径、方案与序贯、竞争证据、信息策略和证据生成。
- `efgartigimod-wiki/concepts/myasthenia-gravis.md`：综合治疗目标、治疗路径和长期监测。
- `efgartigimod-wiki/concepts/efgartigimod-literature-landscape.md`：产品证据全景、特殊人群和研究演进。
- `efgartigimod-wiki/queries/qa-efg-vs-roza-differentiation.md`：差异化维度、可比较项和不可比较项。
- 网站现有 `curated-topics.js`、`wikiTopicCoverage.js`、`knowledge-graph.js`、`community*.js`：把 wiki 策展层连接到 MG-wide 证据。

首批固定为以下 6 个问题。它们不是 6 个平行内容模块，而是一条从定位到补证的策略链：

| ID | 战略维度 | Decision Question | 要形成的判断 |
|---|---|---|---|
| `efgPathwayPositioning` | 治疗路径定位 | 将 EFG 定位为快速诱导、个体化周期治疗，还是难治患者升级方案？现有证据链分别支持到哪一步？ | 明确 EFG 在治疗路径中的可支持位置，而不是泛泛讨论“是否前移” |
| `efgTreatmentGoalValue` | 治疗目标与价值主张 | EFG 的核心疗效主张应建立在快速 CMI、MSE、减激素、减少 rescue，还是长期稳定控制上？目前哪条患者轨迹证据最完整？ | 区分达到过、持续、persistent、stable 和达标后维持，选择可持续的学术主张 |
| `efgRegimenSequencing` | 周期与序贯管理 | 首周期应答后，按需再治疗、固定周期、IST 接续以及 IV→SC 转换，各自适合什么患者？再治疗时点能否由症状轨迹而非固定时间决定？ | 从“药物有效”推进到长期个体化管理 |
| `efgPriorityPatientProfile` | 优先患者画像 | 哪些患者最有理由优先考虑 EFG：需要快速控制、高激素负担、早期/新发、既往多线治疗、高龄共病，还是特定抗体亚型？哪些已有可行动证据，哪些仍是假设？ | 明确有证据支撑的患者选择，避免罗列亚组 |
| `efgAcademicDifferentiation` | 产品学术差异化 | 没有 head-to-head RCT 时，EFG 相对其他 FcRn 和补体抑制剂，哪些差异已具有临床转化意义，哪些仍只是产品特征或跨研究推演？ | 建立可防守的比较框架，并列出不能直接比较的内容 |
| `chinaEvidenceGeneration` | 中国证据生成优先级 | 若要让中国证据真正改变 EFG 的临床定位，下一步最应补齐哪一段：患者轨迹、再治疗算法、长期稳定终点、switching、特殊人群，还是跨中心统一终点？ | 将中国 RWE 从病例和应答率积累升级为可比较的证据网络 |

问题之间的逻辑顺序为：

```text
在哪里用
→ 对谁用
→ 追求什么治疗目标
→ 如何长期管理
→ 如何与其他靶向治疗区隔
→ 中国还需生成什么证据
```

`communityTaxonomy` 仍是底层语义关系。一个问题可以连接多个社区，一个社区也可以支撑多个问题，不要求“一社区一问题”。

### 1.3 数据合约

**Create:** `config/medical-affairs-questions.json`

```json
{
  "schema_version": "1.0",
  "questions": [
    {
      "id": "efgPathwayPositioning",
      "strategy_dimension": "pathway_positioning",
      "question": "将 EFG 定位为快速诱导、个体化周期治疗，还是难治患者升级方案？现有证据链分别支持到哪一步？",
      "intent": "academic_medical_strategy",
      "audiences": ["medical_affairs", "msl"],
      "anchor_nodes": ["efgartigimod", "rapidOnset", "treatmentPathway"],
      "community_ids": ["fcrnTargetedTherapy", "treatmentPathway"],
      "patient_journey_nodes": [
        "treatment_start",
        "first_cycle_response",
        "retreatment",
        "long_term_control"
      ],
      "retrieval": {
        "wiki_dimensions": ["pathway_positioning", "regimen_strategy"],
        "source_channels": ["literatureEvidence", "guidelineConsensus", "trialRegistry", "conference"]
      },
      "guardrails": [
        "快速起效不自动等于支持普遍前移",
        "难治患者证据不能直接外推到所有早期患者"
      ]
    }
  ]
}
```

**Create:** `data/decision-briefs.js` → `window.MG_DECISION_BRIEFS`

```json
{
  "schema_version": "1.0",
  "generated_at": "...",
  "source_release_id": "...",
  "questions": [
    {
      "id": "efgPathwayPositioning",
      "strategy_dimension": "pathway_positioning",
      "question": "...",
      "decision_state": "conditional",
      "current_academic_judgment": "...",
      "critical_evidence_boundary": "...",
      "clinical_decision_context": {
        "population": [],
        "disease_stage": [],
        "prior_treatment": [],
        "treatment_burden": [],
        "decision_need": []
      },
      "patient_journey": [
        {
          "node": "first_cycle_response",
          "coverage": "supported",
          "claim_ids": []
        }
      ],
      "supporting_claim_ids": [],
      "limiting_claim_ids": [],
      "conflicting_claim_ids": [],
      "academic_claims": {
        "supported": [],
        "conditional": [],
        "not_supported": []
      },
      "china_evidence_and_practice": {},
      "expert_discussion_questions": [],
      "evidence_gaps": [],
      "source_refs": [],
      "review_labels": [],
      "delta_summary": {},
      "routes": {
        "knowledge_nodes": [],
        "community_ids": [],
        "topic_ids": []
      }
    }
  ]
}
```

Decision Brief 按三层阅读组织：

1. **5 秒判断**：战略问题、Decision state、当前学术判断、最关键证据边界。
2. **30 秒证据解释**：临床决策场景、患者轨迹、支持证据、限制/反证、不可比较性、中国证据与临床实践。
3. **2 分钟学术准备**：可支持主张、条件性主张、当前不能支持的主张、专家讨论问题、待补证据、来源与审查标签。

`Decision state` 固定为四档：

| 内部值 | 中文展示 | 判定含义 |
|---|---|---|
| `supported` | 明确 | 已有直接证据，可以形成清晰学术判断 |
| `conditional` | 条件 | 可以形成判断，但必须限定人群、终点、时间或证据类型 |
| `exploratory` | 探索 | 适合提出假设和专家讨论，不能形成确定主张 |
| `insufficient` | 不支持结论 | 当前证据不足、冲突，或问题尚未被直接研究 |

Decision state 回答“这个具体问题能回答到什么程度”，不等同于单篇文献的 Oxford Evidence I–V。`abstract_only`、`needs_full_text_review`、`conflicting_evidence` 和 `china_applicability_uncertain` 继续作为独立审查标签。

### 1.4 后端改造

**Create:** `scripts/common/question_catalog.py`

- `load_question_catalog(path)`：schema validation、ID 唯一性、社区/节点引用格式检查。
- `validate_question_spec(spec)`：拒绝空 question、未知 `decision_state`、无 retrieval 规则的条目。

**Create:** `scripts/build-decision-briefs.py`

- 输入：问题目录、literature、source signals、community、graph、curated topics、landscape insights 和现有 Living Answers 兼容视图。
- `efgartigimod-wiki` 负责问题设计和人工策展依据；周更云端不直接依赖本地 wiki。问题规格和已确认锚点写入 tracked config 后再进入 Pipeline。
- 确定性检索负责候选证据、患者轨迹覆盖和引用；每个引用使用统一 `source_ref_id`。
- 首版 `current_academic_judgment` 必须对 6 个新战略问题逐题医学策展，不能复用旧 Living Answer 作为结论。
- R1 只允许输出 `recent_trigger`，且必须标为“新证据入口”。R3 建成前不使用 `Why now` 或“改变判断”的措辞。
- 无足够证据时输出 `decision_state=insufficient`，不能生成肯定结论。
- 可选 LLM 只允许重组证据已覆盖的学术主张、限制和专家讨论问题；所有 claim/source ID 必须回验。
- 使用 `atomic_write_js_global()` 写入。

**Modify:** `scripts/build-frontend-data.py`

- 删除 `LIVING_ANSWER_SPECS` 作为 SSOT 的职责。
- 在过渡期继续生成 `landscape-data.js.living_answers`，但内容从 question catalog 读取，保证现有前端兼容。
- 最终 `landscape-data.js.living_answers` 标为兼容视图；权威产物改为 `decision-briefs.js`。

**Modify:** `scripts/run-weekly-pipeline.py`

- 在 `build-landscape-insights` 后添加 required step：
  - `build-decision-briefs`
  - output: `data/decision-briefs.js`
- cloud-safe 模式可运行，因为其所有输入均有 tracked last-good 版本。

### 1.5 前端改造

**Modify:** `pages/landscape.html`

- 六大页面和 6 项顶级导航完全不动，不新建第七个页面。
- 只将 `pages/landscape.html` 现有 Living Answers 区域改造成“医学策略问题 / Decision Brief”。
- 现有 Evidence Matrix、Clinical Pipeline、Competitive Matrix 和 Landscape Insights 保留，作为 Brief 的深层证据入口。
- 加载 `../data/decision-briefs.js`。
- 支持 `?question=<id>` 直达，不保存浏览历史到站内数据。

**Modify:** `assets/landscape.js`

- 以 `MG_DECISION_BRIEFS.questions` 为主；缺失时回退 `MG_LANDSCAPE_DATA.living_answers`。
- Recommendation Card 与 Decision Brief 使用同一数据模型：折叠态是 Recommendation Card，展开态是完整 Decision Brief。
- Desktop 使用左侧战略问题导航、右侧单一 Brief；Mobile 使用顶部问题选择器和纵向内容。一次只聚焦一个问题。
- 首屏显示：战略问题、Decision state、当前学术判断和最关键证据边界。
- 展开后按顺序显示：临床决策场景、患者轨迹、支持/限制/冲突、可支持/条件性/不支持主张、中国证据与临床实践、专家讨论问题、待补证据、来源与审查标签。
- 每个来源必须回链 PMID、正式指南/共识、试验注册或会议主来源。监管链接只在核查说明书边界时出现。

**Modify:** `assets/msl.js`

- R1 不重构 MSL 页面，也不复制另一套 Decision Brief。
- 后续只把 `MG_DECISION_BRIEFS` 作为现有 `generateBrief()` 的只读输入，组合 `expert + question + selected modules + signals`。
- 不保存选择；刷新页面后状态丢失是预期行为。

### 1.6 测试与验收

**Create:** `tests/test_question_catalog.py`

- 6 个战略问题 ID 稳定且唯一，并与本节确认的问题逐项一致。
- 每个问题至少有一个社区或节点锚点。
- 每个问题至少关联一个 `expert-question-bank.yaml` 医学策略维度或明确的 MG-wide 证据域。
- 非法 source channel、重复 ID、空 question 必须失败。

**Create:** `tests/test_decision_briefs.py`

- 每张 Brief 必须有 `decision_state/current_academic_judgment/critical_evidence_boundary/source_refs`。
- `decision_state` 只能是 `supported/conditional/exploratory/insufficient`。
- `supported` 或 `conditional` 必须至少绑定一个有效 source ID。
- `insufficient` 不得输出肯定式 `academic_claims.supported`。
- Patient journey 必须显式区分达到过、持续、persistent、stable 和达标后维持，不能合并为同一终点。
- 所有 PubMed refs 必须存在于严格 recent、curated topic evidence 或允许的 full-derived reference 中。
- 指南/监管/注册/会议不得携带 Oxford evidence level。
- Brief schema 中不得出现政务、支付、准入或 HEOR 字段。

**Modify:** `tests/test_frontend_flow_and_conference_filters.py`

- `?question=` 正确定位。
- 无 `localStorage` / IndexedDB。
- 无 Decision Brief 数据时 Living Answer fallback 可用。

**验收终止条件：** 6 个新战略问题全部上线；旧问题只作为兼容输入；`pages/landscape.html` 可按问题直达；每张 Brief 均能回到公开原始来源；六大页面和导航不变；无记录功能。

---

## 2. Claim-level Claim–Evidence

### 2.1 改造目标

将“结论文本”和“证据来源”从页面级弱关联，升级为可审计的 Claim–Evidence 合约。支持证据、限制和冲突必须分开，不把所有 PMID 简单堆在同一列表。

### 2.2 现有资产复用

- `curated-topics[].claims[]` 已有 claim text、claim type、evidence_pmids。
- `content-modules[].claims[]` 已有 claim + PMID + evidence level。
- `knowledge-graph.evidence_matrix[]` 已有 source/target/relation/confidence/key_pmids/limitation。
- `signals-weekly` 已有 takeaway/whySignal/evidenceBoundary/refs。
- `source-signals` 已统一五类来源入口。
- `literature-recent` 提供人群、study type、evidence level、日期、China 标记和 abstract。

### 2.3 数据合约

**Create:** `data/claim-evidence.js` → `window.MG_CLAIM_EVIDENCE`

```json
{
  "schema_version": "1.0",
  "generated_at": "...",
  "claims": [
    {
      "claim_id": "claim:steroid-sparing:definition",
      "question_ids": ["efgTreatmentGoalValue"],
      "text": "达到 MSE 不等于持续 MSE。",
      "claim_type": "endpoint_definition",
      "polarity": "limitation",
      "scope": {
        "population": [],
        "intervention": [],
        "comparator": [],
        "outcome": ["MSE"],
        "time_horizon": [],
        "geography": []
      },
      "evidence_links": [
        {
          "source_ref_id": "pubmed:39974170",
          "relation": "supports",
          "evidence_level": "IV",
          "source_channel": "literatureEvidence",
          "full_text_status": "not_verified"
        }
      ],
      "traceability": {},
      "review_labels": [],
      "limitations": []
    }
  ],
  "sources": {}
}
```

统一来源 ID：

- `pubmed:<PMID>`
- `guideline:pubmed:<PMID>`；未来正式全文可用 `guideline:<publisher>:<document-id>`
- `regulatory:<drug-id>:<source-date>`
- `trial:ClinicalTrials.gov:<NCTID>`
- `trial:ChiCTR:<ChiCTR-ID>`
- `conference:<conference>:<abstract-id>`
- `topic:<topic-id>:claim:<index>`

### 2.4 后端改造

**Create:** `scripts/common/source_refs.py`

- 五频道到统一 source ref 的 adapter。
- `validate_source_ref()` 检查 ID、URL、channel 和 evidence policy。
- `resolve_pubmed_ref()` 从 recent / topic refs / graph refs 解析，不凭空生成 PMID。

**Create:** `scripts/common/claim_contract.py`

- Claim schema、polarity、relation 和 scope validator。
- 允许 relation：`supports`、`limits`、`conflicts`、`contextualizes`、`pending`。
- 没有有效 evidence link 的陈述只能标为 `open_question`，不能标为 supported claim。

**Create:** `scripts/build-claim-evidence.py`

按优先级合并：

1. curated topic claims（最高优先，已有策展文本和 PMID）。
2. question catalog guardrails / seed position（作为 seed，必须映射证据后才能发布为 supported）。
3. content module claims。
4. knowledge evidence matrix。
5. Signal takeaway/evidenceBoundary（仅近期变化语境）。

去重策略：稳定 `claim_id` + 规范化文本 + question scope；不按模糊 embedding 自动合并相反结论。

**Modify:** `scripts/build-decision-briefs.py`

- Brief 不再直接堆 references；改为引用 `supporting_claim_ids/limiting_claim_ids/conflicting_claim_ids`。
- `source_refs` 由 Claim 图反向汇总。

**Modify:** `scripts/build-curated-topic-data.py`

- 保留现有 `extract_claims()`，增加稳定 claim key 和 section provenance。
- 不覆盖 wiki 原始 claim 文本。

### 2.5 前端改造

**Modify:** `pages/landscape.html`, `assets/landscape.js`

- Decision Brief 展开区显示三栏：支持 / 限制 / 冲突或未知。
- 每条 Claim 显示 scope、来源关系、证据等级或来源类型、全文状态。
- 点击 Claim 展开来源；不能把来源频道混为统一分数。

**Modify:** `pages/knowledge.html`, `assets/knowledge.js`

- evidence matrix 行可跳转到相关 Claim / Decision Brief。
- curated topic claim 显示其支持的医学问题。

### 2.6 测试与验收

**Create:** `tests/test_claim_contract.py`

- source ID 唯一、可解析、URL 安全。
- PubMed 支持关系只接受存在的 PMID。
- 非 PubMed 来源无 Oxford level。
- 同一 Claim 可同时有 supports + limits，但前端必须分区展示。
- unsupported seed 必须降级为 open question。

**Create:** `tests/test_claim_evidence_builder.py`

- curated topic claim provenance 不丢失。
- 重复文本不会产生重复 claim ID。
- 反向关系不因去重被吞并。
- Decision Brief 中所有 claim ID 均存在。

**验收终止条件：** 每张 Decision Brief 的核心判断、限制、冲突和未知均由 Claim ID 驱动；所有 Claim 可回溯至公开来源或明确标为 open question。

---

## 3. Evidence Delta 变化检测

### 3.1 改造目标

把“新增多少篇”升级为“什么医学判断发生了什么变化”。Delta 必须区分真正的证据变化和滚动窗口自然过期，不能因文章超过 365 天就误报结论减弱。

### 3.2 变化类型

| Event | 触发条件 |
|---|---|
| `new_evidence` | 新 source ref 首次支持某 Claim |
| `strengthened` | 新增 I–III 证据，或多来源一致性提高 |
| `limited` | 新增明确局限、外推边界或不一致结果 |
| `conflict_detected` | 同 scope 下出现相反 polarity/结果 |
| `guideline_changed` | 指南/共识版本或学术建议发生可核查变化；首版只检测文档更新，不猜推荐变化 |
| `trial_evidence_changed` | 新研究设计、终点或结果可能填补既有证据缺口；单纯招募状态变化不进入 Brief |
| `conference_signal` | 新会议摘要进入相关 Claim/Question |
| `china_gap_changed` | 中国患者轨迹、终点一致性、临床实践证据或研究设计填补既有缺口 |
| `stale` | 权威来源超过配置阈值且无更新 |

明确禁止：仅因 recent rolling window 移除 PMID 就触发 `weakened`。

### 3.3 快照与数据合约

**Create:** `.hermes-audit/intelligence-snapshots/<run-id>/`

- 保留上一 coherent release 的：`decision-briefs.js`、`claim-evidence.js`、`source-signals.js`、`china-evidence-practice.js`、release metadata。
- 不推 GitHub；只用于本地/运行时比较。

**Create:** `data/evidence-delta.js` → `window.MG_EVIDENCE_DELTA`

```json
{
  "schema_version": "1.0",
  "generated_at": "...",
  "from_release_id": "...",
  "to_release_id": "...",
  "events": [
    {
      "event_id": "delta:...",
      "event_type": "strengthened",
      "question_ids": [],
      "claim_ids": [],
      "source_ref_ids_added": [],
      "source_ref_ids_removed": [],
      "before": {},
      "after": {},
      "why_it_matters": "...",
      "review_labels": [],
      "detected_by": "deterministic"
    }
  ]
}
```

### 3.4 后端改造

**Create:** `scripts/common/intelligence_snapshot.py`

- 在本轮 derived intelligence 写入前复制上一版产物到 audit snapshot。
- 记录 hash 和 source release ID。
- snapshot 失败时停止 Delta 步骤，但不破坏上一版公开产物。

**Create:** `scripts/build-evidence-delta.py`

- 比较 source ref、Claim relation、Decision state、患者轨迹覆盖和学术来源字段。
- Delta narrative 只由结构化 before/after 生成。
- LLM 可选地润色 `why_it_matters`，但不能更改 event type、source refs 或 before/after。
- 首次上线输出 baseline，明确 `comparison_available=false`；不伪造历史变化。
- 监管状态仍可在情报中心更新，但不作为 Decision Brief Delta 的默认事件；只有适用人群或说明书边界发生变化时，才作为来源边界提示。

**Modify:** `scripts/run-weekly-pipeline.py`

顺序调整为：

```text
snapshot-intelligence
→ build-claim-evidence
→ build-decision-briefs
→ build-china-evidence-practice
→ build-evidence-delta
→ generate-weekly-summary
→ generate-pipeline-status
```

- `snapshot-intelligence` 仅声明 audit 输出，不纳入 public artifacts。
- `build-evidence-delta` required；首次 baseline 合法。
- release manifest 收录四个新增公开产物。

**Modify:** `scripts/generate-weekly-summary.py`

- Top 3 从“高分 Signal”改为优先显示高影响 Delta。
- 保留文献 Signal 区作为来源层，而不是决策层。

### 3.5 前端改造

**Modify:** `index.html`, `assets/dashboard.js`

- 首页首屏显示“本轮改变判断的 3 件事”。
- 每条 Delta 必须显示 event type、问题、为何重要、来源和限制。
- 数量统计退居辅助位置。

**Modify:** `assets/landscape.js`

- 每张 Decision Brief 显示 `delta_summary`。
- 支持筛选“新证据 / 加强 / 局限 / 冲突 / 中国变化”。

### 3.6 测试与验收

**Create:** `tests/test_evidence_delta.py`

- 新 PMID → `new_evidence`。
- 新 I/II 支持 → `strengthened`。
- recent 365 天过期 → 不生成 weakened。
- 新试验设计或结果填补问题缺口 → `trial_evidence_changed`。
- 只有 registry 招募状态改变、没有新增科学信息 → 不生成 Brief Delta。
- 普通监管状态更新 → 保留在情报中心，不生成 Brief Delta。
- 首次无 snapshot → baseline，不能伪造 event。
- snapshot hash 不匹配 → fail closed。

**验收终止条件：** 首页可以回答“本轮哪些判断发生变化”；每个事件有 before/after 和来源；滚动过期不产生伪变化。

---

## 4. 中国证据与临床实践（China Evidence & Practice）

### 4.1 改造目标

中国部分是每张 Decision Brief 的学术子层，不是独立的政策或监管模块。它回答：

- 中国患者证据覆盖了哪些人群、既往治疗和疾病阶段
- 首周期应答、CMI/MSE、减激素、再治疗、长期稳定和 rescue 形成了怎样的患者轨迹
- 中国真实世界研究的设计、终点定义、随访和偏倚允许支持到什么程度
- 全球证据中哪些可以迁移到中国，哪些因人群或终点不同不能直接外推
- 中国正在开展的研究将填补哪个科学缺口
- 哪些中国公开研究团队与该问题直接相关，下一步值得讨论什么证据

NMPA/CDE/NHSA、政务、支付、市场准入和 HEOR 不进入本模块。监管来源继续保留在情报中心；只有适用人群、剂量或说明书边界需要核查时，才作为来源注释被引用。

### 4.2 现有资产复用

- `china-intelligence.js`：严格 recent 的中国文献、人群和证据等级。
- `china-author-network.js`：中国机构、作者、研究主题、药物和 PMID。
- `expert-profiles-china.js`：China-only 公开学术画像。
- `curated-topics.js` 与 efgar-wiki 中国 RWE 专题：患者轨迹、终点口径和研究限制。
- `clinicaltrials-pipeline-cache.json` 与 `chictr-trials-cache.json`：识别未来将生成什么证据，不讨论审批进度。
- `guideline-consensus-cache.json`：中国指南/共识的学术来源；缺少可核查全文时必须显示 source gap。
- `source-signals.js`：继续提供独立来源入口；`chinaRegulatory` 不进入本模块的默认合并逻辑。

### 4.3 数据合约

**Create:** `data/china-evidence-practice.js` → `window.MG_CHINA_EVIDENCE_PRACTICE`

```json
{
  "schema_version": "1.0",
  "generated_at": "...",
  "questions": {
    "efgPathwayPositioning": {
      "china_evidence_refs": [],
      "patient_profile": {
        "antibody_subtypes": [],
        "disease_stage": [],
        "prior_treatments": [],
        "treatment_burden": [],
        "special_populations": []
      },
      "patient_journey": {
        "first_cycle_response": {},
        "cmi_mse": {},
        "steroid_reduction": {},
        "retreatment": {},
        "long_term_stability": {},
        "rescue_use": {}
      },
      "study_quality": {
        "designs": {},
        "multicenter": 0,
        "prospective": 0,
        "endpoint_harmonization": "unknown",
        "follow_up_adequacy": "unknown",
        "bias_notes": []
      },
      "global_to_china_transfer": {
        "directionally_consistent": [],
        "not_directly_comparable": [],
        "evidence_gaps": []
      },
      "ongoing_academic_research": [],
      "public_academic_leads": [],
      "institution_leads": [],
      "next_evidence_questions": [],
      "applicability": "uncertain",
      "applicability_reasons": []
    }
  }
}
```

### 4.4 后端改造

**Create:** `scripts/build-china-evidence-practice.py`

- 按 question anchors、communities 和 claims 匹配中国患者证据、患者轨迹、研究质量、研究缺口及公开学术线索。
- 对 CMI、MSE、达到过、持续、persistent、stable、达标后维持和激素减量分别建模，不合并为“应答率”。
- `ongoing_academic_research[]` 只描述研究问题、设计、终点和预计填补的缺口；不将招募状态或审批进度包装成学术价值。
- 专家/机构只能由公开 PMID、主题和机构支撑；不生成“关系强度”“内部等级”或接触价值。
- `public_academic_leads[]` 字段为 `expert_id/name/affiliation/publication_pmids/matched_topics/rationale/identity_confidence`。
- `rationale` 只能描述公开研究匹配依据，例如“近 3 年在该主题发表 N 篇”。
- builder 不读取政策、支付、准入或 HEOR 字段，不把 `china-regulatory-status.json` 作为核心输入。

**Modify:** `scripts/buildChinaAuthorNetwork.py`

修复并显式区分：

- `article_china_related`：文章存在中国作者/机构。
- `author_geo_scope`：该具体作者/机构的地理归属。
- `geo_source`：affiliation/canonical map/fallback。
- `geo_confidence`：high/medium/low。

禁止把一篇 China-related article 中的所有国际作者自动标为中国作者。此项是本模块上线前的质量门。

**Modify:** `scripts/common/clinical_registry.py`

- 在不破坏现有 schema 的前提下，保留 study design、population、endpoint、country/site 和 linked registry 字段。
- 只有 registry 明确提供中国 location 时才标 `china_site=true`。
- 输出给本模块的是“未来证据地图”，不是审批或招募看板。

**Modify:** `scripts/build-decision-briefs.py`

- 合并 `china-evidence-practice.js` 到每张 Brief 的 `china_evidence_and_practice`。
- 没有中国数据时显示具体缺口，不用全球数据填补“中国证据”。

### 4.5 前端改造

**Modify:** `assets/landscape.js`

- Brief 内显示“中国证据与临床实践”，不显示“中国监管”默认区块。
- 按顺序显示：中国患者画像、患者轨迹、研究质量、全球到中国的可迁移性、正在生成的证据、公开研究团队、待补证据。
- 默认先显示判断和证据缺口，再展示数量。

**Modify:** `assets/msl.js`

- 选中 question 后，专家排序增加“公开学术问题匹配度”。
- 匹配度解释必须展示 PMID 和主题依据。
- 不保存选择，不允许用户添加内部标签。

### 4.6 测试与验收

**Create:** `tests/test_china_evidence_practice.py`

- 每个公开学术 lead 至少有一个公开 PMID 或明确 topic evidence。
- 日本、韩国或其他国际机构不能因共同文章被标为中国机构。
- China-related article 与 author geo 必须分开。
- CMI、MSE、达到过、持续、persistent、stable 和达标后维持不得合并为同一终点。
- 无中国指南全文时输出 `source_gap`，不能生成指南结论。
- ChiCTR 与 ClinicalTrials.gov 不重复；linked registries 保留。
- 非中国 evidence 不能计入中国患者证据。
- public schema 不得出现政策、政务、支付、准入、HEOR 或默认监管字段。

**验收终止条件：** 每张 Brief 都能说明中国证据覆盖了什么、能外推到哪里、研究质量如何、下一步缺什么；公开专家和机构匹配完全基于学术证据；监管、政务和 HEOR 不进入默认学术叙事。

---

## 5. 建议可信度与可审查标签

### 5.1 改造目标

不再依赖单一、模糊的 `confidence=high/medium/low`。可信度改为多个可解释维度，前端展示决策信号而非神秘分数。

### 5.2 质量维度

| 维度 | 来源 |
|---|---|
| `traceability` | Claim 是否全部有有效 source ref、URL、稳定 ID |
| `evidence_maturity` | PubMed I–V 分布；指南/共识、注册、会议按各自类型描述，不混分 |
| `source_authority` | PubMed、正式指南/共识、注册主站、会议主来源；说明书只作边界来源 |
| `consistency` | supports / limits / conflicts 的结构 |
| `freshness` | source date、last verified、pipeline artifact date |
| `full_text_status` | abstract only / full text checked / official document checked |
| `china_applicability` | 中国患者、人群结构、患者轨迹、研究质量、试验和指南覆盖情况 |
| `coverage` | 关键 scope（人群、干预、终点、时间）是否齐全 |

统一 review labels：

- `source_backed`
- `inference`
- `open_question`
- `needs_full_text_review`
- `china_applicability_uncertain`
- `conflicting_evidence`
- `stale_source`
- `official_source_verified`
- `abstract_only`

### 5.3 后端改造

**Create:** `scripts/common/evidence_quality.py`

- `evaluate_claim(claim, sources)` → 维度和 labels。
- `evaluate_brief(brief, claims, china_lens)` → 维度聚合，不输出不可解释总分。
- 阈值放在 `config/evidence-quality-rules.json`，不硬编码到前端。

**Create:** `config/evidence-quality-rules.json`

- freshness thresholds 按 source type 设置。
- full-text 和 official document 默认 false，只有现有数据明确提供时才能 true。
- `source_backed` 要求所有发布 Claim 至少一个有效证据关系。
- `supported/conditional` 要求：支持 Claim 存在、无未披露 conflict、关键 limitation 已展示。

**Modify:** `scripts/build-claim-evidence.py`, `scripts/build-decision-briefs.py`, `scripts/build-evidence-delta.py`

- 写入统一 quality dimensions 和 review labels。
- 旧 `confidence` 暂保留兼容，但由维度映射生成，并标为 deprecated。

**Modify:** `scripts/generate-pipeline-status.py`

增加 intelligence QA：

- brief count
- claim count
- orphan claim count
- invalid source ref count
- abstract-only claim count
- conflict count
- stale source count
- China applicability uncertain count

任一硬错误（orphan/invalid ref/unsupported affirmative claim）阻止 release manifest 更新。

### 5.4 前端改造

**Modify:** `assets/landscape.js`, `assets/knowledge.js`, `assets/msl.js`, `assets/main.css`

- 标签统一视觉语言；颜色只辅助，必须有文字。
- 展示“为什么是这个标签”的 tooltip/展开说明。
- `needs_full_text_review` 和 `conflicting_evidence` 必须显著。
- 不把 Oxford I–V 与 source authority 合并成单一等级。

### 5.5 测试与验收

**Create:** `tests/test_evidence_quality.py`

- abstract-only 自动带 `needs_full_text_review`。
- 正式指南、注册主站或说明书来源经核查后可标 `official_source_verified`。
- 存在 conflict 必须显示 `conflicting_evidence`。
- 无中国证据不能标 China applicable。
- 指南/监管/注册/会议不能获得 Oxford evidence level。
- 任何 affirmative claim 无 source → quality gate 失败。

**验收终止条件：** 用户无需理解算法，也能看到建议为何可信、哪里不确定、哪里需要全文核查；数据状态页可审计所有异常。

---

## 6. UI、性能与无状态导出

### 6.1 页面信息架构

保持 6 个主页面，不新增顶级导航：

| 页面 | 改造后职责 |
|---|---|
| 工作台 | 本轮 Evidence Delta Top 3 + 来源健康；回答“什么改变了” |
| 情报中心 | 五来源频道和原始证据；回答“来源是什么” |
| 诊治格局 | 医学策略问题 + Decision Brief + Claim–Evidence；回答“当前怎么判断” |
| 知识库 | 图谱、社区、专题和 Claim 深挖；回答“判断如何连接” |
| MSL 工作台 | China-only 专家 + question-driven 无状态访前 Brief；回答“和谁讨论什么” |
| 数据状态 | intelligence QA、来源新鲜度、release coherence；回答“是否可审查” |

页面布局方案只指现有 `pages/landscape.html`。R1 改造该页的 Living Answers 区域，不重构另外五个页面，也不改变六大页面或顶级导航。工作台只链接高影响 Delta，知识库只展开 Claim 关系，MSL 工作台只读取同一 Brief 生成访前准备。

### 6.2 性能策略

1. `decision-briefs.js`、`evidence-delta.js`、`china-evidence-practice.js` 预计较小，可直接加载。
2. `claim-evidence.js` 若压缩前超过 500 KB，改为：
   - `data/claimEvidenceIndex.js`
   - `data/claimEvidence-<question-id>.js`
   - 进入或展开问题时使用 `MgHub.loadScriptOnce()` 懒加载。
3. MSL 继续只加载 China shard；国际专家文件无加载路径。
4. 首页只加载 Delta 摘要，不加载完整 Claim 图。
5. 不引入 bundler 或前端框架；保留零构建 GitHub Pages。

### 6.3 无状态路由

支持公开 URL：

```text
pages/landscape.html?question=efgPathwayPositioning
pages/knowledge.html?claim=claim%3Asteroid-sparing%3Adefinition
pages/msl.html?question=efgPathwayPositioning&expert=<public-expert-id>
```

- URL 中只允许公开 ID。
- 不允许 note、rating、feedback、relationship、follow-up 等字段进入 URL。
- URL 参数使用 allowlist 和长度限制。

### 6.4 无状态导出

**Modify:** `assets/common.js`

新增纯客户端 helper：

- `downloadText(filename, content, mime)`：Blob + temporary link，完成后 revoke URL。
- `printSection(element, title)`：生成临时 print view，不存储。
- `serializeDecisionBrief(brief, claims, format)`：Markdown / plain text；所有引用保留。

**Modify:** `assets/landscape.js`

- 导出当前 Decision Brief 为 Markdown。
- 打印友好版必须包含：生成日期、source release、review labels、Claims、来源、限制、非医疗建议声明。

**Modify:** `assets/msl.js`

- 导出当前访前 Brief；内容只在当前 DOM/内存中存在。
- 导出后页面不产生历史记录或“最近导出”。

**Modify:** `assets/main.css`

- `@media print`：隐藏导航/筛选，只打印当前 Brief 和来源。
- 移动端优先显示：当前学术判断 → 关键证据边界 → 患者轨迹 → 支持/限制/冲突 → 中国证据与临床实践 → 专家讨论问题 → 关键来源。

### 6.5 测试与浏览器验收

**Create:** `tests/test_stateless_exports.py`

- 全站无 `localStorage` / IndexedDB / cookie 写入。
- 导出内容包含来源和限制。
- URL allowlist 拒绝未知字段和危险协议。
- Blob URL 被 revoke。
- 打印视图不包含其他专家或隐藏数据。

**Modify:** 现有 frontend contract tests

- 默认页面不请求 claim shards。
- 打开特定问题只请求对应 shard。
- shard 加载失败时显示 Brief 摘要和明确降级，不崩溃。
- 线上验证 Chrome + Safari/WebKit 核心布局。

**验收终止条件：** 访前 Brief 和 Decision Brief 可复制、打印、下载；网站不保存任何行为或历史；首屏性能不因 Claim 图退化。

---

## 7. 串行实施与发布顺序

严格按用户认可的 1 → 6 推进，每个模块独立讨论、构建、验收和 push。

| Release | 内容 | 依赖 | 主要产物 | 结束条件 |
|---|---|---|---|---|
| R1 | 医学策略问题目录 + Decision Brief | MG-wide 证据 + efgar-wiki 策展层 + 旧 Living Answers 兼容视图 | `medical-affairs-questions.json`, `decision-briefs.js` | 6 个新战略问题上线、可直达、可回链 |
| R2 | Claim–Evidence | R1 | `claim-evidence.js` | Brief 核心判断由 Claim ID 驱动 |
| R3 | Evidence Delta | R2 | snapshots, `evidence-delta.js` | 首页显示真实变化，滚动过期不误报 |
| R4 | 中国证据与临床实践 | R1–R3 | `china-evidence-practice.js` | 每个问题呈现中国患者轨迹、研究质量、证据迁移性或明确缺口 |
| R5 | Quality/Review Labels | R2–R4 | quality rules + status QA | unsupported affirmative claim 阻断发布 |
| R6 | UI/性能/无状态导出 | R1–R5 | lazy load、Markdown/print | 可导出但零持久化，性能达标 |

### 每个 Release 的固定过程

1. 从本规划、README、操作手册、5 分钟速览恢复上下文。
2. 检查 `git status`、最新 commit、full 是否可用和 current release manifest。
3. 与用户讨论该 Release 的具体字段和界面；确认后再编码。
4. TDD：先 contract tests，再 builder，再前端。
5. Codex 只实现已确定的复杂前端组件；Machine 不在 Codex 运行时改同一文件。
6. Machine 复核 diff、运行全量质量门、浏览器验收。
7. 更新 README、操作手册、网站设计与审查速览及本规划状态。
8. commit、push、验证 GitHub Pages 及线上数据 hash。

### 预估执行规模

- 串行 Release：6 个。
- 预计编码/验收会话：8–12 个。
- 预计 Agent 实际执行时间：约 12–20 小时，取决于中国学术证据质量和 Claim 审核返工。
- 预计工具调用：约 250–400 次；每个 Release 独立收口，避免单次上下文/工具上限中断。
- 预计 Codex 任务：R1 前端、R2 Claim UI、R3 Delta Dashboard、R4 中国证据与临床实践、R6 导出/移动布局，共约 5–8 次 background coding run。

---

## 8. 完整质量门

每个 Release 至少运行：

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
for f in assets/*.js; do node --check "$f" || exit 1; done
git diff --check
```

新增数据合约检查：

```text
Question IDs unique
→ Brief question IDs resolve
→ Claim IDs resolve
→ Source refs resolve
→ Non-PubMed sources have no Oxford level
→ All affirmative claims are source-backed
→ 中国证据与临床实践不以全球证据替代中国证据
→ Brief schema excludes policy, payer, market-access and HEOR fields
→ Delta has valid before/after or baseline
→ No persistence surface
→ Release manifest covers all public intelligence artifacts
```

浏览器验收：

1. 首页：Delta Top 3 可回到 Decision Brief。
2. 情报中心：五频道仍独立。
3. 诊治格局：战略问题、Claims、中国证据与临床实践、标签和来源可展开。
4. 知识库：Claim 可回到图谱/专题/PMID。
5. MSL：China-only、按问题生成 Brief、无记录功能。
6. 数据状态：新增 intelligence QA 可审查。
7. 导出：Markdown/打印包含来源与限制，刷新后无历史。
8. GitHub Pages：线上数据文件 SHA 与 commit 一致，无 JS error。

---

## 9. 主要风险与处理

| 风险 | 处理 |
|---|---|
| 当前 6 个 Living Answers 基础且硬编码 | 不原样迁移问题；从 MG-wide 与 efgar-wiki 推导 6 个战略问题，旧内容只作兼容基线 |
| curated topic Claim 质量不均 | 保留 provenance；无有效 PMID 只作 open question，不作 supported claim |
| 指南/共识目前多为 PubMed 元数据而非全文结构化推荐 | 只显示来源和缺口；不推断推荐强度 |
| Evidence Delta 缺少历史基线 | 首次发布 baseline；从上线后开始可靠比较，不伪造历史 |
| recent 滚动窗口造成文献消失 | 禁止将自然过期解释为 weakening |
| 中国作者地理归属可能被文章级 China 标记污染 | R4 前先拆分 article geography 与 author/institution geography |
| LLM 生成医学叙事偏离证据 | LLM 可选；候选、Claim ID、source ref、event type 和 gate 全部由确定性程序控制并回验 |
| Claim 文件增大影响性能 | 超过 500 KB 才启用按 question shard；首屏不加载 Claim 全量 |
| 新产物在 cloud-safe 模式覆盖 last-good | 所有 builder 原子写入；输入缺失时 fail closed 或保留 last-good，不写空产物 |
| 规划实施期间 cron 产生新 commit | 每个 Release 开始重新读取 git 状态和最新数据，禁止基于旧 SHA 直接编码 |

---

## 10. 开放问题（进入对应 Release 时讨论，不阻碍本计划）

1. R1：为每个战略问题拆出哪些 decision claims、患者轨迹节点和最低证据门槛。
2. R1：新 6 问的首版 `Decision state` 与当前学术判断需要逐题审校，不能由模型自动决定。
3. R2：哪些 curated topics 可被视为“已医学策展”，哪些仍只算机器抽取；需要从现有 frontmatter/status 建立明确规则。
4. R3：Delta 的默认展示窗口采用“上一 coherent release”还是“近 30 天累计”；建议默认上一 release，同时提供近 30 天聚合。
5. R4：中国指南全文结构化来源尚未接入；需要单独讨论合法、稳定、可引用的数据源和更新方式。
6. R5：是否允许医学团队在仓库中人工维护 `full_text_verified` 标记；这属于公开内容策展，不是拜访记录，但需要明确维护责任。
7. R6：导出优先 Markdown + print/PDF；不建议首版引入 DOCX/PPTX，以免扩大模板和合规面。

---

## 11. 推荐的下一次讨论入口

R1 的问题方向、Brief 阅读顺序、四档 Decision state 和页面归属已经确认。下一次只讨论 6 个问题的证据规格，不立即进入其他模块：

1. 为每个问题拆解 3–6 条核心 decision claims。
2. 明确每条 Claim 对应的人群、治疗节点、终点、时间和不可比较边界。
3. 用 efgar-wiki 与 MG-wide 数据逐题核对当前证据覆盖，形成首版 `Decision state`。
4. 确认 6 张 Brief 的内容规格后，再进入 R1 TDD 和构建。
