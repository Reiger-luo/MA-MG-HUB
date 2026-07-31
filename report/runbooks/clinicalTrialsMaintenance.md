# 临床试验数据维护

情报中心“临床试验”统一使用三套公开注册数据。注册状态用于管线跟踪，不使用 Oxford 证据等级。

## 更新节奏

| 数据源 | 节奏 | 更新方式 | 失败策略 |
|---|---|---|---|
| ClinicalTrials.gov | 每周 | 官方 API v2 自动抓取 | 保留最后良好缓存 |
| ChiCTR | 每 28 天检查一次 | 官方检索页 → 详情页 → `DownloadXml` | WAF 或 XML 失败时保留最后良好缓存，下周继续尝试 |
| ChinaDrugTrials | 每月人工提供文件 | 官方 JSON/CSV/XLS/XLSX 导入 | 文件异常、非完整导出或数量骤降时拒绝覆盖 |

周更在更新缓存后运行 `scripts/build-clinical-trials-data.py`，因此三源缓存变化会同步进入：

- `data/clinical-trials-data.js`：情报中心完整临床试验页；
- `data/clinicalTrialsSummary.js`：首页轻量摘要（含 `weekly_changes` 周更变化要点）；
- `data/release-manifest.js`：成功发布后的文件哈希。

## ClinicalTrials.gov 周更变化提炼

ClinicalTrials.gov 是目前唯一按周抓取的注册源。每次构建时，`build-clinical-trials-data.py` 会把当前 CT.gov 缓存压缩为按 NCT 编号索引的最小快照（状态、首次公示、最近更新、结果发布日期），与上一期快照对比，提炼近 7 天变化并写入首页摘要的 `weekly_changes`：

- 新登记研究（`added`，按首次公示日期落在窗口内）；
- 状态变化（`status_changes`，如 招募中 → 已完成，附中文标签）；
- 结果发布（`results_posted`，窗口内新出现的结果公示日期）；
- 其他字段更新（`updated`，窗口内有更新但不属于以上三类）；
- 移除（`removed`，上一期存在、本期消失的 NCT）。

每组最多保留 5–6 条明细，计数为真实总数。对比基线保存在 `data/clinicaltrials-weekly-changes-snapshot.json` 并随周更提交（本地脚本与 CI workflow 均已纳入 git add）；基线缺失时（如首次运行或新克隆未提交过快照）回退读取 git HEAD 版本，仍不可用则以本次为基线，下一期起自动产出变化。ChiCTR 与 ChinaDrugTrials 更新节奏不同（28 天/月度），暂不参与周更对比。

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
  tests/test_v5_wiring_and_docs.py

python3 scripts/build-clinical-trials-data.py
```

核对要点：

- 差异报告中的新增、更新、移除数量是否合理；
- 三源记录数是否与缓存一致；
- ChinaDrugTrials 是否出现异常大批量移除；
- 临床试验页的更新时间、来源筛选、状态和药物分类是否正常。
