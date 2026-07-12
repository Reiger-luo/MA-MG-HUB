#!/usr/bin/env python3
"""Enrich the deterministic literature Signal-to-KOL layer with evidence-bound LLM synthesis.

The deterministic builder owns the candidate window, MG-core guard, topic clusters,
author leads and fallback output. This optional step only improves the semantic
layer (signal title/takeaway/whySignal and KOL talking points); every reference is
validated against the actual PubMed records before the public payload is written.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from common.io import atomic_write_js_global, load_js_global  # noqa: E402
from llm_client import complete  # noqa: E402

SIGNALS_PATH = PROJECT / "data" / "signals-weekly.js"
LITERATURE_PATH = PROJECT / "data" / "literature-recent.js"
DASHBOARD_PATH = PROJECT / "data" / "dashboard-data.js"

DRUG_REFERENCE_TERMS = {
    "Efgartigimod": ("efgartigimod", "vyvgart", "argx-113", "argx113"),
    "Nipocalimab": ("nipocalimab",),
    "Rozanolixizumab": ("rozanolixizumab",),
    "Batoclimab": ("batoclimab",),
    "Gefurulimab": ("gefurulimab",),
    "Eculizumab": ("eculizumab",),
    "Ravulizumab": ("ravulizumab",),
    "Zilucoplan": ("zilucoplan",),
    "Telitacicept": ("telitacicept", "rc-18", "rc18"),
    "Ofatumumab": ("ofatumumab",),
    "Rituximab": ("rituximab",),
}

SYSTEM = """你是重症肌无力（myasthenia gravis, MG）医学事务情报分析师。
任务：基于给定的近14天 MG-core PubMed records，把单篇候选归纳为文献级 Signal，并在每条 Signal 下生成 KOL talking points。
硬性要求：
1. 只输出 JSON object，不要 Markdown，不要解释。
2. records 已通过 MG-core 过滤；不得引入输入 records 以外的研究或数字。
3. signals 回答“近期文献说明了什么可追踪变化”，不能只是重复单篇文章标题；数量按证据自然决定，通常 6–10 条，最多 10 条。
4. 每条 signal 必须包含 title、takeaway、whySignal、evidenceBoundary、maUse、signalScore、refPmids、talkingPoints；每条最多 2 个 talkingPoints。
5. talkingPoints 必须回答“拿哪条证据去和 KOL 说什么/问什么”，每条包含 priorityTier、dimension、title、whyKol、keyMessages、refPmids。
6. priorityTier 排序：
   - efgar：efgartigimod / Vyvgart / ARGX-113 相关数据；只要确实是该条交流点的证据，优先传递。
   - competitor_response：其他治疗或机制；必须从机制、人群、终点、给药、安全性、证据成熟度与 efgar 区隔，不得虚构 head-to-head。
   - disease_progress：诊断、监测、患者负担、特殊人群、疾病机制等非直接产品进展。
