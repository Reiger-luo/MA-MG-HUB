# 中外差异分析 runbook（两条更新轨道）

诊治格局的两个差异模块更新节奏不同，必须分开维护：

| 模块 | 更新轨道 | 触发 | 脚本 | 产物 |
| --- | --- | --- | --- | --- |
| 近一月中外文献主题差异 | **周更自动** | 每次文献周更 | `analyze-china-foreign-themes.py` | `data/china-foreign-themes.json` |
| 中外指南共识差异 Top 10 | **事件驱动** | 新增/替换指南全文 | `guideline-stance-extract.py` + `analyze-guideline-divergence.py` | `data/guideline-divergence.json` |

两个 JSON 都是本地源（在 `.gitignore` 内），公开前端只发布其派生 `data/landscape-data.js`。
`build-frontend-data.py` 在 JSON 缺失时写 `status=pending_analysis`，页面显示等待分析空态，不报错。

---

## 轨道一：近一月中外文献主题差异（周更滚动）

### 自动运行

`run-weekly-pipeline.py` 在 `build-frontend` **之前**插入该步，顺序不可颠倒（否则前端会读到上一周窗口）：

```python
PipelineStep("analyze-china-foreign-themes",
             py("analyze-china-foreign-themes.py") + ["--days", "30", "--skip-if-current"],
             outputs=[DATA / "china-foreign-themes.json"], optional=True)
```

- `--skip-if-current`：窗口末尾日期与语料篇数都没变时直接退出，不重复计费。
- `optional=True`：LLM 抖动不阻塞发布，但页面状态条会标黄「窗口已 N 天未更新」——过期必须可见，不能静默展示旧数据。
- `--skip-llm` 时该步整体跳过。

### 手动重跑

```bash
python3 scripts/analyze-china-foreign-themes.py --days 30            # 强制重算
python3 scripts/analyze-china-foreign-themes.py --days 30 --skip-if-current
python3 scripts/build-frontend-data.py                                # 重建 landscape-data.js
```

### 流程与口径

1. 从 `data/literature-recent.js` 取窗口内新增文献（按 `entry_date`，即 PubMed 入库时间），按 `china_related` 分中外两组；两侧一律称**「中国」与「国际」**。
2. `deepseek-chat` 逐批给每篇打一个受控主题（18 选 1）、子主题和研究角度。
3. **代码聚合**主题 × 中外计数，保留两侧全部 PMID。
4. LLM 归纳 5 条差异（本月关注点/方法学取向/人群覆盖/终点取向/可及性视角/证据成熟度），PMID 只能引用语料内文献。
5. 代码回验与口径校正（落盘前强制执行，不依赖 prompt 自觉）：
   - 模型给出的 PMID 必须存在且归属阵营正确，否则丢弃；
   - **删除模型自报篇数**（`\d+\s*篇`）：篇数只由代码聚合后经界面展示，模型写的数字会与聚合值冲突；
   - **改写长期判断词**：空白/缺位/代差/落后/完全没有/长期不足/结构性缺失 → 本月未见新增/本窗口未见等；
   - 一侧本窗口 0 篇时置信度强制降为 `medium`；
   - 校正处数写入 `tone_guard`，便于事后核查。

### 措辞纪律（最容易出错的一点）

一个月窗口只有几十篇文献，**某侧本月 0 篇不代表该国在该主题上长期空白或证据落后**。
所有叙述必须是窗口限定的趋势观察（"本月未见新增""若连续数月如此…"），页面固定展示 `scope_note`。
要判断长期差异，只能跨月累积同一口径的结果后另行分析，不能由单月数据推断。

注意：

- `entry_date` 是 PubMed 入库日，不是见刊日；窗口因此可能包含"稍早见刊、本月入库"的文献。
- 篇数按钮显示的是**本窗口内**篇数，不是全库规模；全库证据厚度看竞争矩阵。

---

## 轨道二：中外指南共识差异 Top 10（事件驱动）

### 何时运行

- 拿到新的指南/共识全文（新增国家、新版、重大更新）时。
- 修正提取规则需要重算时。
- 只调整引文回验规则时用 `--reverify-only`，不重复调模型。
- **不要在周更里跑**：几十份 PDF 全量重提取成本高，内容不变时结果也不会变。

### 1. 语料准备

```bash
# 从压缩包或已解压目录生成 pdf/ + texts/ + docs.json
python3 scripts/prepare-guideline-corpus.py --zip ~/Downloads/指南共识.zip
python3 scripts/prepare-guideline-corpus.py --dir ~/Downloads/指南共识
```

