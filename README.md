# MA-MG-HUB

MG Intelligence Hub 是面向重症肌无力（myasthenia gravis, MG）医学事务工作的静态学术情报工作站。项目将 PubMed 文献、可追溯会议摘要、ClinicalTrials 管线、中国监管状态、知识图谱、医学事务社区层和 MSL 拜访准备整合到一个 GitHub Pages 网站中。

本站服务于中国大陆 MSL 的公开学术情报、专家证据检索和拜访前材料准备；不记录拜访，不提供随访、CRM、互动历史、私有后端或浏览器持久化功能。

- 线上站点：[https://reiger-luo.github.io/MA-MG-HUB/](https://reiger-luo.github.io/MA-MG-HUB/)
- 5 分钟设计与审查入口：[report/网站设计与审查速览.md](report/网站设计与审查速览.md)
- 当前操作手册：[report/MG-Intelligence-Hub-操作手册-v5.md](report/MG-Intelligence-Hub-操作手册-v5.md)
- 周报素材：[data/weekly-summary.md](data/weekly-summary.md)

## 项目定位

MA-MG-HUB 不是单纯的文献列表，而是医学事务团队的 MG 情报工作台。它重点回答：

- 近 14 天有哪些值得关注的 MG 学术信号？
- 中国相关证据、机构和作者线索有哪些变化？
- MG 证据网络形成了哪些主题、机制和治疗社区？
- 具体治疗问题目前可以形成怎样的 abstract-level 回答？
- MSL 拜访专家前应准备哪些证据、话题和材料模块？
- 数据产物、社区归类和图谱状态是否健康？

## 当前能力

| 模块 | 页面 | 主要能力 |
|---|---|---|
| 工作台 | [index.html](index.html) | 统计卡片、社区动态、近期信号、工作流状态和数据健康 |
| 情报中心 | [pages/literature.html](pages/literature.html) | 近一年文献、14 天信号、中国情报、会议摘要；AAN / EAN 支持 MG-core 口径审计、逐条 MA 解读和 KOL 问题 |
| 诊治格局 | [pages/landscape.html](pages/landscape.html) | 月度格局洞察、竞争矩阵、ClinicalTrials 管线、Living Answers |
| 知识库 | [pages/knowledge.html](pages/knowledge.html) | 知识图谱、医学事务社区、证据矩阵、专题层、跨库检索 |
| MSL 工作台 | [pages/msl.html](pages/msl.html) | 专家画像、内容模块、拜访话题建议、PMID 文献清单 |
| 数据状态 | [pages/data-ops.html](pages/data-ops.html) | 数据源、公开产物、community audit、graph health、后端选项 |

历史页面 `pages/materials.html`、`pages/outputs.html`、`pages/progress.html` 和 `pages/competitive.html` 仅保留重定向入口。

## 数据口径

当前站点同时存在两个数据口径，维护时必须区分：

| 口径 | 当前规模 | 用途 |
|---|---:|---|
| 公开滚动层 | 截至 2026-07-15：近一年严格公开文献 652 篇；中国相关 211 篇；14 天 MG-core 聚合信号 10 条 / 26 篇 PMID | 工作台、情报中心、信号板、中国情报 |
| full / 语义底座 | 截至 2026-07-15：full、轻索引与社区层均为 10,672 篇 | 知识图谱、社区归类、专家画像、跨库检索 |

`pipeline-status.js` 分开显示两套口径：`public_rolling_count=652`，`semantic_full_count=10672`。full 口径来自 raw full / full-index / community full 产物；recent 口径分别记录 `literature-recent.js` 与 `communityAssignmentsRecent.js`，生效的 active recent 以实际文件更新时间较新的那个为准。`MG_SEMANTIC_FULL_COUNT` 和 `MG_TOTAL_COUNT` 是 recent 文件头部的语义全量声明与兼容字段；云端 recent fallback 必须保留该声明，不能改成 recent 数量。`dashboard-data.js` 与 `china-intelligence.js` 已由严格 recent 重建，分别显示 652 篇 recent 与 211 篇中国相关文献。

核心数据产物：

| 产物 | 当前规模 | 用途 |
|---|---:|---|
| `data/literature-recent.js` | 652 篇 | 近一年严格公开文献列表；全部 MG-core 且 evidence I–V |
| `data/signals-weekly.js` | 10 条父级 Signal / 10 条 KOL talking point / 26 篇 PMID | 近 14 天 MG-core Signal → KOL |
| `data/source-signals.js` | 5 个独立频道 / 383 条频道项 | 文献证据、指南/共识、中国监管、试验注册、会议线索 |
| `data/guideline-consensus-cache.json` | 9 篇 | MG-core 且具有指南/共识主来源标志的独立缓存，不进入 I–V 文献流 |
| `data/china-intelligence.js` | 中国相关 211 篇；展示最新 120 条摘要 | 严格 recent 的中国情报 |
| `data/literature-full-index.js` | 10,672 篇 | full 文献轻索引，不含 abstract |
| `data/communityTaxonomy.js` | 10 个社区 | 医学事务主题 taxonomy |
| `data/communityAudit.js` | 10,672 篇 audit | 社区归类质量状态 |
| `data/knowledge-graph.js` | 55 节点、337 核心边、180 行证据矩阵 | 知识图谱与证据矩阵 |
| `data/expert-profiles-china.js` | 8,958 位 | 中国作者-机构画像 |
| `data/expert-profiles-international.js` | 43,626 位 | 国际作者-机构画像 |
| `data/chictr-trials-cache.json` | 4 条官方核实种子 | ChiCTR 官方字段缓存；支持人工官方 JSON/CSV 刷新 |
| `data/release-manifest.js` | 当前不存在 | 仅在真实 required-step 管线完整成功后生成 coherent run id、公开产物哈希与时间戳 |
| `data/conference-data.js` | 195 条摘要 | AAN、EAN 会议资讯；含会议级 signal-to-kol narrative、覆盖审计和逐条 deepInsight / abstractZh。MGFA / AANEM 后台数据已清空，待新数据源链接后再接入 |

会议资讯当前结构化 195 条摘要：EAN 2026 104 条、AAN 2026 91 条。AAN 2026 保留 MiraSmart 检索命中 109 条、MG 摘要 91 条、规则剔除 18 条的口径审计；EAN 2026 已纳入 acronym-only MG 标题条目，并对外部文章引用摘要完成覆盖核查。MGFA / AANEM 暂不保留历史后台数据，待后续提供稳定摘要链接后按同一流程复刻接入。

## 数据流

```text
PubMed / ClinicalTrials.gov / ChiCTR / EasyScholar / 中国监管状态 / 会议来源
  ↓
本地 full 底座：literature-full.json、communityAssignments.jsonl、communityCorpusPack.jsonl
  ↓
公开滚动层：MG-core gate → 证据等级 I–V gate → literature-recent.js / signals-weekly.js
  ↘ 指南/共识独立缓存；监管、注册、会议进入 source-signals.js 独立频道
  ↓
语义层：communityTaxonomy.js、communityCards.js、communityWeekly.js、communityAssignments-*.js
  ↓
图谱与策展层：knowledge-graph.js、graphHealth.js、curated-topics.js、wikiTopicCoverage.js
  ↓
应用层：dashboard-data.js、expert-profiles*.js、content-modules.js、conference-data.js
```

公开网站只部署 HTML / CSS / JS / JSON。`data/literature-full.json`、weekly 临时数据、LLM 缓存和成本日志留在本地。系统不采集拜访记录；内部专家标签也不进入公开仓库。

MSL 前端为 China-only：`pages/msl.html` 只加载 `expert-profiles-china.js`，搜索和拜访准备仅使用中国作者索引。完整专家重建仍固定生成 `expert-profiles-china.js` 与 `expert-profiles-international.js` 两个分片；国际分片仅供离线分析，不存在前端加载路径。

PubMed 主文献流同时执行 MG-core 与证据门控。题名明确 MG、可靠 MG MeSH/关键词或重复 MG-core 提及可进入相关性候选；单次背景提及和非 MG 疾病主导题名被排除。之后仅证据等级 I–V 进入文献库。指南/共识、监管、试验注册和会议不冒充 Oxford 证据，分别保留在独立频道。

只重建严格公开 recent（不合并 weekly、不写 full）时使用：

```bash
python3 scripts/merge-weekly-literature.py --derive-only
python3 scripts/build-source-signals.py
python3 scripts/generate-pipeline-status.py
```

## 技术栈

- 前端：原生 HTML / CSS / JavaScript，零构建
- 数据加载：`window.MG_*` 全局数据对象
- 共用工具：`window.MgHub`，包括 base path、HTML escape、safe URL、脚本加载和 tabs
- 数据管线：Python 3.11+
- 部署：GitHub Pages
- 自动化：GitHub Actions 轻量周更，本地/Hermes full 驱动周更

## 目录结构

```text
.
├── index.html
├── pages/
│   ├── literature.html
│   ├── landscape.html
│   ├── knowledge.html
│   ├── msl.html
│   └── data-ops.html
├── assets/
│   ├── common.js
│   ├── main.css
│   └── *.js
├── data/
│   ├── *.js
│   ├── weekly-summary.md
│   └── *.json
├── scripts/
├── tests/
├── report/
├── requirements.txt
└── requirements-dev.txt
```

## 本地运行

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

启动静态服务：

```bash
python3 -m http.server 8000
```

然后访问 [http://localhost:8000/](http://localhost:8000/)。

如果只是快速查看，也可以直接打开 `index.html`；推荐使用静态服务，以便更接近 GitHub Pages 的资源加载方式。

## 周更与构建

### 周更链路关系

```text
efgar-wiki 本地 cron
  → 更新本地 Obsidian vault（深度策展、source、link、health、community）
  → 不直接发布网站

MA-MG-HUB Local Weekly Sync（每周一 03:15）
  → 读取本地 efgar-wiki 的 concepts / entities / data-points / comparisons
  → 生成 data/curated-topics.js
  → 映射 full MG community，生成 data/wikiTopicCoverage.js
  → 重建公开 data/*.js
  → git commit && git push origin main
  → GitHub Pages 上线
```

原则：efgar-wiki 是本地策展知识源；MA-MG-HUB 是发布系统。执行分离，状态页/周报合并观察。

本地完整周更入口:

```bash
bash scripts/run-local-weekly-sync.sh
```

dry-run：

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

该入口以本地 `data/literature-full.json` 为源头，执行 PubMed 增量抓取、证据分级、IF/CAS 补充、recent 派生、社区层、知识图谱、专题层、周报、管线状态、校验、commit 和 push。

仅运行管线：

```bash
python3 scripts/run-weekly-pipeline.py
```

可恢复运行示例：

```bash
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume
python3 scripts/run-weekly-pipeline.py --run-id weekly-20260715 --resume --from-step build-source-signals
```

审计检查点位于 `.hermes-audit/pipeline-runs/<run-id>.json`。仅当所有 required 步骤成功时才更新 `data/release-manifest.js`；可选语义增强或 ChiCTR 刷新失败使用缓存并记录 warning。

ChiCTR 默认使用 tracked cache。运营人员取得 ChiCTR 官方导出后可确定性刷新：

```bash
python3 scripts/refresh-chictr-cache.py --input /path/to/official-chictr-export.csv
```

自动访问受 Aliyun WAF 阻断时保持 `mode=cache`，不使用第三方抓取数据，也不再分发 WHO ICTRP 数据。

常用单项重建：

```bash
python3 scripts/build-frontend-data.py
python3 scripts/buildFullLiteratureIndex.py
python3 scripts/buildCommunityData.py
python3 scripts/build-knowledge-data.py
python3 scripts/buildLandscapeInsights.py
python3 scripts/build-conference-data.py
python3 scripts/enrich-conference-zh.py
python3 scripts/enrich-conference-narrative.py --force
python3 scripts/generate-pipeline-status.py
```

`build-frontend-data.py` 默认重建 recent-derived 的 signals、China、dashboard、landscape 与 content modules，并逐字节保留现有专家 manifest 和两个区域分片。仅在明确需要用本地 full 重建专家时运行 `python3 scripts/build-frontend-data.py --rebuild-experts-from-full`；该模式固定重写 China 与 international 两个分片。

会议资讯的可复刻构建思路：`build-conference-data.py` 负责确定性抓取、清洗和基础字段；`enrich-conference-zh.py` 用 LLM 生成真正中文摘要与逐条 KOL key message；`enrich-conference-narrative.py` 用 signal-to-kol 模型生成会议线索和 KOL 交流点。线索回答“会议说明什么变化”，交流点回答“拿哪条证据去和 KOL 说什么/问什么”。交流点必须归属到某条线索下，并按 `efgar 数据优先 → 竞品应对解读 → 重要疾病进展` 排序。`build-conference-data.py` 会保留已有 `abstractZh`、`kolKeyMessageZh` 和 `llmCurated` narrative，避免确定性重建覆盖 LLM 结果。

GitHub Actions 工作流为 `.github/workflows/weekly-pipeline.yml`，支持手动触发，仅作为轻量兜底。完整语义层与 efgar-wiki 融合以本地工作站/Hermes 周更为准；当前 Hermes 主周更排在每周一 03:15（Asia/Shanghai），位于 efgar-wiki 周更和社区摘要之后。

## 质量检查

提交前建议运行：

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
node --check assets/*.js
```

当前测试覆盖：

- 主页面资源路径与相对导航
- `assets/common.js` 的 URL 协议安全约束
- `scripts/studyClassifier.py` 的证据等级与研究类型分类
- 文献 Signal → Talking Points → PMID evidence 的父子关系、引用覆盖率和 MG-core 排除规则
- 中国作者-机构网络的药物标签归一化与边/节点统计

当前完整质量门：

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
for f in assets/*.js; do node --check "$f" || exit 1; done
git diff --check
```

LLM 语义层是可选增强，不应成为公开基础数据发布的单点故障。若 `DEEPSEEK_API_KEY` 不可用或返回不合格 JSON，`build-frontend-data.py` 生成的确定性 MG-core 主题聚合仍然保留；发布前应检查 `data/signals-weekly.js` 的 `source_policy.published_reference_coverage`。

## 开发约定

- 前端保持浅色、低饱和、医学情报工作台风格。
- HTML / CSS / JS 保持零构建，可直接由 GitHub Pages 托管。
- 页面导航变更需同步 6 个主页面，重定向页不算主导航。
- 动态 HTML 必须 escape，外链必须通过 safe URL helper。
- 会议摘要采用数据管线生成，禁止手改 `data/conference-data.js`。应修改 `scripts/build-conference-data.py` 或 LLM enrich 脚本后重建。
- AAN / EAN 会议页采用 signal-to-kol 结构：会议线索是父层，KOL 交流点挂在线索下；efgar 数据优先传递，竞品数据从应对和区隔角度解读，非产品/非治疗疾病进展最后补充。
- 大型数据文件优先使用分片或懒加载；国际专家分片只生成供离线分析，MSL 前端不加载它。
- Python 数据写入优先使用 `scripts/common/io.py` 中的原子写入工具。
- API key 只从环境变量读取，例如 `EASYSCHOLAR_KEY` 和 `NCBI_API_KEY`。

## 医学与安全边界

- 图谱和 Living Answers 基于 PubMed title / abstract / metadata 层级信息，定位为 MSL 快速进入问题的基础提纲，不替代阅读全文后的医学整合。
- 证据矩阵中的关系是摘要级证据线索，不代表全文级因果结论。
- 社区 audit 当前状态为 `needsReview`，表示 taxonomy 和 assignment 仍需医学事务复核，不表示管线失败。
- `dashboard-data.js` 与 `china-intelligence.js` 已同步到严格 recent（652 / 211）；community recent 分片仍属于独立的 full 社区构建口径。
- 本站仅做拜访前公开材料准备，不采集拜访记录、随访、互动历史或 CRM 数据；团队反馈、内部专家标签和私有材料也不得提交到公开仓库。

## 后续重点

1. 等待 MGFA / AANEM 稳定摘要链接，按会议资讯 signal-to-kol 流程重新接入。
2. 继续抽样审计 MG-core 与 Oxford CEBM 2011-informed I–V 自动筛选规则。
3. 改进公开情报频道的来源覆盖与缓存健康展示，不扩展到拜访记录工作流。
