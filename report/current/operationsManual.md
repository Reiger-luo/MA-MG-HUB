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
| GitHub Actions（发布验证） | 手动运行测试、静态构建与当前 release 只读校验；不生成或提交数据 |
| GitHub Actions（代码图） | 对同仓代码 PR 输出 advisory 评论；graph-covered 源码进入 `main` 后完整重建 Graph 并在 summary 留证；不读取 full、不生成数据、不阻断合并 |
| AI coding agent | 实现、测试和维护；不替代医学审核 |

## 3. 页面与导航

| 页面 | 文件 | 核心任务 |
| --- | --- | --- |
| 工作台 | `index.html` | 全宽分组扫描本周文献信号、临床试验信号和数据状态 |
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
| 公开滚动层 | `literature-recent.js`、`signals-weekly.js`、`trial-signals-weekly.js`、`china-intelligence.js` | 近期公开证据和分来源信号；`literature-recent.js` 的 PMID 集合是社区 recent 的唯一窗口契约 |
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
周更前基线差分，生成本周真实新增 PMID 清单
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
- `data/literature-ingest-latest.json`
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
| `trial-signals-weekly.js` | 三源试验冻结窗口、逐项裁决、来源内强度与 MG 专家解读 |
| `source-signals.js` | 文献、指南/共识、监管、三源试验注册、会议独立频道 |
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

指南/共识、监管、临床试验注册和会议来源不赋 Oxford 等级，统一通过 `source-signals.js` 保留独立来源身份。临床试验信号另按“试验重要性 × 本轮更新实质性”给出来源内强/中/弱；它表示注册与开发里程碑的跟踪优先级，不与文献证据强度比较，也不代表疗效结论。

所有自动判断均用于筛选、排序、问题发现和拜访前准备；正式医学结论必须核查全文或官方原始来源。

## 6. 社区、图谱和中国作者网络

- 社区语义层的长期规则见 [communitySemanticLayer.md](../decisions/communitySemanticLayer.md)。
- 中国作者医院网络的长期规则见 [chinaAuthorNetwork.md](../decisions/chinaAuthorNetwork.md)。
- 社区允许 `unassigned` 与冲突状态，避免低置信度文献被强行归类。
- 社区“本周新增”和专题“本周新证据”只读取 `literature-ingest-latest.json` 中相对周更前基线真正新增的 PMID；14 天重叠抓取只用于防漏，不计为重复新增。
- 专题的新证据状态按“专题 × 社区”计算：仅传播到该 PMID 的 primary/secondary 社区；专题历史 PMID 作为长期知识底座单独展示。
- 从社区进入相关专题时保留社区筛选参数；专题页的新证据数量、状态和 PMID 随当前社区过滤，长期专题 PMID 不参与“本周”计数。
- 图谱关系属于 abstract-level 线索，不代表全文级因果。
- 药物标签属于文本相关线索，不代表治疗或疗效判断。

社区分类数量、图谱节点和关系状态由数据状态页显示。中国作者网络的医院数和合作边在知识库页面显示；机构解析率读取 `data/china-author-network.js` 的 `summary.graph_author_hospital_parse_rate`。数据状态页目前不重复展示该解析率。

## 7. 情报中心与会议

首页工作台承载统一“信号板”，按“文献信号 / 临床试验信号”分组。两组分别提供强度统计、筛选和方法学说明，不跨来源聚合或比较；情报中心不再显示信号 tab。

情报中心保持独立频道：

- 公开文献；
- 中国情报；
- 会议摘要；
- 临床试验。

文献信号只使用 `literature-ingest-latest.json` 的 `added_pmids`，窗口起止日期沿用该 ingest manifest，不再按文献最大日期反推“最近 7 天”。信号在首页“文献信号”组呈现，按主题聚合，并保留强度、证据项、证据边界、KOL 讨论问题、PMID、作者和机构线索。文献列表通过 PMID 关联信号强度，可按强、中、弱信号筛选。

页面右上角的简报操作读取当前标签和筛选状态：

- 文献：输出当前筛选文献，最多列出 50 篇；
- 中国情报：输出中国相关文献及证据等级分布，最多列出 50 篇；
- 会议：输出当前会议模块和摘要筛选，最多列出 50 条；
- 临床试验：输出当前药物、状态、来源和阶段筛选，最多列出 50 个药物管线。

文献列表与中国情报的期刊分区统一采用 EasyScholar `xr` 字段返回的“新锐分区”（如 1 区、2 区），旧中科院分区（CAS/sciBase）已不再使用。简报只在浏览器内生成 Markdown 预览并支持复制。信号简报从首页信号板生成，按文献与试验两节分别解释强/中/弱；情报中心不保存简报、筛选条件或复制历史。

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

ClinicalTrials.gov、ChiCTR 和 ChinaDrugTrials 采用不同更新方式，但统一进入 `clinical-trials-data.js` 和 `source-signals.js` 的试验注册频道。三源分别按每周、每 28 天和月度人工节奏产生候选；`trial-signals-weekly.js` 为每个来源保留自己的最新比较窗口，因此未到更新节奏或来源暂时失败时不会清空 last-good。来源频道同时保留原始 `items` 与门控后的 `weekly_signals`，两者不可互相替代。详细流程见 [clinicalTrialsMaintenance.md](../runbooks/clinicalTrialsMaintenance.md)。

