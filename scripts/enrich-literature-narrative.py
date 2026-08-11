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

SYSTEM = """你是一名长期从事重症肌无力（myasthenia gravis, MG）诊疗和临床研究的神经肌病专家，同时熟悉医学事务证据解读。
任务：仅基于给定的本周（7 天）MG-core PubMed 标题、摘要和结构化元数据，先逐篇判断是否具有相对当前 MG 临床实践的增量价值，再把真正值得关注的文献归纳为 Signal，并生成 KOL talking points。
硬性要求：
1. 只输出 JSON object，不要 Markdown，不要解释。
2. records 已通过 MG-core 过滤；不得引入输入 records 以外的研究或数字。
3. 必须先对每个 PMID 输出 recordDecisions：include=构成明确的本周增量信号；background=与 MG 有关但主要是背景补充、重复已知结论或证据过弱；exclude=摘要显示并非有效 MG 情报或结论存在根本性方法问题。每个 PMID 必须且只能裁决一次。
4. signals 只纳入 decision=include 的 PMID，数量由证据自然决定，可以为 0；不得为了覆盖全部文献或凑数量而制造信号。每条 signal 必须包含 type、strength、title、takeaway、whySignal、gapBefore、gapFilled、remainingGap、evidenceItems、maUse、signalScore、strategicNoveltyScore、noveltyType、refPmids、talkingPoints；每条最多 2 个 talkingPoints。
5. talkingPoints 必须回答“拿哪条证据去和 KOL 说什么/问什么”，每条包含 priorityTier、dimension、title、whyKol、keyMessages、refPmids。
6. priorityTier 排序：
   - efgar：efgartigimod / Vyvgart / ARGX-113 相关数据；只要确实是该条交流点的证据，优先传递。
   - competitor_response：其他治疗或机制；必须从机制、人群、终点、给药、安全性、证据成熟度与 efgar 区隔，不得虚构 head-to-head。
   - disease_progress：诊断、监测、患者负担、特殊人群、疾病机制等非直接产品进展。
7. evidenceItems 必须与 refPmids 一一对应；每篇写清 finding（实际结果）、gapContribution（相对现有 MG 认识补上什么）和 boundary（最关键的设计或外推限制）。finding 必须完整翻译摘要结果段的全部关键数字与结论（样本量、终点、效应值、区间、时间点），不得截断、不得以省略号结尾、不得只写一句概括。keyMessages 只能使用 records 的 title、abstract、evidenceLevel、studyTypes、pubTypes、journal 和已有 metrics；优先保留原始结果段中的人群、样本量、终点、时间点和数字。
8. 设计、探索性、病例或摘要级证据必须明确写“探索性/病例级/摘要级/需全文核查/疗效数据待公布”等边界；不能把关联写成因果，不能把不同研究横向比较成 head-to-head。
   网络荟萃分析/ITC 只能写“间接估计的改善幅度数值更大/排序靠前”，不能写“优于”；评论或 V 级机制推理只能写“报道/提示”，不能写“证实/证明”。
   病例报告、无对照单臂研究、动物/体外或纯计算机制研究不得写成可改变临床实践，也不得宣称可替代 PLEX、IVIG 或其他标准治疗。
9. refPmids 只能填写输入 records 中 decision=include 的 PMID，且每条 signal/talking point 至少绑定 1 个 PMID；每个 include PMID 必须且最多归入一个 signal，background/exclude PMID 不得进入 signals。
10. 所有面向用户的叙事字段必须使用中文，包括 signal 的 title、takeaway、whySignal、evidenceBoundary、maUse，以及 talking point 的 dimension、title、whyKol、keyMessages；药物名、量表名和通用缩写可保留英文。
11. 父层字段不得套用同一句模板或互相复述：takeaway=MG 专家对结果的临床结论；gapBefore=此前具体不知道什么；gapFilled=本期证据真正补了什么；remainingGap=最关键且足以限制应用的缺口；whySignal=这项结果改变、强化或不改变哪项临床判断。
12. 不要生成作者姓名或机构名称；作者和机构由程序根据 PMID 自动聚合。"""

