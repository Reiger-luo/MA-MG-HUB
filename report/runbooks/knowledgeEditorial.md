# 知识库编辑层每周校对（LLM 参与）

`data/knowledgeEditorial.js`（`window.MG_KNOWLEDGE_EDITORIAL`）是知识库三镜的策展内容层：
每个概念的精读导语、思考问题，以及重点关系的定制解读。它和 `curated-topics.js`（由 wiki vault 周更同步的策展层）不是一回事：后者提供候选专题，编辑层 `topics` 白名单决定每个节点显示哪些。

## 为什么要单独做

- 首页信号按周刷新、文献按周滚动；策展层如果也跟着重写，观点会漂移。
- 诊治格局的章节与临床问题由 `build-landscape-knowledge.py` 每次整体重建，并有 PMID fail-closed 保证；LLM 不得直接写这些正文。
- 因此采用项目已有的"候选 → 人工确认 → 再并入正文"路径：LLM 只产出**待审草稿**，落在 `.hermes-audit/`，不进公开产物。

## 每周流程

```bash
# 用户 2026-11-25 指示：不再人工批准，LLM 全自动。
# 周更管线必填步骤 review-knowledge-editorial 自动执行；--skip-llm 时跳过。

python3 scripts/enrich-knowledge-editorial.py --no-llm   # 调试：只看确定性缺口，不写公开产物
python3 scripts/enrich-knowledge-editorial.py            # LLM 校验通过后自动写 data/knowledgeEditorial.js
python3 scripts/validatePublicRelease.py --source-only --require-release
python3 -m pytest -q tests/test_knowledge_editorial.py
```

`.hermes-audit/reports/knowledgeEditorialQueueLatest.md` 与 `knowledgeEditorialQueue.json`
现在是**本次自动写入的审计留痕**（证据 PMID、改写内容、写入概念 id），不是待审闸门。

## 脚本判定"要改什么"的规则

1. **新证据落点**：从 `literature-ingest-latest.json` 取本周真实新增 PMID（缺失时回退公开层近 30 天），
   用 `assets/knowledge.js` 里唯一的 `nodeAlias` 表做加权匹配（≥6 分）得到概念。
2. **锚点是否过时**：本周信号已落到某概念、但编辑层仍指向旧锚点时，标记需要复核。
3. **关系待补**：同一批新证据同时命中两个概念、且该概念对还没有定制解读时，进入待审队列（本次版本先入队概念项）。
4. LLM 只拿到受控上下文（概念当前内容 + 限定 PMID 的题录/摘要 + 合法锚点清单），输出受严格 JSON 约束。

## 硬边界

- LLM 草稿经过 `valid_draft` 严格校验（不得新增 PMID、过度声明、非法锚点、非中文问句）后，**自动原子写入** `knowledgeEditorial.js`；没有合格草稿时保持 last-good 不覆盖。
- 草稿不得新增 PMID、数字、试验结论、适应症；不得写成"本周新证据""证实""优于"。
- 思考项必须是问题，不是答案；答案在诊治格局，锚点必须精确到问题 / 章节 / 分歧 id。
- 发布产物必须是严格 JSON（`window.MG_KNOWLEDGE_EDITORIAL = <json>;`），否则 `common.io.load_js_global` 与发布校验会失败。
- LLM 调用失败或没有 key 时，只输出确定性缺口报告，周更不中断。

## 相关文件

- 队列（自动生成，覆盖）：`.hermes-audit/knowledgeEditorialQueue.json`、`.hermes-audit/reports/knowledgeEditorialQueueLatest.md`
- 公开产物：`data/knowledgeEditorial.js`
- 契约：`tests/test_knowledge_editorial.py`、`tests/test_knowledge_sediment_layer.py`、`scripts/verifyFrontendRender.js`
- LLM 客户端：`scripts/llm_client.py`（`complete()`，DeepSeek，缓存与成本日志）
