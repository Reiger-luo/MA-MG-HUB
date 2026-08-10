# Code Review Graph 审查流程

> 本流程规范 MA-MG-HUB 的代码 review。`code-review-graph`（CRG）用于补充调用关系、影响半径和测试关系，不替代源码、测试、发布契约或医学内容审核。

## 1. 适用范围

CRG 主要审查以下目录中的 Python、JavaScript 和 Shell 源码：

- `scripts/`；
- `assets/*.js`；
- `worker/`；
- `tests/`。

`data/**` 是公开或本地生成产物，已由 `.code-review-graphignore` 排除。HTML、CSS、Markdown、`window.MG_*` 动态装载关系、release manifest 一致性和医学证据边界不属于 CRG 的完整覆盖面，必须继续执行直接检查和仓库测试。

## 2. 本地准备

仓库使用项目级 `.codex/config.toml` 注册受限 MCP 工具，不修改全局 Codex 配置，不安装自动写入源码的重构工具，也不启用文件监视或 Git hook。

首次使用安装固定版本并构图：

```bash
uv tool install "code-review-graph==2.3.7"
code-review-graph build
code-review-graph status
```

如果不希望安装持久 CLI，可使用固定版本的 `uvx`：

```bash
uvx --from "code-review-graph==2.3.7" code-review-graph build
uvx --from "code-review-graph==2.3.7" code-review-graph status
```

新增或修改 `.codex/config.toml` 后，需要新开 Codex 任务或重启对应本地客户端，随后用 `/mcp` 或 `codex mcp list` 确认 `code-review-graph` 已连接。项目级 MCP 只在受信任仓库中加载。

## 3. Review 顺序

1. 检查 `git status` 和 diff 基线，区分源码、生成数据和文档变更。
2. 图谱陈旧时运行 `code-review-graph update --brief`；只读查看现有图谱时运行 `code-review-graph detect-changes --brief --base origin/main`。
3. 在 Codex 中先调用 `detect_changes_tool`，再调用 `get_review_context_tool` 获取受影响函数、调用者、执行流和测试关系。
4. 对高风险或跨文件变更，使用 `get_impact_radius_tool`、`get_affected_flows_tool` 和 `query_graph_tool` 复核传播路径。
5. 阅读实际 diff 和关键源码；不得只依据风险分数或 token savings 下结论。
6. 运行与范围相称的测试。数据管线、发布边界和文档结构仍按 `AGENTS.md` 与当前操作手册执行。
7. 以 findings-first 格式输出 review，按严重度排序并附文件、行号、触发条件、影响和修复建议。

## 4. 修改与上线后的闭环

用户明确批准 push 或上线时，使用仓库 Skill `$refresh-review-graph`。Skill 不提供 push 授权，只在授权操作成功后闭合 Graph：

1. push 前记录当前 upstream SHA；
2. 完成获批的验证、commit、push 和部署；
3. push 成功后运行 `scripts/refreshReviewGraphAfterPush.sh --base <pre-push-sha>`；
4. 在已推送 commit 上完整重建 Graph，并重新检查影响范围、执行流和测试缺口；
5. 在交付结果中报告 pushed SHA、Graph 状态、风险摘要和未覆盖边界。

脚本会验证本地 `HEAD` 已等于 upstream，并拒绝把 push 后新增的未提交源码混入 Graph。每次使用完整重建而非依赖历史增量状态，确保 Graph 对应当前上线 commit；纯数据、HTML、CSS 或文档 push 没有 CRG 可解析变更时，只报告不适用原因。

Hermes/本地周更等已经获准自动发布的后台任务调用同一个共享脚本，不复制第二套 Graph 逻辑。后台任务在 push 前记录远端 SHA，只进行一次 commit/push，随后以该 SHA 为 base 执行脚本。常规周更只改 `data/**`、`pages/**` 和 `index.html`，因此返回 `CRG_REFRESH_SKIPPED`；若管线生成源码或其他白名单外变更，必须在 commit 前 fail closed 并等待人工 review，不能为了刷新 Graph 追加第二次提交。

## 5. 结论规则

- CRG finding 是待验证线索，不是自动缺陷判定。
- 风险分数为低或零不表示安全，尤其是 HTML/CSS、动态全局对象、生成数据和跨语言契约。
- CRG 指出的测试关系必须与真实测试内容核对；“存在测试”不等于覆盖当前行为。
- 没有 finding 时，明确写明“未发现可执行问题”，并列出残余风险与未运行测试。
- 不使用 CRG 自动重构写入；重构建议必须先形成独立变更计划并由正常编辑流程实施。

## 6. GitHub 自动审查与刷新

`.github/workflows/code-review-graph.yml` 只在 `scripts/**`、`assets/*.js`、`worker/**` 或 `tests/**` 发生变化时运行。它对同仓分支 PR 写入单个 advisory 评论，固定使用 CRG v2.3.7，不因风险分数阻断合并。

`.github/workflows/code-review-graph-refresh.yml` 在上述源码或 Graph 配置 push 到 `main` 后运行。它在部署 commit 上完整重建 Graph，不依赖历史缓存，并把 Graph 状态和相对 push 前 SHA 的影响分析写入 workflow summary。该工作流也支持手动 `workflow_dispatch` 恢复验证。

该 workflow：

- 不读取本地 full 数据；
- 不生成或提交 `data/**`；
- 不改变 `data/release-manifest.js`；
- 不替代 `.github/workflows/weekly-pipeline.yml` 的发布验证；
- 不处理 fork PR 评论。未来开放 fork PR 时，应按上游安全建议拆分无权限分析 workflow 与可信 `workflow_run` 评论 workflow。

## 7. 故障与降级

```bash
code-review-graph status
code-review-graph build
```

如果 MCP 无法启动，先确认 `uvx` 可用、版本固定为 2.3.7，并在新任务中重新检查 `/mcp`。无法及时恢复时，直接使用 `rg`、源码阅读和仓库测试完成 review；CRG 不得成为审查单点故障。

push 已成功但本地 Graph 刷新失败时，不回滚或重复 push。应明确报告失败，并在修复环境后运行：

```bash
bash scripts/refreshReviewGraphAfterPush.sh --base <pre-push-sha>
```
