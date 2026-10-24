# 临床试验数据维护

情报中心“临床试验”统一使用三套公开注册数据。注册状态用于管线跟踪，不使用 Oxford 证据等级。

## 更新节奏

| 数据源 | 节奏 | 更新方式 | 失败策略 |
|---|---|---|---|
| ClinicalTrials.gov | 每周 | 官方 API v2 自动抓取 | 保留最后良好缓存 |
| ChiCTR | 每 28 天检查一次 | 官方检索页 → 详情页 → `DownloadXml`；WAF 挑战由无头浏览器自动求解 | WAF 或 XML 失败时保留最后良好缓存，下周继续尝试 |
| ChinaDrugTrials | 每周 | 官方检索页全量翻页 + 详情页自动抓取；RSS（`keywords` 主题过滤）作新登记早报 | 抓取失败或数量骤降时保留最后良好缓存 |

周更先运行 ChiCTR 刷新，再生成诊治格局、临床试验数据和来源频道，避免同一次发布混用新旧缓存。`scripts/build-clinical-trials-data.py` 会统一阶段标签（包括把 `0`、`N/A` 和空值归为“未标注”），并通过原子写入更新公开产物，因此三源缓存变化会同步进入：

- `data/clinical-trials-data.js`：情报中心完整临床试验页；
- `data/clinicalTrialsSummary.js`：三源轻量摘要、各来源缓存 `revision` 与 CT.gov `weekly_changes` 完整候选差分；
- `data/trial-signals-weekly.js`：三源各自冻结窗口、逐项裁决、来源内强度和 MG 专家解读；
- `data/source-signals.js`：三源原始注册列表，以及与其分离的已裁决 `weekly_signals`；
- `data/weekly-summary.md`：按文献与试验分节的周更简报，试验节直接消费 `trial-signals-weekly.js`；
- `data/release-manifest.js`：成功发布后的文件哈希。

## ClinicalTrials.gov 周更变化提炼

ClinicalTrials.gov 是目前唯一按周抓取的注册源。每次构建时，`build-clinical-trials-data.py` 会把当前 CT.gov 缓存压缩为按 NCT 编号索引的最小快照（状态、首次公示、最近更新、结果发布日期），与上一期快照对比，提炼近 7 天变化并写入首页摘要的 `weekly_changes`：

- 新登记研究（`added`，按首次公示日期落在窗口内）；
- 状态变化（`status_changes`，如 招募中 → 已完成，附中文标签）；
- 结果发布（`results_posted`，窗口内新出现的结果公示日期）；
- 其他字段更新（`updated`，窗口内有更新但不属于以上三类）；
- 移除（`removed`，上一期存在、本期消失的 NCT）。

`weekly_changes` 的兼容明细数组仍可截断，但 `candidate_changes` 保留全部真实差分供信号分析，计数也为真实总数。“其他字段更新”只有在本期与基线上次更新时间确实不同时才计入。对相同缓存和相同窗口重复构建时，底层 diff 为零但会保留本窗口已经发布的非空 `weekly_changes`，避免第二次运行清空本周变化；缓存 revision 真正变化时不套用该保留逻辑。对比基线保存在 `data/clinicaltrials-weekly-changes-snapshot.json` 并随周更提交（本地脚本与 CI workflow 均已纳入 git add）；基线缺失时（如首次运行或新克隆未提交过快照）回退读取 git HEAD 版本，仍不可用则仅保存本次基线并返回 `comparison_available=false`，不把现存研究伪装成新增或更新。ChiCTR 与 ChinaDrugTrials 不强行套用 7 天窗口，而是在各自 28 天/月度缓存真正更新时产生候选。

## 临床试验信号分析

`scripts/enrich-clinical-trial-signals.py` 在三源差分完成后运行。处理顺序固定为：

1. 严格 MG-core 门控，排除 LEMS、SCLC、MG 仅为不可解释小亚组、重复和未经确认的移除；
2. 依据阶段、关键/注册性标识、重要未满足人群、新机制和治疗节点确定 `trialImportance`；
3. 依据新增、状态、结果记录和实际字段变化确定 `updateMateriality`；
4. 确定性代码给出 `include/background/exclude` 与强度上限；
5. MG 专家 LLM 只解释可验证字段，输出 takeaway、战略意义、边界和后续追踪问题；
6. 校验候选—裁决覆盖、登记引用、强度上限和防疗效夸大后，原子写入 `trial-signals-weekly.js`。