SELECTION_RULES = """纳入必须保守：
- include 通常必须能回答一个具体且当前可讨论的 MG 临床决策问题，valueScore 必须为 3–5。优先包括比较性治疗试验、MG 为主要研究对象的大型调整队列、具有临床性能指标的前瞻性诊断研究，或未满足场景中的前瞻性干预数据。
- 另设“概念/战略信号”例外：只用于原本会因纯计算、机制或模型设计而进入 background 的研究。若研究提出一个具体、可证伪且可能改变 MG 药理、疾病分层、治疗监测或开发框架的新命题，可以 include；但必须 strategicNoveltyScore≥4、noveltyType 为 concept_reframing 或 pharmacology_threshold，并分别写清 conceptAdvance、clinicalImplication 和验证路径。此类信号 strength 必须为弱、signalScore 最高为3，不得写成可改变当前临床实践。前瞻性临床干预、诊断研究或调整队列若已满足常规 include 条件，仍按直接临床证据评分，不得改套概念例外而降级。
- “新术语”本身不等于新概念。需区分既有上位分类与真正新增命题：例如沿用“补体介导疾病”这一既有总称不构成新概念；若研究以跨适应证数据挑战既有 C5 抑制浓度阈值，则新颖性来自可验证的药理阈值假说，而不是重新命名疾病。
- background 的 valueScore 为 1–2。普通病例/小病例系列、基于病例报告的综述、小样本发现型组学或生物标志物、无比较组的单中心回顾性描述队列、纯计算/体外机制、重复已知标准治疗结论、MG 仅为很小且无法解释的亚组，默认均为 background。
- exclude 的 valueScore 为 1。动物病例、MG 只是偶然背景，以及摘要中的研究设计不能支持作者核心结论时，应 exclude。
- 单例严重安全事件只有在摘要明确显示此前未识别、致死或足以立即改变监测行为时才可 include 为弱信号；“罕见、严重”本身不等于新增信号。
- 仅分析死亡者的死亡年龄、再与一般人群预期寿命比较，不能推出患者生存更好；没有风险集和随访时间的此类结论应按方法学缺陷处理。
- 同一 signal 内的文献必须回答同一个具体临床问题，且共享可解释的人群、干预/暴露和结局链条。仅仅同属“安全性、诊断、预后、机制”等大类不能合并；不同工具、不同治疗、不同暴露或不同决策节点必须拆开。"""


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
                # 摘要必须完整传入：截断会让模型看不到结果段，导致 finding 不完整
                "abstract": normalize_text(article.get("abstract"))[:4000],
                "evidenceLevel": article.get("evidence_level"),
                "studyTypes": article.get("study_types") or [],
                "pubTypes": article.get("pub_types") or [],
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
        "recordDecisions": [
            {
                "pmid": "PMID",
                "decision": "include | background | exclude",
                "category": "治疗疗效与定位 | 急性期与危象 | 安全性与药物警戒 | 诊断与监测 | 预后与流行病学 | 机制与转化 | 临床路径 | 病例级警示",
                "valueScore": "1–5整数",
                "strategicNoveltyScore": "1–5整数：5=可能重塑疾病/药理/开发框架；4=明确挑战既有框架并有MG相关战略含义；1–2=沿用旧概念或普通探索",
                "noveltyType": "none | concept_reframing | pharmacology_threshold | method",
                "conceptAdvance": "必须使用中文；具体说明新增或被挑战的命题，不能只说首次、新颖或值得关注",
                "clinicalImplication": "必须使用中文；若未来验证，对MG判断、监测或开发可能影响什么；不得写成当前建议",
                "reason": "一句话说明相对当前 MG 实践的增量价值或不纳入原因",
            }
        ],
        "signals": [
            {
                "type": "治疗证据 | 急性期与危象 | 安全性 | 诊断与监测 | 预后与流行病学 | 机制与转化 | 临床路径 | 病例级警示",
                "strength": "强 | 中 | 弱",
                "title": "近期文献变化标题",
                "takeaway": "必须使用中文；1–2句先回答临床问题，再写研究实际发现及其临床解释，不写追踪价值或局限",
                "whySignal": "必须使用中文；明确该发现改变、强化或不改变哪项现有 MG 临床判断，不复述 takeaway",
                "gapBefore": "必须使用中文；本期证据出现前，具体缺少哪项人群/终点/路径/安全性信息",
                "gapFilled": "必须使用中文；这些结果具体补上了 gap 的哪一部分，不夸大为完全解决",
                "remainingGap": "必须使用中文；只突出最关键、足以限制临床应用或外推的一至两项问题",
                "evidenceBoundary": "兼容字段；用一句话概括 remainingGap",
                "clinicalQuestion": "必须使用中文；本信号共同回答的一个具体临床问题",
                "aggregationRationale": "必须使用中文；若聚合多篇，逐项说明这些文献为何属于同一人群/干预或暴露/结局/决策节点；单篇可简写",
                "evidenceItems": [
                    {
                        "pmid": "PMID",
                        "finding": "必须使用中文；完整写出研究结果的全部关键内容：样本量、人群、干预、主要终点、时间点、效应值及区间/置信区间，按摘要原文逐项翻译，不得省略、概括或以省略号结尾；药物名、量表名可保留英文",
                        "gapContribution": "必须使用中文；说明这篇结果单独补上什么信息",
                        "boundary": "必须使用中文；说明设计和外推限制",
                    }
                ],
                "maUse": "如何用于 MSL briefing 或后续证据追踪",
                "kolQuestion": "基于本组结果最值得向 KOL 追问的一个具体问题",
                "mslAction": "会前需要完成的一项具体核查或对比动作",
                "signalScore": "1–5整数：5=可能改变实践或重要Ⅲ期/指南/安全警示；4=明显推进临床判断；3=有明确增量但受设计限制；2=主要为探索或强化已知；1=无独立信号价值",
                "strategicNoveltyScore": "1–5整数；与证据成熟度独立评分",
                "noveltyType": "none | concept_reframing | pharmacology_threshold | method",
                "conceptAdvance": "必须使用中文；这条信号新增或挑战的具体命题",
                "clinicalImplication": "必须使用中文；验证成功后可能影响什么，不写成当前实践建议",
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
            "candidateSignalId 只用于组织批次，不是最终医学分类：若同一候选簇中的文献回答不同临床问题，必须拆分；"
            "若不同 candidateSignalId 的文献确实回答同一个具体临床问题，可以合并，但必须填写 clinicalQuestion 和 aggregationRationale，"
            "说明它们共享的人群、干预或暴露、结局及临床决策节点；仅共享疾病大类或主题词不得合并。\n"
        )
    return (
        "请根据 records 生成文献级 Signal-to-KOL 分析。\n"
        f"本批共 {len(records)} 条 records，PMID 为 {json.dumps(batch_pmids, ensure_ascii=False)}。本批每个 PMID 必须在 recordDecisions 中恰好裁决一次；只有 include PMID 才能进入 signals，且不得输出本批以外的 PMID。\n"
        + grouping_instruction + SELECTION_RULES + "\n" +
        "所有面向用户的叙事字段必须使用中文；药物名、量表名和通用缩写可保留英文。\n"
        "分类必须依据研究主要回答的临床问题，而不是依据标题中的单个关键词。strength 只表示证据成熟度与当前临床可行动性，不等同于战略新颖性、evidenceLevel 或期刊 IF。强信号通常需要 I/II 级比较性临床证据且 signalScore≥4；III/IV 级通常最高为中；V 级、病例、动物/体外和纯计算机制研究通常为弱或 background。满足概念/战略信号例外的纯计算研究可以 include，但必须标为弱，且清楚说明尚不可用于剂量或治疗调整。\n"
        "MG 专家判断时需核查：AChR/MuSK/LRP4/血清阴性亚型，gMG/OMG/危象/胸腺瘤场景，急性救援或长期维持，是否有对照与伴随治疗，以及 MG-ADL/QMG/MGC/MGFA、危象、住院、激素减量等终点是否具有临床意义。\n"
        "字段责任必须严格区分：takeaway=MG 专家临床结论；gapBefore=此前不知道什么；gapFilled=本期证据补了什么；remainingGap=限制应用的关键缺口；whySignal=改变、强化或不改变什么判断。各字段不得使用同一句话或同义样板。\n"
        "区分原则：Signal 是父层，回答‘近期文献说明了什么变化’；talkingPoints 是子层，回答‘拿哪条证据去和 KOL 说什么/问什么’。每个 include PMID 只归入一个 signal；background/exclude 只保留在 recordDecisions。\n"
        "同一 PMID 可以支持同一 signal 下的多个 talking point，但每条 talking point 必须归属于一个 signal。evidenceItems 必须逐篇覆盖 refPmids，且所有叙事字段、keyMessages 和标题里不得重复写 PMID；PMID 只放结构化的 refPmids/evidenceItems.pmid。\n"
        f"schema = {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"records = {json.dumps(records, ensure_ascii=False)}"
    )


def normalize_record_decisions(raw_decisions: Any, pending_pmids: set[str]) -> dict[str, dict]:
    """规范逐篇价值裁决；无效或重复 PMID 留给下一次有界重试。"""
    normalized = {}
    for item in raw_decisions if isinstance(raw_decisions, list) else []:
        if not isinstance(item, dict):
            continue
        pmid = str(item.get("pmid") or "")
        decision = normalize_text(item.get("decision")).lower()
        if pmid not in pending_pmids or pmid in normalized or decision not in {"include", "background", "exclude"}:
            continue
        normalized[pmid] = {
            "pmid": pmid,
            "decision": decision,
            "category": normalize_text(item.get("category")),
            "valueScore": clamp_score(item.get("valueScore"), 3 if decision == "include" else 2),
            "strategicNoveltyScore": clamp_score(item.get("strategicNoveltyScore"), 1),
            "noveltyType": normalize_text(item.get("noveltyType")).lower() or "none",
            "conceptAdvance": strip_pmid_mentions(item.get("conceptAdvance")),
            "clinicalImplication": strip_pmid_mentions(item.get("clinicalImplication")),
            "reason": normalize_text(item.get("reason")),
        }
    return normalized


def is_valid_concept_signal(item: dict, record: dict) -> bool:
    """识别低成熟度但具有明确、可验证战略命题的概念信号。"""
    novelty_type = normalize_text(item.get("noveltyType")).lower()
    novelty_score = clamp_score(item.get("strategicNoveltyScore"), 1)
    concept_advance = strip_pmid_mentions(item.get("conceptAdvance"))
    clinical_implication = strip_pmid_mentions(item.get("clinicalImplication"))
    blob = " ".join([
        str(record.get("title") or ""),
        str(record.get("abstract") or ""),
        " ".join(record.get("studyTypes") or []),
    ]).lower()
    has_testable_frame = any(term in blob for term in (
        "threshold", "concentration", "dose-response", "dose response", "pharmacokinetic",
        "pharmacodynamic", "predict", "model", "framework", "stratification", "classifier",
    ))
    has_mg_link = any(term in blob for term in (
        "myasthenia gravis", "generalized myasthenia", "gmg", "mg-adl", "qmg",
    ))
    return (
        novelty_type in {"concept_reframing", "pharmacology_threshold"}
        and novelty_score >= 4
        and is_predominantly_chinese(concept_advance)
        and len(concept_advance) >= 12
        and is_predominantly_chinese(clinical_implication)
        and len(clinical_implication) >= 12
        and has_testable_frame
        and has_mg_link
    )


def apply_decision_evidence_ceiling(decision: dict, record: dict) -> dict:
    """用标题/摘要与既有证据分级拦截病例和非临床研究的过度纳入。"""
    item = dict(decision)
    blob = " ".join([
        str(record.get("title") or ""),
        str(record.get("abstract") or ""),
        " ".join(record.get("studyTypes") or []),
        " ".join(record.get("pubTypes") or []),
    ]).lower()
    animal = any(term in blob for term in (
        "animal study", "animal model", "rat model", "mouse model", "feline",
        "in a cat", "in cats", "in a dog", "in dogs", "veterinary",
    ))
    laboratory_or_computational = any(term in blob for term in (
        "in vitro", "network toxicology", "molecular dynamics", "machine learning model",
        "purely computational", "computational study",
    ))
    case_level = any(term in blob for term in (
        "case report", "case reports", "case series", "we report a patient", "two cases",
    ))
    uncontrolled_review = "systematic review" in blob and any(
        term in blob for term in ("case report", "case reports", "case series")
    )
    insufficient_mg_subgroup = (
        any(term in blob for term in ("among mg patients", "mg subgroup", "patients with mg"))
        and any(term in blob for term in ("insufficient events", "precluding reliable", "unable to estimate", "could not estimate"))
    )
    invalid_decedent_comparison = (
        "death certificate" in blob
        and "age at death" in blob
        and any(term in blob for term in ("life expectancy", "general population"))
    )
    evidence_level = str(record.get("evidenceLevel") or "")
    descriptive_single_center = (
        evidence_level == "IV"
        and "single arm" in blob
        and "retrospective" in blob
        and any(term in blob for term in ("single-center", "single center"))
        and not any(term in blob for term in ("matched control", "matched comparator", "propensity score", "nationwide", "population-based"))
    )
    exceptional_safety = (
        "安全性" in str(item.get("category") or "")
        and any(term in blob for term in ("fatal", "death", "previously unreported", "first safety signal"))
    )
    decision_name = item.get("decision")
    reason = str(item.get("reason") or "")
    valid_concept_signal = is_valid_concept_signal(item, record)
    if valid_concept_signal and not (animal or invalid_decedent_comparison):
        item.update({
            "decision": "include",
            "valueScore": 3,
            "reason": reason + " 临床证据尚不成熟，但提出了可验证且具有MG战略含义的新命题，作为弱概念信号纳入。",
        })
        return item
    if decision_name == "exclude" and not (animal or invalid_decedent_comparison):
        fundamental_failure = any(term in reason for term in ("根本性方法", "方法学缺陷", "不能推出", "无效研究"))
        incidental_mg = any(term in reason for term in ("MG只是偶然", "MG 只是偶然", "并非MG", "非MG情报"))
        if not fundamental_failure and not incidental_mg:
            item.update({
                "decision": "background",
                "valueScore": min(2, int(item.get("valueScore") or 1)),
                "reason": reason + " 该文仍属MG相关病例或探索性背景，不作为正式信号，但保留在背景层。",
            })
        return item
    if decision_name != "include":
        return item
    if animal or invalid_decedent_comparison:
        item.update({
            "decision": "exclude",
            "valueScore": 1,
            "reason": reason + " 动物证据或缺少有效风险集的死亡者比较不进入临床周更信号。",
        })
    elif (
        case_level
        or uncontrolled_review
        or evidence_level == "V"
        or insufficient_mg_subgroup
        or descriptive_single_center
        or laboratory_or_computational
    ) and not exceptional_safety:
        if descriptive_single_center:
            ceiling_reason = " 无比较组的单中心回顾性描述队列按证据上限降为背景。"
        elif insufficient_mg_subgroup:
            ceiling_reason = " MG亚组事件不足以支持可靠估计，按证据上限降为背景。"
        elif laboratory_or_computational:
            ceiling_reason = " 体外或计算性探索尚无直接临床证据，保留为背景。"
        else:
            ceiling_reason = " 病例级、非对照综述或 V 级证据按临床证据上限降为背景。"
        item.update({
            "decision": "background",
            "valueScore": min(2, int(item.get("valueScore") or 2)),
            "reason": reason + ceiling_reason,
        })
    return item


def _accepted_batch_signals(
    raw_signals: Any,
    pending_pmids: set[str],
    claimed_pmids: set[str],
    include_pmids: set[str] | None = None,
    records_by_pmid: dict[str, dict] | None = None,
) -> list[dict]:
    """保留批次内可用输出，并确保同一 PMID 不会进入多个原始 signal。"""
    accepted = []
    for item in raw_signals if isinstance(raw_signals, list) else []:
        if not isinstance(item, dict):
            continue
        item_pmids = item.get("refPmids") or item.get("pmids") or []
        if not isinstance(item_pmids, list):
            item_pmids = [item_pmids]
        eligible_item_pmids = {
            str(pmid)
            for pmid in item_pmids
            if str(pmid) in pending_pmids and str(pmid) not in claimed_pmids
        }
        if include_pmids is not None and eligible_item_pmids - include_pmids:
            # 若原始叙事混入已降为背景/排除的文献，整条拒绝并让 include PMID 单独重试，避免文字残留污染。
            continue
        available_pmids = []
        for pmid in item_pmids:
            pmid = str(pmid)
            if (
                pmid in pending_pmids
                and pmid not in claimed_pmids
                and pmid not in available_pmids
                and (include_pmids is None or pmid in include_pmids)
            ):
                available_pmids.append(pmid)
        if not available_pmids:
            continue
        candidate_ids = {
            str((records_by_pmid or {}).get(pmid, {}).get("candidateSignalId") or "")
            for pmid in available_pmids
        } - {""}
        if len(candidate_ids) > 1:
            # 候选簇只是确定性预分组。跨簇聚合必须由模型明确给出同一临床问题及聚合依据，
            # 防止仅凭“安全性/诊断/预后”等宽泛大类拼接文献。
            clinical_question = strip_pmid_mentions(item.get("clinicalQuestion"))
            aggregation_rationale = strip_pmid_mentions(item.get("aggregationRationale"))
            if not (
                is_predominantly_chinese(clinical_question)
                and is_predominantly_chinese(aggregation_rationale)
                and len(clinical_question) >= 8
                and len(aggregation_rationale) >= 16
            ):
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


def collect_llm_analysis(
    records: list[dict],
    complete_fn=None,
    batch_size: int = LLM_BATCH_SIZE,
    max_attempts: int = LLM_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """分批请求 LLM；逐篇裁决或有效 signal 任一完成后即停止重试该 PMID。"""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    complete_fn = complete if complete_fn is None else complete_fn
    collected_signals = []
    collected_decisions = {}
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

            decisions = normalize_record_decisions(raw.get("recordDecisions", []), set(pending))
            decisions = {
                pmid: apply_decision_evidence_ceiling(item, pending[pmid])
                for pmid, item in decisions.items()
            }
            include_pmids = {pmid for pmid, item in decisions.items() if item["decision"] == "include"}
            accepted = _accepted_batch_signals(
                raw.get("signals", []),
                set(pending),
                claimed_pmids,
                include_pmids if decisions else None,
                pending,
            )
            for signal in accepted:
                signal_decisions = [
                    decisions[pmid]
                    for pmid in signal.get("refPmids", [])
                    if pmid in decisions
                ]
                if not signal_decisions:
                    continue
                most_novel = max(
                    signal_decisions,
                    key=lambda item: int(item.get("strategicNoveltyScore") or 1),
                )
                raw_novelty_score = clamp_score(signal.get("strategicNoveltyScore"), 1)
                decision_novelty_score = int(most_novel.get("strategicNoveltyScore") or 1)
                signal["strategicNoveltyScore"] = max(raw_novelty_score, decision_novelty_score)
                if decision_novelty_score >= raw_novelty_score:
                    signal["noveltyType"] = most_novel.get("noveltyType") or "none"
                    signal["conceptAdvance"] = most_novel.get("conceptAdvance") or ""
                    signal["clinicalImplication"] = most_novel.get("clinicalImplication") or ""
            collected_signals.extend(accepted)
            for signal in accepted:
                for pmid in signal["refPmids"]:
                    collected_decisions[pmid] = decisions.get(pmid) or {
                        "pmid": pmid,
                        "decision": "include",
                        "category": normalize_text(signal.get("type")),
                        "valueScore": clamp_score(signal.get("signalScore"), 3),
                        "strategicNoveltyScore": clamp_score(signal.get("strategicNoveltyScore"), 1),
                        "noveltyType": normalize_text(signal.get("noveltyType")).lower() or "none",
                        "conceptAdvance": strip_pmid_mentions(signal.get("conceptAdvance")),
                        "clinicalImplication": strip_pmid_mentions(signal.get("clinicalImplication")),
                        "reason": "模型将该 PMID 纳入正式信号。",
                    }
                    pending.pop(pmid, None)

            # background/exclude 是有效裁决，不应因未进入 signal 而被自动回退发布。
            for pmid, decision in decisions.items():
                if decision["decision"] not in {"background", "exclude"} or pmid in claimed_pmids:
                    continue
                collected_decisions[pmid] = decision
                claimed_pmids.add(pmid)
                pending.pop(pmid, None)

        if pending:
            print(
                f"LLM did not adjudicate PMIDs after {max_attempts} attempts: {','.join(pending)}; using fallback",
                file=sys.stderr,
            )

    return {"signals": collected_signals, "decisions": collected_decisions}


def collect_llm_signals(
    records: list[dict],
    complete_fn=None,
    batch_size: int = LLM_BATCH_SIZE,
    max_attempts: int = LLM_MAX_ATTEMPTS,
) -> list[dict]:
    """兼容既有调用；新发布流程使用 collect_llm_analysis 保留逐篇裁决。"""
    return collect_llm_analysis(
        records,
        complete_fn=complete_fn,
        batch_size=batch_size,
        max_attempts=max_attempts,
    )["signals"]


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


SIGNAL_TYPES = {
    "治疗证据",
    "急性期与危象",
    "安全性",
    "诊断与监测",
    "预后与流行病学",
    "机制与转化",
    "临床路径",
    "病例级警示",
}


def normalize_signal_type(value: Any, articles: list[dict], fallback: Any = "") -> str:
    """优先采用专家按临床问题给出的类型，并兼容旧候选簇标签。"""
    value = normalize_text(value)
    if value in SIGNAL_TYPES:
        return value
    fallback = normalize_text(fallback)
    fallback_map = {
        "治疗证据": "治疗证据",
        "竞品证据": "治疗证据",
        "治疗比较": "治疗证据",
        "安全性": "安全性",
        "新机制": "机制与转化",
        "诊疗进展": "诊断与监测",
        "真实世界": "预后与流行病学",
        "风险分层": "预后与流行病学",
        "患者旅程": "预后与流行病学",
        "临床路径": "临床路径",
        "照护路径": "临床路径",
    }
    if fallback in fallback_map:
        return fallback_map[fallback]
    text = " ".join(
        normalize_text(article.get("title")) + " " + normalize_text(article.get("abstract"))
        for article in articles
    ).lower()
    if any(term in text for term in ("case report", "we report a patient", "two cases")):
        return "病例级警示"
    return "临床路径"


def normalize_signal_strength(value: Any, articles: list[dict], signal_score: int) -> str:
    """将专家价值判断限制在证据设计允许的上限内。"""
    requested = normalize_text(value)
    if requested not in {"强", "中", "弱"}:
        requested = ""
    levels = {str(article.get("evidence_level") or "") for article in articles}
    design_text = " ".join(
        [str(article.get("title") or "") for article in articles]
        + [str(item) for article in articles for item in (article.get("study_types") or [])]
        + [str(item) for article in articles for item in (article.get("pub_types") or [])]
    ).lower()
    low_evidence_only = bool(articles) and (
        levels.issubset({"V", ""})
        or all(
            any(term in (str(article.get("title") or "") + " " + " ".join(article.get("study_types") or [])).lower()
                for term in ("case report", "animal", "in vitro", "mechanistic/genetic association"))
            for article in articles
        )
    )
    if low_evidence_only:
        return "弱"
    has_strong_clinical_design = bool(levels.intersection({"I", "II"})) and not any(
        term in design_text for term in ("protocol", "narrative review", "case report")
    )
    if requested == "强":
        return "强" if signal_score >= 4 and has_strong_clinical_design else ("中" if signal_score >= 4 else "弱")
    if requested == "中":
        return "中" if signal_score >= 4 and bool(levels.intersection({"I", "II", "III", "IV"})) else "弱"
    if requested == "弱":
        return "弱"
    if signal_score >= 4 and has_strong_clinical_design:
        return "强"
    if signal_score >= 4 and bool(levels.intersection({"I", "II", "III", "IV"})):
        return "中"
    return "弱"


def expert_signal_score_floor(articles: list[dict]) -> int:
    """为明确的未满足临床场景和高质量比较队列提供通用价值下限。"""
    blob = " ".join(
        [str(article.get("title") or "") for article in articles]
        + [str(article.get("abstract") or "") for article in articles]
        + [str(item) for article in articles for item in (article.get("study_types") or [])]
    ).lower()
    levels = {str(article.get("evidence_level") or "") for article in articles}
    high_quality_comparative_cohort = (
        bool(levels.intersection({"III", "IV"}))
        and any(term in blob for term in ("propensity", "nationwide", "national database", "matched control", "matched cohort"))
        and any(term in blob for term in ("control", "matched", "propensity"))
    )
    prospective_unmet_clinical_scenario = (
        "prospective" in blob
        and any(term in blob for term in ("severe exacerbation", "myasthenic crisis", "ventilatory support", "enteral support"))
        and any(term in blob for term in ("mg-adl", "qmg", "clinical improvement", "clinical efficacy"))
    )
    prospective_diagnostic_performance = (
        "prospective" in blob
        and any(term in blob for term in ("diagnostic", "distinguish", "differentiate"))
        and "auc" in blob
        and "sensitivity" in blob
        and "specificity" in blob
    )
    return 4 if high_quality_comparative_cohort or prospective_unmet_clinical_scenario or prospective_diagnostic_performance else 0


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
    text = text.replace("进行性低视距", "进行性低幅扫视")
    text = text.replace("视频眼震图", "视频眼动图")
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
    if "single arm" in designs or "单臂" in designs:
        # 单臂急性期研究不能暗示可替代 PLEX/IVIG，也不能把作者结论升级成路径改变。
        text = re.sub(
            r"可能改变[^。；]*?(?:PLEX|IVIG)[^。；]*?(?:依赖|使用)(?:，但[^。；]*)?",
            "提出了值得在标准救援治疗背景下验证的研究问题，但尚不能据此替代或减少 PLEX/IVIG 的使用",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"[^。；]*(?:可|可能|或可)(?:作为|成为)[^。；]*?(?:PLEX|IVIG)[^。；]*?(?:替代(?:方案|选择)?|alternative)",
            "该探索性结果尚不能据此替代 PLEX/IVIG",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?:提示|表明)?[^。；]*?(?:可|可能)(?:作为|成为)急性期治疗的替代(?:方案|选择)",
            "该探索性结果仅提示值得在标准救援治疗背景下进一步验证",
            text,
        )
    observational = articles and not any(
        "rct" in " ".join(str(item) for item in (article.get("study_types") or [])).lower()
        for article in articles
    )
    if observational:
        # 观察性时间关联可提高诊断警觉，但不能直接升级为前驱标志或筛查建议。
        text = text.replace("可能作为MG前驱标志", "在MG诊断前更常见，但不能据此认定为前驱标志")
        text = re.sub(
            r"临床可考虑[^。；]*?加强[^。；]*?筛查(?:，但[^。；]*)?",
            "这种时间关联可提高诊断警觉，但不足以直接支持扩大筛查，仍需前瞻性验证",
            text,
        )
        if re.search(r"临床(?:实践中)?应考虑[^。；]*?(?:筛查|监测)", text):
            text = "该关联可提高对相关共病的诊断警觉，但不足以直接支持新增常规筛查或监测策略。"
        if re.search(r"提示临床医生[^。；]*?应关注[^。；]*?自身免疫", text):
            text = "该关联可提高对既往自身免疫病史的诊断警觉，但不足以直接支持改变筛查策略。"
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
        raw_finding = apply_evidence_language(raw.get("finding") or raw.get("keyFinding"), [article])
        finding = raw_finding if is_predominantly_chinese(raw_finding) else f"本期 {design} 提供了相关人群的初步结果数据，摘要级定位，需阅读全文确认具体数字与外推边界。"
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
    title = apply_evidence_language(chinese_or_fallback(raw.get("title"), fallback["title"]), articles)
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
    strategic_novelty_score = clamp_score(
        raw.get("strategicNoveltyScore"),
        clamp_score(base.get("strategicNoveltyScore"), 1),
    )
    novelty_type = normalize_text(raw.get("noveltyType")).lower()
    if novelty_type not in {"none", "concept_reframing", "pharmacology_threshold", "method"}:
        novelty_type = "none"
    concept_advance = apply_evidence_language(raw.get("conceptAdvance"), articles)
    clinical_implication = apply_evidence_language(raw.get("clinicalImplication"), articles)
    if "single arm" in " ".join(
        str(item).lower() for article in articles for item in (article.get("study_types") or [])
    ) and re.search(r"PLEX|IVIG", clinical_implication, re.IGNORECASE):
        clinical_implication = "若经对照试验验证，可能补充急性重症MG的治疗证据；当前不能替代或减少 PLEX/IVIG 的使用。"
    if not is_predominantly_chinese(concept_advance):
        concept_advance = ""
    if not is_predominantly_chinese(clinical_implication):
        clinical_implication = ""
    computational_or_mechanistic_only = bool(articles) and all(
        any(term in " ".join(str(item).lower() for item in (article.get("study_types") or []))
            for term in ("prediction model", "mechanistic", "genetic", "omics", "in vitro", "animal"))
        for article in articles
    )
    concept_only_signal = (
        strategic_novelty_score >= 4
        and novelty_type in {"concept_reframing", "pharmacology_threshold"}
        and computational_or_mechanistic_only
        and not any(str(article.get("evidence_level") or "") in {"I", "II", "III"} for article in articles)
    )
    signal_score = clamp_score(raw.get("signalScore"), clamp_score(base.get("signalScore"), 3))
    if concept_only_signal:
        signal_score = 3
        strength = "弱"
    else:
        value_floor = expert_signal_score_floor(articles)
        signal_score = max(signal_score, value_floor)
        requested_strength = "中" if value_floor >= 4 else raw.get("strength")
        strength = normalize_signal_strength(requested_strength, articles, signal_score)
    signal_type = normalize_signal_type(raw.get("type"), articles, base.get("type"))
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
    raw_kol_question = chinese_or_fallback(
        raw.get("kolQuestion"),
        "这些结果中，哪一项最可能改变您对患者选择、治疗节点或监测方式的判断？",
    )
    if "single arm" in " ".join(
        str(item).lower() for article in articles for item in (article.get("study_types") or [])
    ) and re.search(r"相比[^？。]*(?:PLEX|IVIG)", raw_kol_question, re.IGNORECASE):
        kol_question = "在标准 PLEX/IVIG 救援背景下，哪类患者最值得纳入前瞻性对照研究以评估该治疗？"
    else:
        kol_question = apply_evidence_language(raw_kol_question, articles)
    msl_action = chinese_or_fallback(
        raw.get("mslAction"),
        "会前逐篇核对研究人群、主要终点、效应值与全文限制，并准备同类证据对照。",
    )
    return {
        "id": signal_id,
        "date": max(dates),
        "date_range": {"from": min(dates), "to": max(dates)},
        "type": signal_type,
        "strength": strength,
        "title": title,
        "summary": title,
        "takeaway": takeaway,
        "whySignal": why_signal,
        "evidenceBoundary": evidence_boundary,
        "gapBefore": gap_before,
        "gapFilled": gap_filled,
        "remainingGap": remaining_gap,
        "clinicalQuestion": chinese_or_fallback(
            raw.get("clinicalQuestion"),
            "这组结果是否足以改变对应 MG 人群的临床判断？",
        ),
        "aggregationRationale": chinese_or_fallback(
            raw.get("aggregationRationale"),
            "所纳入文献围绕同一具体临床问题组织，证据贡献与边界按篇呈现。",
        ),
        "evidenceItems": evidence_items,
        "maUse": chinese_or_fallback(raw.get("maUse"), fallback["maUse"]),
        "signalScore": signal_score,
        "strategicNoveltyScore": strategic_novelty_score,
        "noveltyType": novelty_type,
        "noveltyLabel": "高战略新颖性" if strategic_novelty_score >= 4 and novelty_type != "none" else "",
        "conceptAdvance": concept_advance,
        "clinicalImplication": clinical_implication,
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
            "analysis_model": "literature-signal-to-kol-v4",
            "aggregation": "mg_core_topic_cluster_llm_expert_adjudicated",
            "parent_signal_id": signal_id,
            "source_pmids": [str(article.get("pmid") or "") for article in articles],
            "auto_publish": True,
            "review_required": False,
        },
    }


