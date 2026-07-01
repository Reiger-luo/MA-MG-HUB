# MA-MG-HUB 二次审查报告：Codex 判断版

审查日期：2026-07-01
审查对象：

- `report/website-code-review-2026-07-01.md`
- `report/code-review-2026-07-01.md`
- 当前仓库前端页面、`assets/*.js`、`scripts/*.py`、GitHub Actions 配置与公开数据产物体积

本报告不是两份报告的合并稿，而是基于二次核验后的优先级重排。

## 结论先行

两份报告都有价值，但都不够精确。

第一份报告的风险意识更接近我对这个项目的判断：安全边界、流水线可信度、工程化缺口确实应该排在前面。但它把“所有 `innerHTML` 都未转义”说得过粗，实际代码里很多文本内容已经做了 `escapeHtml`。

第二份报告的优点是看到了项目架构和若干具体 bug，例如 EasyScholar 密钥、懒加载回调丢失、导航重复。但它低估了前端安全问题，并且有事实错误：`node_modules` 目录当前存在于本地，但被 `.gitignore` 忽略，`git ls-files node_modules` 结果为 0，所以不是“已提交到仓库”。

我自己的判断：MA-MG-HUB 当前不是“代码马上崩”的状态，语法检查通过，功能结构也清楚；真正的风险是“医学情报站的可信度基建不够硬”。优先级应该是：

1. 先消掉密钥、SSL、属性上下文 XSS 这类安全边界问题。
2. 再补最小测试与 CI 质量门，防止数据管线静默生成错误产物。
3. 然后处理大数据加载、base path、重复导航和可访问性。

## 我已核验的事实

本次我做了快速静态核验，没有执行会改写数据的完整周更管线。

- `node --check assets/*.js` 通过。
- `python3 -m py_compile scripts/*.py` 通过。
- `python` 命令在当前 shell 不存在，需使用 `python3` 或 CI 中的 `python`。
- `scripts/easyscholar_api.py` 是已跟踪文件，并包含 EasyScholar fallback key。
- 多个脚本全局禁用 SSL 证书校验，不只 `fetch-pubmed-weekly.py`。
- 根目录没有 `requirements.txt`、`pyproject.toml`、`package.json` 或 lock 文件。
- GitHub Actions 只安装 `requests`，且只支持 `workflow_dispatch` 手动触发。
- `node_modules` 本地大小约 25 MB，但未被 Git 跟踪。
- 公开数据体积最大项为：`data/expert-profiles.js` 约 29 MB，`data/knowledge-graph.js` 约 6.7 MB，`data/literature-full-index.js` 约 5.4 MB，`data/literature-recent.js` 约 2.8 MB。

## 两份报告的关键校正

| 争议点 | 我的判断 |
|---|---|
| “XSS 防护已基本到位” | 不成立。文本节点多数有转义，但属性上下文仍有明显注入面。 |
| “大量 `innerHTML` 未转义” | 方向正确但表述过粗。问题不是单纯 `innerHTML`，而是上下文不区分地拼 HTML。 |
| “EasyScholar 密钥硬编码” | 成立，而且该文件已被 Git 跟踪，应视为已泄露并轮换。 |
| “全局禁用 SSL 只在一个脚本” | 不完整。至少 `easyscholar_api.py`、`fetch-pubmed-weekly.py`、`fetch-pubmed-full.py`、`backfill-author-affiliations.py`、`normalize-journal-names.py` 存在类似问题。 |
| “懒加载回调丢失” | 成立，但要限定范围。`literature.js` 的 `loadEcharts`、`loadChinaData` 确实会丢第二个回调；`knowledge.js` 的 community assignment 分片已经有回调队列。 |
| “node_modules 已提交” | 不成立。目录存在但 `.gitignore` 生效，未被 Git 跟踪。 |
| “URL 参数直接进 `querySelector` 是高风险” | 风险存在但不是最高优先级。`knowledge.js` 有 `cssEscape`，更紧急的是属性上下文与 URL 属性拼接。 |
| “无测试覆盖” | 成立，而且应升为 P0/P1 之间的质量门问题。 |

## P0：必须先修

### P0-1：硬编码密钥与全局 SSL 关闭

位置：

- `scripts/easyscholar_api.py`
- `scripts/fetch-pubmed-weekly.py`
- `scripts/fetch-pubmed-full.py`
- `scripts/backfill-author-affiliations.py`
- `scripts/normalize-journal-names.py`

问题：

- `scripts/easyscholar_api.py` 中 `SECRET_KEY = os.environ.get("EASYSCHOLAR_KEY", "...")` 把真实密钥作为 fallback 写入已跟踪文件。
- 多个脚本通过 `ssl._create_default_https_context = ssl._create_unverified_context` 全局关闭证书校验。

影响：

- 密钥应按已泄露处理，需轮换。
- 全局 SSL monkey patch 会影响当前进程内所有 HTTPS 请求，医学数据抓取链路可能被中间人篡改。

建议：