脚本会做 GBK 文件名回转、pymupdf/python-docx 抽取、地区判定（中国/国际/中国台湾），
并对 >20 万字符的多病种合集只保留「重症肌无力」章节（`chapter_sliced: true`）。

原始 PDF 保留在本地语料目录，不进仓库：

```
$MG_GUIDELINE_SCRATCH/            默认 ~/.hermes/cache/scratch/guidelines
├── pdf/                          # 解压后的 PDF/DOCX
├── texts/g01.txt … gNN.txt       # 抽取的纯文本
├── docs.json                     # key / 年份 / 地区 / 语言 / 页数 / 字符数
└── stances/g01.json … gNN.json   # 结构化立场卡
```

PDF 原件归档到 efgartigimod-wiki `raw/papers/`，文件名沿用 wiki 的中文前缀规范；多病种合集（如中国罕见病诊疗指南）只归档 MG 章节摘录到 `raw/articles/`，不整体入库。归档前先 SHA256 去重，与既有文件逐字节相同的不要重复入库。

### 2. 抽取立场卡

```bash
python3 scripts/guideline-stance-extract.py            # 可加 --docs g23,g27 只跑指定文件
```

每份指南按 16 个维度（适用范围、诊断、治疗目标、一线、激素、免疫抑制剂、抢救、生物制剂、胸腺切除、危象、眼肌型、特殊人群、随访、可及性、方法学、地域特有）输出立场卡，必须带**原文逐字引文**和所在小节。已有立场卡会跳过，可断点续跑。

### 3. 归纳差异

```bash
python3 scripts/analyze-guideline-divergence.py
python3 scripts/analyze-guideline-divergence.py --reverify-only   # 只重算引文回验
python3 scripts/analyze-guideline-divergence.py --relabel-only    # 只把 gNN 代号换成可读短名
```

### 可读短名（不要露 gNN 代号）

`g01`–`gNN` 只是语料内部代号，读者无法理解。面向页面的文本一律用短名，如「中国 2025 MG 指南」「英国 2025 MG 指南」「MGFA 2016 国际共识」。

- 规则在 `scripts/common/guidelineLabels.py` 的 `RULES`（按文件名特征匹配，顺序敏感，具体规则在前）；
- 新增语料时补一条规则，否则回退到「地区 + 年份 + 文件名截断」的兜底短名；
- 代号只保留在 `evidence[].doc` 与 `corpus[].key`，用于回到 PDF 溯源；
- 命名规则调整后跑 `--relabel-only` 就地修正已有产物，不必重跑 LLM。

流程：维度级中外比对（每维度最多 4 条）→ 汇总排序为 Top 10 → 引文回验。

引文回验口径（`quote_match`）：

| 取值 | 含义 |
| --- | --- |
| `exact` | NFKC 规范化后整段连续命中原文 |
| `partial` | 前 70% 命中（PDF 跨页/连字），或剔除数字后命中（上标引文序号被抽成正文数字） |
| 未命中 | 标记 `quote_verified=false`，页面显示「待核对」 |

---

## 重建前端产物

```bash
python3 scripts/build-frontend-data.py        # 读入两份 JSON，写 landscape-data.js
```

## 发布闭环

数据产物或页面资源变动后，必须走发布闭环（清单哈希 + 资源版本号），否则 `validatePublicRelease.py --require-release` 会失败：

```bash
python3 scripts/run-weekly-pipeline.py --mode rebuild-full --reuse-ingest
```

只改了 `assets/`（JS/CSS）而数据未变时，只需刷新页面版本号并按 [releaseManifestRepair.md](releaseManifestRepair.md) 以同一 run_id 重建清单两次：

```bash
RUN=$(date -u +%Y%m%dT%H%M%SZ)
python3 scripts/updateFrontendReleaseToken.py --release-id "$RUN"
python3 scripts/validatePublicRelease.py --source-only --require-release
```

## 验收清单

1. 两个面板彼此独立：滚动模块带 `⟳ 周更滚动`，指南模块带 `◈ 新指南入库后更新`；各自状态条只引用自己的数字。
2. 滚动模块元信息行的窗口末尾应接近本次周更日期；若出现琥珀色「窗口已 N 天未更新」，说明本周自动重算没跑成，需手动重跑轨道一。
3. 主题差异每侧篇数按钮可点开，弹窗列出该侧全部 PMID，条数与按钮数字一致。
4. 指南差异每条展开后引文回验为「逐字命中/部分命中」，没有大面积「待核对」；语料份数与归档的 wiki 文件对得上。
5. `pytest tests/test_public_release_contract.py tests/test_static_site.py -q` 通过。
6. 抽查 1 条指南差异，回到 PDF 原文确认双方立场表述没有越界。
