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
LLM_BATCH_SIZE = 8
LLM_MAX_ATTEMPTS = 2

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
任务：基于给定的本周（7 天）MG-core PubMed records，把单篇候选归纳为文献级 Signal，并在每条 Signal 下生成 KOL talking points。
硬性要求：
1. 只输出 JSON object，不要 Markdown，不要解释。
2. records 已通过 MG-core 过滤；不得引入输入 records 以外的研究或数字。
3. signals 回答“近期文献说明了什么可追踪变化”，不能只是重复单篇文章标题；数量按证据自然决定，通常 6–10 条，最多 10 条。
4. 每条 signal 必须包含 title、takeaway、whySignal、gapBefore、gapFilled、remainingGap、evidenceItems、maUse、signalScore、refPmids、talkingPoints；每条最多 2 个 talkingPoints。
5. talkingPoints 必须回答“拿哪条证据去和 KOL 说什么/问什么”，每条包含 priorityTier、dimension、title、whyKol、keyMessages、refPmids。
6. priorityTier 排序：
   - efgar：efgartigimod / Vyvgart / ARGX-113 相关数据；只要确实是该条交流点的证据，优先传递。
   - competitor_response：其他治疗或机制；必须从机制、人群、终点、给药、安全性、证据成熟度与 efgar 区隔，不得虚构 head-to-head。
   - disease_progress：诊断、监测、患者负担、特殊人群、疾病机制等非直接产品进展。
7. evidenceItems 必须与 refPmids 一一对应；每篇写清 finding（实际结果）、gapContribution（补上哪块信息）和 boundary（这篇证据不能推出什么）。keyMessages 只能使用 records 的 title、abstract、evidenceLevel、studyTypes、journal 和已有 metrics；优先保留原始结果段中的人群、样本量、终点、时间点和数字。
8. 设计、探索性、病例或摘要级证据必须明确写“探索性/病例级/摘要级/需全文核查/疗效数据待公布”等边界；不能把关联写成因果，不能把不同研究横向比较成 head-to-head。
   网络荟萃分析/ITC 只能写“间接估计的改善幅度数值更大/排序靠前”，不能写“优于”；评论或 V 级机制推理只能写“报道/提示”，不能写“证实/证明”。