- 立即轮换 EasyScholar key。
- 移除所有硬编码 fallback key，只允许环境变量或本地 `.env`。
- 删除全局 SSL 关闭逻辑。若是 macOS 证书问题，改用 `certifi` 或明确的 per-request SSL context。
- CI 中加入简单 secret scan，例如 `gitleaks` 或 `detect-secrets`。

### P0-2：属性上下文 XSS，而不是普通“文本没转义”

当前 `escapeHtml` 的实现一般是：

```javascript
function escapeHtml(value) {
  var div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}
```

这个函数适合 HTML 文本节点，但不适合双引号属性。它不会稳定转义 `"`。例如：

```html
<a href="https://example.test/" onclick="alert(1)">x</a>
```

这种结构可以由 `href="' + escapeHtml(url) + '"` 产生。

高风险位置示例：

- `assets/dashboard.js:61`、`assets/dashboard.js:74`：`href` 直接使用 `escapeHtml`，没有 URL 白名单。
- `assets/knowledge.js:676`、`assets/knowledge.js:779`、`assets/knowledge.js:957`、`assets/knowledge.js:1568`：`href` 使用 `escapeHtml`，包括 PMID、Obsidian URL、文献 URL。
- `assets/literature.js:607`、`assets/literature.js:924`、`assets/literature.js:996`：`escapeHref` 只做协议判断，仍返回 `escapeHtml`，属性引号未安全处理。
- `assets/literature.js:610`、`assets/literature.js:611`：`article.pmid` 原样拼入 `data-pmid` 与 `id`。
- `assets/conference.js:259`、`assets/conference.js:332`、`assets/conference.js:601`、`assets/conference.js:602`：`data-*` 和 `id` 用 `escapeHtml`。
- `assets/msl.js:542`、`assets/msl.js:641`、`assets/msl.js:684`：专家与模块 ID 拼入 `data-*`。

建议：

- 不要只建一个 `escapeHtml` 就收工。至少拆成 `escapeText`、`escapeAttr`、`safeUrl`、`safeClassToken`。
- 能用 DOM API 的地方优先用 `createElement`、`textContent`、`setAttribute`，不要拼字符串。
- URL 必须使用 `new URL(value, location.origin)` 解析，并限制协议为 `http:`、`https:`，站内链接限制为 `/MA-MG-HUB/`。
- `id`、`data-*`、`class` 应使用白名单 token 或 `setAttribute`。PMID 应正则限制为数字。
- CSP 可以做兜底，但不应替代模板修复。

### P0-3：没有最小质量门

现在代码语法通过，但没有自动测试、lint、格式检查或 smoke test。对医学情报站来说，这意味着“数据错了但页面看起来正常”的风险很高。

建议先加最小 CI：

- `python3 -m py_compile scripts/*.py`
- `node --check assets/*.js`
- `pytest` 覆盖 `studyClassifier.py`、社区归类、证据等级映射。
- 用小样本 fixture 跑 `build-frontend-data.py`、`buildCommunityData.py`、`build-knowledge-data.py` 的核心输出 schema。
- 用 Playwright 或 jsdom 做 5 个核心页面 smoke test：Dashboard、Literature、Landscape、Knowledge、MSL。

## P1：近期修复

### P1-1：`literature.js` 懒加载会丢回调

位置：

- `assets/literature.js:34-41`
- `assets/literature.js:44-51`

问题：

- `loadEcharts(cb)` 和 `loadChinaData(cb)` 在 `echartsLoading` 或 `chinaDataLoading` 为 true 时直接 `return`。
- 第二个调用方的 callback 会被丢弃，快速切换标签或重复触发时，后续渲染可能悬空。

建议：

- 对 ECharts 和中国数据都维护 callback queue。
- 加载失败时 callback 应收到 `false`，页面显示失败提示，而不是继续静默渲染。
- `knowledge.js` 的 community assignment 分片已经有队列，不需要重复修同一类问题。

### P1-2：依赖不可复现

位置：

- `.github/workflows/weekly-pipeline.yml`
- 根目录依赖配置缺失

问题：

- CI 只安装 `requests`。
- 项目脚本实际还涉及 `bs4`、`PyMuPDF`、`requests` 等依赖，其中会议脚本虽然不在 weekly pipeline 中运行，但依赖边界仍不透明。

建议：

- 新建 `requirements.txt` 和 `requirements-dev.txt`。
- CI 使用 `python3 -m pip install -r requirements.txt`。
- 如果会议抓取是离线或人工任务，把它拆到单独 extras 或单独文档，不要让主流水线依赖边界模糊。

### P1-3：数据管线静默降级过多

问题：

- 多个脚本通过正则解析 `window.X = ...;`，并直接 `json.loads`。
- 多处 `except Exception` 后继续执行。
- 写文件大多不是原子写入。
- 输入数据缺少 schema 校验。

我的判断：

这比“函数太长”更重要。MG 情报站最怕的不是页面样式不一致，而是某个数据源失败后，站点仍然显示一个看似完整但实际缺字段的结论。

建议：

