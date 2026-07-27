#!/usr/bin/env python3
"""从已审计缓存构建情报中心临床试验数据。"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common.clinical_registry import load_china_drug_trials_cache
from scripts.common.source_channels import _cdt_items, _chictr_items, _ct_items, deduplicate_trials


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CT_CACHE_PATH = DATA_DIR / "clinicaltrials-pipeline-cache.json"
CHICTR_CACHE_PATH = DATA_DIR / "chictr-trials-cache.json"
CHINA_DRUG_TRIALS_CACHE_PATH = DATA_DIR / "china-drug-trials-cache.json"
OUTPUT_PATH = DATA_DIR / "clinical-trials-data.js"

SOURCE_ORDER = ["ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials"]
INDICATION = "重症肌无力"

STATUS_MAP = {
    "RECRUITING": ("招募中", "recruiting"),
    "ENROLLING_BY_INVITATION": ("招募中", "recruiting"),
    "ACTIVE_NOT_RECRUITING": ("进行中", "active"),
    "COMPLETED": ("已完成", "completed"),
    "TERMINATED": ("已终止", "terminated"),
    "WITHDRAWN": ("已撤回", "terminated"),
    "SUSPENDED": ("暂停", "other"),
    "NOT_YET_RECRUITING": ("尚未招募", "recruiting"),
    "UNKNOWN": ("未知", "other"),
}

DRUG_CLASS_TERMS = (
    (
        "FcRn 拮抗剂",
        (
            "batoclimab",
            "efgartigimod",
            "rozanolixizumab",
            "nipocalimab",
            "m281",
            "imvt-1401",
            "imvt-1402",
            "fcrn antagonist",
            "fcrn inhibitor",
            "hbm9161",
            "hl161",
            "艾加莫德",
            "argx-113",
            "罗泽利昔珠单抗",
        ),
    ),
    (
        "补体抑制剂",
        (
            "eculizumab",
            "ravulizumab",
            "zilucoplan",
            "crovalimab",
            "complement inhibitor",
            "complement inhibition",
            "cemdisiran",
            "pozelimab",
            "依库珠单抗",
            "瑞利珠单抗",
            "alxn1720",
        ),
    ),
    (
        "B细胞/抗CD19/CD20",
        (
            "rituximab",
            "ocrelizumab",
            "inebilizumab",
            "telitacicept",
            "anti-cd19",
            "anti-cd20",
            "泰它西普",
            "sys6020",
            "bcma",
            "senl103",
            "car-t",
            "cizutamig",
        ),
    ),
    (
        "免疫抑制剂",
        (
            "mycophenolate",
            "azathioprine",
            "tacrolimus",
            "cyclosporine",
            "methotrexate",
            "cladribine",
            "remibrutinib",
            "lou064",
            "btk inhibitor",
            "硫唑嘌呤",
            "他克莫司",
            "克拉屈滨",
        ),
    ),
    ("胆碱酯酶抑制剂", ("pyridostigmine", "溴吡斯的明", "huperzine", "石杉碱甲", "edrophonium", "依酚氯铵")),
    (
        "免疫调节",
        (
            "plasma exchange",
            "plex",
            "ivig",
            "immunoglobulin",
            "immune globulin",
        ),
    ),
    (
        "IL-6 抑制剂",
        ("satralizumab", "萨特利珠单抗", "tocilizumab", "sar442168"),
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    """读取构建所需的本地 JSON 缓存。"""
    return json.loads(path.read_text(encoding="utf-8"))


def date_part(value: Any) -> str:
    """提取 ISO 日期部分，避免构建时间随运行时钟变化。"""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or "").strip())
    return match.group(1) if match else ""


def normalize_status(value: Any) -> tuple[str, str]:
    """将注册库状态统一为中文标签和前端样式类。"""
    raw_status = str(value or "").strip()
    status_key = re.sub(r"[\s-]+", "_", raw_status.upper())
    return STATUS_MAP.get(status_key, (raw_status, "other"))


def contains_term(text: str, term: str) -> bool:
    """短缩写使用词边界匹配，避免 PLEX 命中 complex 等单词。"""
    if term in {"m281", "plex", "ivig"}:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


def extract_drug_class(title: Any, drug_name: Any = "") -> str:
    """仅从归一化题名和药物名称提取药物机制分类。"""
    normalized = (str(title or "") + " " + str(drug_name or "")).lower()
    for drug_class, terms in DRUG_CLASS_TERMS:
        if any(contains_term(normalized, term) for term in terms):
            return drug_class
    return "其他"


def phase_label(value: Any) -> str:
    """将 CT.gov 或中文注册库的分期字段转为可读文本。"""
    if isinstance(value, list):
        values = [phase_label(item) for item in value if item]
        values = [item for item in values if item != "未标注"]
        return " / ".join(dict.fromkeys(values)) or "未标注"

    raw_phase = str(value or "").strip()
    phase_key = raw_phase.upper().replace(" ", "_")
    labels = {
        "EARLY_PHASE1": "Early Phase 1",
        "PHASE1": "Phase 1",
        "PHASE1_PHASE2": "Phase 1/2",
        "PHASE2": "Phase 2",
        "PHASE2_PHASE3": "Phase 2/3",
        "PHASE3": "Phase 3",
        "PHASE4": "Phase 4",
        "NA": "N/A",
        "N/A": "N/A",
        "UNKNOWN": "未标注",
    }
    return labels.get(phase_key, raw_phase or "未标注")


def ct_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 NCT 编号索引 CT.gov 中未进入轻量归一化结果的展示字段。"""
    result: dict[str, dict[str, Any]] = {}
    for study in payload.get("studies") or []:
        protocol = study.get("protocolSection") or {}
        identification = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        design = protocol.get("designModule") or {}
        sponsor = protocol.get("sponsorCollaboratorsModule") or {}
        registry_id = identification.get("nctId") or ""
        if not registry_id:
            continue
        result[registry_id] = {
            "phase": design.get("phases") or [],
            "sponsor": (sponsor.get("leadSponsor") or {}).get("name") or "",
            "start_date": (status.get("startDateStruct") or {}).get("date") or "",
            "registered_date": (
                (status.get("studyFirstPostDateStruct") or {}).get("date")
                or status.get("studyFirstSubmitDate")
                or ""
            ),
        }
    return result


