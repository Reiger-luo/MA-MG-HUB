#!/usr/bin/env python3
"""LLM-enrich conference-level panorama signals and KOL talking points.

This script is opt-in. It reads the already structured conference data, asks the
shared LLM client to synthesize meeting-level MA signals from actual abstracts,
then nests KOL-facing talking points under the signal they come from.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
DATA_JSON = PROJECT / "data" / "conference-data.json"
DATA_JS = PROJECT / "data" / "conference-data.js"
SCRIPTS = PROJECT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from llm_client import complete  # noqa: E402

SYSTEM = """你是神经免疫 / 重症肌无力会议摘要的医学事务分析师。
任务：基于给定会议的真实摘要条目，提炼“会议线索”和“KOL交流点”，并明确二者关系。
硬性要求：
1. 只输出 JSON object，不要 Markdown，不要解释。
2. 不要写“对照页”“HUB 升级目标”“raw search”“curated MG-core”“新闻式综述”“MSL 行动问题”等页面建设说明。
3. headline 必须是本会议所有线索的医学总结语，不是产品说明。
4. chapters 是会议线索：回答“本次会议说明 MG 领域什么方向正在变化”。数量按内容自然决定，建议 5–7 条；不要固定 4 条。
5. 每条线索必须包含 whySignal 和 evidenceBoundary：说明为什么它是会议级线索，以及证据边界是什么。
6. talkingPoints 是该线索下可转化为 KOL 交流的内容：回答“拿哪条证据去和 KOL 说什么/问什么”。每条必须有 parentSignalId、priorityTier、whyKol、keyMessages。
7. KOL 交流点优先级：
   - priorityTier="efgar"：efgartigimod / Vyvgart / ARGX-113 / efgar 相关数据，只要有明确数据，优先作为传递重点。
   - priorityTier="competitor_response"：竞品或其他治疗机制数据，必须从应对角度解读与 efgar 的区隔；可比较机制、人群、终点、给药、安全性、证据成熟度，但禁止虚构 head-to-head。
   - priorityTier="disease_progress"：最后才放与产品或治疗无直接关系但重要的疾病进展、监测、负担、诊断或特殊人群信息。