- 建一个 `scripts/common/io.py`：统一 `load_json`、`load_js_global`、`write_atomic`。
- 核心产物同时输出 `.json` 和 `.js`，脚本之间优先读 `.json`。
- 对关键输入加 schema 校验，至少手写 `validateArticle`、`validateCommunity`、`validateGraphPayload`。
- Pipeline 状态中记录每一步的输入数量、输出数量、失败数量和异常类型。
- 对关键数据缺失使用非 0 退出，不要只打印 warning。

### P1-4：公开数据体积已影响体验

当前体积：

- `data/expert-profiles.js`：约 29 MB
- `data/knowledge-graph.js`：约 6.7 MB
- `data/literature-full-index.js`：约 5.4 MB
- `data/literature-recent.js`：约 2.8 MB

建议：

- 专家画像拆成轻索引和详情分片。MSL 列表页只加载轻索引，详情按需加载。
- `knowledge-graph.js` 拆成 graph summary、nodes、edges、references，首屏只加载 summary 与核心节点边。
- `literature-full-index.js` 用搜索轻索引字段，不要把展示用详情字段混入。
- 大文件统一加加载状态、失败状态和重试入口。

### P1-5：`/MA-MG-HUB/` 硬编码影响本地调试与迁移

位置：

- `index.html`
- `pages/*.html`
- 多个 `assets/*.js` 动态脚本路径

问题：

- GitHub Pages 当前路径可用，但本地直接 serve 项目根目录时资源路径会 404。
- 未来仓库名或部署路径变化时需要改多处。

建议：

- 短期提供 `window.MgHubConfig = { basePath: '/MA-MG-HUB/' }`。
- 所有动态脚本加载与站内 URL 都走 `toAssetUrl()`、`toPageUrl()`。
- 中期引入轻量构建或静态模板，在构建时注入 base path。

## P2：可以排队做

### P2-1：导航和页面骨架重复

导航在多个 HTML 文件重复。第二份报告建议用 `document.write` 注入导航，我不推荐作为最终方案，因为它会增加脚本时序和 CSP 难度。

更稳的方案：

- 若保持零构建：用 Python 小脚本在发布前生成 HTML，维护一个 `templates/nav.html`。
- 若接受轻量构建：用 Eleventy 或简单 Vite 多页入口。

### P2-2：Tabs 可访问性不完整

当前有 `role="tablist"`，但按钮缺 `role="tab"`、`aria-selected`、`aria-controls`，panel 缺 `role="tabpanel"`，键盘方向键切换也没有统一实现。

建议在统一 `initTabs` 时一起补齐。

### P2-3：CSS 与 `data-ops.html` 内联代码

`assets/main.css` 约 92 KB，`pages/data-ops.html` 内联 CSS 和 JS 较多。它不是最高风险，但会让后续样式维护越来越钝。

建议：

- 拆出 `assets/dataOps.js`。
- 将 data ops 样式迁入 `main.css` 的明确分区，或拆 `dataOps.css`。

### P2-4：工具函数重复

`escapeHtml`、`escapeHref`、脚本加载、tab 初始化重复分布在多个文件中。抽工具是对的，但顺序要注意：先把安全模型设计好，再抽公共函数。否则只是把错误的 `escapeHtml` 复制得更统一。

## 我建议的修复路线

### 第 0 天：安全止血

1. 轮换 EasyScholar key，删除硬编码 fallback。
2. 删除所有全局 SSL unverified monkey patch。
3. 加 `escapeAttr`、`safeUrl`、`safeIdToken`，先修最容易被外部数据污染的 `href`、`data-*`、`id`。
4. 修 `literature.js` 的 ECharts 与中国数据 callback queue。
5. CI 加 `py_compile` 和 `node --check`。

### 第 1 周：让数据可信

1. 建 `requirements.txt` 与 `requirements-dev.txt`。
2. 为 `studyClassifier.py`、社区 assignment、文献筛选加最小单测。
3. 建 `load_js_global` 与 `write_atomic` 共享工具。
4. 给核心输入输出加 schema 校验。
5. 增加页面 smoke test。

### 第 2 到 4 周：让站点轻起来

1. 拆 `expert-profiles.js`。
2. 拆知识图谱大包。
3. 抽 base path 配置。
4. 统一导航、tabs、错误横幅。
5. 整理 data ops 页。

## 最后判断

这个项目的方向是好的：原生静态站加本地数据管线，适合一个 MG 学术情报工作站快速迭代。现在不需要马上上重框架，也不应该把大量时间花在“漂亮重构”上。

真正要抓的是三件事：

1. 安全边界要硬：密钥、SSL、属性上下文 XSS。
2. 数据产物要可信：失败就明确失败，不能静默产出半成品。
3. 首屏和检索要轻：29 MB 专家画像和 6.7 MB 图谱不能长期靠浏览器硬扛。

如果按这个顺序修，MA-MG-HUB 会从“能用的个人情报站”稳定迈向“可协作、可审计、可放心给医学事务团队使用的工作站”。
