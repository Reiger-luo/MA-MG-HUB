#!/usr/bin/env python3
"""知识库编辑层 · 每周 LLM 自动校对（写入公开产物）。

输入：本周真实新增 PMID、当前信号、当前编辑层、图谱概念与关键词别名、站内深链目标。
处理：确定性算出"哪些概念需要改"，再把 bounded 上下文交给 LLM 产出草稿。
输出：校验通过后自动写入 data/knowledgeEditorial.js（无人工闸门）；
      .hermes-audit/ 下的 JSON + Markdown 是本次写入的审计留痕。

用法：
  python3 scripts/enrich-knowledge-editorial.py                 # 有 key 则调 LLM
  python3 scripts/enrich-knowledge-editorial.py --no-llm        # 只出确定性缺口
  python3 scripts/enrich-knowledge-editorial.py --limit 6
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

from common.io import load_js_global, load_json, atomic_write_json, atomic_write_text, atomic_write_js_global  # noqa: E402
from llm_client import complete  # noqa: E402

DATA = PROJECT / "data"
AUDIT = PROJECT / ".hermes-audit"
QUEUE_JSON = AUDIT / "knowledgeEditorialQueue.json"
QUEUE_MD = AUDIT / "reports" / "knowledgeEditorialQueueLatest.md"

SYSTEM = """你是 MG 医学事务知识库的编辑助手。任务：根据本周新增证据，为既有概念卡片提出改写草稿。
硬约束：
1. 只能使用提供的 records 中的 PMID 与标题；严禁新增 PMID、数字、试验结论或适应症。
2. 只写中文；lead / point / caution 各不超过 80 字，thought 是一个不超过 60 字的问题。
3. 不得写"本周新证据""证实""优于""疗效显著"等表述；共现与落点不是因果。
4. link 必须从提供的合法锚点中原样选取。
5. 输出严格 JSON 数组： [{"id":"概念id或a::b","kind":"concept|relation","draft":{...},"reason":"为什么改"}]
   概念 draft 字段：lead, point, caution, thought, link；关系 draft 字段：read, caution。