8. keyMessages 为 1–3 句可直接告诉 KOL 的中文 key message，优先包含具体数据、终点、时间点、人群或研究设计；不得编造数据。
9. refs / refKeys 只能使用输入 records 里的 key。每个 chapter 和 talkingPoint 选 1–4 个最相关证据锚点。
10. 如果证据只是设计或探索性结果，必须明确说“疗效数据待公布/需全文核查/探索性”。
"""

TIER_RANK = {"efgar": 0, "competitor_response": 1, "disease_progress": 2}
TIER_LABEL = {
    "efgar": "efgar重点传递",
    "competitor_response": "竞品应对解读",
    "disease_progress": "疾病进展传递",
}
EFGAR_ALIASES = ("efgartigimod", "vyvgart", "argx-113", "argx113", "efgar")


def load_payload() -> dict:
    if DATA_JSON.exists():
        return json.loads(DATA_JSON.read_text(encoding="utf-8"))
    text = DATA_JS.read_text(encoding="utf-8")
    prefix = "window.MG_CONFERENCE_DATA = "
    if not text.startswith(prefix):
        raise RuntimeError(f"Unexpected JS payload prefix in {DATA_JS}")
    body = text[len(prefix) :].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def write_payload(payload: dict) -> None:
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DATA_JS.write_text(
        "window.MG_CONFERENCE_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def local_token(item: dict) -> str:
    if item.get("programNumber"):
        return str(item["programNumber"])
    item_id = str(item.get("id") or "")
    token = item_id.split("::")[-1] if "::" in item_id else item_id
    if item.get("page"):
        return f"{token} · p.{item['page']}"
    return token


def mini_ref(item: dict) -> dict:
    insight = item.get("deepInsight") or {}
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "presentationType": item.get("presentationType"),
        "researchType": item.get("researchType"),
        "drugs": item.get("drugs", []),
        "topics": item.get("topics", []),
        "countries": item.get("countries", []),
        "sourceUrl": item.get("sourceUrl") or item.get("pageUrl"),
        "keyMetrics": insight.get("keyMetrics", [])[:3],
    }


def truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def records_for_prompt(items: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    # Put high-priority and metric-rich abstracts first, but keep all records in the prompt.
    sorted_items = sorted(
        items,
        key=lambda item: (
            -int(item.get("priorityScore") or 0),
            -len((item.get("deepInsight") or {}).get("keyMetrics", [])),
            item.get("title", ""),
        ),
    )
    records: list[dict] = []
    key_to_item: dict[str, dict] = {}
    for idx, item in enumerate(sorted_items, start=1):
        key = f"R{idx:03d}"
        insight = item.get("deepInsight") or {}
        key_to_item[key] = item
        records.append(
            {
                "key": key,
                "id": item.get("id"),
                "locator": local_token(item),
                "title": item.get("title"),
                "type": item.get("researchType"),
                "drugs": item.get("drugs", []),
                "topics": item.get("topics", []),
                "countries": item.get("countries", []),
                "priorityScore": item.get("priorityScore", 0),
                "keyMetrics": insight.get("keyMetrics", [])[:3],
                "kolKeyMessageZh": insight.get("kolKeyMessageZh", ""),
                "abstractZh": truncate(item.get("abstractZh") or "", 420),
            }
        )
    return records, key_to_item


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


def synthesize_conference(conference: str, items: list[dict]) -> tuple[dict, dict[str, dict]]:
    records, key_to_item = records_for_prompt(items)
    topic_counts = Counter(topic for item in items for topic in item.get("topics", []))
    drug_counts = Counter(drug for item in items for drug in item.get("drugs", []))
    type_counts = Counter(item.get("researchType") for item in items)
    country_counts = Counter(country for item in items for country in item.get("countries", []))
    stats = {
        "conference": conference,
        "total": len(items),
        "highPriority": sum(1 for item in items if int(item.get("priorityScore") or 0) >= 6),
        "chinaRelated": sum(1 for item in items if item.get("isChinaRelated")),
        "topTopics": topic_counts.most_common(10),
        "topDrugs": drug_counts.most_common(10),
        "topResearchTypes": type_counts.most_common(8),
        "topCountries": country_counts.most_common(10),
    }
    schema = {
        "conference": conference,
        "headline": "一句会议全景总结，不超过 70 个中文字符",
        "strategicRead": "一句补充解释，必须是医学内容总结，不是产品/页面说明",
        "chapters": [
            {
                "id": "S01",
                "title": "线索标题：回答会议说明什么变化",
                "takeaway": "该线索的实际内容解读，1–2句",
                "whySignal": "为什么它是会议级线索：多摘要支撑/改变证据格局/揭示未满足需求/提示MA机会",
                "evidenceBoundary": "证据边界：RCT/extension/RWE/探索性/样本量/需全文核查等",
                "maUse": "医学事务如何使用，1句",
                "signalScore": 1,
                "refKeys": ["R001", "R002"],
                "talkingPoints": [
                    {
                        "priorityTier": "efgar | competitor_response | disease_progress",
                        "dimension": "交流维度，2–6字",
                        "title": "交流主题标题",
                        "whyKol": "为什么值得与KOL交流；若为竞品，说明从什么角度应对与efgar区隔",
                        "kolScore": 1,
                        "keyMessages": ["1–3句给KOL传递的信息，带数据/终点/人群/设计"],
                        "refKeys": ["R001"],
                    }
                ],
            }
        ],
        "briefingQuestions": ["会议级必答问题"],
    }
    prompt = (
        "请根据以下会议摘要 records 生成会议级分析。返回 JSON object，结构必须完全遵循 schema。\n"
        "区分原则：chapters=会议线索，回答‘会议说明什么变化’；talkingPoints=KOL交流点，回答‘拿哪条证据去和KOL说什么/问什么’。\n"
        "同一摘要可以同时支撑线索和交流点，但交流点必须归属到一个线索下。\n"
        "交流点排序原则：efgar相关数据优先；竞品/其他治疗数据第二，必须从与efgar区隔和应对角度解读；非产品/非治疗疾病进展第三。\n"
        "线索和交流点数量由实际内容决定，建议 5–7 条；不要固定四条。\n\n"
        f"schema = {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"stats = {json.dumps(stats, ensure_ascii=False)}\n\n"
        f"records = {json.dumps(records, ensure_ascii=False)}"
    )
    reply = complete(prompt, system=SYSTEM, temperature=0.12, max_tokens=8192, use_cache=True)
    return parse_json_object(reply), key_to_item


def map_refs(keys: list, key_to_item: dict[str, dict]) -> list[dict]:
    refs: list[dict] = []
    seen: set[str] = set()
    for key in keys or []:
        item = key_to_item.get(str(key))
        if not item:
            continue
        item_id = str(item.get("id") or "")
        if item_id in seen:
            continue
        seen.add(item_id)
        refs.append(mini_ref(item))
    return refs


def clamp_score(value: Any, default: int = 3) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = default
    return max(1, min(score, 5))


def clean_tier(value: Any, refs: list[dict], raw: dict) -> str:
    tier = str(value or "").strip().lower().replace("-", "_")
    if tier in {"efgar", "efgartigimod", "vyvgart"}:
        return "efgar"
    if tier in {"competitor", "competitor_response", "competitive", "other_treatment"}:
        return "competitor_response"
    if tier in {"disease", "disease_progress", "non_product"}:
        return "disease_progress"
    blob = json.dumps(raw, ensure_ascii=False).lower() + " " + json.dumps(refs, ensure_ascii=False).lower()
    if any(alias in blob for alias in EFGAR_ALIASES):
        return "efgar"
    if any((ref.get("drugs") or []) for ref in refs):
        return "competitor_response"
    return "disease_progress"


def normalize_talking_point(
    point: dict,
    parent_id: str,
    parent_title: str,
    key_to_item: dict[str, dict],
) -> dict | None:
    if not isinstance(point, dict):
        return None
    ref_keys = point.get("refKeys") or point.get("refs") or []
    refs = map_refs(ref_keys if isinstance(ref_keys, list) else [], key_to_item)
    if not refs:
        return None
    messages = [str(msg).strip() for msg in point.get("keyMessages", []) if str(msg).strip()]
    if not messages:
        return None
    tier = clean_tier(point.get("priorityTier") or point.get("productAngle"), refs, point)
    title = str(point.get("title") or "").strip()
    if not title:
        title = TIER_LABEL[tier]
    return {
        "parentSignalId": parent_id,
        "parentSignalTitle": parent_title,
        "priorityTier": tier,
        "priorityLabel": TIER_LABEL[tier],
        "priorityRank": TIER_RANK[tier],
        "dimension": str(point.get("dimension") or "交流").strip(),
        "title": title,
        "whyKol": str(point.get("whyKol") or point.get("rationale") or "").strip(),
        "kolScore": clamp_score(point.get("kolScore"), 4 if tier == "efgar" else 3),
        "keyMessages": messages[:3],
        "refs": refs,
    }


def normalize_narrative(obj: dict, conference: str, existing: dict, key_to_item: dict[str, dict]) -> dict:
    chapters = []
    flat_kol_focus = []
    for idx, chapter in enumerate(obj.get("chapters", []), start=1):
        if not isinstance(chapter, dict):
            continue
        ref_keys = chapter.get("refKeys") or chapter.get("refs") or []
        refs = map_refs(ref_keys if isinstance(ref_keys, list) else [], key_to_item)
        if not refs:
            continue
        signal_id = str(chapter.get("id") or f"S{idx:02d}").strip() or f"S{idx:02d}"
        title = str(chapter.get("title") or "").strip()
        talking_points = []
        for raw_point in chapter.get("talkingPoints", []) or []:
            point = normalize_talking_point(raw_point, signal_id, title, key_to_item)
            if point:
                talking_points.append(point)
                flat_kol_focus.append(point)
        talking_points.sort(key=lambda p: (p["priorityRank"], -p["kolScore"], p["title"]))
        chapters.append(
            {
                "id": signal_id,
                "title": title,
                "takeaway": str(chapter.get("takeaway") or "").strip(),
                "whySignal": str(chapter.get("whySignal") or "").strip(),
                "evidenceBoundary": str(chapter.get("evidenceBoundary") or "").strip(),
                "maUse": str(chapter.get("maUse") or "").strip(),
                "signalScore": clamp_score(chapter.get("signalScore"), 4),
                "refs": refs,
                "talkingPoints": talking_points,
            }
        )

    # Backward-compatible fallback if a model returned top-level kolFocus only.
    if not flat_kol_focus:
        known = {chapter["id"]: chapter for chapter in chapters}
        title_to_id = {chapter["title"]: chapter["id"] for chapter in chapters}
        for raw_point in obj.get("kolFocus", []) or []:
            if not isinstance(raw_point, dict):
                continue
            parent_id = str(raw_point.get("parentSignalId") or "").strip()
            parent_id = parent_id if parent_id in known else title_to_id.get(str(raw_point.get("parentSignalTitle") or "").strip(), "")
            if not parent_id and chapters:
                parent_id = chapters[0]["id"]
            parent_title = known.get(parent_id, {}).get("title", "")
            point = normalize_talking_point(raw_point, parent_id, parent_title, key_to_item)
            if point:
                flat_kol_focus.append(point)
                for chapter in chapters:
                    if chapter["id"] == parent_id:
                        chapter.setdefault("talkingPoints", []).append(point)
                        break

    flat_kol_focus.sort(key=lambda p: (p["priorityRank"], -p["kolScore"], p["title"]))
    narrative = dict(existing or {})
    narrative.pop("competitiveComparison", None)
    narrative.update(
        {
            "headline": str(obj.get("headline") or "").strip(),
            "strategicRead": str(obj.get("strategicRead") or "").strip(),
            "chapters": chapters or existing.get("chapters", []),
            "kolFocus": flat_kol_focus,
            "briefingQuestions": [str(q).strip() for q in obj.get("briefingQuestions", []) if str(q).strip()][:6]
            or existing.get("briefingQuestions", []),
            "analysisModel": "signal-to-kol-v2",
            "talkingPointPriority": ["efgar", "competitor_response", "disease_progress"],
            "llmCurated": True,
            "curationSource": "scripts/enrich-conference-narrative.py",
        }
    )
    banned = ["对照页", "HUB 的升级目标", "raw search", "curated MG-core", "新闻式综述"]
    blob = json.dumps(narrative, ensure_ascii=False)
    hits = [term for term in banned if term in blob]
    if hits:
        raise ValueError(f"{conference} narrative still contains banned terms: {hits}")
    return narrative


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conference", action="append", default=[], help="Conference short title, e.g. 'AAN 2026'. Repeatable.")
    parser.add_argument("--force", action="store_true", help="Regenerate even if llmCurated already exists.")
    args = parser.parse_args()

    target_conferences = args.conference or ["AAN 2026", "EAN 2026"]
    payload = load_payload()
    narratives = payload.setdefault("meetingNarratives", {})

    for conference in target_conferences:
        existing = narratives.get(conference, {})
        if existing.get("llmCurated") and existing.get("analysisModel") == "signal-to-kol-v2" and not args.force:
            print(f"skip {conference}: already signal-to-kol-v2")
            continue
        items = [item for item in payload.get("abstracts", []) if item.get("conference") == conference]
        if not items:
            print(f"skip {conference}: no abstracts", file=sys.stderr)
            continue
        obj, key_to_item = synthesize_conference(conference, items)
        narratives[conference] = normalize_narrative(obj, conference, existing, key_to_item)
        write_payload(payload)
        print(
            f"updated {conference}: {len(narratives[conference].get('chapters', []))} signals, "
            f"{len(narratives[conference].get('kolFocus', []))} KOL points",
            flush=True,
        )


if __name__ == "__main__":
    main()