强试验信号仅包括新增关键试验或关键试验的高实质更新。关键试验的联系人、普通地点、格式或不可解释字段变化仍为背景；一般试验的高实质更新为中，早期/探索试验的有限真实变化为弱。注册平台出现结果记录或研究完成，只能写为结果/开发里程碑，不能写成疗效阳性。

三个来源各自保留最新有效窗口。某一来源未到更新节奏或读取失败时，该来源的冻结候选和窗口继续保留；只有该来源产生新有效窗口时才替换。所有来源窗口都未推进时脚本不改写公开产物。LLM 失败发生在原子写入之前，因此不会推进基线或清空 last-good。需要在不推进窗口的情况下重做专家解读时运行：

```bash
python3 scripts/enrich-clinical-trial-signals.py --replay-current-window
```

每个来源窗口同时记录缓存实质内容的稳定 `source_revision`（`semantic-v1` 忽略纯抓取时间戳）。发布校验把它与 `clinicalTrialsSummary.js.source_updates` 对齐；只要三源任一缓存实质内容已变化而试验信号仍指向旧 revision，发布就会 fail closed。旧冻结产物在受控 replay 时只有窗口时间仍与当前缓存完全一致、且旧版全缓存摘要仍能匹配时，才允许迁移 revision，避免把旧候选伪装成已分析当前缓存。

首页统一“信号板”只展示通过门控的试验信号，以及三源原始变化计数、比较窗口和更新时间；完整原始变化继续在情报中心临床试验页核查。`source-signals.js` 的 `trialRegistry.items` 保留原始登记列表，`trialRegistry.weekly_signals` 则只接收门控后的试验信号。周更 Markdown 同样按文献/试验分节，不复用旧的文献 Top 3 代替试验判断。文献与试验即使属于同一项目也不跨组聚合。

## ChiCTR 周更

默认周更命令会调用：

```bash
python3 scripts/refresh-chictr-cache.py --interval-days 7 --detail-budget 60
```

脚本读取 `data/chictr-trials-cache.json` 的 `last_verified`：距上次**整库核对完成**不足 7 天时跳过。ChiCTR 与 CT.gov 同频（每周），靠两点把成本压下来：

1. **XML 直连**：官方 `DownloadXml` 的加密路径可跨会话复用，首次拿到后写进缓存的 `xml_url`。此后每条只需 1 次请求取约 14 KB 的 XML，不再取约 130 KB 的详情页，请求量从 2N 降到 N（121 条约 240s → 约 50s）。
2. **分批迁移**：老缓存没有 `xml_url`，`--detail-budget 60` 限定每轮最多回退详情页 60 条，未迁移项保留旧记录并计入 `records_deferred`，且**不推进 `last_verified`**，下一周自动续做，不会把未核对当成已核对。

站点由阿里云 WAF 保护，刷新链路按以下顺序取 Cookie：

1. 运行环境提供 `CHICTR_COOKIE` 时直接使用（最高优先级，适合临时人工会话）；
2. 否则用 `curl_cffi` 的浏览器指纹发起请求；
3. 遇到 `acw_sc__v2` 挑战时，用本机 Playwright（优先系统 Chrome，回退内置 Chromium）执行官网挑战脚本取出 Cookie，再用同一会话继续检索。挑战页按**目标 URL 路径**拦截，`searchproj` / `showproj` / `historyversionpub` 各自可解，单个客户端最多求解 3 次。

```bash
# 自动求解（推荐）
python3 scripts/refresh-chictr-cache.py --force-live

# 自动求解不可用时，人工提供短期 Cookie
export CHICTR_COOKIE='当前浏览器会话中的 Cookie 字符串'
python3 scripts/refresh-chictr-cache.py --force-live
```

### fail-closed 契约

