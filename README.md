# MA-MG-HUB

MG Intelligence Hub 是面向重症肌无力（myasthenia gravis, MG）医学事务工作的静态学术情报工作站。项目把 PubMed 文献、指南/共识、会议摘要、临床试验注册、中国监管状态、知识图谱、医学事务社区层和 MSL 拜访准备组织为可追溯的公开信息。

本站服务于中国大陆 MSL 的公开学术情报、专家证据检索和拜访前材料准备；不记录拜访，不提供随访、CRM、互动历史、私有后端或浏览器持久化功能。

- 线上站点：[https://reiger-luo.github.io/MA-MG-HUB/](https://reiger-luo.github.io/MA-MG-HUB/)
- 文档入口：[report/README.md](report/README.md)
- 5 分钟设计与审查入口：[report/current/designReview.md](report/current/designReview.md)
- 当前操作手册：[report/current/operationsManual.md](report/current/operationsManual.md)
- 周报素材：[data/weekly-summary.md](data/weekly-summary.md)

## 项目定位

MA-MG-HUB 重点回答：

- 本周有哪些值得关注的 MG 学术信号？
- 如何按当前文献、信号、中国、会议或临床试验筛选生成可复制简报？
- 中国相关证据、机构和作者线索有哪些变化？
- MG 证据网络形成了哪些主题、机制和治疗社区？
- 具体治疗问题目前可以形成怎样的 abstract-level 回答？
- MSL 拜访专家前应准备哪些证据、话题和材料模块？
- 数据产物、社区归类和图谱状态是否健康？

## 页面

| 模块 | 页面 | 主要能力 |
| --- | --- | --- |
| 工作台 | [index.html](index.html) | 近期信号、社区动态、工作流状态和数据健康 |
| 情报中心 | [pages/literature.html](pages/literature.html) | 公开文献、信号板、中国情报、会议摘要、临床试验和当前上下文简报 |
| 诊治格局 | [pages/landscape.html](pages/landscape.html) | 格局洞察、竞争矩阵、临床管线和 Living Answers |
| 知识库 | [pages/knowledge.html](pages/knowledge.html) | 知识图谱、医学事务社区、证据矩阵、专题和中国作者网络 |
| MSL 工作台 | [pages/msl.html](pages/msl.html) | China-only 专家画像、内容模块、拜访话题建议和 PMID 清单 |
| 数据状态 | [pages/data-ops.html](pages/data-ops.html) | 数据源、公开产物、community audit、graph health 和后端选项 |

历史页面 `pages/materials.html`、`pages/outputs.html`、`pages/progress.html` 和 `pages/competitive.html` 仅保留重定向入口。

## 数据架构

网站同时维护两个用途不同的口径：

| 口径 | 权威产物 | 用途 |
| --- | --- | --- |
| 公开滚动层 | `literature-recent.js`、`signals-weekly.js`、`china-intelligence.js` | 工作台、情报中心、信号板和中国情报；社区 recent 与文献 recent 共用同一 PMID 集合 |
| full / 语义底座 | 本地 full、`literature-full-index.js`、community、knowledge graph | 知识图谱、社区归类、专家画像和跨库检索 |

当前数量、生成时间和一致性状态不写入本文档，统一查看：

- 网站“数据状态”页；
- `data/pipeline-status.js`；
- `data/release-manifest.js`；
- `data/weekly-summary.md`。

数据流：

```text
PubMed / ClinicalTrials.gov / ChiCTR / ChinaDrugTrials / 指南 / 监管 / 会议
  ↓
本地 full 与 tracked last-good caches
  ↓
MG-core gate + 证据等级 I–V gate + 独立来源频道
  ↓
公开滚动层 / 社区语义层 / 知识图谱 / 策展专题 / 中国作者网络
  ↓
工作台 / 情报中心 / 诊治格局 / 知识库 / MSL 工作台 / 数据状态
```

公开网站只部署必要的 HTML、CSS、JavaScript 和 JSON。full 文献、weekly 临时输入、LLM 缓存、成本日志和详细审计保留在本地。

## 核心边界

- PubMed 主文献流同时执行 MG-core 与证据等级 I–V 门控。
- 指南/共识、监管、注册和会议保留为独立来源频道，不冒充 Oxford 文献证据。
- MSL 前端只加载 `expert-profiles-china.js`；国际专家分片没有页面加载路径，只供离线分析。该 tracked 文件仍可通过 GitHub Pages 公开访问，因此只能包含公开元数据。
- 页面不采集拜访记录、团队反馈、内部专家标签或任何需要登录保存的数据。
- GitHub Actions 不持有 full，也不生成公开数据；它只读校验已提交 release，避免部分构建覆盖 last-good 产物。

## 技术栈

- 前端：原生 HTML / CSS / JavaScript，零前端编译步骤
- 数据加载：`window.MG_*` 全局对象
- 数据管线：Python 3.11+
- 主发布：GitHub Pages
- Sites 受控部署构建：`scripts/build-sites-static.sh`
- 自动化：本地/Hermes full 驱动周更；GitHub Actions 手动只读发布校验

## 本地查看

```bash
python3 -m http.server 8000
```

然后访问 `http://localhost:8000/`。

## 周更

本地完整周更：

```bash
bash scripts/run-local-weekly-sync.sh
```

仅验证、不提交：

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

可恢复管线：

```bash
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id weekly-example
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id weekly-example --resume
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id weekly-example --resume --from-step build-source-signals
```

只读验证使用 `python3 scripts/run-weekly-pipeline.py --mode validate-only`；仅在明确复用当前自然周 `literature-ingest-latest.json` 时，才可使用 `--mode rebuild-full --reuse-ingest`。审计检查点写入 `.hermes-audit/pipeline-runs/`。只有完整公开产物契约全部生成、跨产物口径校验通过后才更新 `data/release-manifest.js`；同一 run id 同时写入活动页面资源 URL，降低 HTML、脚本和数据的缓存混版风险。

ChinaDrugTrials 的人工导入流程见 [临床试验数据维护](report/runbooks/clinicalTrialsMaintenance.md)。

## 质量检查

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
for file in assets/*.js; do node --check "$file" || exit 1; done
git diff --check
```

## 文档与审计

- `report/` 只保存当前文档、路线图、runbook、长期参考和架构决定。
- 自动报告统一写入 `.hermes-audit/reports/`，默认覆盖 `*Latest.md`。
- 历史方案和已完成审查由 Git 历史保存，不留在当前文档树。
- 文档生命周期由 `AGENTS.md` 和 `tests/test_document_lifecycle.py` 自动约束。

## 医学与安全边界

- 图谱、社区、Living Answers 和 Decision Brief 主要基于 title/abstract/metadata，不能替代全文医学审核。
- 自动证据分级只用于筛选与排序，正式医学材料必须核查原文。
- 药物、机构和合作关系标签是公开证据线索，不代表因果、疗效或内部评价。
- API key 只从环境变量读取，不进入前端、报告或公开数据。
