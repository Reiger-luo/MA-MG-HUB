#!/usr/bin/env python3
"""构建并 enrich 三源临床试验周更信号。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from common.io import atomic_write_js_global, load_js_global  # noqa: E402
from common.mg_relevance import assess_mg_core  # noqa: E402
from common.trial_source_version import legacy_source_revision, source_revision  # noqa: E402
from llm_client import complete  # noqa: E402

DATA = PROJECT / "data"
OUTPUT_PATH = DATA / "trial-signals-weekly.js"
SUMMARY_PATH = DATA / "clinicalTrialsSummary.js"
CT_CACHE_PATH = DATA / "clinicaltrials-pipeline-cache.json"
CHICTR_CACHE_PATH = DATA / "chictr-trials-cache.json"
CDT_CACHE_PATH = DATA / "china-drug-trials-cache.json"
CDT_CHANGES_PATH = DATA / "china-drug-trials-changes.json"

IMPORTANCE_RANK = {"早期/探索": 1, "一般": 2, "关键": 3}
MATERIALITY_RANK = {"轻微": 1, "中等": 2, "高": 3}
STRENGTH_RANK = {"弱": 1, "中": 2, "强": 3}
REGISTRY_ID_PATTERN = re.compile(r"\b(?:NCT\d{8}|ChiCTR[A-Za-z0-9-]{6,}|CTR[A-Za-z0-9-]{6,})\b", re.I)

UNMET_TERMS = (
    "myasthenic crisis", "crisis", "severe exacerbation", "ocular myasthenia",
    "seronegative", "seronegative", "musk", "juvenile", "pediatric", "paediatric",
    "children", "adolescent", "thymoma", "refractory", "难治", "危象", "眼肌型",
    "血清阴性", "儿童", "青少年",
)
NOVEL_MECHANISM_TERMS = (
    "car-t", "car t", "caart", "bispecific", "bcma", "cd19", "cd20", "cd38",
    "baff", "april", "gene therapy", "tolerogenic", "antigen-specific",
    "细胞治疗", "基因治疗", "耐受诱导", "抗原特异性",
)
STRATEGIC_EXPANSION_TERMS = (
    "subcutaneous", "self-administered", "home administration", "maintenance treatment",
    "rescue treatment", "acute exacerbation", "treatment sequence", "switching study",
    "皮下给药", "居家给药", "维持治疗", "急性加重", "治疗序贯", "转换治疗",
)
ADMIN_FIELDS = {
    "contact", "contacts", "location", "locations", "address", "phone", "email",
    "last_update_date", "other", "format",
}
HIGH_FIELDS = {
    "phase", "phase_label", "intervention", "interventions", "drug_name", "drug_names",
    "primary_outcome", "primary_outcomes", "condition", "conditions", "population",
    "eligibility", "inclusion_criteria", "study_type",
}
MEDIUM_FIELDS = {
    "status", "recruitment_status", "enrollment", "enrollment_count", "target_size",
    "primary_completion_date", "completion_date", "readout_date", "countries",
    "locations_count", "date_enrolment",
}

SYSTEM = """你是重症肌无力（MG）临床研究与医学事务专家。你只分析试验注册变化，不把注册状态写成疗效证据。
硬性要求：
1. 只输出 JSON object；不得补充输入之外的结果、数字或原因。
2. 每个 candidateId 必须且只能裁决一次。include=值得进入本期试验信号板；background=真实但不足以形成信号。
3. deterministicStrength 是代码允许的最高等级，不能提高；可以降级或转为 background。
4. “结果已发布”只表示注册平台出现结果记录，不能写成疗效阳性；“完成”也不等于达到终点。
5. 所有叙事字段使用中文；药物、量表、阶段和登记号可保留英文。
6. 不得把联系人、地点、格式或无法解释的字段变化包装为重要进展。"""


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def current_source_versions() -> dict[str, dict[str, str]]:
    """读取三源当前版本；仅在窗口 ID 相同时允许为冻结窗口补 revision。"""
    summary = load_js_global(SUMMARY_PATH, "MG_CLINICAL_TRIALS_SUMMARY")
    ct_payload = load_json(CT_CACHE_PATH, {})
    chictr_payload = load_json(CHICTR_CACHE_PATH, {})
    cdt_payload = load_json(CDT_CACHE_PATH, {})
    cdt_changes = load_json(CDT_CHANGES_PATH, {})
    return {
        "ClinicalTrials.gov": {
            "updated_at": normalize_text((summary.get("weekly_changes") or {}).get("generated_at")),
            "source_revision": source_revision(ct_payload),
            "legacy_source_revision": legacy_source_revision(ct_payload),
        },
        "ChiCTR": {
            "updated_at": normalize_text(chictr_payload.get("last_verified") or chictr_payload.get("scraped_at")),
            "source_revision": source_revision(chictr_payload),
            "legacy_source_revision": legacy_source_revision(chictr_payload),
        },
        "ChinaDrugTrials": {
            "updated_at": normalize_text(cdt_changes.get("generated_at") or cdt_payload.get("generated_at")),
            "source_revision": source_revision(cdt_payload),
            "legacy_source_revision": legacy_source_revision(cdt_payload),
        },
    }


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def title_key(value: Any) -> str:
    return "".join(char for char in normalize_text(value).lower() if char.isalnum())


def registry_ids_from(value: Any, primary_id: str = "") -> list[str]:
    try:
        text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    except (TypeError, ValueError):
        text = normalize_text(value)
    primary = normalize_text(primary_id).upper()
    return sorted({match.group(0) for match in REGISTRY_ID_PATTERN.finditer(text) if match.group(0).upper() != primary})


def phase_rank(value: Any) -> float:
    text = normalize_text(value).lower().replace("_", " ")
    text = re.sub(r"\bphase\s*([1-4])\b", r"phase \1", text)
    if "phase 4" in text or text == "4":
        return 4
    if "phase 3" in text or "phase iii" in text or text == "3":
        return 3
    if "phase 2/3" in text or "phase 2 / phase 3" in text:
        return 2.5
    if "phase 2" in text or "phase ii" in text or text == "2":
        return 2
    if "phase 1/2" in text or "phase 1 / phase 2" in text:
        return 1.5
    if "phase 1" in text or "phase i" in text or text == "1":
        return 1
    return 0


def phase_label(value: Any) -> str:
    if isinstance(value, list):
        value = " / ".join(str(item) for item in value)
    rank = phase_rank(value)
    return {
        4: "Phase 4", 3: "Phase 3", 2.5: "Phase 2/3", 2: "Phase 2",
        1.5: "Phase 1/2", 1: "Phase 1",
    }.get(rank, normalize_text(value) or "未标注")


def parse_llm_json(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", value)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("LLM response is not an object")
    return payload


def chinese_text(value: Any, fallback: str) -> str:
    text = normalize_text(value)
    return text if len(re.findall(r"[\u3400-\u9fff]", text)) >= 4 else fallback


def ct_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {}
    for study in payload.get("studies") or []:
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        design = protocol.get("designModule") or {}
        conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
        eligibility = protocol.get("eligibilityModule") or {}
        interventions = (protocol.get("armsInterventionsModule") or {}).get("interventions") or []
        registry_id = normalize_text(ident.get("nctId"))
        if not registry_id:
            continue
        drug_names = []
        for item in interventions:
            if normalize_text(item.get("type")).upper() not in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}:
                continue
            name = normalize_text(item.get("name"))
            if name and name.lower() != "placebo" and name not in drug_names:
                drug_names.append(name)
        why_stopped = normalize_text(status.get("whyStopped"))
        records[registry_id] = {
            "registry": "ClinicalTrials.gov",
            "registryId": registry_id,
            "title": ident.get("briefTitle") or ident.get("officialTitle") or "",
            "url": f"https://clinicaltrials.gov/study/{registry_id}",
            "phase": phase_label(design.get("phases") or []),
            "studyType": normalize_text(design.get("studyType")),
            "conditions": [normalize_text(item) for item in conditions if normalize_text(item)],
            "population": normalize_text(eligibility.get("briefSummary") or eligibility.get("eligibilityCriteria"))[:1200],
            "interventions": drug_names,
            "status": normalize_text(status.get("overallStatus")),
            "whyStopped": why_stopped,
            "updatedAt": normalize_text((status.get("lastUpdatePostDateStruct") or {}).get("date")),
            "primaryCompletionDate": normalize_text((status.get("primaryCompletionDateStruct") or {}).get("date")),
            "completionDate": normalize_text((status.get("completionDateStruct") or {}).get("date")),
            "crossRegistryIds": registry_ids_from(ident.get("secondaryIdInfos") or [], registry_id),
        }
    return records


def chictr_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {}
    for item in payload.get("records") or []:
        registry_id = normalize_text(item.get("registry_id") or item.get("trial_id"))
        if not registry_id:
            continue
        title = item.get("title") or item.get("public_title") or item.get("scientific_title") or ""
        records[registry_id] = {
            "registry": "ChiCTR", "registryId": registry_id, "title": title,
            "url": item.get("url") or item.get("official_url") or "",
            "phase": phase_label(item.get("phase")), "studyType": item.get("study_type") or item.get("study_design") or "",
            "conditions": [item.get("hc_freetext") or ""],
            "population": normalize_text(item.get("inclusion_criteria"))[:1200],
            "interventions": [normalize_text(item.get("i_freetext"))] if normalize_text(item.get("i_freetext")) else [],
            "status": item.get("recruitment_status") or "", "whyStopped": "",
            "updatedAt": item.get("date_registration") or item.get("registered_date") or "",
            "primaryCompletionDate": item.get("results_date_completed") or "",
            "completionDate": item.get("results_date_completed") or "",
            "crossRegistryIds": registry_ids_from(item, registry_id),
            "raw": item,
        }
    return records


def cdt_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {}
    for item in payload.get("records") or []:
        registry_id = normalize_text(item.get("registry_id"))
        if not registry_id:
            continue
        records[registry_id] = {
            "registry": "ChinaDrugTrials", "registryId": registry_id,
            "title": item.get("title") or "", "url": item.get("official_url") or "",
            "phase": phase_label(item.get("phase")), "studyType": item.get("study_type") or "Interventional",
            "conditions": [item.get("indication") or "重症肌无力"],
            "population": normalize_text(item.get("population") or item.get("inclusion_criteria"))[:1200],
            "interventions": [normalize_text(item.get("drug_name"))] if normalize_text(item.get("drug_name")) else [],
            "status": item.get("status") or "", "whyStopped": item.get("why_stopped") or "",
            "updatedAt": item.get("updated_at") or item.get("registered_date") or "",
            "primaryCompletionDate": item.get("primary_completion_date") or "",
            "completionDate": item.get("completion_date") or "",
            "crossRegistryIds": registry_ids_from(item, registry_id), "raw": item,
        }
    return records


def git_head_json(path: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(PROJECT).as_posix()
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {}
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def strict_mg_core(record: dict[str, Any]) -> tuple[bool, str]:
    abstract = " ".join([
        " ".join(str(item) for item in record.get("conditions") or []),
        normalize_text(record.get("population")),
    ])
    assessment = assess_mg_core({
        "title": record.get("title") or "", "abstract": abstract,
        "keywords": record.get("conditions") or [],
    })
    return assessment.is_core, assessment.reason_code


def classify_trial_importance(record: dict[str, Any]) -> tuple[str, str, bool]:
    blob = " ".join([
        normalize_text(record.get("title")), normalize_text(record.get("studyType")),
        " ".join(record.get("conditions") or []), normalize_text(record.get("population")),
        " ".join(record.get("interventions") or []),
    ]).lower()
    rank = phase_rank(record.get("phase"))
    interventional = "observational" not in blob and "观察" not in blob
    unmet = any(term in blob for term in UNMET_TERMS)
    novel = any(term in blob for term in NOVEL_MECHANISM_TERMS)
    strategic_expansion = any(term in blob for term in STRATEGIC_EXPANSION_TERMS)
    pivotal = any(term in blob for term in ("pivotal", "registrational", "confirmatory", "关键性", "注册性", "确证性"))
    if interventional and (rank >= 3 or pivotal or (rank >= 2 and (unmet or novel or strategic_expansion))):
        reasons = []
        if rank >= 3:
            reasons.append(f"{phase_label(record.get('phase'))}干预试验")
        if unmet:
            reasons.append("覆盖重要未满足MG人群")
        if novel:
            reasons.append("涉及可能改变开发格局的机制")
        if strategic_expansion:
            reasons.append("涉及适应证、给药方式或治疗节点扩展")
        if pivotal:
            reasons.append("登记信息明确为关键/注册性研究")
        return "关键", "；".join(reasons) or "关键MG开发试验", novel or unmet or strategic_expansion
    if interventional and rank >= 1.5:
        return "一般", f"{phase_label(record.get('phase'))} MG干预试验", novel or unmet or strategic_expansion
    return "早期/探索", "早期、观察性或辅助性MG研究", novel or unmet or strategic_expansion


def changed_fields(event: dict[str, Any]) -> set[str]:
    fields = set()
    raw = event.get("changes") or {}
    if isinstance(raw, dict):
        fields.update(normalize_text(key).lower() for key in raw)
    summary = normalize_text(event.get("change_summary") or event.get("changeSummary")).lower()
    if "样本量" in summary:
        fields.add("enrollment_count")
    if "阶段" in summary:
        fields.add("phase")
    if "新增干预" in summary or "移除干预" in summary:
        fields.add("interventions")
    if "完成日期" in summary:
        fields.add("primary_completion_date")
    if "研究地点" in summary:
        fields.add("locations_count")
    return fields


def classify_update_materiality(event: dict[str, Any], record: dict[str, Any], importance: str) -> tuple[str, str]:
    event_type = normalize_text(event.get("eventType") or event.get("event_type")).lower()
    fields = changed_fields(event)
    from_status = normalize_text(event.get("from_status") or event.get("fromStatus")).upper()
    to_status = normalize_text(event.get("to_status") or event.get("toStatus") or record.get("status")).upper()
    why_stopped = normalize_text(record.get("whyStopped")).lower()
    if event_type == "added":
        return ("高", "新增关键试验") if importance == "关键" else ("中等", "新增MG试验")
    if event_type == "results_posted":
        return "高", "注册平台首次出现结果记录"
    if event_type == "removed":
        return "轻微", "仅观察到注册记录从当前数据源消失，尚不能解释原因"
    if fields.intersection(HIGH_FIELDS):
        return "高", "阶段、主要终点、核心干预或关键人群发生变化"
    if event_type == "status_change":
        if from_status == "UNKNOWN" and to_status in {"RECRUITING", "ENROLLING_BY_INVITATION"} and not fields:
            return "轻微", "仅由未知状态恢复为招募，缺少其他实质变化"
        if to_status in {"COMPLETED"}:
            return ("高", "关键试验达到研究完成状态") if importance == "关键" else ("中等", "试验状态更新为已完成")
        if to_status in {"TERMINATED", "SUSPENDED", "WITHDRAWN"}:
            verified_reason = any(term in why_stopped for term in ("safety", "futility", "lack of efficacy", "development", "安全", "无效"))
            if verified_reason:
                return "高", "暂停或终止且登记信息给出安全性、无效性或开发原因"
            return ("中等", "关键试验暂停、终止或撤回，但原因仍需核查") if importance == "关键" else ("轻微", "状态停止但缺少可解释原因")
        if to_status in {"RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"}:
            return ("高", "关键试验进入招募或进行阶段") if importance == "关键" else ("中等", "招募状态发生真实推进")
    if fields.intersection(MEDIUM_FIELDS):
        return "中等", "样本量、完成日期、地区覆盖或招募信息发生可解释变化"
    if event_type == "updated" or fields.intersection(ADMIN_FIELDS):
        return "轻微", "仅有行政性或无法解释的字段更新"
    return "轻微", "变化不足以影响当前开发判断"


def deterministic_decision(candidate: dict[str, Any]) -> dict[str, Any]:
    core, core_reason = strict_mg_core(candidate)
    importance, key_reason, strategic = classify_trial_importance(candidate)
    materiality, materiality_reason = classify_update_materiality(candidate, candidate, importance)
    event_type = candidate.get("eventType")
    if not core:
        decision, strength, score = "exclude", "", 1
        strength_reason = f"未通过严格MG-core门控：{core_reason}"
    elif event_type == "removed":
        decision, strength, score = "exclude", "", 1
        strength_reason = "未经确认的注册记录移除不形成信号"
    elif materiality == "轻微":
        decision, strength, score = "background", "", 2
        strength_reason = "行政性或不可解释更新仅保留为背景"
    else:
        decision = "include"
        if importance == "关键" and materiality == "高":
            strength, score = "强", 5
        elif (importance == "关键" and materiality == "中等") or (importance == "一般" and materiality == "高"):
            strength, score = "中", 4
        elif importance == "早期/探索" and materiality == "高" and strategic:
            strength, score = "中", 4
        else:
            strength, score = "弱", 3
        strength_reason = f"{importance}试验 × {materiality}更新"
    return {
        **candidate,
        "mgCore": core,
        "mgCoreReason": core_reason,
        "trialImportance": importance,
        "keyTrialRationale": key_reason,
        "strategicContext": strategic,
        "updateMateriality": materiality,
        "materialityRationale": materiality_reason,
        "deterministicDecision": decision,
        "deterministicStrength": strength,
        "signalScore": score,
        "strengthRationale": strength_reason,
    }


def event_from_change(source: str, event_type: str, item: Any, lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(item, str):
        item = {"registry_id": item}
    if not isinstance(item, dict):
        return None
    registry_id = normalize_text(item.get("registry_id") or item.get("registryId"))
    record = dict(lookup.get(registry_id) or {})
    if not record:
        record = {
            "registry": source, "registryId": registry_id, "title": item.get("title") or "",
            "url": item.get("url") or "", "phase": item.get("phase_label") or "未标注",
            "conditions": [], "population": "", "interventions": [item.get("drug_name")] if item.get("drug_name") else [],
            "status": item.get("to_status") or "", "whyStopped": "", "updatedAt": "",
        }
    record.update({
        "eventType": event_type,
        "changeSummary": item.get("change_summary") or "",
        "fromStatus": item.get("from_status") or "",
        "toStatus": item.get("to_status") or record.get("status") or "",
        "changes": item.get("changes") or {},
        "date": item.get("first_post_date") or item.get("updated_date") or item.get("results_post_date") or record.get("updatedAt") or "",
        "registryRefs": [{
            "registry": record.get("registry") or source,
            "registryId": registry_id,
            "url": record.get("url") or item.get("url") or "",
        }],
    })
    record["candidateId"] = f"{source}:{registry_id}:{event_type}"
    return record


def visible_ct_changes(weekly: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(weekly.get("candidate_changes"), list):
        return weekly["candidate_changes"]
    items = []
    for event_type, key in (
        ("added", "added"), ("status_change", "status_changes"),
        ("results_posted", "results_posted"), ("updated", "updated"), ("removed", "removed"),
    ):
        for item in weekly.get(key) or []:
            items.append({"event_type": event_type, **item} if isinstance(item, dict) else {"event_type": event_type, "registry_id": item})
    return items


def compare_chictr(current: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    if not baseline:
        return []
    changes = []
    for registry_id in sorted(set(current) - set(baseline)):
        changes.append(("added", {"registry_id": registry_id}))
    fields = ("recruitment_status", "phase", "target_size", "date_enrolment", "i_freetext", "results_date_completed", "results_date_posted")
    for registry_id in sorted(set(current) & set(baseline)):
        before = (baseline[registry_id].get("raw") or baseline[registry_id])
        after = (current[registry_id].get("raw") or current[registry_id])
        field_changes = {
            field: {"before": normalize_text(before.get(field)), "after": normalize_text(after.get(field))}
            for field in fields if normalize_text(before.get(field)) != normalize_text(after.get(field))
        }
        if field_changes:
            changes.append(("updated", {"registry_id": registry_id, "changes": field_changes}))
    return changes


def source_event_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "registry", "registryId", "registryRefs", "crossRegistryIds", "title", "phase",
        "studyType", "conditions", "population", "interventions", "status", "whyStopped",
        "updatedAt", "primaryCompletionDate", "completionDate", "eventType", "changeSummary",
        "fromStatus", "toStatus", "changes", "date",
    )
    return {key: candidate.get(key) for key in keys}


def merge_duplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = []
    title_to_index = {}
    registry_id_to_index = {}
    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        candidate["sourceEvents"] = candidate.get("sourceEvents") or [source_event_snapshot(candidate)]
        key = title_key(candidate.get("title"))
        registry_aliases = {
            normalize_text(candidate.get("registryId")).upper(),
            *(normalize_text(item).upper() for item in candidate.get("crossRegistryIds") or []),
            *(
                normalize_text(ref.get("registryId")).upper()
                for ref in candidate.get("registryRefs") or [] if ref.get("registryId")
            ),
        }
        registry_aliases.discard("")
        matched_indices = {registry_id_to_index[item] for item in registry_aliases if item in registry_id_to_index}
        index = min(matched_indices) if matched_indices else (title_to_index.get(key) if len(key) >= 40 else None)
        if index is None:
            title_to_index[key] = len(merged)
            merged.append(candidate)
            for registry_alias in registry_aliases:
                registry_id_to_index[registry_alias] = len(merged) - 1
            continue
        existing = merged[index]
        refs = existing.get("registryRefs") or []
        seen = {(item.get("registry"), item.get("registryId")) for item in refs}
        for ref in candidate.get("registryRefs") or []:
            marker = (ref.get("registry"), ref.get("registryId"))
            if marker not in seen:
                refs.append(ref)
                seen.add(marker)
        source_events = list(existing.get("sourceEvents") or [])
        seen_events = {
            (
                normalize_text(item.get("registry")), normalize_text(item.get("registryId")),
                normalize_text(item.get("eventType")), normalize_text(item.get("date")),
            )
            for item in source_events
        }
        for event in candidate.get("sourceEvents") or []:
            marker = (
                normalize_text(event.get("registry")), normalize_text(event.get("registryId")),
                normalize_text(event.get("eventType")), normalize_text(event.get("date")),
            )
            if marker not in seen_events:
                source_events.append(event)
                seen_events.add(marker)
        if MATERIALITY_RANK.get(candidate.get("updateMateriality"), 0) > MATERIALITY_RANK.get(existing.get("updateMateriality"), 0):
            preserved_refs = refs
            merged[index] = {**candidate, "registryRefs": preserved_refs, "sourceEvents": source_events}
        else:
            existing["registryRefs"] = refs
            existing["sourceEvents"] = source_events
        cross_ids = {
            normalize_text(item) for item in (existing.get("crossRegistryIds") or []) + (candidate.get("crossRegistryIds") or [])
            if normalize_text(item)
        }
        merged[index]["crossRegistryIds"] = sorted(cross_ids)
        if key:
            title_to_index[key] = index
        for registry_alias in registry_aliases:
            registry_id_to_index[registry_alias] = index
    for candidate in merged:
        ids = sorted(ref.get("registryId") or "" for ref in candidate.get("registryRefs") or [] if ref.get("registryId"))
        candidate["candidateId"] = "|".join(ids) + ":" + normalize_text(candidate.get("eventType"))
    return merged


def build_candidates(previous_payload: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    previous_payload = previous_payload or {}
    previous_windows = previous_payload.get("source_windows") or {}
    summary = load_js_global(SUMMARY_PATH, "MG_CLINICAL_TRIALS_SUMMARY")
    ct_payload = load_json(CT_CACHE_PATH, {})
    chictr_payload = load_json(CHICTR_CACHE_PATH, {})
    cdt_payload = load_json(CDT_CACHE_PATH, {})
    cdt_changes = load_json(CDT_CHANGES_PATH, {})
    ct_lookup = ct_records(ct_payload)
    chictr_lookup = chictr_records(chictr_payload)
    cdt_lookup = cdt_records(cdt_payload)
    raw_candidates: list[dict[str, Any]] = []
    source_new_counts = {"ClinicalTrials.gov": 0, "ChiCTR": 0, "ChinaDrugTrials": 0}

    weekly = summary.get("weekly_changes") or {}
    ct_window_id = normalize_text(weekly.get("generated_at"))
    chictr_window_id = normalize_text(chictr_payload.get("last_verified") or chictr_payload.get("scraped_at"))
    cdt_window_id = normalize_text(cdt_changes.get("generated_at") or cdt_payload.get("generated_at"))
    chictr_baseline_payload = git_head_json(CHICTR_CACHE_PATH)
    chictr_baseline_id = normalize_text(chictr_baseline_payload.get("last_verified") or chictr_baseline_payload.get("scraped_at"))
    cdt_baseline_payload = git_head_json(CDT_CACHE_PATH)
    cdt_baseline_id = normalize_text(cdt_baseline_payload.get("generated_at"))
    current_window_ids = {
        "ClinicalTrials.gov": ct_window_id,
        "ChiCTR": chictr_window_id,
        "ChinaDrugTrials": cdt_window_id,
    }
    current_source_revisions = {
        "ClinicalTrials.gov": source_revision(ct_payload),
        "ChiCTR": source_revision(chictr_payload),
        "ChinaDrugTrials": source_revision(cdt_payload),
    }
    advanced_sources = {
        source for source, window_id in current_window_ids.items()
        if window_id and (
            window_id != normalize_text((previous_windows.get(source) or {}).get("updated_at"))
            or (
                current_source_revisions[source]
                and current_source_revisions[source] != normalize_text((previous_windows.get(source) or {}).get("source_revision"))
            )
        )
    }

    # 未到原生更新节奏或来源暂时失败时，保留该来源上一轮冻结队列。
    for previous_candidate in previous_payload.get("analysis_cohort") or []:
        source_events = previous_candidate.get("sourceEvents") or []
        if source_events:
            for source_event in source_events:
                source = normalize_text(source_event.get("registry"))
                if source in advanced_sources:
                    continue
                preserved = {**previous_candidate, **source_event, "sourceEvents": [source_event]}
                raw_candidates.append(preserved)
            continue
        preserved_refs = [
            dict(ref) for ref in previous_candidate.get("registryRefs") or []
            if normalize_text(ref.get("registry")) not in advanced_sources
        ]
        if not preserved_refs:
            continue
        preserved = dict(previous_candidate)
        preserved["registryRefs"] = preserved_refs
        preserved["registry"] = preserved_refs[0].get("registry") or preserved.get("registry")
        preserved["registryId"] = preserved_refs[0].get("registryId") or preserved.get("registryId")
        raw_candidates.append(preserved)

    if "ClinicalTrials.gov" in advanced_sources:
        for item in visible_ct_changes(weekly):
            candidate = event_from_change("ClinicalTrials.gov", item.get("event_type") or "updated", item, ct_lookup)
            if candidate:
                raw_candidates.append(candidate)
                source_new_counts["ClinicalTrials.gov"] += 1

    if "ChiCTR" in advanced_sources:
        baseline_lookup = chictr_records(chictr_baseline_payload)
        for event_type, item in compare_chictr(chictr_lookup, baseline_lookup):
            candidate = event_from_change("ChiCTR", event_type, item, chictr_lookup)
            if candidate:
                raw_candidates.append(candidate)
                source_new_counts["ChiCTR"] += 1

    if "ChinaDrugTrials" in advanced_sources:
        for event_type, key in (("added", "added"), ("updated", "updated"), ("removed", "removed")):
            for item in cdt_changes.get(key) or []:
                candidate = event_from_change("ChinaDrugTrials", event_type, item, cdt_lookup)
                if candidate:
                    raw_candidates.append(candidate)
                    source_new_counts["ChinaDrugTrials"] += 1

    candidates = [deterministic_decision(candidate) for candidate in raw_candidates]
    candidates = merge_duplicate_candidates(candidates)
    windows = {
        "ClinicalTrials.gov": {
            **(previous_windows.get("ClinicalTrials.gov") or {}),
            "cadence": "weekly", "updated_at": ct_window_id or (previous_windows.get("ClinicalTrials.gov") or {}).get("updated_at", ""),
            "window_start": weekly.get("window_start") or (previous_windows.get("ClinicalTrials.gov") or {}).get("window_start", ""),
            "window_end": ct_window_id or (previous_windows.get("ClinicalTrials.gov") or {}).get("window_end", ""),
            "comparison_available": weekly.get("comparison_available") is True if ct_window_id else (previous_windows.get("ClinicalTrials.gov") or {}).get("comparison_available", False),
            "raw_change_count": source_new_counts["ClinicalTrials.gov"] if "ClinicalTrials.gov" in advanced_sources else (previous_windows.get("ClinicalTrials.gov") or {}).get("raw_change_count", 0),
            "source_revision": current_source_revisions["ClinicalTrials.gov"] or (previous_windows.get("ClinicalTrials.gov") or {}).get("source_revision", ""),
        },
        "ChiCTR": {
            **(previous_windows.get("ChiCTR") or {}),
            "cadence": "28_days", "updated_at": chictr_window_id or (previous_windows.get("ChiCTR") or {}).get("updated_at", ""),
            "window_start": chictr_baseline_id or (previous_windows.get("ChiCTR") or {}).get("window_start", ""),
            "window_end": chictr_window_id or (previous_windows.get("ChiCTR") or {}).get("window_end", ""),
            "comparison_available": bool(chictr_baseline_payload) if chictr_window_id else (previous_windows.get("ChiCTR") or {}).get("comparison_available", False),
            "raw_change_count": source_new_counts["ChiCTR"] if "ChiCTR" in advanced_sources else (previous_windows.get("ChiCTR") or {}).get("raw_change_count", 0),
            "source_revision": current_source_revisions["ChiCTR"] or (previous_windows.get("ChiCTR") or {}).get("source_revision", ""),
        },
        "ChinaDrugTrials": {
            **(previous_windows.get("ChinaDrugTrials") or {}),
            "cadence": "monthly_manual", "updated_at": cdt_window_id or (previous_windows.get("ChinaDrugTrials") or {}).get("updated_at", ""),
            "window_start": cdt_baseline_id or (previous_windows.get("ChinaDrugTrials") or {}).get("window_start", ""),
            "window_end": cdt_window_id or (previous_windows.get("ChinaDrugTrials") or {}).get("window_end", ""),
            "comparison_available": "old_count" in cdt_changes if cdt_window_id else (previous_windows.get("ChinaDrugTrials") or {}).get("comparison_available", False),
            "raw_change_count": source_new_counts["ChinaDrugTrials"] if "ChinaDrugTrials" in advanced_sources else (previous_windows.get("ChinaDrugTrials") or {}).get("raw_change_count", 0),
            "source_revision": current_source_revisions["ChinaDrugTrials"] or (previous_windows.get("ChinaDrugTrials") or {}).get("source_revision", ""),
        },
    }
    return candidates, windows


def build_prompt(candidates: list[dict[str, Any]]) -> str:
    compact = [{
        "candidateId": item["candidateId"], "title": item.get("title"), "registryRefs": item.get("registryRefs"),
        "phase": item.get("phase"), "studyType": item.get("studyType"), "conditions": item.get("conditions"),
        "population": item.get("population"), "interventions": item.get("interventions"),
        "eventType": item.get("eventType"), "fromStatus": item.get("fromStatus"), "toStatus": item.get("toStatus"),
        "changeSummary": item.get("changeSummary"), "trialImportance": item.get("trialImportance"),
        "keyTrialRationale": item.get("keyTrialRationale"), "updateMateriality": item.get("updateMateriality"),
        "materialityRationale": item.get("materialityRationale"), "deterministicStrength": item.get("deterministicStrength"),
        "deterministicDecision": item.get("deterministicDecision"), "whyStopped": item.get("whyStopped"),
    } for item in candidates]
    schema = {
        "decisions": [{"candidateId": "ID", "decision": "include | background", "reason": "中文理由"}],
        "signals": [{
            "candidateId": "ID", "type": "关键试验 | 开发进展 | 结果里程碑 | 安全性/终止 | 中国开发 | 早期探索",
            "title": "中文信号标题", "takeaway": "本次注册变化是什么及其开发含义",
            "whySignal": "为什么现在值得关注", "evidenceBoundary": "不能从登记信息推出什么",
            "maUse": "医学事务用途",
            "strategicNoveltyScore": "1-5整数",
        }],
    }
    return (
        "请逐项复核 clinical trial candidates。deterministicDecision=exclude/background 的条目不会交给你；"
        "你只能在其余候选中保留或降级。每个 candidateId 必须有 decision；只有 include 才能有 signal。\n"
        "强度已由代码确定，不输出也不得改写强度。\n"
        f"输出结构：{json.dumps(schema, ensure_ascii=False)}\n"
        f"candidates：{json.dumps(compact, ensure_ascii=False)}"
    )


def deterministic_fallback(candidate: dict[str, Any]) -> dict[str, str]:
    event_label = {
        "added": "新增登记", "status_change": "状态更新", "results_posted": "结果登记",
        "updated": "注册信息更新", "removed": "记录移除",
    }.get(candidate.get("eventType"), "注册更新")
    title = normalize_text(candidate.get("title")) or normalize_text(candidate.get("candidateId"))
    change = normalize_text(candidate.get("changeSummary")) or candidate.get("materialityRationale") or event_label
    return {
        "title": f"{title}出现{event_label}",
        "takeaway": f"本期可核实的变化为“{change}”，其意义应按{candidate.get('trialImportance')}试验的开发阶段解读。",
        "whySignal": f"该变化属于{candidate.get('updateMateriality')}更新，可能影响后续招募、读出或开发路径的跟踪优先级。",
        "evidenceBoundary": "这是注册与开发里程碑信号，不代表疗效、安全性或主要终点已经得到临床证实。",
        "maUse": "用于核对试验设计、预计读出和竞争格局变化。",
    }


def normalize_signal(candidate: dict[str, Any], raw: dict[str, Any], index: int) -> dict[str, Any]:
    fallback = deterministic_fallback(candidate)
    registry_refs = candidate.get("registryRefs") or []
    signal = {
        "id": f"T{index:02d}", "candidateId": candidate.get("candidateId"),
        "sourceType": "clinical_trial", "strengthScale": "trial_milestone_priority",
        "strength": candidate.get("deterministicStrength") or "弱", "type": normalize_text(raw.get("type")) or "开发进展",
        "title": chinese_text(raw.get("title"), fallback["title"]),
        "takeaway": chinese_text(raw.get("takeaway"), fallback["takeaway"]),
        "whySignal": chinese_text(raw.get("whySignal"), fallback["whySignal"]),
        "evidenceBoundary": chinese_text(raw.get("evidenceBoundary"), fallback["evidenceBoundary"]),
        "maUse": chinese_text(raw.get("maUse"), fallback["maUse"]),
        "signalScore": int(candidate.get("signalScore") or 3),
        "strategicNoveltyScore": max(1, min(5, int(raw.get("strategicNoveltyScore") or (4 if candidate.get("strategicContext") else 2)))),
        "trialImportance": candidate.get("trialImportance"), "keyTrialRationale": candidate.get("keyTrialRationale"),
        "updateMateriality": candidate.get("updateMateriality"), "materialityRationale": candidate.get("materialityRationale"),
        "strengthRationale": candidate.get("strengthRationale"), "eventType": candidate.get("eventType"),
        "phase": candidate.get("phase") or "未标注", "fromStatus": candidate.get("fromStatus") or "",
        "toStatus": candidate.get("toStatus") or candidate.get("status") or "", "changeSummary": candidate.get("changeSummary") or "",
        "interventions": candidate.get("interventions") or [], "conditions": candidate.get("conditions") or [],
        "date": candidate.get("date") or candidate.get("updatedAt") or "", "registryRefs": registry_refs,
        "registryIds": [ref.get("registryId") for ref in registry_refs if ref.get("registryId")],
    }
    no_result_data = candidate.get("eventType") in {"results_posted", "status_change"}
    overclaim_pattern = r"(?:证实|证明|显示|表明|提示).{0,24}(?:疗效|有效|改善|降低|优于|阳性|达到主要终点)"
    if no_result_data and re.search(overclaim_pattern, signal["takeaway"], re.I):
        signal["takeaway"] = fallback["takeaway"]
    if no_result_data and re.search(overclaim_pattern, signal["whySignal"], re.I):
        signal["whySignal"] = fallback["whySignal"]
    if no_result_data and re.search(overclaim_pattern, signal["evidenceBoundary"], re.I):
        signal["evidenceBoundary"] = fallback["evidenceBoundary"]
    return signal


def analyze_candidates(candidates: list[dict[str, Any]], complete_fn=complete) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = []
    eligible = []
    for candidate in candidates:
        base_decision = candidate.get("deterministicDecision")
        if base_decision in {"exclude", "background"}:
            decisions.append({
                "candidateId": candidate["candidateId"], "decision": base_decision,
                "reason": candidate.get("strengthRationale") or candidate.get("materialityRationale"),
                "trialImportance": candidate.get("trialImportance"), "updateMateriality": candidate.get("updateMateriality"),
                "strength": "",
            })
        else:
            eligible.append(candidate)
    if not eligible:
        return [], decisions

    response = parse_llm_json(complete_fn(build_prompt(eligible), system=SYSTEM, temperature=0.1, max_tokens=8000, use_cache=True))
    raw_decisions = {
        normalize_text(item.get("candidateId")): item
        for item in response.get("decisions") or [] if isinstance(item, dict) and item.get("candidateId")
    }
    raw_signals = {
        normalize_text(item.get("candidateId")): item
        for item in response.get("signals") or [] if isinstance(item, dict) and item.get("candidateId")
    }
    expected = {item["candidateId"] for item in eligible}
    if set(raw_decisions) != expected:
        missing = sorted(expected - set(raw_decisions))
        extra = sorted(set(raw_decisions) - expected)
        raise RuntimeError(f"Trial LLM decisions mismatch: missing={missing}, extra={extra}")

    included = []
    for candidate in eligible:
        candidate_id = candidate["candidateId"]
        raw_decision = normalize_text(raw_decisions[candidate_id].get("decision")).lower()
        decision = "include" if raw_decision == "include" and candidate_id in raw_signals else "background"
        decisions.append({
            "candidateId": candidate_id, "decision": decision,
            "reason": chinese_text(raw_decisions[candidate_id].get("reason"), candidate.get("strengthRationale") or "按规则裁决"),
            "trialImportance": candidate.get("trialImportance"), "updateMateriality": candidate.get("updateMateriality"),
            "strength": candidate.get("deterministicStrength") if decision == "include" else "",
        })
        if decision == "include":
            included.append((candidate, raw_signals[candidate_id]))
    included.sort(key=lambda pair: (
        -STRENGTH_RANK.get(pair[0].get("deterministicStrength"), 0),
        normalize_text(pair[0].get("date")), pair[0]["candidateId"],
    ))
    signals = [normalize_signal(candidate, raw, index) for index, (candidate, raw) in enumerate(included, 1)]
    decisions.sort(key=lambda item: item["candidateId"])
    return signals, decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-current-window", action="store_true", help="重放已发布试验候选，不推进三源窗口")
    args = parser.parse_args()
    previous = load_js_global(OUTPUT_PATH, "MG_TRIAL_SIGNALS_DATA") if OUTPUT_PATH.exists() else {}
    if args.replay_current_window:
        candidates = previous.get("analysis_cohort") or []
        current_versions = current_source_versions()
        windows = {
            source: {
                **window,
                "window_start": window.get("window_start") or window.get("updated_at") or "",
                "window_end": window.get("window_end") or window.get("updated_at") or "",
                # 只给仍与当前缓存处在同一比较窗口的旧产物补版本摘要；缓存已推进时保持缺失并由发布校验拦截。
                **({"source_revision": current_versions[source]["source_revision"]}
                   if normalize_text(window.get("source_revision")) in {
                       "", current_versions[source]["legacy_source_revision"],
                   }
                   and normalize_text(window.get("updated_at")) == current_versions[source]["updated_at"]
                   and current_versions[source]["source_revision"] else {}),
            }
            for source, window in (previous.get("source_windows") or {}).items()
        }
    else:
        candidates, windows = build_candidates(previous)
        if previous and all(
            all(
                normalize_text((windows.get(source) or {}).get(key)) ==
                normalize_text(((previous.get("source_windows") or {}).get(source) or {}).get(key))
                for key in ("updated_at", "source_revision")
            )
            for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
        ):
            print("No source window advanced; preserved existing trial signal artifact")
            return 0
    signals, decisions = analyze_candidates(candidates)
    payload = {
        "schema_version": "1.0", "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_policy": {
            "analysis_model": "clinical-trial-signal-enrichment-v2", "llm_enrichment": True,
            "strength_scale": "source_internal_trial_milestone_priority",
            "mg_core_policy": "strict_title_condition_population_guard",
            "cross_source_comparison": False, "replay_window_preserved": bool(args.replay_current_window),
        },
        "source_windows": windows, "analysis_cohort": candidates, "selection_decisions": decisions,
        "signal_summary": {
            "total_count": len(signals),
            "strength_counts": {label: sum(item.get("strength") == label for item in signals) for label in ("强", "中", "弱")},
        },
        "signals": signals,
    }
    atomic_write_js_global(OUTPUT_PATH, "MG_TRIAL_SIGNALS_DATA", payload)
    try:
        output_label = OUTPUT_PATH.relative_to(PROJECT)
    except ValueError:
        output_label = OUTPUT_PATH
    print(f"Wrote {len(signals)} trial signals from {len(candidates)} candidates to {output_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