def chictr_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 ChiCTR 编号索引起始日期等缓存字段。"""
    return {
        str(record.get("registry_id") or ""): {
            "start_date": record.get("start_date") or "",
            "registered_date": record.get("registered_date") or "",
        }
        for record in payload.get("records") or []
        if record.get("registry_id")
    }


def enrich_record(
    item: dict[str, Any],
    ct_details: dict[str, dict[str, Any]],
    chictr_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """补齐前端卡片、状态和筛选器所需字段。"""
    registry = str(item.get("registry") or item.get("source") or "")
    registry_id = str(item.get("registry_id") or item.get("id") or "")
    details = ct_details.get(registry_id, {}) if registry == "ClinicalTrials.gov" else chictr_details.get(registry_id, {})
    status = str(item.get("status") or "Unknown")
    status_label, status_class = normalize_status(status)
    linked_registries = sorted(
        item.get("linked_registries") or [],
        key=lambda linked: (
            str(linked.get("registry") or ""),
            str(linked.get("registry_id") or ""),
        ),
    )

    return {
        "registry": registry,
        "registry_id": registry_id,
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "status": status,
        "status_label": status_label,
        "status_class": status_class,
        "drug_class": extract_drug_class(item.get("title"), item.get("drug_name")),
        "drug_name": str(item.get("drug_name") or ""),
        "indication": INDICATION,
        "phase_label": phase_label(details.get("phase", item.get("phase"))),
        "sponsor": str(item.get("sponsor") or details.get("sponsor") or ""),
        "start_date": str(item.get("start_date") or details.get("start_date") or ""),
        "readout_date": str(item.get("readout_date") or ""),
        "completion_date": str(item.get("completion_date") or ""),
        "registered_date": str(details.get("registered_date") or item.get("date") or ""),
        "linked_registries": linked_registries,
    }


def six_month_cutoff(reference: date) -> date:
    """计算自然月口径的六个月前日期。"""
    month_index = reference.year * 12 + reference.month - 1 - 6
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    month_lengths = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(reference.day, month_lengths[month - 1]))


def parse_iso_date(value: Any) -> date | None:
    """宽容解析 YYYY-MM-DD 日期。"""
    try:
        return date.fromisoformat(date_part(value))
    except ValueError:
        return None


def build_decision_signals(records: list[dict[str, Any]], generated_at: str) -> list[dict[str, str]]:
    """基于完整记录集生成稳定、可复核的决策信号。"""
    recruiting_keys = {"RECRUITING", "ENROLLING_BY_INVITATION"}
    recruiting_count = sum(
        re.sub(r"[\s-]+", "_", record.get("status", "").upper()) in recruiting_keys
        for record in records
    )

    known_class_counts = Counter(
        record["drug_class"] for record in records if record.get("drug_class") not in {"", "其他"}
    )
    if known_class_counts:
        leading_class, leading_count = sorted(
            known_class_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        class_detail = f"{leading_class}在可识别机制中最多，共 {leading_count} 项。"
    else:
        class_detail = "当前题名未识别出明确药物机制分类。"

    reference_date = parse_iso_date(generated_at)
    cutoff = six_month_cutoff(reference_date) if reference_date else None
    recent_count = sum(
        bool(registered_date and cutoff and cutoff <= registered_date <= reference_date)
        for registered_date in (parse_iso_date(record.get("registered_date")) for record in records)
    )

    return [
        {
            "title": "招募中试验",
            "detail": f"当前共有 {recruiting_count} 项招募中或邀请入组试验。",
            "tag": "招募",
        },
        {
            "title": "药物机制热点",
            "detail": class_detail,
            "tag": "药物分类",
        },
        {
            "title": "近 6 个月新登记",
            "detail": f"截至 {generated_at}，近 6 个月登记 {recent_count} 项试验。",
            "tag": "近期登记",
        },
    ]


PHASE_RANK = {
    "Early Phase 1": 0.5, "Phase 1": 1, "Phase 1/2": 1.5,
    "Phase 2": 2, "Phase 2/3": 2.5, "Phase 3": 3, "Phase 4": 4,
}

DRUG_CLASS_ORDER = [
    "FcRn 拮抗剂", "补体抑制剂", "B细胞/抗CD19/CD20",
    "IL-6 抑制剂", "免疫抑制剂", "胆碱酯酶抑制剂", "免疫调节", "其他",
]

# Canonical drug name mapping: lowercase alias → display name
DRUG_SYNONYMS: dict[str, str] = {
    # FcRn
    "efgartigimod": "Efgartigimod (艾加莫德)",
    "efgartigimod ph20 sc": "Efgartigimod (艾加莫德)",
    "efgartigimod alfa": "Efgartigimod (艾加莫德)",
    "efgartigimod iv": "Efgartigimod (艾加莫德)",
    "argx-113": "Efgartigimod (艾加莫德)",
    "argx-113-2308": "Efgartigimod (艾加莫德)",
    "艾加莫德": "Efgartigimod (艾加莫德)",
    "艾加莫德α注射液": "Efgartigimod (艾加莫德)",
    "艾加莫德α注射液（皮下注射）": "Efgartigimod (艾加莫德)",
    "艾加莫德 α 注射液": "Efgartigimod (艾加莫德)",
    "efgartigimod浓缩注射液": "Efgartigimod (艾加莫德)",
    "efgartigimod注射液": "Efgartigimod (艾加莫德)",
    "rozanolixizumab": "Rozanolixizumab (罗泽利昔珠单抗)",
    "罗泽利昔珠单抗注射液": "Rozanolixizumab (罗泽利昔珠单抗)",
    "nipocalimab": "Nipocalimab",
    "nipocalimab注射液": "Nipocalimab",
    "hbm9161": "Batoclimab (HBM9161)",
    "hbm9161注射液": "Batoclimab (HBM9161)",
    "hbm9161 injection (680mg)": "Batoclimab (HBM9161)",
    "hbm9161(hl161bkn)注射液": "Batoclimab (HBM9161)",
    "hl161": "Batoclimab (HBM9161)",
    "imvt-1401": "Batoclimab (HBM9161)",
    "imvt-1402": "IMVT-1402",
    "batoclimab": "Batoclimab (HBM9161)",
    "m281": "Batoclimab (HBM9161)",
    "mom-m281": "Batoclimab (HBM9161)",
    # Complement
    "eculizumab": "Eculizumab (依库珠单抗)",
    "依库珠单抗注射液": "Eculizumab (依库珠单抗)",
    "ravulizumab": "Ravulizumab (瑞利珠单抗)",
    "瑞利珠单抗注射液": "Ravulizumab (瑞利珠单抗)",
    "alxn1720": "Ravulizumab (ALXN1720)",
    "alxn1720注射液": "Ravulizumab (ALXN1720)",
    "zilucoplan": "Zilucoplan",
    "zilucoplan (ra101495)": "Zilucoplan",
    "ra101495": "Zilucoplan",
    "crovalimab": "Crovalimab",
    "cemdisiran": "Cemdisiran",
    "pozelimab": "Pozelimab",
    # B-cell
    "telitacicept": "Telitacicept (泰它西普)",
    "泰它西普注射液": "Telitacicept (泰它西普)",
    "注射用泰它西普": "Telitacicept (泰它西普)",
    "rituximab": "Rituximab (利妥昔单抗)",
    "inebilizumab": "Inebilizumab",
    "inebilizumab 注射液": "Inebilizumab",
    "sys6020注射液": "SYS6020 (BCMA CAR-T)",
    "senl103自体t细胞注射液": "SENL103 (CAR-T)",
    "cizutamig": "Cizutamig",
    "cizutamig注射液": "Cizutamig",
    # IL-6
    "satralizumab": "Satralizumab (萨特利珠单抗)",
    "萨特利珠单抗注射液": "Satralizumab (萨特利珠单抗)",
    "sar442168": "SAR442168 (已终止)",
    # Immunosuppressants
    "remibrutinib": "Remibrutinib (LOU064)",
    "remibrutinib (lou064)": "Remibrutinib (LOU064)",
    "cladribine": "Cladribine (克拉屈滨)",
    "克拉屈滨胶囊": "Cladribine (克拉屈滨)",
    "azathioprine": "Azathioprine (硫唑嘌呤)",
    "硫唑嘌呤片": "Azathioprine (硫唑嘌呤)",
    "tacrolimus": "Tacrolimus (他克莫司)",
    "他克莫司胶囊": "Tacrolimus (他克莫司)",
    "shr-2173注射液": "SHR-2173",
    "b007注射液": "B007",
    # Cholinesterase
    "pyridostigmine": "Pyridostigmine (溴吡斯的明)",
    "溴吡斯的明片": "Pyridostigmine (溴吡斯的明)",
    "溴吡斯的明缓释片": "Pyridostigmine (溴吡斯的明)",
    "huperzine": "Huperzine A (石杉碱甲)",
    "石杉碱甲口服溶液": "Huperzine A (石杉碱甲)",
    "edrophonium": "Edrophonium (依酚氯铵)",
    "依酚氯铵注射液": "Edrophonium (依酚氯铵)",
    # Other
    "belimumab": "Belimumab",
    "注射用重组人b淋巴细胞刺激因子受体－抗体融合蛋白": "Belimumab",
}


def normalize_drug_name(raw: str) -> str:
    """Map raw drug name to canonical display name."""
    if not raw:
        return ""
    key = raw.strip().lower()
    return DRUG_SYNONYMS.get(key, raw.strip())


def _extract_drug_name(record: dict[str, Any]) -> str:
    """从记录中提取药物名称并归一化。"""
    drug = str(record.get("drug_name") or "").strip()
    if drug and drug != "NA":
        return normalize_drug_name(drug)
    # Fallback: try to extract from title
    title = str(record.get("title") or "")
    if not title:
        return record.get("registry_id", "Unknown")
    # Check if any known drug appears in title
    title_lower = title.lower()
    for alias, canonical in DRUG_SYNONYMS.items():
        if alias in title_lower:
            return canonical
    return title[:60]


def build_pipeline_matrix(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按药物机制分类 → 药物名称聚合为管线矩阵行。"""
    # Group by (drug_class, drug_name)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        drug_class = rec.get("drug_class") or "其他"
        drug_name = _extract_drug_name(rec)
        key = (drug_class, drug_name)
        groups.setdefault(key, []).append(rec)

    matrix = []
    for (drug_class, drug_name), trials in groups.items():
        # Determine highest phase
        phases = [t.get("phase_label", "未标注") for t in trials]
        phase_ranks = [PHASE_RANK.get(p, -1) for p in phases]
        best_idx = max(range(len(phase_ranks)), key=lambda i: phase_ranks[i])
        highest_phase = phases[best_idx] if phase_ranks[best_idx] >= 0 else "未标注"

        # Status summary
        status_counts = Counter(t.get("status_label", "未知") for t in trials)
        recruiting = status_counts.get("招募中", 0) + status_counts.get("尚未招募", 0)
        active = status_counts.get("进行中", 0)
        completed = status_counts.get("已完成", 0)
        terminated = status_counts.get("已终止", 0) + status_counts.get("已撤回", 0)

        # Source breakdown
        source_counts = Counter(t.get("registry", "") for t in trials)

        # Key trial (most recent or highest phase)
        key_trial = trials[best_idx]

        # Sponsors
        sponsors = sorted({t.get("sponsor", "") for t in trials if t.get("sponsor")})

        # Timeline: earliest start / latest readout / latest completion
        start_dates = sorted(d for d in (date_part(t.get("start_date")) for t in trials) if d)
        readout_dates = sorted(d for d in (date_part(t.get("readout_date")) for t in trials) if d)
        completion_dates = sorted(d for d in (date_part(t.get("completion_date")) for t in trials) if d)
        registered_dates = sorted(
            d for d in (date_part(t.get("registered_date") or t.get("start_date")) for t in trials) if d
        )

        matrix.append({
            "drug_class": drug_class,
            "name": drug_name,
            "highest_phase_label": highest_phase,
            "stage_number": PHASE_RANK.get(highest_phase, 0),
            "study_count": len(trials),
            "status_summary": f"招募 {recruiting} · 进行 {active} · 完成 {completed}" + (f" · 终止 {terminated}" if terminated else ""),
            "sponsors": sponsors[:3],
            "sources": dict(source_counts),
            "key_trial": {
                "registry": key_trial.get("registry", ""),
                "registry_id": key_trial.get("registry_id", ""),
                "title": key_trial.get("title", ""),
                "url": key_trial.get("url", ""),
            },
            "trials": [
                {"registry": t.get("registry"), "registry_id": t.get("registry_id"), "url": t.get("url")}
                for t in trials[:10]
            ],
            "timeline": {
                "start": start_dates[0] if start_dates else (registered_dates[0] if registered_dates else ""),
                "readout": readout_dates[-1] if readout_dates else "",
                "completion": completion_dates[-1] if completion_dates else "",
            },
            "first_registered": registered_dates[0] if registered_dates else "",
            "latest_registered": registered_dates[-1] if registered_dates else "",
            "linked_registries": [
                lr for t in trials for lr in (t.get("linked_registries") or [])
            ],
        })

    # Sort: drug class order → stage desc → study count desc
    class_rank = {c: i for i, c in enumerate(DRUG_CLASS_ORDER)}
    matrix.sort(key=lambda m: (
        class_rank.get(m["drug_class"], 99),
        -m["stage_number"],
        -m["study_count"],
        m["name"],
    ))
    return matrix


