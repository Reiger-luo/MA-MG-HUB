# 临床试验数据维护

情报中心“临床试验”统一使用三套公开注册数据。注册状态用于管线跟踪，不使用 Oxford 证据等级。

## 更新节奏

| 数据源 | 节奏 | 更新方式 | 失败策略 |
|---|---|---|---|
| ClinicalTrials.gov | 每周 | 官方 API v2 自动抓取 | 保留最后良好缓存 |
| ChiCTR | 每 28 天检查一次 | 官方检索页 → 详情页 → `DownloadXml` | WAF 或 XML 失败时保留最后良好缓存，下周继续尝试 |
| ChinaDrugTrials | 每月人工提供文件 | 官方 JSON/CSV/XLS/XLSX 导入 | 文件异常、非完整导出或数量骤降时拒绝覆盖 |

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

## ChiCTR 月更

默认周更命令会调用：

```bash
python3 scripts/refresh-chictr-cache.py
```

脚本读取 `data/chictr-trials-cache.json` 的 `last_verified`。距离上次成功核对不足 28 天时跳过；达到 28 天时运行官方中英文疾病检索并逐条下载 XML。

阿里云 WAF Cookie 通过运行环境提供，禁止写入仓库：

```bash
export CHICTR_COOKIE='当前浏览器会话中的 Cookie 字符串'
python3 scripts/refresh-chictr-cache.py --force-live
```

可用 `--interval-days` 调整间隔。实时刷新失败时命令返回非零状态，但不会改写缓存；在周更管线中该步骤是 optional，因此会记录 warning 并继续发布最后良好数据。

如取得 ChiCTR 官方 JSON/CSV 导出，也可直接导入：

```bash
python3 scripts/refresh-chictr-cache.py --input /absolute/path/chictr-export.csv
```

## ChinaDrugTrials 月度人工交接

运营人员每月只需提供从药物临床试验登记与信息公示平台下载的完整 MG 查询结果。支持：

- `.json`
- `.csv` / `.tsv`
- `.xlsx`
- 二进制 `.xls`
- 以 `.xls` 命名的 HTML 表格导出

如平台把结果拆成多个文件，可重复传入 `--input`。建议先做只读比较：

```bash
python3 scripts/refresh-china-drug-trials-cache.py \
  --input /absolute/path/export-1.xls \
  --input /absolute/path/export-2.xls \
  --dry-run
```

确认后执行正式更新：

```bash
python3 scripts/refresh-china-drug-trials-cache.py \
  --input /absolute/path/export-1.xls \
  --input /absolute/path/export-2.xls
```

正式命令会依次完成：

1. 识别官方表头并只保留重症肌无力记录；
2. 按 CTR 登记号合并去重；
3. 把中文招募状态归一化为网站统一状态；
4. 与上次缓存逐字段比较；
5. 输出 `data/china-drug-trials-changes.json`，记录新增、更新和移除；
6. 原子更新 `data/china-drug-trials-cache.json`；
7. 自动重建临床试验页、首页摘要和数据状态页。

若新文件数量低于旧缓存的 60%，命令会停止，防止误把分页文件或增量文件当成完整数据覆盖。只有人工确认平台本月确实大幅删减后，才使用 `--allow-large-drop`。

## 更新后验证

```bash
python3 -m pytest -q \
  tests/test_chictr_adapter.py \
  tests/test_china_drug_trials_import.py \
  tests/test_clinical_trials_fix.py \
  tests/test_clinical_trials_weekly_changes.py \
  tests/test_trial_signal_analysis.py \
  tests/test_v5_wiring_and_docs.py

python3 scripts/build-clinical-trials-data.py
python3 scripts/enrich-clinical-trial-signals.py
python3 scripts/build-source-signals.py
python3 scripts/generate-weekly-summary.py
python3 scripts/validatePublicRelease.py
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