ChiCTR 是三个来源里唯一没有公开 API 的，因此把「抓取失败」与「抓取不全」都当作失败，宁可保留 last-good：

| 情形 | 行为 |
|---|---|
| 站点级拦截（405 / WAF / 挑战页面） | 立即中止整轮，不回退旧数据凑数，缓存不变 |
| 单条记录失败 | 退避 1.5s 重试一次，仍失败才回退；回退条数上限为发现数的 10%（至少 3 条） |
| 结果条数 | 同时受「发现项目数 75%」与「上一版缓存 90%」双重下限约束 |
| 分批迁移未完成 | 写回缓存但标记 `mode=live_partial`，`last_verified` 不前移 |

早期实现只按「发现项目数的 75%」判断，且逐条异常被静默回退，实测出现过「97/121 条沿用旧数据却报告 updated」；上述四条是针对性修补，`tests/test_chictr_weekly.py` 覆盖。

Cookie 只存在于运行环境，禁止写入仓库。在周更管线中该步骤是 optional，失败会记录 warning 并继续发布最后良好数据。

如取得 ChiCTR 官方 JSON/CSV 导出，也可直接导入：

```bash
python3 scripts/refresh-chictr-cache.py --input /absolute/path/chictr-export.csv
```

## ChinaDrugTrials 周更自动抓取

周更管线中的 `refresh-china-drug-trials-cache` 步骤调用：

```bash
python3 scripts/refresh-cde-live-cache.py --no-build --interval-days 6
```

脚本行为：

1. 读取缓存 `generated_at`，距上次成功抓取不足 `--interval-days` 天时跳过（同日重复运行不会重复打站点）；
2. 以 `重症肌无力` 检索官方列表页，按「共 N 页」逐页抓取，再按题名/适应症做 MG 二次门控；
3. 逐条抓取详情页，补全 `试验分期`、`申请人名称`、`首次公示信息日期`、`试验专业题目`、`目标/已入组人数` 等列表页没有的字段；
4. 分期统一归一化为 `1`、`2`、`3`、`4`、`1/2`、`2/3`，`其它 其他说明:生物等效性试验` 这类非分期说明归为未标注；终止/暂停细分状态统一映射到 `TERMINATED` / `SUSPENDED`；
5. 与旧缓存逐字段比较，输出新增、更新、移除，并把「旧缓存为空、本期补全」的字段单独计入 `enriched_count`，不伪装成真实更新；
6. 原子更新 `data/china-drug-trials-cache.json` 与 `data/china-drug-trials-changes.json`，再抓一次 RSS 早报。

### 与 CT.gov 对齐的差分字段

CT.gov 能用 `last_update_date` / `results_posted` 判断「发生了什么更新」，CDE 没有等价字段。为此详情页额外抓取并参与差分：

| 字段 | 含义 | 归类 |
|---|---|---|
| `protocol_version` / `protocol_version_date` | 方案最新版本号与版本日期 | 高实质：登记内容被实质修订 |
| `first_consent_date` / `first_enrollment_date` | 首例知情、首例入组日期 | 中等：真实执行里程碑 |
| `completion_date` | 试验完成日期 | 中等 |
| `enrollment_actual` | 已入组人数 | 中等 |

没有这些字段时，方案修订只能表现为「无变化」；有了它们，CDE 的周更差分才与 CT.gov 同级。实测 51 条中 48 条有版本日期。

::: warning 同一周内重复全量抓取会推进窗口
`changes.generated_at` 是 CDE 的比较窗口标识。同一周内再次全量抓取会生成「0 变化」的新窗口，把该周已发布的 CDE 候选挤掉。需要在一周内重跑构建时，先 `git checkout HEAD -- data/china-drug-trials-changes.json` 恢复本周真实差分集，再 `--force-rebuild` 重算信号。
:::

RSS（`https://www.chinadrugtrials.org.cn/clinicaltrials.search.rss.dhtml?keywords=重症肌无力`）**支持按主题过滤**，带 `keywords` 参数时返回该主题最近 20 条登记，可作为本主题的「新登记早报」：结果写入 `.hermes-audit/cde-rss-snapshot.json`，打印较上次快照新增的登记号，并核对 RSS 已知的 MG 登记是否都已进入缓存（缺失即提示分页或门控异常）。

