# MG Intelligence Hub：架构设计与操作手册

> 本手册是当前操作依据。设计与审查请先读 [designReview.md](designReview.md)，全部长期文档见 [文档入口](../README.md)。

## 1. 系统总览

MG Intelligence Hub 是面向 MG 医学事务团队的静态情报工作站。它把公开文献、指南/共识、会议、临床试验、监管状态、知识图谱、社区语义层和 MSL 拜访前准备整合到统一网站。

核心原则：

- 公开网站只承载 Git 管理的公开文件，包括必要的 HTML、CSS、JavaScript、JSON 和当前周报 Markdown。
- full 文献底座与大体量中间产物保留在本地。
- 页面通过 `window.MG_*` 数据对象渲染。
- 社区、图谱、Living Answers 和 MSL action 必须保留来源回链。
- 中国大陆 MSL 使用面只提供公开情报和拜访前材料，不记录拜访。

## 2. 系统角色

| 角色 | 职责 |
| --- | --- |
| GitHub Pages | 承载公开主站 |
| Sites 受控部署 | 从同一组 Git 管理的公开文件生成隔离静态部署包 |
| 本地工作站 | 保存 full 文献和中间数据，运行完整重建 |
| Hermes / 本地计划任务 | 调度 full 驱动周更 |
| GitHub Actions | 质量门和云端轻量兜底 |
| AI coding agent | 实现、测试和维护；不替代医学审核 |

## 3. 页面与导航

| 页面 | 文件 | 核心任务 |
| --- | --- | --- |
| 工作台 | `index.html` | 扫描本周文献信号板、社区动态和数据状态 |
| 情报中心 | `pages/literature.html` | 浏览公开文献、中国情报、会议和临床试验，并按当前标签与筛选条件生成简报 |
| 诊治格局 | `pages/landscape.html` | 解释格局变化、竞争证据和 Living Answers |
| 知识库 | `pages/knowledge.html` | 使用图谱、社区、证据矩阵、专题和中国作者网络 |
| MSL 工作台 | `pages/msl.html` | China-only 专家检索与拜访前准备 |
| 数据状态 | `pages/data-ops.html` | 审查来源、产物、质量和发布一致性 |

历史 URL 由重定向页兼容，不进入主导航。

## 4. 数据架构

### 4.1 两套口径

| 口径 | 权威产物 | 用途 |
| --- | --- | --- |
| 公开滚动层 | `literature-recent.js`、`signals-weekly.js`、`china-intelligence.js` | 近期公开证据和信号 |
| full / 语义底座 | 本地 full、full index、community、knowledge graph | 全库关系、分类、专家和检索 |

`MG_PUBLIC_ROLLING_COUNT` 表示公开滚动层；`MG_SEMANTIC_FULL_COUNT` 和兼容字段 `MG_TOTAL_COUNT` 表示语义底座。两者不能相互替代。

当前数量、时间和一致性状态只从以下位置读取：

- 网站“数据状态”页；
- `data/pipeline-status.js`；
- `data/release-manifest.js`；
- 对应 `data/*.js` 的 `generated_at` 或摘要字段。

人工文档不复制这些动态数字，因此周更不需要修改本手册。

### 4.2 数据流

```text
公开来源与 tracked caches
  ↓
本地 full / weekly 增量
  ↓
MG-core 与证据门控
  ↓
公开滚动层 + 独立来源频道
  ↓
社区语义层 + 知识图谱 + 策展专题 + 中国作者网络
  ↓
前端应用层与发布状态
```

### 4.3 本地文件

以下文件不进入公开部署：

- `data/literature-full.json`
- `data/literature-weekly.json`
- `data/communityCorpusPack.jsonl`
- `data/communityAssignments.jsonl`
- `data/.llm_cache/`
- `data/.llm_cost.log`
- `data/archive/`
- `.hermes-audit/`

### 4.4 主要公开产物

| 产物 | 用途 |
| --- | --- |
| `dashboard-data.js` | 工作台近期信号、页面摘要和数据健康 |
| `literature-recent.js` | 严格 MG-core + 证据等级 I–V 文献 |
| `signals-weekly.js` | 当前周 Signal、证据项和 KOL key points |
| `source-signals.js` | 文献、指南/共识、监管、注册、会议独立频道 |
| `china-intelligence.js` | 严格 recent 的中国相关文献 |
| `community*.js` | taxonomy、卡片、周更、分配和质量审计 |
| `knowledge-graph.js`、`graphHealth.js` | 图谱、证据矩阵和图谱健康 |
| `curated-topics.js`、`wikiTopicCoverage.js` | 策展专题及其社区覆盖 |
| `china-author-network.js` | 中国医院、作者、合作关系和药物线索 |
| `expert-profiles*.js` | China-only 前端画像与离线国际分片 |
| `clinical-trials-data.js` | 多注册源临床试验数据 |
| `clinicalTrialsSummary.js` | 工作台临床试验轻量摘要 |
| `conference-data.js` | 会议摘要与 signal-to-kol 结构 |
| `content-modules.js` | MSL 工作台学术与产品内容模块 |
| `pipeline-status.js` | 当前数据与管线状态 |
| `release-manifest.js` | 最近一次完整 required-step 发布证明 |

## 5. 证据与来源边界

PubMed 主文献流必须先通过 MG-core，再通过证据等级 I–V 门控。分类由 `scripts/studyClassifier.py` 执行，方法学依据见 [evidenceGrading.md](../reference/evidenceGrading.md)。

指南/共识、监管、临床试验注册和会议来源不赋 Oxford 等级，统一通过 `source-signals.js` 保留独立来源身份。

