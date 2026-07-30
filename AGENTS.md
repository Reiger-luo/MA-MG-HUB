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
- 修改数据管线时继续使用原子写入，并保持 cloud-safe last-good 行为。
- 提交前运行与改动范围相称的测试；文档结构至少运行 `tests/test_document_lifecycle.py`。