6. 不确定就少写；宁可输出空数组，也不要编造。
"""

OVERCLAIM = re.compile(r"(证实|证明|显著优于|疗效显著|已获批|完成非劣效|本周新证据)")


def load_aliases() -> dict[str, list[tuple[str, int]]]:
    """从前端知识库脚本读取唯一的关键词别名表，避免两处维护漂移。"""
    source = (PROJECT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    match = re.search(r"var nodeAlias = \{(.*?)\n  \};", source, re.S)
    if not match:
        raise RuntimeError("未找到 knowledge.js 的 nodeAlias")
    body = re.sub(r"^\s{4}([A-Za-z0-9_]+):", r'    "\1":', match.group(1), flags=re.M)
    return ast.literal_eval("{" + body + "}")


def build_matcher():
    aliases = load_aliases()
    rules = []
    for node_id, entries in aliases.items():
        for alias, weight in entries:
            rules.append((node_id, str(alias).rstrip("*").lower(), int(weight)))
    return rules


def match_concepts(title: str, abstract: str, rules, threshold: int = 6) -> dict[str, int]:
    text = ((title or "") + " " + (abstract or "")[:600]).lower()
    scores: dict[str, int] = defaultdict(int)
    for node_id, alias, weight in rules:
        if alias and alias in text:
            scores[node_id] += weight
    return {node_id: score for node_id, score in scores.items() if score >= threshold}


def load_records() -> list[dict]:
    """本周真实新增 PMID；没有 ingest 清单时回退近 30 天公开层。"""
    recent = load_js_global(DATA / "literature-recent.js", "MG_LITERATURE_DATA")
    article_list = recent if isinstance(recent, list) else (recent.get("items") or [])
    articles = {str(a.get("pmid")): a for a in article_list if a.get("pmid")}
    ingest_path = DATA / "literature-ingest-latest.json"
    added: list[str] = []
    if ingest_path.exists():
        ingest = load_json(ingest_path)
        added = [str(x) for x in (ingest.get("added_pmids") or [])]
    if added:
        selected = [articles[p] for p in added if p in articles]
    else:
        cutoff = datetime.now(timezone.utc).timestamp() - 30 * 86400
        selected = []
        for article in articles.values():
            entry = str(article.get("entry_date") or "")
            if entry and entry[:10].replace("/", "-") >= datetime.fromtimestamp(cutoff, timezone.utc).strftime("%Y-%m-%d"):
                selected.append(article)
    return selected[:60]


def valid_links() -> dict[str, set[str]]:
    questions = load_js_global(DATA / "clinicalQuestions.js", "MG_CLINICAL_QUESTIONS")
    chapters = load_js_global(DATA / "treatmentChapters.js", "MG_TREATMENT_CHAPTERS")
    landscape = load_js_global(DATA / "landscape-data.js", "MG_LANDSCAPE_DATA")
    topics = load_js_global(DATA / "curated-topics.js", "MG_CURATED_TOPICS")
    signals = load_js_global(DATA / "signals-weekly.js", "MG_SIGNALS_DATA")
    return {
        "question": {q["id"] for g in questions["groups"] for q in g["questions"]},
        "chapter": {c["id"] for c in chapters["chapters"]},
        "divergence": {d["id"] for d in landscape["china_landscape"]["guideline_divergence"]["divergences"]},
        "topic": {t["id"] for t in topics["topics"]},
        "signal": {s["id"] for s in signals["signals"]},
    }


def parse_llm_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return []


def valid_draft(item: dict, concept_ids: set[str], links: dict[str, set[str]]) -> bool:
    if not isinstance(item, dict) or item.get("id") not in concept_ids:
        return False
    draft = item.get("draft") or {}
    for field in ("lead", "point", "caution", "thought"):
        value = str(draft.get(field) or "")
        if not value or len(value) > 90 or OVERCLAIM.search(value):
            return False
    if not ("?" in str(draft.get("thought") or "") or "？" in str(draft.get("thought") or "")):
        return False
    link = str(draft.get("link") or "")
    kind, _, value = link.partition(":")
    if kind not in links or value not in links[kind]:
        return False
    return True


def build_prompt(batch: list[dict], current: dict, links: dict[str, set[str]]) -> tuple[str, str]:
    allowed = ", ".join(f"{k}:{v}" for k, values in links.items() for v in sorted(values)[:6])
    records = []
    for gap in batch:
        for ref in gap.get("evidence", [])[:3]:
            records.append({
                "pmid": ref.get("pmid"),
                "title": ref.get("title"),
                "abstract": (ref.get("abstract") or "")[:300],
            })
    payload = {
        "anchors_sample": allowed,
        "concepts": [
            {
                "id": gap["id"],
                "reason": gap["reason"],
                "current": current.get(gap["id"], {}),
            }
            for gap in batch
        ],
        "records": records,
    }
    prompt = "请为下列概念生成知识卡改写草稿。只能引用下面 records 里的 PMID / 标题，不得新增事实。\n" + \
        json.dumps(payload, ensure_ascii=False, indent=2)[:14000]
    return prompt, SYSTEM


def main() -> int:
    parser = argparse.ArgumentParser(description="知识库编辑层每周校对队列")
    parser.add_argument("--no-llm", action="store_true", help="只做确定性缺口分析，不调用 LLM")
    parser.add_argument("--limit", type=int, default=8, help="每次送审的概念数上限")
    args = parser.parse_args()

    editorial = load_js_global(DATA / "knowledgeEditorial.js", "MG_KNOWLEDGE_EDITORIAL")
    graph = load_js_global(DATA / "knowledge-graph.js", "MG_KNOWLEDGE_GRAPH")
    concept_ids = {n["id"] for n in graph["nodes"]}
    links = valid_links()
    rules = build_matcher()
    records = load_records()

    hits_by_concept: dict[str, list[dict]] = defaultdict(list)
    for article in records:
        for node_id in match_concepts(article.get("title"), article.get("abstract"), rules):
            hits_by_concept[node_id].append({
                "pmid": str(article.get("pmid") or ""),
                "title": article.get("title") or "",
                "abstract": article.get("abstract") or "",
            })

    signals = load_js_global(DATA / "signals-weekly.js", "MG_SIGNALS_DATA")
    signal_hits: dict[str, list[str]] = defaultdict(list)
    for signal in signals.get("signals", []):
        for node_id in match_concepts(signal.get("title"), signal.get("summary"), rules):
            signal_hits[node_id].append(str(signal.get("id") or ""))

    current = editorial.get("concepts", {})
    gaps = []
    for node_id, refs in hits_by_concept.items():
        if node_id not in concept_ids:
            continue
        item = current.get(node_id, {})
        stale = str(item.get("link") or "") not in {f"signal:{sid}" for sid in signal_hits.get(node_id, [])}
        gaps.append({
            "id": node_id,
            "kind": "concept",
            "reason": f"本周有 {len(refs)} 条(add窗口)文献落到该概念" +
              ("；编辑层的锚点未指向本周信号" if stale and signal_hits.get(node_id) else ""),
            "evidence": refs,
            "draft": None,
            "status": "needs_review",
        })
    gaps.sort(key=lambda g: (-len(g["evidence"]), g["id"]))
    gaps = gaps[: max(1, args.limit)]

    llm_note = "未调用 LLM（--no-llm）"
    if gaps and not args.no_llm:
        try:
            prompt, system = build_prompt(gaps, current, links)
            reply = complete(prompt, system=system, temperature=0.1, max_tokens=6000, use_cache=True)
            for draft in parse_llm_json(reply):
                if not valid_draft(draft, {g["id"] for g in gaps}, links):
                    continue
                for gap in gaps:
                    if gap["id"] == draft["id"]:
                        gap["draft"] = draft["draft"]
                        gap["status"] = "applied"
            llm_note = "LLM 草稿已直接写入公开编辑层（全自动，无人工闸门）"
        except Exception as exc:  # 无 key / 超时都不阻塞周更
            llm_note = f"LLM 未启用或失败：{type(exc).__name__}；仅输出确定性缺口"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run": (DATA / "literature-ingest-latest.json").exists(),
        "records_scanned": len(records),
        "concepts_with_new_evidence": len(hits_by_concept),
        "items": gaps,
        "llm_note": llm_note,
        "approval_rule": "用户 2026-11-25 指示：不再人工批准，LLM 校验通过后自动写入公开编辑层",
    }
    if not AUDIT.exists():
        AUDIT.mkdir()
    if not (AUDIT / "reports").exists():
        (AUDIT / "reports").mkdir()
    atomic_write_json(QUEUE_JSON, payload)
    # wiki 专题层周更同步后，把"中文摘要 + 有 PMID + 非低置信"的新专题自动纳入白名单。
    # 只按 anchor_nodes 落到具体概念；不撤掉人工已收缩的条目（收缩是质量决策，不自动回滚）。
    new_topics = []
    if not args.no_llm:
        try:
            topics_payload = load_js_global(DATA / "curated-topics.js", "MG_CURATED_TOPICS")
            cjk_pattern = re.compile(r"[\u4e00-\u9fff]")
            seen = {topic_id for ids in editorial.get("topics", {}).values() for topic_id in ids}
            for item in topics_payload.get("topics", []):
                if item["id"] in seen:
                    continue
                if len(cjk_pattern.findall(str(item.get("summary") or ""))) < 20:
                    continue
                if not item.get("evidence_pmids") or item.get("confidence") in ("low", "unknown"):
                    continue
                for node_id in (item.get("anchor_nodes") or []):
                    if node_id in concept_ids and node_id != "myastheniaGravis":
                        editorial.setdefault("topics", {}).setdefault(node_id, []).append(item["id"])
                        seen.add(item["id"])
                        new_topics.append({"id": item["id"], "node": node_id})
                        break
            if new_topics:
                print("wiki 新专题纳入白名单：" + ", ".join(t["id"] for t in new_topics))
        except Exception as exc:
            llm_note += f"；wiki 专题同步跳过：{type(exc).__name__}"

    applied = [gap for gap in gaps if gap.get("draft")]
    if applied or new_topics:
        editorial["generated_at"] = payload["generated_at"]
        editorial["version"] = "llm-auto-" + payload["generated_at"][:10]
        for gap in applied:
            editorial["concepts"][gap["id"]] = gap["draft"]
        log = editorial.setdefault("applied", [])
        if applied:
            log.append({
                "at": payload["generated_at"],
                "mode": "llm_auto",
                "concept_ids": [gap["id"] for gap in applied],
            })
        if new_topics:
            log.append({
                "at": payload["generated_at"],
                "mode": "wiki_whitelist_sync",
                "topic_ids": [t["id"] for t in new_topics],
                "node_ids": [t["node"] for t in new_topics],
            })
        atomic_write_js_global(DATA / "knowledgeEditorial.js", "MG_KNOWLEDGE_EDITORIAL", editorial,
                               header="/* MA-MG-HUB 知识库编辑层 · 每周 LLM 自动校对写入。 */\n")
    lines = [
        "# 知识库编辑层 · 每周校对队列", "",
        f"生成时间：{payload['generated_at']} · 扫描文献 {len(records)} 条 · " +
        f"有新证据落点概念 {len(hits_by_concept)} 个 · 本次入队 {len(gaps)} 个", "",
        f"LLM：{llm_note}", "",
        "> LLM 草稿校验通过后已自动写入 `data/knowledgeEditorial.js`（用户指示：不再人工批准）。" +
        "本 Markdown 与 JSON 是本次写入的审计留痕，不是待审闸门。", "",
        "| 概念 | 原因 | 状态 |", "| --- | --- | --- |",
    ]
    for gap in gaps:
        lines.append(f"| {gap['id']} | {gap['reason']} | {gap['status']} |")
    lines.extend(["", "## 草稿详情", ""])
    for gap in gaps:
        lines.extend([f"### {gap['id']}", "", gap["reason"], ""])
        refs = gap.get("evidence", [])[:3]
        ref_text = ", ".join("PMID " + str(r.get("pmid")) for r in refs if r.get("pmid")) or "无"
        lines.append(f"- 证据：{ref_text}")
        lines.append("")
        if gap["draft"]:
            for key, value in gap["draft"].items():
                lines.append(f"- **{key}**：{value}")
        else:
            lines.append("- 无 LLM 草稿；请人工判断是否需要改写，以及改写后指向哪个站内锚点。")
        lines.append("")
    atomic_write_text(QUEUE_MD, "\n".join(lines) + "\n")
    print(f"✅ 校对队列：{len(gaps)} 项 · {QUEUE_MD.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