def merge_llm_signals(
    raw_signals: Any,
    payload: dict,
    by_pmid: dict[str, dict],
    builder,
    decisions: dict[str, dict] | None = None,
) -> tuple[list[dict], float]:
    """发布 include 信号；仅对未被 LLM 裁决的 PMID 使用确定性回退。"""
    normalized = []
    llm_covered: set[str] = set()
    decisions = decisions or {}
    adjudicated_pmids = {str(pmid) for pmid in decisions if str(pmid) in by_pmid}
    non_signal_pmids = {
        str(pmid)
        for pmid, item in decisions.items()
        if str(pmid) in by_pmid and item.get("decision") in {"background", "exclude"}
    }
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
            if pmid in by_pmid and pmid not in non_signal_pmids and pmid not in llm_covered and pmid not in available_pmids:
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

    coverage = len(adjudicated_pmids or llm_covered) / max(1, len(by_pmid))
    assigned_pmids = set(llm_covered) | non_signal_pmids

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
        signal["signal_to_kol"]["analysis_model"] = "literature-signal-to-kol-v4-fallback"
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
    expected_published_pmids = set(by_pmid) - non_signal_pmids
    if len(published_pmids) != len(set(published_pmids)) or set(published_pmids) != expected_published_pmids:
        raise RuntimeError("Published signal PMID invariant failed")

    tier_rank = {"efgar": 0, "competitor_response": 1, "disease_progress": 2}
    strength_rank = {"强": 0, "中": 1, "弱": 2}

    def signal_sort_key(signal):
        points = signal.get("talkingPoints") or []
        first_point = points[0] if points else {}
        return (
            strength_rank.get(str(signal.get("strength") or "弱"), 2),
            -max(
                float(signal.get("signalScore") or 0),
                float(signal.get("strategicNoveltyScore") or 0),
            ),
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
    parser.add_argument(
        "--replay-current-window",
        action="store_true",
        help="Reanalyse the PMID cohort already published in signals-weekly.js without advancing or clearing its window.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override the LLM batch size. Replay defaults to the full frozen cohort so cross-candidate aggregation can be assessed.",
    )
    args = parser.parse_args()
    published_payload = load_js_global(SIGNALS_PATH, "MG_SIGNALS_DATA")
    literature = load_js_global(LITERATURE_PATH, "MG_LITERATURE_DATA")
    builder = load_builder_module()
    if args.replay_current_window:
        # 受控重放只修改语义分析层：窗口、文献队列和上游采集状态均取当前已发布 last-good。
        # 首次重放从既有信号收集 PMID；后续重放优先使用完整裁决队列，避免背景文献被永久丢失。
        payload = published_payload
        candidate_pmid_order = list(dict.fromkeys(
            str(pmid)
            for pmid in (
                payload.get("analysis_cohort_pmids")
                or [item.get("pmid") for item in payload.get("selection_decisions", []) or []]
                or [
                    pmid
                    for signal in payload.get("signals", []) or []
                    for pmid in signal.get("related_pmids", []) or []
                ]
            )
            if pmid
        ))
        if not candidate_pmid_order:
            raise RuntimeError("Cannot replay an empty published signal cohort")
        if not payload.get("window_start") or not payload.get("window_end"):
            raise RuntimeError("Cannot replay signals without a published window_start/window_end")
    else:
        # 正常周更从确定性主题簇重新起步，避免重复 enrichment 后信号越拆越细。
        # 窗口口径与正式构建一致：传入 ingest manifest 并强制 trueIngestAddedPmids。
        ingest_manifest = builder.load_weekly_ingest_manifest()
        payload = builder.build_signals(literature, ingest_manifest, requireIngest=True)
        candidate_pmid_order = list(dict.fromkeys(
            str(pmid)
            for signal in payload.get("signals", [])
            for pmid in signal.get("related_pmids", [])
            if pmid
        ))
    candidate_pmids = set(candidate_pmid_order)
    by_pmid = {str(article.get("pmid")): article for article in literature if str(article.get("pmid")) in candidate_pmids}
    missing_pmids = [pmid for pmid in candidate_pmid_order if pmid not in by_pmid]
    if missing_pmids:
        raise RuntimeError(
            "Published signal replay is missing local literature records: " + ",".join(missing_pmids)
        )
    baseline_by_pmid = {
        str(pmid): signal
        for signal in payload.get("signals", [])
        for pmid in signal.get("related_pmids", [])
    }
    ordered_articles = [by_pmid[pmid] for pmid in candidate_pmid_order if pmid in by_pmid]
    # 受控重放一次性查看完整冻结队列，不让上一次 LLM 生成的候选簇反向锚定本次判断。
    prompt_baseline_by_pmid = {} if args.replay_current_window else baseline_by_pmid
    records = records_for_prompt(ordered_articles, prompt_baseline_by_pmid)
    if not records:
        # 本周无新增 MG-core 信号（requireIngest 窗口新增=0）属正常场景，不是错误。
        # 不调用 LLM、不生成占位 finding；按发布契约写入合法的空信号 payload 并优雅结束，
        # 让 validatePublicRelease 的 llm_enrichment 契约通过、整轮管线继续发布本周数据。
        policy = payload.setdefault("source_policy", {})
        policy.update({
            "analysis_model": "literature-signal-to-kol-v4",
            "aggregation": "mg_core_topic_cluster_llm_expert_adjudicated",
            "llm_enrichment": True,
            "llm_reference_coverage": 0.0,
            "published_reference_coverage": 0.0,
            "llm_source": "scripts/enrich-literature-narrative.py",
            "llm_skip_reason": "no_new_mg_core_signals",
        })
        payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        atomic_write_js_global(SIGNALS_PATH, "MG_SIGNALS_DATA", payload)
        print("无新增 MG-core 信号：发布空信号 payload，LLM enrich 跳过（no_new_mg_core_signals）")
        return
    effective_batch_size = args.batch_size or (len(records) if args.replay_current_window else LLM_BATCH_SIZE)
    analysis = collect_llm_analysis(records, batch_size=effective_batch_size)
    raw_signals = analysis["signals"]
    decisions = analysis["decisions"]
    normalized, coverage = merge_llm_signals(raw_signals, payload, by_pmid, builder, decisions=decisions)
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    policy = payload.setdefault("source_policy", {})
    policy.update({
        "analysis_model": "literature-signal-to-kol-v4",
        "aggregation": "mg_core_topic_cluster_llm_expert_adjudicated",
        "llm_enrichment": True,
        "llm_reference_coverage": round(coverage, 3),
        "published_reference_coverage": round(len({pmid for signal in normalized for pmid in signal.get("related_pmids", [])}) / max(1, len(by_pmid)), 3),
        "llm_decision_counts": dict(Counter(item.get("decision") for item in decisions.values())),
        "strength_policy": "evidence_ceiling_then_mg_expert_incremental_value",
        "llm_source": "scripts/enrich-literature-narrative.py",
    })
    if args.replay_current_window:
        policy.update({
            "weekly_selection": "replay_current_published_window",
            "replay_window_preserved": True,
            "replay_source_count": len(candidate_pmid_order),
        })
    payload["analysis_cohort_pmids"] = candidate_pmid_order
    payload["selection_decisions"] = sorted(decisions.values(), key=lambda item: item["pmid"])
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