但 RSS 条目只有题名、链接、登记号和公示日期，**不含状态与分期，也不反映既有试验的状态变化**——而三源实际变化里多数是状态推进（本月 10 项变化中 6 项是状态变更）。因此 RSS 不能替代全量检索，只做早报与覆盖度核对。

参数名必须是复数 `keywords`：写成 `keyword` 时平台忽略该参数并返回全站最近 20 条无关登记（本项目早期探测即因此误判 RSS 不可用于 MG）。

手工全量刷新或排查时：

```bash
python3 scripts/refresh-cde-live-cache.py --force-live --interval-days 0   # 立即抓取并重建
python3 scripts/refresh-cde-live-cache.py --force-live --dry-run           # 只比较不写入
python3 scripts/refresh-cde-live-cache.py --rss-only                       # 只看 RSS 早报
```

若数量低于旧缓存的 60%，命令停止，防止误把分页抓取结果当成完整数据覆盖；确认平台确实大幅删减后才使用 `--allow-large-drop`。

### 人工交接文件仍受支持

运营人员提供的官方导出仍可直接导入，支持 `.json`、`.csv`/`.tsv`、`.xlsx`、二进制 `.xls`、以 `.xls` 命名的 HTML 表格，以及平台「下载 Excel」默认的 Excel 2003 XML（SpreadsheetML，含 `&nbsp;` 等未声明实体的导出也能解析）：

```bash
python3 scripts/refresh-china-drug-trials-cache.py --input /absolute/path/export.xls --dry-run
python3 scripts/refresh-china-drug-trials-cache.py --input /absolute/path/export.xls
```

注意：平台列表页固定每页 20 条，「下载 Excel」只导出当前页。人工交接前必须逐页导出并全部传入，否则会被 60% 数量检查拦下。

## 三源周更对比（为什么现在可以同频）

| 维度 | ClinicalTrials.gov | ChiCTR | ChinaDrugTrials |
|---|---|---|---|
| 官方接口 | API v2（JSON，分页 token） | 无 API，HTML 检索页 + 加密 XML 下载 | 无 API，HTML 检索页 + 详情页 |
| 抓取成本 | 4 次请求 / 354 项 | 121 次请求 / 121 项（XML 直连后） | 3 + 51 次请求 / 51 项 |
| 单次耗时 | 约 10–20s | 约 50s（迁移期约 240s） | 约 35s |
| 访问限制 | 无 | 阿里云 WAF（`acw_sc__v2` 挑战 + 频率拦截） | 无 WAF，仅需首页 Cookie |
| 更新判定字段 | `last_update_date` / `results_posted` | XML 全字段（状态、分期、样本量、入排） | 方案版本日期、首例入组、完成日期 |
| 失败策略 | 保留 last-good | 站点拦截即中止，回退超 10% 即放弃写回 | 保留 last-good，数量骤降拒绝覆盖 |
| 节奏 | 每周 | 每周（原 28 天） | 每周（原人工月度） |
| 触发点 | 周一 05:00 `build-frontend` | 周一 05:00 步骤 6 | 周一 05:00 步骤 7 |

ChiCTR 与 CDE 早期被设成低频，是因为抓取成本高且缺可比较字段，不是因为数据不需要周更。今天的两处改造消掉了这两个前提：ChiCTR 靠 XML 直连把请求量减半、并把不完整抓取改为 fail-closed；CDE 补上方案版本与入组里程碑字段，使「发生了什么更新」可以判定。三个来源因此具备同等周更能力，统一进一次周一任务。

## 周更调度

三个注册源统一由**周一 05:00** 的 Hermes cron 一次性刷新，不再有独立的注册源任务：

| 任务 | 时间 | 入口 | 作用 |
|---|---|---|---|
| MG-HUB Local Weekly Sync (周一) | 周一 05:00 | `~/.hermes/scripts/mg-hub-local-weekly-sync.sh` → `run-weekly-pipeline.py --mode authoritative-full` | 文献周更 + 三源注册数据 + 全量发布 |
| （已删除）MG-HUB 注册源周更 | 原周日 05:00 | — | 已合并进上方周一任务，避免三源分两次更新 |