所有自动判断均用于筛选、排序、问题发现和拜访前准备；正式医学结论必须核查全文或官方原始来源。

## 6. 社区、图谱和中国作者网络

- 社区语义层的长期规则见 [communitySemanticLayer.md](../decisions/communitySemanticLayer.md)。
- 中国作者医院网络的长期规则见 [chinaAuthorNetwork.md](../decisions/chinaAuthorNetwork.md)。
- 社区允许 `unassigned` 与冲突状态，避免低置信度文献被强行归类。
- 图谱关系属于 abstract-level 线索，不代表全文级因果。
- 药物标签属于文本相关线索，不代表治疗或疗效判断。

社区分类数量、图谱节点和关系状态由数据状态页显示。中国作者网络的医院数和合作边在知识库页面显示；机构解析率读取 `data/china-author-network.js` 的 `summary.graph_author_hospital_parse_rate`。数据状态页目前不重复展示该解析率。

## 7. 情报中心与会议

首页工作台承载完整文献信号板，提供强度筛选、摘要、列表、关键词云和方法学说明；情报中心不再显示信号 tab。

情报中心保持独立频道：

- 公开文献；
- 中国情报；
- 会议摘要；
- 临床试验。

文献信号使用当前 7 天 PubMed 增量，在首页文献信号板呈现。信号按主题聚合，并保留强度、证据项、证据边界、KOL 讨论问题、PMID、作者和机构线索。文献列表通过 PMID 关联信号强度，可按强、中、弱信号筛选。

页面右上角的简报操作读取当前标签和筛选状态：

- 文献：输出当前筛选文献，最多列出 50 篇；
- 中国情报：输出中国相关文献及证据等级分布，最多列出 50 篇；
- 会议：输出当前会议模块和摘要筛选，最多列出 50 条；
- 临床试验：输出当前药物、状态、来源和阶段筛选，最多列出 50 个药物管线。

简报只在浏览器内生成 Markdown 预览并支持复制。信号简报从首页文献信号板生成；情报中心不保存简报、筛选条件或复制历史。

会议数据由 `build-conference-data.py` 确定性构建，再由可选 enrich 脚本生成中文摘要和 signal-to-kol 叙事。确定性重建必须保留已经通过校验的 LLM 字段。

无稳定主来源的会议不保留伪完整数据，前端显示待接入状态。

## 8. MSL 工作台

MSL 工作台是 China-only：

- 前端加载 `expert-profiles-china.js`；
- `expert-profiles-international.js` 不被任何公开页面加载，只供离线分析；该文件仍由 Git 跟踪并可通过 GitHub Pages 公开访问，因此不得包含私有信息；
- `expert-profiles.js` 只作为分片 manifest；
- 输出是公开证据、话题建议和 PMID 材料；
- 不保存用户选择、行为或历史。

## 9. 临床试验数据

ClinicalTrials.gov、ChiCTR 和 ChinaDrugTrials 采用不同更新方式，但统一进入 `clinical-trials-data.js`。详细流程见 [clinicalTrialsMaintenance.md](../runbooks/clinicalTrialsMaintenance.md)。

失败时保留 last-good cache；不使用低可信第三方数据静默覆盖官方缓存。

## 10. 周更与恢复

本地完整周更：

```bash
bash scripts/run-local-weekly-sync.sh
```

验证模式：

```bash
MG_WEEKLY_DRY_RUN=1 bash scripts/run-local-weekly-sync.sh
```

恢复指定运行：

```bash
python3 scripts/run-weekly-pipeline.py --run-id weekly-example --resume
python3 scripts/run-weekly-pipeline.py --run-id weekly-example --resume --from-step build-source-signals
```

检查点写入 `.hermes-audit/pipeline-runs/`。required 步骤全部成功后才更新 `release-manifest.js`；optional 步骤失败只记录 warning 并按其定义使用 fallback。

GitHub Actions 仅手动 `workflow_dispatch`，用于质量门和轻量兜底，不替代本地 full 驱动周更。

## 11. 文档与自动报告

文档生命周期由 `AGENTS.md`、[report/README.md](../README.md) 和自动测试共同约束：

- `report/` 根目录只允许文档索引；
- 当前说明、路线图、runbook、参考和架构决定分目录保存；
- 自动报告写入 `.hermes-audit/reports/`；
- 默认覆盖 `*Latest.md`，不按日期无限生成；
- 当前数量只进入数据状态产物，不进入人工文档；
- 历史方案由 Git 历史保存。

## 12. 开发约定

- 原生 HTML/CSS/JavaScript 保持零前端编译步骤。
- 文件名和变量名使用英文 camelCase，代码注释使用中文。
- 页面动态文本必须 escape，外链必须经过 safe URL helper。
- 大文件使用懒加载或分片。
- Python 数据写入优先使用 `scripts/common/io.py` 的原子写入。
- API key 只从环境变量读取。
- 修改主导航时同步所有主页面。

## 13. 验证

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py scripts/common/*.py
for file in assets/*.js; do node --check "$file" || exit 1; done
bash scripts/build-sites-static.sh
git diff --check
```

## 14. 后续建设方向

1. 按 `roadmap/decisionIntelligencePlan.md` 串行推进 Decision Brief、Claim–Evidence、Evidence Delta、中国证据和质量标签。
2. 持续提高来源覆盖、引用回验和发布一致性。
3. 保持公开静态架构，只有明确触发条件出现时才评估窄职责后端。
4. 持续抽样审计 MG-core、证据分级、社区边界和机构归一化。
