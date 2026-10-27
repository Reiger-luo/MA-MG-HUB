#!/usr/bin/env python3
"""诊疗现状 / 临床问题库的周更证据审查接口（候选队列，不自动改写正文）。

口径（与建设者约定）：
- 只把「高质量证据」送入候选：文献证据等级 I/II（含 RCT、系统综述/Meta）；
- 命中方式：本周真实新增 PMID × 章节/问题关键词（title + keywords 字段）；
- 候选一律 status=pending，由人工确认后才并入正文（编辑 build-landscape-knowledge.py 后重建）；
- 可选 --llm：调用 llm_client 对候选做重要性评分，仅记录建议，不自动合并；
- 全程不生成医学结论，不改动 treatmentChapters.js / clinicalQuestions.js 正文。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "data" / "literature-ingest-latest.json"
FULL = ROOT / "data" / "literature-full.json"
QUESTIONS = ROOT / "data" / "clinicalQuestions.js"
OUT = ROOT / "data" / "landscapeKnowledgeReview.js"

CHAPTER_KEYWORDS = {
    "goals": ["mse", "mms", "minimal symptom", "minimal manifestation", "remission", "mg-adl"],
    "steroid": ["steroid", "prednisone", "prednisolone", "glucocorticoid", "taper"],
    "targeted": ["efgartigimod", "rozanolixizumab", "nipocalimab", "eculizumab", "ravulizumab", "zilucoplan", "batoclimab", "fcrn", "complement"],
    "rescue": ["ivig", "plasmapheresis", "plex", "crisis", "immunoadsorption", "dfpp", "lpe"],
    "thymectomy": ["thymectomy", "thymoma"],
    "ocular": ["ocular"],
    "access": ["cost", "reimbursement", "access", "insurance", "mdt"],
}


def load_js(path: Path, name: str):
    text = path.read_text()
    payload = text[text.index("=") + 1:].strip().rstrip(";")
    return json.loads(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="可选：调用 LLM 对候选做重要性评分（仅建议，不自动合并）")
    args = parser.parse_args()

    added = []
    if INGEST.exists():
        added = json.loads(INGEST.read_text()).get("added_pmids") or []
    full = json.loads(FULL.read_text())
    articles = full if isinstance(full, list) else full.get("items") or full.get("articles") or []
    by_pmid = {str(a.get("pmid")): a for a in articles}

    questions = load_js(QUESTIONS, "MG_CLINICAL_QUESTIONS") if QUESTIONS.exists() else {"groups": []}
    targets = []
    for chapter_id, keywords in CHAPTER_KEYWORDS.items():
        targets.append(("chapter", chapter_id, keywords))
    for group in questions.get("groups", []):
        for q in group.get("questions", []):
            targets.append(("question", q["id"], q.get("keywords") or []))

    candidates = []
    for pmid in added:
        article = by_pmid.get(str(pmid))
        if not article:
            continue
        level = article.get("evidence_level")
        if level not in ("I", "II"):
            continue  # 高等级证据门控：III/IV/未分级一律不进候选
        haystack = " ".join([
            str(article.get("title") or ""),
            " ".join(article.get("keywords") or []),
            " ".join(article.get("study_types") or []),
        ]).lower()
        for target_type, target_id, keywords in targets:
            matched = [kw for kw in keywords if kw.lower() in haystack]
            if not matched:
                continue
            candidates.append({
                "target_type": target_type,
                "target_id": target_id,
                "pmid": str(pmid),
                "title": article.get("title") or "",
                "journal": article.get("journal") or "",
                "pub_date": article.get("pub_date") or article.get("entry_date") or "",
                "evidence_level": level,
                "matched_keywords": matched,
                "url": article.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "status": "pending",
            })

    if args.llm and candidates:
        try:
            from llm_client import LLMClient  # type: ignore
            client = LLMClient()
            for cand in candidates:
                prompt = (
                    "你是重症肌无力医学事务审校。仅评估这条新证据是否值得更新进对应知识条目，"
                    "不得生成医学结论。输出 JSON：{\"importance\":\"high|medium|low\",\"reason\":\"<=40字\"}\n"
                    f"条目：{cand['target_type']}:{cand['target_id']}\n"
                    f"文献：{cand['title']}（{cand['journal']}，证据等级 {cand['evidence_level']}）"
                )
                try:
                    reply = client.chat(prompt)
                    cand["llm_note"] = reply[:200]
                except Exception as err:  # LLM 失败只记录，不阻塞候选队列
                    cand["llm_note"] = f"llm_unavailable: {err}"
        except Exception as err:
            print(f"LLM 未启用：{err}")

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window": json.loads(INGEST.read_text()).get("window") if INGEST.exists() else None,
        "rule": "仅 I/II 级新证据进入候选；候选一律待人工确认，正文不自动改写",
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    from common.io import atomic_write_js_global
    atomic_write_js_global(OUT, "MG_KNOWLEDGE_REVIEW", payload, header="/* 诊疗现状/临床问题周更候选证据：由 scripts/review-landscape-knowledge.py 生成 */\n")
    print(f"新增 PMID {len(added)} 个，候选证据 {len(candidates)} 条（I/II 级门控后）")


if __name__ == "__main__":
    main()