9. refPmids 只能填写输入 records 的 PMID，且每条 signal/talking point 至少绑定 1 个 PMID；每个 PMID 最多归入一个 signal，必须尽量覆盖全部 records。
10. 所有面向用户的叙事字段必须使用中文，包括 signal 的 title、takeaway、whySignal、evidenceBoundary、maUse，以及 talking point 的 dimension、title、whyKol、keyMessages；药物名、量表名和通用缩写可保留英文。
11. 父层字段不得套用同一句模板或互相复述：takeaway=研究实际发现及其解释；gapBefore=此前不知道什么；gapFilled=本期证据补了什么；remainingGap=仍不知道什么；whySignal=为何这组变化值得现在关注。
12. 不要生成作者姓名或机构名称；作者和机构由程序根据 PMID 自动聚合。"""


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


def strip_pmid_mentions(value: Any) -> str:
    """叙事只保留结论；PMID 由结构化证据项统一呈现。"""
    text = normalize_text(value)
    text = re.sub(
        r"PMIDs?\s*\d{6,9}(?:\s*[、,，/]\s*(?:PMIDs?\s*)?\d{6,9})*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"（\s*）|\(\s*\)", "", text)
    text = re.sub(r"\s+([，。；：])", r"\1", text)
    return text.strip(" ：:、，,；;\t\n")


def is_predominantly_chinese(value: Any) -> bool:
    """判断叙事是否以中文为主，同时允许医学缩写和药物英文名。"""
    text = normalize_text(value)
    chinese_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
    latin_word_count = len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z0-9]+)*", text))
    return chinese_count >= 2 and chinese_count / max(1, chinese_count + latin_word_count) >= 0.6


def chinese_or_fallback(value: Any, fallback: str, disallowed: set[str] | None = None) -> str:
    text = strip_pmid_mentions(value)
    if not is_predominantly_chinese(text) or text in (disallowed or set()):
        return fallback
    return text


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


def records_for_prompt(articles: list[dict], baseline_by_pmid: dict[str, dict] | None = None) -> list[dict]:
    records = []
    baseline_by_pmid = baseline_by_pmid or {}
    for article in articles:
        pmid = str(article.get("pmid") or "")
        baseline = baseline_by_pmid.get(pmid, {})
        records.append(
            {
                "pmid": pmid,
                "title": article.get("title", ""),
                "abstract": normalize_text(article.get("abstract"))[:1800],
                "evidenceLevel": article.get("evidence_level"),
                "studyTypes": article.get("study_types") or [],
                "journal": article.get("journal", ""),
                "journalIF": article.get("journal_if"),
                "chinaRelated": bool(article.get("china_related")),
                "candidateSignalTitle": strip_pmid_mentions(baseline.get("title")),
                "candidateSignalType": baseline.get("type", ""),
                "candidateSignalId": baseline.get("id", ""),
            }
        )
    return records


def batch_records(records: list[dict], batch_size: int = LLM_BATCH_SIZE) -> list[list[dict]]:
    """按 PMID 生成有界批次，并在请求模型前拒绝空值或重复记录。"""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    unique_records = []
    seen_pmids: set[str] = set()
    for record in records:
        pmid = str(record.get("pmid") or "")
        if not pmid:
            raise ValueError("Every LLM record must have a PMID")
        if pmid in seen_pmids:
            raise ValueError(f"Duplicate PMID in LLM records: {pmid}")
        seen_pmids.add(pmid)
        unique_records.append(record)
    if not any(record.get("candidateSignalTitle") for record in unique_records):
        return [unique_records[index:index + batch_size] for index in range(0, len(unique_records), batch_size)]

    # 尽量不把确定性候选簇拆到两个 LLM 批次，避免同一主题被重复生成。
    groups = []
    for record in unique_records:
        group_key = record.get("candidateSignalId") or record.get("candidateSignalTitle") or f"pmid:{record['pmid']}"
        if groups and groups[-1][0] == group_key:
            groups[-1][1].append(record)
        else:
            groups.append((group_key, [record]))
    batches = []
    current = []
    for _group_key, group in groups:
        if len(group) > batch_size:
            if current:
                batches.append(current)
                current = []
            batches.extend(group[index:index + batch_size] for index in range(0, len(group), batch_size))
            continue
        if current and len(current) + len(group) > batch_size:
            batches.append(current)
            current = []
        current.extend(group)
    if current:
        batches.append(current)
    return batches


def build_prompt(records: list[dict]) -> str:
    schema = {
        "signals": [
            {
                "title": "近期文献变化标题",
                "takeaway": "必须使用中文；1–2句写研究实际发现及其解释，不写追踪价值或局限",
                "whySignal": "必须使用中文；写该发现为何改变现有判断或开启可持续追踪的问题，不复述 takeaway",
                "gapBefore": "必须使用中文；本期证据出现前，具体缺少哪项人群/终点/路径/安全性信息",
                "gapFilled": "必须使用中文；这些结果具体补上了 gap 的哪一部分，不夸大为完全解决",
                "remainingGap": "必须使用中文；研究设计、证据等级、人群/终点差异和可推广性仍留下什么问题",
                "evidenceBoundary": "兼容字段；用一句话概括 remainingGap",
                "evidenceItems": [
                    {
                        "pmid": "PMID",
                        "finding": "必须使用中文；保留样本量、人群、终点、时间点、效应值和区间等实际结果",
                        "gapContribution": "必须使用中文；说明这篇结果单独补上什么信息",
                        "boundary": "必须使用中文；说明设计和外推限制",
                    }
                ],
                "maUse": "如何用于 MSL briefing 或后续证据追踪",
                "kolQuestion": "基于本组结果最值得向 KOL 追问的一个具体问题",
                "mslAction": "会前需要完成的一项具体核查或对比动作",
                "signalScore": 1,
                "refPmids": ["PMID"],
                "talkingPoints": [
                    {
                        "priorityTier": "efgar | competitor_response | disease_progress",
                        "dimension": "人群/终点/安全性/机制/路径等",
                        "title": "KOL交流主题",
                        "whyKol": "为什么值得与KOL讨论；竞品必须说明与efgar的区隔角度",
                        "kolScore": 1,
                        "keyMessages": ["必须使用中文；只用输入证据写出的1–3句可传递信息；句中不得写 PMID"],
                        "refPmids": ["PMID"],
                    }
                ],
            }
        ]
    }
    batch_pmids = [str(record.get("pmid") or "") for record in records]
    candidate_groups = []
    for record in records:
        candidate_id = str(record.get("candidateSignalId") or "")
        if candidate_id and candidate_id not in candidate_groups:
            candidate_groups.append(candidate_id)
    grouping_instruction = ""
    if candidate_groups:
        grouping_instruction = (
            f"records 已按确定性候选簇标注 candidateSignalId，本批包含 {json.dumps(candidate_groups, ensure_ascii=False)}。"
            "每个 candidateSignalId 必须且只能生成 1 条 signal；不得把同一候选簇拆成多条，也不得跨 candidateSignalId 合并。\n"
        )
    return (
        "请根据 records 生成文献级 Signal-to-KOL 分析。\n"
        f"本批共 {len(records)} 条 records，PMID 为 {json.dumps(batch_pmids, ensure_ascii=False)}。本批每个 PMID 必须恰好分配一次：不得遗漏、不得重复，也不得输出本批以外的 PMID。\n"
        + grouping_instruction +
        "所有面向用户的叙事字段必须使用中文；药物名、量表名和通用缩写可保留英文。\n"
        "字段责任必须严格区分：takeaway=研究实际发现及其解释；gapBefore=此前不知道什么；gapFilled=本期证据补了什么；remainingGap=仍不知道什么；whySignal=为什么这组变化值得现在关注。各字段不得使用同一句话或同义样板。\n"
        "区分原则：Signal 是父层，回答‘近期文献说明了什么变化’；talkingPoints 是子层，回答‘拿哪条证据去和 KOL 说什么/问什么’。每个 PMID 只归入一个 signal，必须尽量覆盖全部 records。\n"
        "同一 PMID 可以支持同一 signal 下的多个 talking point，但每条 talking point 必须归属于一个 signal。evidenceItems 必须逐篇覆盖 refPmids，且所有叙事字段、keyMessages 和标题里不得重复写 PMID；PMID 只放结构化的 refPmids/evidenceItems.pmid。\n"
        f"schema = {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"records = {json.dumps(records, ensure_ascii=False)}"
    )


def _accepted_batch_signals(raw_signals: Any, pending_pmids: set[str], claimed_pmids: set[str]) -> list[dict]:
    """保留批次内可用输出，并确保同一 PMID 不会进入多个原始 signal。"""
    accepted = []
    for item in raw_signals if isinstance(raw_signals, list) else []:
        if not isinstance(item, dict):
            continue
        item_pmids = item.get("refPmids") or item.get("pmids") or []
        if not isinstance(item_pmids, list):
            item_pmids = [item_pmids]
        available_pmids = []
        for pmid in item_pmids:
            pmid = str(pmid)
            if pmid in pending_pmids and pmid not in claimed_pmids and pmid not in available_pmids:
                available_pmids.append(pmid)
        if not available_pmids:
            continue

        item_copy = dict(item)
        item_copy["refPmids"] = available_pmids
        raw_points = item.get("talkingPoints", []) or []
        filtered_points = []
        if isinstance(raw_points, list):
            for point in raw_points:
                if not isinstance(point, dict):
                    continue
                point_copy = dict(point)
                point_pmids = point.get("refPmids") or point.get("pmids") or available_pmids
                if not isinstance(point_pmids, list):
                    point_pmids = [point_pmids]
                point_copy["refPmids"] = list(dict.fromkeys(
                    str(pmid) for pmid in point_pmids if str(pmid) in available_pmids
                ))
                if point_copy["refPmids"]:
                    filtered_points.append(point_copy)
        item_copy["talkingPoints"] = filtered_points
        accepted.append(item_copy)
        claimed_pmids.update(available_pmids)
    return accepted


def collect_llm_signals(
    records: list[dict],
    complete_fn=None,
    batch_size: int = LLM_BATCH_SIZE,
    max_attempts: int = LLM_MAX_ATTEMPTS,
) -> list[dict]:
    """分批请求 LLM；每次只重试未被有效输出覆盖的 PMID。"""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    complete_fn = complete if complete_fn is None else complete_fn
    collected_signals = []
    claimed_pmids: set[str] = set()

    for batch in batch_records(records, batch_size=batch_size):
        pending = {str(record["pmid"]): record for record in batch}
        for attempt in range(1, max_attempts + 1):
            if not pending:
                break
            requested_records = list(pending.values())
            try:
                response = complete_fn(
                    build_prompt(requested_records),
                    system=SYSTEM,
                    temperature=0.12,
                    max_tokens=14000,
                    use_cache=True,
                )
                raw = parse_json_object(response)
            except Exception as exc:
                print(
                    f"LLM batch attempt {attempt}/{max_attempts} failed for PMIDs "
                    f"{','.join(pending)}: {exc}",
                    file=sys.stderr,
                )
                continue

            accepted = _accepted_batch_signals(raw.get("signals", []), set(pending), claimed_pmids)
            collected_signals.extend(accepted)
            for signal in accepted:
                for pmid in signal["refPmids"]:
                    pending.pop(pmid, None)

        if pending:
            print(
                f"LLM omitted PMIDs after {max_attempts} attempts: {','.join(pending)}; using fallback",
                file=sys.stderr,
            )

    return collected_signals


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


def evidence_level_text(articles: list[dict]) -> str:
    levels = Counter(str(article.get("evidence_level") or "未分类") for article in articles)
    return "、".join(f"{level}级 {count}篇" for level, count in sorted(levels.items()))


def narrative_fallbacks(articles: list[dict], baseline: dict | None = None) -> dict[str, str]:
    count = len(articles)
    levels = evidence_level_text(articles)
    baseline = baseline or {}
    topics = list(dict.fromkeys(
        normalize_text(topic)
        for article in articles
        for topic in (article.get("keywords") or [])
        if is_predominantly_chinese(topic)
    ))
    topic_text = "、".join(topics[:2]) or strip_pmid_mentions(baseline.get("type")) or "MG 临床研究"
    baseline_title = strip_pmid_mentions(baseline.get("title"))
    title = baseline_title if is_predominantly_chinese(baseline_title) and "证据补充" not in baseline_title else f"{topic_text}出现可量化的新结果"
    remaining = f"现有证据构成为 {levels}，研究设计、人群和终点并不一致，摘要结果仍需结合全文确认。"
    return {
        "title": title,
        "takeaway": f"本期新增 {count} 项带结果数据的{topic_text}研究，可据此重新核对相关人群、终点与临床路径判断。",
        "whySignal": f"新增结果把{topic_text}从宽泛议题推进到可按研究设计和结果逐项验证的问题。",
        "gapBefore": f"此前{topic_text}缺少可同时定位人群、终点和结果方向的近期证据。",
        "gapFilled": f"本期 {count} 项研究提供了可追溯的摘要结果，补上了部分人群和结局信息。",
        "remainingGap": remaining,
        "evidenceBoundary": remaining,
        "maUse": "用于逐篇核对结果与研究边界，并据此准备专家交流问题。",
        "pointTitle": f"核对{topic_text}结果能否改变当前判断",
        "keyMessage": f"本期结果已提供具体研究人群和结局线索，但临床含义必须结合设计强度与外推边界解释。",
    }


def apply_evidence_language(value: Any, articles: list[dict]) -> str:
    """按证据设计收紧比较与因果措辞，避免把间接或评论性证据写成确定结论。"""
    text = strip_pmid_mentions(value)
    designs = " ".join(
        str(design).lower()
        for article in articles
        for design in (article.get("study_types") or [])
    )
    titles = " ".join(str(article.get("title") or "").lower() for article in articles)
    if "itc" in designs or "network meta" in titles or "indirect treatment" in titles:
        text = text.replace("显著优于", "间接估计的改善幅度数值大于").replace("优于", "间接估计的改善幅度数值大于")
    if articles and all(str(article.get("evidence_level") or "") == "V" for article in articles):
        text = text.replace("证实", "报道").replace("证明", "提示")
    return text


def normalize_evidence_items(raw_items: Any, articles: list[dict], fallback: dict[str, str]) -> list[dict]:
    """每个 PMID 只生成一个证据项，并保留逐篇结果、gap 贡献和边界。"""
    raw_by_pmid = {}
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            pmid = str(item.get("pmid") or "")
            if pmid and pmid not in raw_by_pmid:
                raw_by_pmid[pmid] = item

    evidence_items = []
    for article in articles:
        pmid = str(article.get("pmid") or "")
        raw = raw_by_pmid.get(pmid, {})
        design = " / ".join(str(value) for value in (article.get("study_types") or [])[:2]) or "研究设计待补充"
        level = str(article.get("evidence_level") or "未分类")
        original_excerpt = excerpt(article)
        raw_finding = apply_evidence_language(raw.get("finding") or raw.get("keyFinding"), [article])
        finding = raw_finding if is_predominantly_chinese(raw_finding) else f"摘要结果原文：{original_excerpt}"
        contribution = apply_evidence_language(chinese_or_fallback(
            raw.get("gapContribution") or raw.get("contribution"),
            "这项研究提供了可定位到具体人群和结局的结果，使该信号不再只停留在主题层面。",
        ), [article])
        boundary = chinese_or_fallback(
            raw.get("boundary") or raw.get("limit"),
            f"{design}，证据 {level} 级；仅按摘要定位，因果解释与人群外推需核查全文。",
        )
        evidence_items.append({
            "pmid": pmid,
            "finding": finding,
            "gapContribution": contribution,
            "boundary": boundary,
        })
    return evidence_items


def normalize_point(raw: dict, parent_id: str, parent_title: str, by_pmid: dict[str, dict], builder) -> dict | None:
    if not isinstance(raw, dict):
        return None
    pmids = raw.get("refPmids") or raw.get("pmids") or []
    if not isinstance(pmids, list):
        pmids = [pmids]
    articles = [by_pmid[str(pmid)] for pmid in pmids if str(pmid) in by_pmid]
    if not articles:
        return None
    refs = [compact_ref(article) for article in articles]
    tier = clean_tier(raw.get("priorityTier"), refs, raw)
    fallback = narrative_fallbacks(articles)
    raw_messages = raw.get("keyMessages", [])
    if not isinstance(raw_messages, list):
        raw_messages = [raw_messages]
    messages = [
        apply_evidence_language(msg, articles)
        for msg in raw_messages
        if is_predominantly_chinese(strip_pmid_mentions(msg))
    ]
    if not messages:
        messages = [fallback["keyMessage"]]
    return {
        "parentSignalId": parent_id,
        "parentSignalTitle": parent_title,
        "priorityTier": tier,
        "priorityLabel": {"efgar": "efgar重点传递", "competitor_response": "竞品应对解读", "disease_progress": "疾病进展传递"}[tier],
        "priorityRank": {"efgar": 0, "competitor_response": 1, "disease_progress": 2}[tier],
        "dimension": chinese_or_fallback(raw.get("dimension"), "临床结果"),
        "title": apply_evidence_language(chinese_or_fallback(raw.get("title"), parent_title or fallback["pointTitle"]), articles),
        "whyKol": apply_evidence_language(chinese_or_fallback(raw.get("whyKol"), "该证据可用于与专家讨论研究结果、临床意义和外推边界。"), articles),
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
    refs = [compact_ref(article) for article in articles]
    signal_id = f"L{signal_index:02d}"
    base = baseline or {}
    fallback = narrative_fallbacks(articles, base)
    title = chinese_or_fallback(raw.get("title"), fallback["title"])
    points = []
    raw_points = raw.get("talkingPoints", []) or []
    if not isinstance(raw_points, list):
        raw_points = []
    for point in raw_points[:2]:
        normalized = normalize_point(point, signal_id, title, by_pmid, builder)
        if normalized:
            points.append(normalized)
    if not points:
        points.append(
            normalize_point(
                {
                    "priorityTier": "disease_progress",
                    "title": fallback["pointTitle"],
                    "whyKol": "代表性文献可用于与 KOL 讨论结果、研究设计和证据边界。",
                    "keyMessages": [fallback["keyMessage"]],
                    "refPmids": [article.get("pmid") for article in articles],
                },
                signal_id,
                title,
                by_pmid,
                builder,
            )
        )
    points = [point for point in points if point]
    points.sort(key=lambda point: (point["priorityRank"], -point["kolScore"], point["title"]))
    level_text = evidence_level_text(articles)
    dates = [str(article.get("entry_date") or article.get("pub_date") or "")[:10] for article in articles]
    best = sorted(articles, key=lambda article: (-builder.evidence_score(article.get("evidence_level")), str(article.get("entry_date") or "")), reverse=True)[0]
    strength = normalize_text(raw.get("strength"))
    if strength not in {"强", "中", "弱"}:
        strength = "强" if any(article.get("evidence_level") in {"I", "II"} for article in articles) else ("中" if len(articles) > 1 else "弱")
    tier = points[0]["priorityTier"] if points else "disease_progress"
    takeaway = apply_evidence_language(chinese_or_fallback(raw.get("takeaway"), fallback["takeaway"]), articles)
    why_signal = apply_evidence_language(chinese_or_fallback(raw.get("whySignal"), fallback["whySignal"], {takeaway}), articles)
    evidence_boundary = chinese_or_fallback(
        raw.get("evidenceBoundary"),
        fallback["evidenceBoundary"],
        {takeaway, why_signal},
    )
    gap_before = apply_evidence_language(chinese_or_fallback(raw.get("gapBefore"), fallback["gapBefore"], {takeaway, why_signal}), articles)
    gap_filled = apply_evidence_language(chinese_or_fallback(raw.get("gapFilled"), why_signal or fallback["gapFilled"], {takeaway, gap_before}), articles)
    remaining_gap = apply_evidence_language(chinese_or_fallback(
        raw.get("remainingGap"),
        evidence_boundary or fallback["remainingGap"],
        {takeaway, why_signal, gap_before, gap_filled},
    ), articles)
    evidence_items = normalize_evidence_items(raw.get("evidenceItems"), articles, fallback)
    kol_question = chinese_or_fallback(
        raw.get("kolQuestion"),
        "这些结果中，哪一项最可能改变您对患者选择、治疗节点或监测方式的判断？",
    )
    msl_action = chinese_or_fallback(
        raw.get("mslAction"),
        "会前逐篇核对研究人群、主要终点、效应值与全文限制，并准备同类证据对照。",
    )
    return {
        "id": signal_id,
        "date": max(dates),
        "date_range": {"from": min(dates), "to": max(dates)},
        "type": chinese_or_fallback(raw.get("type"), chinese_or_fallback(base.get("type"), "文献证据")),
        "strength": strength,
        "title": title,
        "summary": title,
        "takeaway": takeaway,
        "whySignal": why_signal,
        "evidenceBoundary": evidence_boundary,
        "gapBefore": gap_before,
        "gapFilled": gap_filled,
        "remainingGap": remaining_gap,
        "evidenceItems": evidence_items,
        "maUse": chinese_or_fallback(raw.get("maUse"), fallback["maUse"]),
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
            "suggested_kol_question": kol_question,
            "msl_action": msl_action,
            "evidence_context": f"{level_text}；文献日期 {min(dates)}–{max(dates)}；摘要级聚合。",
        },
        "medical_affairs_implication": f"{len(articles)} 篇 MG-core 文献聚合为“{title}”，可用于结构化 KOL 交流和后续证据追踪。",
        "kol_leads": builder.aggregate_kol_leads(articles),
        "institution_leads": builder.aggregate_institution_leads(articles, builder.aggregate_kol_leads(articles)),
        "signal_to_kol": {
            "source_artifact": "data/literature-recent.js",
            "scope": "literature_only",
            "analysis_model": "literature-signal-to-kol-v3",
            "aggregation": "mg_core_topic_cluster_llm_normalized",
            "parent_signal_id": signal_id,
            "source_pmids": [str(article.get("pmid") or "") for article in articles],
            "auto_publish": True,
            "review_required": False,
        },
    }


def merge_llm_signals(raw_signals: Any, payload: dict, by_pmid: dict[str, dict], builder) -> tuple[list[dict], float]:
    """保留有效 LLM 聚类，并为每个遗漏 PMID 添加确定性中文回退条目。"""
    normalized = []
    llm_covered: set[str] = set()
    baseline_by_pmid = {}
    for signal in payload.get("signals", []) or []:
        for pmid in signal.get("related_pmids", []) or []:
            baseline_by_pmid.setdefault(str(pmid), signal)

    items = raw_signals if isinstance(raw_signals, list) else []
    for raw_index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        raw_pmids = item.get("refPmids") or item.get("pmids") or []
        if not isinstance(raw_pmids, list):
            raw_pmids = [raw_pmids]
        available_pmids = []
        for pmid in raw_pmids:
            pmid = str(pmid)
            if pmid in by_pmid and pmid not in llm_covered and pmid not in available_pmids:
                available_pmids.append(pmid)
        if not available_pmids:
            continue
        item_for_normalization = dict(item)
        item_for_normalization["refPmids"] = available_pmids
        filtered_points = []
        raw_points = item.get("talkingPoints", []) or []
        if not isinstance(raw_points, list):
            raw_points = []
        for point in raw_points[:2]:
            if not isinstance(point, dict):
                continue
            point_copy = dict(point)
            point_pmids = point_copy.get("refPmids") or point_copy.get("pmids") or available_pmids
            if not isinstance(point_pmids, list):
                point_pmids = [point_pmids]
            point_copy["refPmids"] = list(dict.fromkeys(
                str(pmid) for pmid in point_pmids if str(pmid) in available_pmids
            ))
            if point_copy["refPmids"]:
                filtered_points.append(point_copy)
        item_for_normalization["talkingPoints"] = filtered_points
        signal = normalize_signal(
            item_for_normalization,
            raw_index,
            by_pmid,
            baseline_by_pmid.get(available_pmids[0]) or {},
            builder,
        )
        if not signal:
            continue
        normalized.append(signal)
        llm_covered.update(signal["related_pmids"])

    coverage = len(llm_covered) / max(1, len(by_pmid))
    assigned_pmids = set(llm_covered)

    def add_fallback(baseline: dict, missing: list[str]) -> None:
        articles = [by_pmid[pmid] for pmid in missing]
        fallback_text = narrative_fallbacks(articles)
        fallback_raw = {
            "title": fallback_text["title"],
            "takeaway": fallback_text["takeaway"],
            "whySignal": fallback_text["whySignal"],
            "evidenceBoundary": fallback_text["evidenceBoundary"],
            "gapBefore": fallback_text["gapBefore"],
            "gapFilled": fallback_text["gapFilled"],
            "remainingGap": fallback_text["remainingGap"],
            "maUse": fallback_text["maUse"],
            "refPmids": missing,
            "talkingPoints": [{
                "priorityTier": "disease_progress",
                "dimension": "临床结果",
                "title": fallback_text["pointTitle"],
                "whyKol": "该证据可用于与专家讨论研究结果、临床意义和外推边界。",
                "keyMessages": [fallback_text["keyMessage"]],
                "refPmids": missing,
            }],
        }
        signal = normalize_signal(
            fallback_raw,
            len(normalized) + 1,
            by_pmid,
            baseline,
            builder,
        )
        if not signal:
            return
        signal["signal_to_kol"]["analysis_model"] = "literature-signal-to-kol-v3-fallback"
        signal["signal_to_kol"]["aggregation"] = "deterministic_missing_pmid_fallback"
        normalized.append(signal)
        assigned_pmids.update(signal["related_pmids"])

    for baseline in payload.get("signals", []) or []:
        missing = []
        for pmid in baseline.get("related_pmids", []) or []:
            pmid = str(pmid)
            if pmid in by_pmid and pmid not in assigned_pmids and pmid not in missing:
                missing.append(pmid)
        if missing:
            add_fallback(baseline, missing)

    orphan_pmids = [pmid for pmid in sorted(by_pmid) if pmid not in assigned_pmids]
    if orphan_pmids:
        add_fallback({}, orphan_pmids)

    published_pmids = [pmid for signal in normalized for pmid in signal.get("related_pmids", [])]
    if len(published_pmids) != len(set(published_pmids)) or set(published_pmids) != set(by_pmid):
        raise RuntimeError("Published signal PMID invariant failed")

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
    return normalized, coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate even when an enriched payload exists.")
    args = parser.parse_args()
    _published_payload = load_js_global(SIGNALS_PATH, "MG_SIGNALS_DATA")
    literature = load_js_global(LITERATURE_PATH, "MG_LITERATURE_DATA")
    builder = load_builder_module()
    # 每次都从确定性主题簇重新起步，避免重复执行 enrichment 后信号越拆越细。
    payload = builder.build_signals(literature)
    candidate_pmid_order = list(dict.fromkeys(
        str(pmid)
        for signal in payload.get("signals", [])
        for pmid in signal.get("related_pmids", [])
        if pmid
    ))
    candidate_pmids = set(candidate_pmid_order)
    by_pmid = {str(article.get("pmid")): article for article in literature if str(article.get("pmid")) in candidate_pmids}
    baseline_by_pmid = {
        str(pmid): signal
        for signal in payload.get("signals", [])
        for pmid in signal.get("related_pmids", [])
    }
    ordered_articles = [by_pmid[pmid] for pmid in candidate_pmid_order if pmid in by_pmid]
    records = records_for_prompt(ordered_articles, baseline_by_pmid)
    if not records:
        raise SystemExit("No deterministic MG-core signal records available")
    raw_signals = collect_llm_signals(records)
    normalized, coverage = merge_llm_signals(raw_signals, payload, by_pmid, builder)
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    policy = payload.setdefault("source_policy", {})
    policy.update({
        "analysis_model": "literature-signal-to-kol-v3",
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
        dashboard["signal_summary"] = builder.build_signal_summary(normalized)
        dashboard["top_signals"] = normalized[:5]
        if isinstance(dashboard.get("stats"), dict):
            dashboard["stats"]["signals"] = len(normalized)
        strength_counts = Counter(item.get("strength") for item in normalized)
        for stat_card in dashboard.get("stat_cards", []) or []:
            if stat_card.get("label") in {"14 天信号", "本周信号"}:
                stat_card["label"] = "本周信号"
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
            if work_item.get("label") in {"近 14 天信号", "本周信号"}:
                work_item["label"] = "本周信号"
                work_item["count"] = len(normalized)
        atomic_write_js_global(DASHBOARD_PATH, "MG_DASHBOARD_DATA", dashboard)
    llm_covered_count = round(coverage * len(by_pmid))
    print(f"updated literature Signal-to-KOL: {len(normalized)} signals, {llm_covered_count}/{len(by_pmid)} PMIDs covered by LLM, coverage={coverage:.1%}")


if __name__ == "__main__":
    main()