7. keyMessages 只能使用 records 的 title、abstract、evidenceLevel、studyTypes、journal 和已有 metrics；优先保留原始结果段中的人群、样本量、终点、时间点和数字。
8. 设计、探索性、病例或摘要级证据必须明确写“探索性/病例级/摘要级/需全文核查/疗效数据待公布”等边界；不能把关联写成因果，不能把不同研究横向比较成 head-to-head。
9. refPmids 只能填写输入 records 的 PMID，且每条 signal/talking point 至少绑定 1 个 PMID；每个 PMID 最多归入一个 signal，必须尽量覆盖全部 records。
10. 不要生成作者姓名或机构名称；作者和机构由程序根据 PMID 自动聚合。"""


def load_builder_module():
    path = SCRIPTS / "build-frontend-data.py"
    spec = importlib.util.spec_from_file_location("mg_frontend_builder", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_json_object(text: str) -> dict:
    text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise ValueError("LLM response is not a JSON object")
    return obj


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def excerpt(article: dict, limit: int = 380) -> str:
    text = normalize_text(article.get("abstract"))
    if not text:
        return "摘要正文未提供，需全文核查。"
    match = re.search(
        r"(?:findings|results|main results|outcomes|conclusions?|interpretation|implications?)\s*:\s*(.+?)(?=\s+(?:funding|limitations?|conclusions?|interpretation|implications?)\s*:|$)",
        text,
        flags=re.IGNORECASE,
    )
    text = normalize_text(match.group(1) if match else text)
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return text


def article_drugs(article: dict) -> list[str]:
    text = normalize_text(article.get("title")) + " " + normalize_text(article.get("abstract"))
    lower = text.lower()
    return sorted(name for name, terms in DRUG_REFERENCE_TERMS.items() if any(term in lower for term in terms))


def records_for_prompt(articles: list[dict]) -> list[dict]:
    records = []
    for article in sorted(articles, key=lambda item: str(item.get("pmid") or "")):
        records.append(
            {
                "pmid": str(article.get("pmid") or ""),
                "title": article.get("title", ""),
                "abstract": normalize_text(article.get("abstract"))[:1800],
                "evidenceLevel": article.get("evidence_level"),
                "studyTypes": article.get("study_types") or [],
                "journal": article.get("journal", ""),
                "journalIF": article.get("journal_if"),
                "chinaRelated": bool(article.get("china_related")),
            }
        )
    return records


def build_prompt(records: list[dict]) -> str:
    schema = {
        "signals": [
            {
                "title": "近期文献变化标题",
                "takeaway": "1–2句，概括多篇文献形成的可追踪变化",
                "whySignal": "为什么是 signal，而非单篇摘要复述",
                "evidenceBoundary": "研究设计、证据等级、人群/终点差异和摘要级局限",
                "maUse": "如何用于 MSL briefing 或后续证据追踪",
                "signalScore": 1,
                "refPmids": ["PMID"],
                "talkingPoints": [
                    {
                        "priorityTier": "efgar | competitor_response | disease_progress",
                        "dimension": "人群/终点/安全性/机制/路径等",
                        "title": "KOL交流主题",
                        "whyKol": "为什么值得与KOL讨论；竞品必须说明与efgar的区隔角度",
                        "kolScore": 1,
                        "keyMessages": ["只用输入证据写出的1–3句可传递信息"],
                        "refPmids": ["PMID"],
                    }
                ],
            }
        ]
    }
    return (
        "请根据 records 生成文献级 Signal-to-KOL 分析。\n"
        "区分原则：Signal 是父层，回答‘近期文献说明了什么变化’；talkingPoints 是子层，回答‘拿哪条证据去和 KOL 说什么/问什么’。每个 PMID 只归入一个 signal，必须尽量覆盖全部 records。\n"
        "同一 PMID 可以支持同一 signal 下的多个 talking point，但每条 talking point 必须归属于一个 signal。\n"
        f"schema = {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"records = {json.dumps(records, ensure_ascii=False)}"
    )


def clean_tier(value: Any, refs: list[dict], raw: dict) -> str:
    value = normalize_text(value).lower().replace("-", "_")
    ref_drugs = {drug.lower() for ref in refs for drug in (ref.get("drugs") or [])}
    if value in {"efgar", "efgartigimod", "vyvgart"}:
        return "efgar"
    if value in {"competitor", "competitor_response", "competitive", "other_treatment"}:
        return "competitor_response"
    if value in {"disease", "disease_progress", "non_product"}:
        if ref_drugs - {"efgartigimod"}:
            return "competitor_response"
        if "efgartigimod" in ref_drugs:
            return "efgar"
        return "disease_progress"
    blob = json.dumps(raw, ensure_ascii=False).lower()
    if any(alias in blob for alias in ("efgartigimod", "vyvgart", "argx-113", "argx113")):
        return "efgar"
    if any(ref.get("drugs") for ref in refs):
        return "competitor_response"
    return "disease_progress"


def compact_ref(article: dict) -> dict:
    return {
        "pmid": str(article.get("pmid") or ""),
        "title": article.get("title", ""),
        "journal": article.get("journal", ""),
        "entry_date": article.get("entry_date", ""),
        "pub_date": article.get("pub_date", ""),
        "url": article.get("url", ""),
        "evidence_level": article.get("evidence_level"),
        "study_types": article.get("study_types") or [],
        "journal_if": article.get("journal_if"),
        "china_related": bool(article.get("china_related")),
        "drugs": article_drugs(article),
        "topics": article.get("keywords") or [],
        "key_evidence": excerpt(article),
    }


def clamp_score(value: Any, default: int = 3) -> int:
    try:
        return max(1, min(5, int(float(value))))
    except (TypeError, ValueError):
        return default


def normalize_point(raw: dict, parent_id: str, parent_title: str, by_pmid: dict[str, dict], builder) -> dict | None:
    if not isinstance(raw, dict):
        return None
    pmids = raw.get("refPmids") or raw.get("pmids") or []
    if not isinstance(pmids, list):
        pmids = [pmids]
    articles = [by_pmid[str(pmid)] for pmid in pmids if str(pmid) in by_pmid]
    if not articles:
        return None
    refs = [compact_ref(article) for article in articles[:5]]
    tier = clean_tier(raw.get("priorityTier"), refs, raw)
    messages = [normalize_text(msg) for msg in raw.get("keyMessages", []) if normalize_text(msg)]
    if not messages:
        messages = [f"PMID {article['pmid']}：{excerpt(article)}" for article in articles[:2]]
    return {
        "parentSignalId": parent_id,
        "parentSignalTitle": parent_title,
        "priorityTier": tier,
        "priorityLabel": {"efgar": "efgar重点传递", "competitor_response": "竞品应对解读", "disease_progress": "疾病进展传递"}[tier],
        "priorityRank": {"efgar": 0, "competitor_response": 1, "disease_progress": 2}[tier],
        "dimension": normalize_text(raw.get("dimension")) or "交流",
        "title": normalize_text(raw.get("title")) or parent_title,
        "whyKol": normalize_text(raw.get("whyKol")) or "该证据可用于与 KOL 讨论研究设计、临床意义和外推边界。",
        "kolScore": clamp_score(raw.get("kolScore"), 4 if tier == "efgar" else 3),
        "keyMessages": messages[:3],
        "refs": refs,
    }


def normalize_signal(raw: dict, signal_index: int, by_pmid: dict[str, dict], baseline: dict, builder) -> dict | None:
    if not isinstance(raw, dict):
        return None
    pmids = raw.get("refPmids") or raw.get("pmids") or []
    if not isinstance(pmids, list):
        pmids = [pmids]
    articles = [by_pmid[str(pmid)] for pmid in pmids if str(pmid) in by_pmid]
    if not articles:
        return None
    articles.sort(key=lambda article: (str(article.get("entry_date") or ""), str(article.get("pmid") or "")), reverse=True)
    refs = [compact_ref(article) for article in articles[:6]]
    signal_id = f"L{signal_index:02d}"
    title = normalize_text(raw.get("title")) or "近期 MG 文献证据变化"
    points = []
    for point in raw.get("talkingPoints", []) or []:
        normalized = normalize_point(point, signal_id, title, by_pmid, builder)
        if normalized:
            points.append(normalized)
    if not points:
        points.append(
            normalize_point(
                {
                    "priorityTier": "disease_progress",
                    "title": title,
                    "whyKol": "代表性文献可用于与 KOL 讨论结果、研究设计和证据边界。",
                    "keyMessages": [f"PMID {article['pmid']}：{excerpt(article)}" for article in articles[:2]],
                    "refPmids": [article.get("pmid") for article in articles[:2]],
                },
                signal_id,
                title,
                by_pmid,
                builder,
            )
        )
    points = [point for point in points if point]
    points.sort(key=lambda point: (point["priorityRank"], -point["kolScore"], point["title"]))
    levels = Counter(str(article.get("evidence_level") or "未分类") for article in articles)
    level_text = "、".join(f"{level}级 {count}篇" for level, count in sorted(levels.items()))
    dates = [str(article.get("entry_date") or article.get("pub_date") or "")[:10] for article in articles]
    best = sorted(articles, key=lambda article: (-builder.evidence_score(article.get("evidence_level")), str(article.get("entry_date") or "")), reverse=True)[0]
    base = baseline or {}
    strength = normalize_text(raw.get("strength"))
    if strength not in {"强", "中", "弱"}:
        strength = "强" if any(article.get("evidence_level") in {"I", "II"} for article in articles) else ("中" if len(articles) > 1 else "弱")
    tier = points[0]["priorityTier"] if points else "disease_progress"
    return {
        "id": signal_id,
        "date": max(dates),
        "date_range": {"from": min(dates), "to": max(dates)},
        "type": normalize_text(raw.get("type")) or base.get("type") or "文献证据",
        "strength": strength,
        "title": title,
        "summary": title,
        "takeaway": normalize_text(raw.get("takeaway")) or f"{len(articles)} 篇文献聚合形成该主题的近期证据变化。",
        "whySignal": normalize_text(raw.get("whySignal")) or "多篇近期 MG-core 文献形成主题聚集，值得继续追踪。",
        "evidenceBoundary": normalize_text(raw.get("evidenceBoundary")) or f"聚合 {len(articles)} 篇文献，证据等级为 {level_text}；不同研究不可直接横向比较，需全文核查。",
        "maUse": normalize_text(raw.get("maUse")) or "用于 MSL briefing、KOL 问题设计和后续全文追踪。",
        "signalScore": clamp_score(raw.get("signalScore"), 4 if len(articles) > 1 else 3),
        "related_pmids": [str(article.get("pmid") or "") for article in articles],
        "keywords": sorted(set((base.get("keywords") or []) + [topic for article in articles for topic in builder.infer_topics(article)])),
        "drugs": sorted(set((base.get("drugs") or []) + [drug.lower() for article in articles for drug in article_drugs(article)])),
        "score": round(float(base.get("score") or 0), 2),
        "article_count": len(articles),
        "china_related": any(bool(article.get("china_related")) for article in articles),
        "article": compact_ref(best),
        "refs": refs,
        "talkingPoints": points,
        "kolFocus": points,
        "medical_affairs": {
            "implication": f"{len(articles)} 篇 MG-core 文献聚合为“{title}”，可用于结构化 KOL 交流和后续证据追踪。",
            "suggested_kol_question": "这些研究在人群、终点、治疗节点和证据成熟度上，哪一项最可能改变当前 MG 临床决策？",
            "msl_action": "按 PMID 核对研究设计、样本量、终点和结果，再准备与 KOL 讨论的区隔问题。",
            "evidence_context": f"{level_text}；文献日期 {min(dates)}–{max(dates)}；摘要级聚合。",
        },
        "medical_affairs_implication": f"{len(articles)} 篇 MG-core 文献聚合为“{title}”，可用于结构化 KOL 交流和后续证据追踪。",
        "kol_leads": builder.aggregate_kol_leads(articles),
        "institution_leads": builder.aggregate_institution_leads(articles, builder.aggregate_kol_leads(articles)),
        "signal_to_kol": {
            "source_artifact": "data/literature-recent.js",
            "scope": "literature_only",
            "analysis_model": "literature-signal-to-kol-v2",
            "aggregation": "mg_core_topic_cluster_llm_normalized",
            "parent_signal_id": signal_id,
            "source_pmids": [str(article.get("pmid") or "") for article in articles],
            "auto_publish": True,
            "review_required": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate even when an enriched payload exists.")
    args = parser.parse_args()
    payload = load_js_global(SIGNALS_PATH, "MG_SIGNALS_DATA")
    literature = load_js_global(LITERATURE_PATH, "MG_LITERATURE_DATA")
    builder = load_builder_module()
    candidate_pmids = {
        str(pmid)
        for signal in payload.get("signals", [])
        for pmid in signal.get("related_pmids", [])
        if pmid
    }
    by_pmid = {str(article.get("pmid")): article for article in literature if str(article.get("pmid")) in candidate_pmids}
    records = records_for_prompt(list(by_pmid.values()))
    if not records:
        raise SystemExit("No deterministic MG-core signal records available")
    prompt = build_prompt(records)
    raw = parse_json_object(complete(prompt, system=SYSTEM, temperature=0.12, max_tokens=14000, use_cache=True))
    normalized = []
    covered = set()
    baseline_by_pmid = {
        str(pmid): signal
        for signal in payload.get("signals", [])
        for pmid in signal.get("related_pmids", [])
    }
    for raw_index, item in enumerate(raw.get("signals", []) or [], 1):
        raw_pmids = item.get("refPmids") or item.get("pmids") or []
        if not isinstance(raw_pmids, list):
            raw_pmids = [raw_pmids]
        available_pmids = [str(pmid) for pmid in raw_pmids if str(pmid) in by_pmid and str(pmid) not in covered]
        if not available_pmids:
            continue
        item_for_normalization = dict(item)
        item_for_normalization["refPmids"] = available_pmids
        filtered_points = []
        for point in item.get("talkingPoints", []) or []:
            if not isinstance(point, dict):
                continue
            point_copy = dict(point)
            point_pmids = point_copy.get("refPmids") or point_copy.get("pmids") or available_pmids
            if not isinstance(point_pmids, list):
                point_pmids = [point_pmids]
            point_copy["refPmids"] = [str(pmid) for pmid in point_pmids if str(pmid) in available_pmids]
            if point_copy["refPmids"]:
                filtered_points.append(point_copy)
        item_for_normalization["talkingPoints"] = filtered_points
        signal = normalize_signal(item_for_normalization, raw_index, by_pmid, baseline_by_pmid.get(available_pmids[0]) or {}, builder)
        if not signal:
            continue
        normalized.append(signal)
        covered.update(signal["related_pmids"])
    coverage = len(covered) / max(1, len(by_pmid))
    if coverage < 0.8:
        raise RuntimeError(f"LLM signal reference coverage too low: {len(covered)}/{len(by_pmid)}")
    # LLM may omit a low-priority record. Preserve it through the deterministic fallback
    # rather than silently dropping a source article from the public signal layer.
    for signal in payload.get("signals", []):
        missing = [pmid for pmid in signal.get("related_pmids", []) if pmid not in covered]
        if not missing:
            continue
        fallback_articles = [by_pmid[pmid] for pmid in missing if pmid in by_pmid]
        if not fallback_articles:
            continue
        fallback = dict(signal)
        fallback["id"] = f"L{len(normalized) + 1:02d}"
        fallback["related_pmids"] = missing
        fallback["article_count"] = len(missing)
        fallback["article"] = compact_ref(fallback_articles[0])
        fallback["refs"] = [compact_ref(article) for article in fallback_articles[:5]]
        fallback["title"] = "补充文献：" + (fallback_articles[0].get("title") or "近期 MG 证据")
        fallback["summary"] = fallback["title"]
        fallback["takeaway"] = "该文献未被 LLM 归入其他主题簇，保留为独立的近期 MG-core 证据入口。"
        fallback["whySignal"] = "这是 MG-core 候选窗口中的未归类文献，保留以避免证据在语义聚合时丢失。"
        fallback["evidenceBoundary"] = "确定性回退条目；仅作摘要级证据入口，需全文核查，不代表已形成跨文献趋势。"
        fallback["maUse"] = "用于逐篇证据追踪，不作为跨文献趋势结论。"
        fallback["talkingPoints"] = [
            {
                **point,
                "parentSignalId": fallback["id"],
                "parentSignalTitle": fallback.get("title") or fallback.get("summary") or "未归类近期文献",
                "refs": [compact_ref(article) for article in fallback_articles[:3]],
                "keyMessages": [f"PMID {article['pmid']}：{excerpt(article)}" for article in fallback_articles[:2]],
            }
            for point in (fallback.get("talkingPoints") or fallback.get("kolFocus") or [])[:1]
        ]
        fallback["kolFocus"] = fallback["talkingPoints"]
        fallback["signal_to_kol"] = {**(fallback.get("signal_to_kol") or {}), "analysis_model": "literature-signal-to-kol-v2-fallback", "parent_signal_id": fallback["id"], "source_pmids": missing}
        normalized.append(fallback)
    tier_rank = {"efgar": 0, "competitor_response": 1, "disease_progress": 2}

    def signal_sort_key(signal):
        points = signal.get("talkingPoints") or []
        first_point = points[0] if points else {}
        return (
            tier_rank.get(str(first_point.get("priorityTier") or "disease_progress"), 2),
            -float(signal.get("score") or 0),
            str(signal.get("title") or ""),
        )

    normalized.sort(key=signal_sort_key)
    for index, signal in enumerate(normalized, 1):
        signal["id"] = f"L{index:02d}"
        signal["signal_to_kol"]["parent_signal_id"] = signal["id"]
        for point in signal.get("talkingPoints", []):
            point["parentSignalId"] = signal["id"]
            point["parentSignalTitle"] = signal.get("title", "")
        signal["kolFocus"] = signal.get("talkingPoints", [])
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    policy = payload.setdefault("source_policy", {})
    policy.update({
        "analysis_model": "literature-signal-to-kol-v2",
        "aggregation": "mg_core_topic_cluster_llm_normalized",
        "llm_enrichment": True,
        "llm_reference_coverage": round(coverage, 3),
        "published_reference_coverage": round(len({pmid for signal in normalized for pmid in signal.get("related_pmids", [])}) / max(1, len(by_pmid)), 3),
        "llm_source": "scripts/enrich-literature-narrative.py",
    })
    payload["signals"] = normalized
    atomic_write_js_global(SIGNALS_PATH, "MG_SIGNALS_DATA", payload)
    if DASHBOARD_PATH.exists():
        dashboard = load_js_global(DASHBOARD_PATH, "MG_DASHBOARD_DATA")
        dashboard["top_signals"] = normalized[:5]
        if isinstance(dashboard.get("stats"), dict):
            dashboard["stats"]["signals"] = len(normalized)
        strength_counts = Counter(item.get("strength") for item in normalized)
        for stat_card in dashboard.get("stat_cards", []) or []:
            if stat_card.get("label") == "14 天信号":
                stat_card["value"] = len(normalized)
                stat_card["note"] = "MG-core 聚合 Signal"
        for section in dashboard.get("sections", []) or []:
            if section.get("title") != "情报中心":
                continue
            section["metric"] = f"{len(normalized)} 条 Signal"
            facts = section.get("facts") or []
            section["facts"] = [
                f"强信号 {strength_counts.get('强', 0)} 条" if str(fact).startswith("强信号") else fact
                for fact in facts
            ]
        for work_item in dashboard.get("work_items", []) or []:
            if work_item.get("label") == "近 14 天信号":
                work_item["count"] = len(normalized)
        atomic_write_js_global(DASHBOARD_PATH, "MG_DASHBOARD_DATA", dashboard)
    print(f"updated literature Signal-to-KOL: {len(normalized)} signals, {len(covered)}/{len(by_pmid)} PMIDs covered, coverage={coverage:.1%}")


if __name__ == "__main__":
    main()
