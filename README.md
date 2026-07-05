# MA-MG-HUB

MG Intelligence Hub 是面向重症肌无力（myasthenia gravis, MG）医学事务工作的静态学术情报工作站。项目将 PubMed 文献、会议摘要、ClinicalTrials 管线、中国监管状态、知识图谱、医学事务社区层和 MSL 拜访准备整合到一个 GitHub Pages 网站中。

- 线上站点：[https://reiger-luo.github.io/MA-MG-HUB/](https://reiger-luo.github.io/MA-MG-HUB/)
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
| 情报中心 | [pages/literature.html](pages/literature.html) | 近一年文献、14 天信号、中国情报、会议摘要 |
| 诊治格局 | [pages/landscape.html](pages/landscape.html) | 月度格局洞察、竞争矩阵、ClinicalTrials 管线、Living Answers |
| 知识库 | [pages/knowledge.html](pages/knowledge.html) | 知识图谱、医学事务社区、证据矩阵、专题层、跨库检索 |
| MSL 工作台 | [pages/msl.html](pages/msl.html) | 专家画像、内容模块、拜访话题建议、PMID 文献清单 |
| 数据状态 | [pages/data-ops.html](pages/data-ops.html) | 数据源、公开产物、community audit、graph health、后端选项 |

历史页面 `pages/materials.html`、`pages/outputs.html`、`pages/progress.html` 和 `pages/competitive.html` 仅保留重定向入口。

## 数据口径

当前站点同时存在两个数据口径，维护时必须区分：

| 口径 | 当前规模 | 用途 |
|---|---:|---|
| 公开滚动层 | 近一年文献 1,154 篇；中国相关 323 篇；14 天候选信号 38 条 | 工作台、情报中心、信号板、中国情报 |
| full / 语义底座 | full 轻索引与社区层 10,635 篇 | 知识图谱、社区归类、专家画像、跨库检索 |

Dashboard 与 `pipeline-status.js` 现在统一显示两套口径：`public_rolling_count` 为 1,154 篇，`semantic_full_count` 为 10,635 篇。full 口径来自 raw full / full-index / community full 产物；recent 口径分别记录 `literature-recent.js` 与 `communityAssignmentsRecent.js`，当前生效的 active recent 以实际文件更新时间较新的那个为准。`MG_SEMANTIC_FULL_COUNT` 和 `MG_TOTAL_COUNT` 只作为 recent 文件头部的声明与兼容校验字段。

核心数据产物：

| 产物 | 当前规模 | 用途 |
|---|---:|---|
| `data/literature-recent.js` | 1,154 篇 | 近一年公开文献列表 |
| `data/signals-weekly.js` | 38 条 | 近 14 天候选信号 |
| `data/china-intelligence.js` | 120 条摘要 | 中国情报 |
| `data/literature-full-index.js` | 10,635 篇 | full 文献轻索引，不含 abstract |
| `data/communityTaxonomy.js` | 10 个社区 | 医学事务主题 taxonomy |
| `data/communityAudit.js` | 10,635 篇 audit | 社区归类质量状态 |
| `data/knowledge-graph.js` | 55 节点、334 核心边、180 行证据矩阵 | 知识图谱与证据矩阵 |
| `data/expert-profiles-china.js` | 8,926 位 | 中国作者-机构画像 |
| `data/expert-profiles-international.js` | 43,485 位 | 国际作者-机构画像 |
| `data/conference-data.js` | 458 条摘要 | MGFA、AAN、EAN 等会议资讯 |

## 数据流

```text
PubMed / ClinicalTrials.gov / EasyScholar / 中国监管状态 / 会议来源
  ↓
本地 full 底座：literature-full.json、communityAssignments.jsonl、communityCorpusPack.jsonl
  ↓
公开滚动层：literature-recent.js、signals-weekly.js、china-intelligence.js
  ↓
语义层：communityTaxonomy.js、communityCards.js、communityWeekly.js、communityAssignments-*.js
  ↓
图谱与策展层：knowledge-graph.js、graphHealth.js、curated-topics.js、wikiTopicCoverage.js
  ↓
应用层：dashboard-data.js、expert-profiles*.js、content-modules.js、conference-data.js
```

公开网站只部署 HTML / CSS / JS / JSON。`data/literature-full.json`、weekly 临时数据、LLM 缓存、成本日志、拜访记录和内部专家标签留在本地，不进入公开仓库。

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

常用单项重建：

```bash
python3 scripts/build-frontend-data.py
python3 scripts/buildFullLiteratureIndex.py
python3 scripts/buildCommunityData.py
python3 scripts/build-knowledge-data.py
python3 scripts/buildLandscapeInsights.py
python3 scripts/generate-pipeline-status.py
```

GitHub Actions 工作流为 `.github/workflows/weekly-pipeline.yml`，支持手动触发，仅作为轻量兜底。完整语义层与 efgar-wiki 融合以本地工作站/Hermes 周更为准；当前 Hermes 主周更排在每周一 03:15（Asia/Shanghai），位于 efgar-wiki 周更和社区摘要之后。

## 质量检查

提交前建议运行：

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py
node --check assets/*.js
```

当前测试覆盖：

- 主页面资源路径与相对导航
- `assets/common.js` 的 URL 协议安全约束
- `scripts/studyClassifier.py` 的证据等级与研究类型分类

## 开发约定

- 前端保持浅色、低饱和、医学情报工作台风格。
- HTML / CSS / JS 保持零构建，可直接由 GitHub Pages 托管。
- 页面导航变更需同步 6 个主页面，重定向页不算主导航。
- 动态 HTML 必须 escape，外链必须通过 safe URL helper。
- 大型数据文件优先使用分片或懒加载，例如 full index、国际专家画像和 community assignment shards。
- Python 数据写入优先使用 `scripts/common/io.py` 中的原子写入工具。
- API key 只从环境变量读取，例如 `EASYSCHOLAR_KEY` 和 `NCBI_API_KEY`。

## 医学与安全边界

- 图谱和 Living Answers 基于 PubMed title / abstract / metadata 层级信息，定位为 MSL 快速进入问题的基础提纲，不替代阅读全文后的医学整合。
- 证据矩阵中的关系是摘要级证据线索，不代表全文级因果结论。
- 社区 audit 当前状态为 `needsReview`，表示 taxonomy 和 assignment 仍需医学事务复核，不表示管线失败。
- 拜访记录、团队反馈、内部专家标签、私有材料和任何敏感业务数据不得提交到公开仓库。

## 后续重点

1. 将 MSL 拜访助手升级为可保存、可导出、可 follow-up 的工作流。
2. 补齐 AANEM 结构化会议摘要数据。
