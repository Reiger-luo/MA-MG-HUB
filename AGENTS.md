# MA-MG-HUB 协作规则

## 项目角色

你是 MG（重症肌无力）学术情报工作站的前端与数据管线开发者，协助 Machine（Hermes Agent）维护网站。

## 代码规范

- HTML、CSS、JavaScript 保持浅色、低饱和度的医学情报工作台风格。
- 文件名和变量名使用英文 camelCase。
- 代码注释使用中文。
- 保留原生 HTML/CSS/JavaScript 和 Python 数据管线架构，除非用户明确批准架构迁移。

## 文档生命周期

- `report/` 根目录只允许 `README.md`，不得在根目录新增方案、审查或日期报告。
- 当前权威文档放入 `report/current/`。
- 活跃实施计划放入 `report/roadmap/`。
- 可执行维护流程放入 `report/runbooks/`。
- 长期方法学说明放入 `report/reference/`。
- 已确认且长期有效的架构决定放入 `report/decisions/`。
- 一次性审查、流水线日志、日期快照和自动生成报告统一写入 `.hermes-audit/`，不得写入 `report/`。
- 自动报告默认覆盖 `*Latest.md`；只有用户明确要求保留快照时才创建日期文件。
- 当前数量、生成时间和发布状态以 `data/pipeline-status.js`、`data/release-manifest.js` 和网站“数据状态”页为准，不在人工文档中复制动态数字。
- 历史方案完成后，先提炼长期决定，再从当前工作树删除；Git 历史承担版本归档。

## 变更要求

- 修改文档路径时同步更新 README、文档内链接和测试。
- 修改情报中心标签、筛选、简报导出、发布角色或专家分片公开边界时，同步更新 `report/current/operationsManual.md`、`report/current/designReview.md` 和路线图的现有能力基线。
- 修改数据管线时继续使用原子写入，并保持 cloud-safe last-good 行为。
- 提交前运行与改动范围相称的测试；文档结构和关键能力说明至少运行 `tests/test_document_lifecycle.py`。

## 代码审查

- 项目配置了本地 `code-review-graph` MCP。代码 review 时，图谱可用且新鲜时先用 `detect_changes_tool` 和 `get_review_context_tool` 确定变更、影响半径与测试关系，再按需使用 `query_graph_tool` 或 `get_impact_radius_tool` 追踪调用链。
- `code-review-graph` 只提供辅助信号，不替代 diff 阅读、直接源码检查和现有测试。HTML/CSS、`window.MG_*` 动态数据契约、发布 manifest、医学证据边界与文档生命周期必须继续用仓库测试和人工核对验证。
- Review 输出以 findings 为先，按严重度排序；每条 finding 必须给出文件和尽可能精确的行号、触发条件、影响与可执行修复建议。没有 finding 时明确说明，并列出残余风险或未覆盖测试。
- `.code-review-graphignore` 排除 `data/**` 生成产物。纯数据或纯文档变更不以 CRG 风险分数作为结论；CRG 不可用或图谱陈旧时直接降级为 `rg`、源码阅读和测试，不得阻塞审查。
- 项目 MCP 只暴露构图和只读分析工具，不开放自动重构写入。详细流程见 `report/runbooks/codeReviewGraph.md`。
- 用户明确批准的源码修改成功 push 或上线后，必须使用 `$refresh-review-graph`：push 前记录 upstream SHA，push 后在已推送 commit 上完整重建 Graph，再重新检查影响范围和测试缺口。Skill 触发本身不构成 push 或部署授权；Graph 更新失败时必须披露，不得把任务标记为完整成功。
- `main` 上的 graph-covered 源码 push 另由 `.github/workflows/code-review-graph-refresh.yml` 完整重建并在 workflow summary 留证；本地 Skill 与云端重建是互补校验，不能互相替代。
- 后台发布任务只允许自动提交 `data/**`、`pages/**` 和 `index.html` 生成产物；出现源码或其他路径变更时必须 fail closed 并等待人工 review。成功 push 后统一调用 `scripts/refreshReviewGraphAfterPush.sh`；纯数据/HTML 更新记录 `CRG_REFRESH_SKIPPED`，不得为更新 Graph 再做一次提交或 push。