三源在管线里是连续的三步，构建阶段因此读到同一批新缓存：

| 顺序 | 步骤 | 源 | 抓取节奏 |
|---|---|---|---|
| 6 | `refresh-chictr-cache` | ChiCTR | 每周（`--interval-days 7`），XML 直连 + 分批迁移（`--detail-budget 60`） |
| 7 | `refresh-china-drug-trials-cache` | ChinaDrugTrials | 每周（`--interval-days 1`，同日重跑自动跳过） |
| 8 | `build-frontend`（内部调用 CT.gov API v2） | ClinicalTrials.gov | 每次周更都抓 |

步骤 18 `build-clinical-trials` 之后才统一生成临床试验页、试验信号、来源频道与周报，因此三源不会出现「一次发布混用新旧缓存」。

三源现在同为每周节奏。ChiCTR 的访问克制由「XML 直连把请求量减半」和「分批迁移（每轮最多 60 个详情页）」实现，而不是靠拉长间隔；`--interval-days` 已改为 7。

`--mode trials-only` 保留为**手工工具**，用于周中临时补抓注册源（只跑三源与试验相关产物，不动文献/专家/社区/图谱），已不再由 cron 调度。

约束：

- 工作树必须干净，否则直接退出（避免把人工未提交改动混进自动提交）；
- 只允许在 `main` 分支执行；
- 仅自动提交 `data/**`、`pages/**`、`index.html`，出现其他路径变更立即 fail closed；
- 纯数据/HTML 更新的 push 记录 `CRG_REFRESH_SKIPPED`，不额外提交或再次 push。

CDE 刷新脚本会把本次动作写入 `.hermes-audit/cde-refresh-status.json`（`crawled` / `skipped_interval` / `failed` / `rss_only`），周一的飞书汇报据此区分「本次确实全量抓取」与「间隔未到、沿用 last-good」，不会把上一次的差异当成本期变化重复播报。

## 更新后验证

```bash
python3 -m pytest -q \
  tests/test_cde_live.py \
  tests/test_chictr_adapter.py \
  tests/test_china_drug_trials_import.py \
  tests/test_clinical_trials_fix.py \
  tests/test_clinical_trials_weekly_changes.py \
  tests/test_trial_signal_analysis.py \
  tests/test_v5_wiring_and_docs.py

python3 scripts/refresh-cde-live-cache.py --force-live --dry-run
python3 scripts/build-clinical-trials-data.py
python3 scripts/enrich-clinical-trial-signals.py
python3 scripts/build-source-signals.py
python3 scripts/generate-weekly-summary.py
python3 scripts/validatePublicRelease.py
```

裁决规则（例如 MG-core 判定、分期归一化、重要性分级）修正后，缓存窗口本身没有推进，正常运行会打印 “No source window advanced” 并保留旧产物。此时用以下命令在同一窗口内重算，不会伪造新窗口：

```bash
python3 scripts/enrich-clinical-trial-signals.py --force-rebuild
```

核对要点：

- 差异报告中的新增、更新、移除数量是否合理；
- 三源记录数是否与缓存一致；
- 相同 CT.gov 快照重复构建时是否保持零变化；
- 每个候选是否都有 include/background/exclude 裁决，强度是否未突破确定性上限；
- 关键试验的高实质更新是否可判强，行政更新是否留在背景；
- LEMS、非 MG、小亚组和跨注册重复是否正确排除或合并；
- 首页是否按文献/试验分组独立筛选，试验卡是否显示“注册/开发信号，不代表疗效证据”；
- `source-signals.js` 的试验注册频道是否分别提供三套原始注册源与已裁决 `weekly_signals`；
- `weekly-summary.md` 是否按文献/试验分节，并在无合格试验时发布合法空组；
- 三源缓存 revision 与试验信号窗口是否一致，缓存变化后旧信号能否被发布门禁拦截；
- ChinaDrugTrials 是否出现异常大批量移除；
- 临床试验页的更新时间、来源筛选、状态和药物分类是否正常。