def build_payload() -> dict[str, Any]:
    """装配前端要求的三来源数据结构。"""
    ct_payload = load_json(CT_CACHE_PATH)
    chictr_payload = load_json(CHICTR_CACHE_PATH)
    china_payload = load_china_drug_trials_cache(CHINA_DRUG_TRIALS_CACHE_PATH)

    normalized_items = deduplicate_trials(
        _ct_items(ct_payload) + _chictr_items(chictr_payload) + _cdt_items(china_payload)
    )
    ct_details = ct_metadata(ct_payload)
    chictr_details = chictr_metadata(chictr_payload)
    records = [
        enrich_record(item, ct_details, chictr_details)
        for item in normalized_items
    ]
    records.sort(key=lambda record: (record["registry"], record["registry_id"]))

    records_by_source = {
        source: sorted(
            (record for record in records if record["registry"] == source),
            key=lambda record: record["registry_id"],
        )
        for source in SOURCE_ORDER
    }

    generated_at = date_part(ct_payload.get("generated_at")) or date_part(chictr_payload.get("last_verified"))
    ct_generated_at = date_part(ct_payload.get("generated_at"))
    chictr_generated_at = date_part(chictr_payload.get("last_verified") or chictr_payload.get("generated_at"))
    china_records = records_by_source["ChinaDrugTrials"]
    china_mode = str(china_payload.get("mode") or "unavailable")
    if not china_records:
        china_mode = "unavailable"

    sources = [
        {
            "source": "ClinicalTrials.gov",
            "meta": {"generated_at": ct_generated_at, "mode": "cache"},
            "records": records_by_source["ClinicalTrials.gov"],
        },
        {
            "source": "ChiCTR",
            "meta": {"generated_at": chictr_generated_at, "mode": "cache"},
            "records": records_by_source["ChiCTR"],
        },
        {
            "source": "ChinaDrugTrials",
            "meta": {
                "generated_at": date_part(china_payload.get("generated_at") or china_payload.get("last_verified")),
                "mode": china_mode,
                "warning": str(china_payload.get("warning") or "无已验证数据源"),
            },
            "records": china_records,
        },
    ]

    pipeline_matrix = build_pipeline_matrix(records)

    return {
        "meta": {
            "generated_at": generated_at,
            "total_count": sum(len(source["records"]) for source in sources),
            "sources_order": SOURCE_ORDER,
        },
        "decision_signals": build_decision_signals(records, generated_at),
        "pipeline_matrix": pipeline_matrix,
        "sources": sources,
    }


def main() -> None:
    """生成可由浏览器直接加载的 JavaScript 数据文件。"""
    payload = build_payload()
    output = "window.MG_CLINICAL_TRIALS_DATA = " + json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ) + ";\n"
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Wrote {payload['meta']['total_count']} records to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