ClinicalTrials.gov 每次构建对比上一期快照（`clinicaltrials-weekly-changes-snapshot.json`），把近 7 天新登记、状态变化、结果发布、字段更新和移除提炼为 `clinicalTrialsSummary.js` 的 `weekly_changes`。全部变化作为试验信号候选，不受首页展示条数截断影响。首次运行只建立基线；相同快照重复构建保持零变化。阶段字段统一归一化，公开 JS 和对比快照均使用原子写入。

试验信号先经过严格 MG-core、移除/重复/行政变化排除，再由确定性规则给出 `trialImportance`、`updateMateriality` 和强度上限。关键试验新增或发生高实质更新可为强；关键试验的中等更新、一般试验的高实质更新或战略性早期项目的重要变化可为中；其余真实而有限的开发变化为弱。MG 专家 LLM 只接收结构化注册字段并解释临床/开发意义、限制和追踪问题，不得提高强度、改写登记号，或把“结果已上传”“研究完成”写成疗效阳性。首页试验组显示三源变化计数、比较窗口、更新时间与管线矩阵入口；完整原始变化继续在临床试验页查看。

`clinicalTrialsSummary.js.source_updates` 为三源缓存记录稳定 revision，必须同时等于原始缓存的当前语义 revision 和 `trial-signals-weekly.js.source_windows[*].source_revision`；CT.gov 的差分日期还必须与其信号窗口一致。任一来源缓存推进但摘要或信号分析未更新时，公开发布校验失败。来源频道和 `weekly-summary.md` 均在试验 enrichment 之后生成，周报按文献/试验分节并允许合法空试验组，不能沿用旧的纯文献周报逻辑。

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

后台周更从干净的 `main` 开始，只允许自动提交 `data/**`、`pages/**` 和 `index.html` 中已跟踪的生成产物。若构建过程修改 `scripts/**`、`assets/*.js`、`worker/**`、`tests/**` 或其他白名单外路径，任务在 commit 前 fail closed，保留现场等待人工 review。成功 push 后脚本以 push 前远端 SHA 调用 `scripts/refreshReviewGraphAfterPush.sh`；常规数据/HTML 周更记录 `CRG_REFRESH_SKIPPED`，不产生第二次 commit/push。

恢复指定运行：

```bash
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id weekly-example --resume
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id weekly-example --resume --from-step build-source-signals
```

三个模式的边界固定如下：`authoritative-full` 抓取、合并、完整重建并发布；`rebuild-full --reuse-ingest` 只在人工确认复用当前自然周 ingest 时重建；`validate-only` 只读核对当前公开产物和 release manifest。检查点写入 `.hermes-audit/pipeline-runs/`。`merge-weekly` 原子写入本地 `literature-ingest-latest.json`，记录本周累计真实新增与本次更新 PMID；同一自然周重跑累积新增，跨周自动清空。

完整发布使用集中维护的公开产物白名单，检查声明的全局变量、社区分片、文献/社区 recent PMID 集合、信号 ingest 口径、工作台计数和 release hash。required 步骤全部成功后才更新 `release-manifest.js`；状态生成与清单采用两遍收口，使 `pipeline-status.js` 的一致性结论也进入最终哈希。活动页面的 CSS、脚本和数据 URL 同步使用该 run id 作为缓存版本。当前公开 JS 与清单出现哈希不符、缺失或未入清单时，首页和数据状态显示发布漂移，不再沿用历史“完整发布成功”。optional 步骤失败只记录 warning 并按其定义使用 fallback。

发布验证 workflow 仍仅手动 `workflow_dispatch`，运行测试、`validate-only` 和静态构建；权限为只读，不替代本地 full 驱动周更，也不会提交局部生成结果。PR 代码图 workflow 由同仓代码 PR 触发，只对 `scripts/**`、`assets/*.js`、`worker/**` 和 `tests/**` 输出 advisory 评论。Post-push Graph workflow 在这些源码或 Graph 配置进入 `main` 后完整重建一次并把证据写入 summary；两个 workflow 都不读取 full、不生成 `data/**`、不更新 release manifest，也不以风险分数阻断合并。

数据状态中的“更新时间”优先读取产物自身 `generated_at`、`last_verified` 或 `snapshot_date`，不以文件 mtime 伪装数据新鲜度。公开 rolling 权威源固定为 `literature-recent.js`；社区 recent 只用于覆盖核对。过期来源显示黄色 warning，缺失或错误显示红色。

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
- 代码 review 遵循 [Code Review Graph 审查流程](../runbooks/codeReviewGraph.md)：图谱可用时先做变更与影响分析，再读 diff、核对动态契约并运行测试；CRG 不可用时降级为源码检索和测试。
- 用户批准的源码修改成功 push 或上线后，调用仓库 Skill `$refresh-review-graph` 在已推送 commit 上完整重建本地图谱并做二次影响检查；Skill 不替代 push 授权，失败必须在交付结果中披露。
- 已获准运行的后台发布器在单次 push 后调用同一共享 Graph 脚本；自动提交严格限制在声明的生成产物白名单，任何源码漂移都必须转入人工 review。

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
