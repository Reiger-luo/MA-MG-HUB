# MA-MG-HUB — MG Intelligence Hub · 学术工作站

> 重症肌无力（MG）团队内部情报工作台。纯前端静态站，GitHub Pages + Cloudflare 部署。
> GitHub: `Reiger-luo/MA-MG-HUB` | 域名字段：Cloudflare 管理

**这是一个 AI 协作项目：Machine（Hermes Agent）做架构+数据管线+编码主体，Codex 仅用于复杂前端组件。**

---

## 项目结构

```
/
├── index.html                 # 首页 Dashboard（速览面板 + 模块入口卡片）
├── assets/
│   ├── main.css               # 全局样式（浅色主题、低饱和度、CSS 变量）
│   └── literature.js          # 前端用文献数据（Gzip 友好格式）
├── data/
│   ├── literature-YYYY-MM.json # 按月分片的原始文献数据
│   ├── literature-recent.js   # 近1年文献（前端加载用，.js 格式享 Gzip）
│   ├── literature-recent.json # 近1年文献原始 JSON
│   └── literature-full.json   # 全量文献（~10k+ 篇）
├── pages/
│   ├── literature.html        # 文献浏览 + 筛选
│   ├── data-ops.html          # 数据管线状态仪表盘
│   ├── progress.html          # 管线进度
│   ├── competitive.html       # 竞争情报（预留）
│   ├── landscape.html         # 诊治格局（预留）
│   ├── materials.html         # 资料库（预留）
│   └── outputs.html           # 产出中心（预留）
├── scripts/
│   ├── fetch-pubmed-weekly.py # 周更 PubMed 抓取
│   ├── fetch-pubmed-full.py   # 全量 PubMed 抓取
│   ├── backfill-study-classification.py  # 证据等级分类（LLM）
│   ├── backfill-journal-metrics.py       # IF/分区回填（Ablesci）
│   ├── browser-enrich.py      # 浏览器降级回填
│   ├── normalize-journal-names.py        # 期刊名规范化
│   └── split-recent-data.py   # 近1年数据分片 + 更新 counter
├── report/
│   ├── 项目规划.md             # 完整 roadmap（必须先读）
│   └── ...                    # 其他分析报告
└── AGENTS.md                  # ⬅️ 本文件
```

---

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | 原生 HTML + CSS + JS（无框架），ECharts（按需） |
| 数据 | JSON 按月分片，`literature.js` 供前端加载 |
| 部署 | GitHub Pages → Cloudflare CDN |
| 数据管线 | Python（Hermes Agent 执行 / cron 调度） |
| API | PubMed E-utilities, Ablesci（IF/分区查询）, ClinicalTrials.gov |
| 编程平台 | Machine（Hermes Agent） 全线主导，Codex 做组件 |

---

## 数据管线流程

```
fetch-pubmed → literature-full.json
  → backfill-study-classification（LLM 分类：先分级）
  → backfill-journal-metrics（仅对有证据等级的期刊查 IF）
  → split-recent-data.py（生成 frontend .js + 更新 counter）
  → git push → Pages 自动部署
```

**关键字段（每条文献记录）：**
- `pmid`, `title`, `abstract`, `authors`, `journal`, `pub_date`
- `journal_full` — 期刊全称（已从 ISO 缩写转换）
- `study_type` — RCT / Cohort / Case-Control / Systematic-Review / Meta-Analysis / Review / Case-Report / Letter / Narrative-Review / Single-Arm / Cross-Sectional / Other / Unclassified
- `evidence_level` — L1 / L2 / L3
- `journal_if` — 最新 IF（Ablesci 查询）
- `journal_quartile` — Q1/Q2/Q3/Q4
- `china_related` — 中国研究标记
- `mechanisms` — 机制标签（AChR / MuSK / LRP4 / FcRn 等）

---

## 现有页面功能

| 页面 | 状态 | 关键功能 |
|------|------|----------|
| index.html | ✅ 完成 | 7 大模块入口卡片 + 速览面板（总文献数、近1年、统计健康状态） |
| pages/literature.html | ✅ 完成 | 文献浏览 + 多选筛选器（年份/机制/IF/分区/证据等级/中国研究）|
| pages/data-ops.html | ✅ 完成 | 数据管线状态 + 数据诊断面板 |
| pages/competitive.html | ⏳ 预留 | 竞争情报 |
| pages/landscape.html | ⏳ 预留 | 诊治格局（阶段 6） |
| pages/materials.html | ⏳ 预留 | 资料库 |
| pages/outputs.html | ⏳ 预留 | 产出中心 |
| pages/progress.html | ⏳ 预留 | 管线进度 |

---

## 开发约定

### 前端

- **浅色主题**：`var(--bg) = #f5f5f7`, `var(--bg2) = #fff`, `var(--bg3) = #e5e5e7`
- **低饱和度**：accent 使用 `#4a7c9b`（蓝灰），标注色：`#c0392b`（红）/ `#27ae60`（绿）
- **CSS 变量**：全部在 `:root` 中定义，放 `assets/main.css`
- **药丸按钮**：`border-radius: 20px` + `padding: 4px 12px`
- **筛选器**：展开式多选 checkbox，不折叠
- **卡片 hover**：`transform: translateY(-2px)` + `box-shadow`
- **骨架屏**：数据加载前显示灰色占位
- **路径前缀**：所有资源路径以 `/MA-MG-HUB/` 为前缀（GitHub Pages）
- **分页**：每页 20 条，底部加载更多按钮
- **年/月筛选**：年份下拉单选 + 月份多选

### 数据管线

- **Python 3.11+**，Hermes Agent 环境下运行
- 管线脚本独立可运行：`python scripts/xxx.py`
- **后处理顺序固定**：先分类 → 再 IF → 再分片
- **文献总量硬编码**：修改 `assets/literature.js` 和 `index.html` 中的数字
- 每次跑完管线立即 `git add + commit + push`

### Git

- commit 用中文描述
- 分支策略：`main` 直接推送（单人项目）
- 禁止提交大文件（data/ 下只提交 .js 和 .json，不做 git lfs）
- 修改后立即推送，不留本地改动

---

## Codex 在本项目的协作模式

**Codex 不做架构决策和 Git 操作！Codex 只写具体前端组件：**

```
Machine（Hermes Agent） → 写好页面骨架 + 数据加载逻辑
                      → 启动 Codex CLI
Codex                   → 接收具体任务（一个组件、一个页面）
                      → 输出到 assets/ 指定文件
Machine（Hermes Agent） → 检查命名/字段一致性 → 集成到页面 → 验收
```

### 可委派的组件类型
- ECharts 图表（趋势图、热力图、分布图）
- 交互式数据矩阵（展开/折叠、多维筛选）
- 筛选器 UI 组件
- 快速导出/报表生成组件
- 文件上传/拖拽交互

### Codex 不应碰的
- 数据管线脚本（Python）
- 项目架构决策
- 数据 JSON 结构变更
- Git 操作
- HTML 骨架和导航

---

## 当前状态（2026-06-12）

- ✅ 阶段 1（信息架构）：完成
- ✅ 阶段 2（数据底座）：完成（全量 10k+ 文献，近1年 520 篇，IF 覆盖 83.2%）
- ✅ 阶段 3（文献页面）：完成
- ⏳ 阶段 4（会议）：待启动
- ⏳ 阶段 5（临床试验/监管）：待启动
- ⏳ 阶段 6（竞争情报/诊治格局）：待启动
- ⏳ 阶段 7（Dashboard 精细打磨）：待启动
- ⏳ 阶段 8（自动化流水线）：待启动
