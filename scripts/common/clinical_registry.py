"""临床试验注册缓存加载与归一化。"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import atomic_write_json


ACTIVE_STATUSES = {"RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}
STATUS_LABELS = {
    "RECRUITING": "招募中", "ACTIVE_NOT_RECRUITING": "进行中/停止招募",
    "NOT_YET_RECRUITING": "尚未招募", "ENROLLING_BY_INVITATION": "邀请入组",
}
PHASE_RANK = {"PHASE4": 4, "PHASE3": 3, "PHASE2_PHASE3": 2.5, "PHASE2": 2, "PHASE1_PHASE2": 1.5}
CANONICAL_INTERVENTIONS = [
    ("Batoclimab", ["batoclimab", "hbm9161", "hl161", "rvt-1401"], "FcRn", "FcRn", "Immunovant / Harbour"),
    ("IMVT-1402", ["imvt-1402"], "FcRn", "FcRn", "Immunovant"),
    ("B007", ["b007"], "待补充", "待补充", "Shanghai Jiaolian"),
    ("Iptacopan", ["iptacopan"], "补体", "Factor B", "Novartis"),
    ("Claseprubart", ["claseprubart", "dnth103"], "补体", "补体通路", "Dianthus"),
    ("Pozelimab/Cemdisiran", ["pozelimab", "cemdisiran"], "补体", "C5 / C5 siRNA", "Regeneron"),
    ("Empasiprubart", ["empasiprubart"], "补体", "C2", "argenx"),
    ("Inebilizumab", ["inebilizumab"], "B细胞", "CD19", "Amgen"),
    ("Remibrutinib", ["remibrutinib"], "B细胞", "BTK", "Novartis"),
    ("Blinatumomab", ["blinatumomab"], "B细胞", "CD19/CD3 BiTE", "Academic"),
    ("Povetacicept", ["povetacicept"], "BAFF/APRIL", "BAFF/APRIL", "Vertex"),
    ("Aritinercept", ["aritinercept"], "BAFF/APRIL", "APRIL/BAFF", "Aurinia"),
    ("Descartes-08", ["descartes-08", "decartes-08"], "细胞治疗", "BCMA CAR-T", "Cartesian"),
    ("CABA-201", ["caba-201"], "细胞治疗", "CD19 CAR-T", "Cabaletta"),
    ("KYV-101", ["kyv-101"], "细胞治疗", "CD19 CAR-T", "Kyverna"),
    ("BAFF-R CAR-T", ["baff-r cart", "baff-r car-t"], "细胞治疗", "BAFF-R CAR-T", "Academic"),
    ("NMD670", ["nmd670"], "神经肌接头", "ClC-1", "NMD Pharma"),
    ("Cladribine", ["cladribine"], "免疫调节", "淋巴细胞耗竭", "Merck KGaA"),
    ("Tocilizumab", ["tocilizumab"], "免疫调节", "IL-6R", "Academic"),
    ("CNP-106", ["cnp-106"], "免疫耐受", "抗原特异免疫耐受", "COUR"),
    ("IM-101", ["im-101"], "待补充", "待补充", "ImmunAbs"),
    ("SHR-2173", ["shr-2173"], "待补充", "待补充", "Hengrui"),
]
EXCLUDE_INTERVENTIONS = [
    "placebo", "prednisone", "prednisolone", "corticosteroid", "pyridostigmine", "azathioprine",
    "mycophenolate", "tacrolimus", "ivig", "immune globulin", "immunoglobulin", "eculizumab",
    "ravulizumab", "zilucoplan", "efgartigimod", "rozanolixizumab", "nipocalimab", "telitacicept",
]


CHICTR_FIELD_ALIASES = {
    "registry_id": ("registry_id", "registration_number", "regno", "registrationNo"),
    "title": ("title", "scientific_title", "official_title", "study_title"),
    "registered_date": ("registered_date", "registration_date", "date_registered"),
    "registration_type": ("registration_type", "retrospective_or_prospective"),
    "status": ("status", "recruitment_status", "study_status"),
    "official_url": ("official_url", "url", "source_url"),
    "sponsor": ("sponsor", "primary_sponsor"),
    "institution": ("institution", "study_institution", "applicant_institution"),
    "study_type": ("study_type", "type"),
    "phase": ("phase", "study_phase"),
    "start_date": ("start_date", "execution_start", "execute_start"),
    "end_date": ("end_date", "execution_end", "execute_end"),
    "secondary_ids": ("secondary_ids", "secondary_id"),
}


def _first(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, "", []):
            return value
    return ""


def normalize_chictr_record(source: dict[str, Any]) -> dict[str, Any]:
    """只保留公开研究字段；未知字段保持空白或 Unknown。"""
    values = {key: _first(source, aliases) for key, aliases in CHICTR_FIELD_ALIASES.items()}
    secondary = values["secondary_ids"]
    if isinstance(secondary, str):
        secondary = [item.strip() for item in secondary.replace(";", ",").split(",") if item.strip()]
    return {
        "registry": "ChiCTR",
        "registry_id": str(values["registry_id"]).strip(),
        "secondary_ids": secondary or [],
        "title": str(values["title"]).strip(),
        "registered_date": str(values["registered_date"]).strip(),
        "registration_type": str(values["registration_type"]).strip() or "Unknown",
        "status": str(values["status"]).strip() or "Unknown",
        "official_url": str(values["official_url"]).strip(),
        "sponsor": str(values["sponsor"]).strip(),
        "institution": str(values["institution"]).strip(),
        "study_type": str(values["study_type"]).strip() or "Unknown",
        "phase": str(values["phase"]).strip() or "Unknown",
        "start_date": str(values["start_date"]).strip(),
        "end_date": str(values["end_date"]).strip(),
    }


def load_chictr_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1.0",
            "source": "ChiCTR official registry",
            "mode": "cache",
            "records": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("records", [])
    payload.setdefault("mode", "cache")
    return payload


def _load_manual(path: Path) -> tuple[list[dict[str, Any]], str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("records") or payload.get("trials") or payload.get("data") or []
        if not isinstance(payload, list):
            raise ValueError("ChiCTR JSON export must contain a list of records")
        return payload, "json"
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle)), "csv"
    raise ValueError("ChiCTR manual input must be official JSON or CSV export")


def refresh_chictr_cache(cache_path: Path, *, input_path: Path | None = None) -> dict[str, Any]:
    """从官方导出刷新；失败时不写目标并返回最后良好缓存。"""
    try:
        if input_path is None:
            cached = load_chictr_cache(cache_path)
            cached["mode"] = "cache"
            return cached
        raw_records, input_format = _load_manual(input_path)
        by_id: dict[str, dict[str, Any]] = {}
        for raw in raw_records:
            record = normalize_chictr_record(raw)
            if not record["registry_id"] or not record["title"]:
                continue
            if record["official_url"] and not record["official_url"].startswith("https://www.chictr.org.cn/"):
                raise ValueError("ChiCTR source URL must use the official chictr.org.cn domain")
            by_id[record["registry_id"]] = record
        if not by_id:
            raise ValueError("No valid ChiCTR records found in official export")
        payload = {
            "schema_version": "1.0",
            "source": "ChiCTR official registry",
            "source_url": "https://www.chictr.org.cn/",
            "mode": "manual",
            "input_format": input_format,
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "records": sorted(by_id.values(), key=lambda item: item["registry_id"]),
        }
        atomic_write_json(cache_path, payload)
        return payload
    except Exception as exc:
        fallback = load_chictr_cache(cache_path)
        returned = dict(fallback)
        returned["mode"] = "cache"
        returned["warning"] = str(exc)
        return returned


def normalize_registry_trials(clinicaltrials_payload: dict[str, Any], chictr_payload: dict[str, Any], china_drug_trials_payload: dict[str, Any] | None = None):
    """输出保留注册库名称/ID的统一轻量记录，绝不添加 Oxford 等级。"""
    from .source_channels import _ct_items, _chictr_items, deduplicate_trials

    items = _ct_items(clinicaltrials_payload) + _chictr_items(chictr_payload)
    if china_drug_trials_payload:
        from .source_channels import _cdt_items
        items += _cdt_items(china_drug_trials_payload)
    return deduplicate_trials(items)


def compact_raw_clinical_study(study: dict[str, Any]) -> dict[str, Any]:
    protocol = study.get("protocolSection") or {}
    keys = (
        "identificationModule", "statusModule", "sponsorCollaboratorsModule", "conditionsModule",
        "designModule", "armsInterventionsModule", "eligibilityModule",
    )
    return {"protocolSection": {key: protocol.get(key) or {} for key in keys}}


def load_clinicaltrials_studies(cache_path: Path, *, requests_module=None):
    """优先官方 API；任何失败均回退最后良好缓存且不破坏缓存。"""
    source_url = "https://clinicaltrials.gov/search?cond=Myasthenia%20Gravis"
    try:
        if os.environ.get("MG_SKIP_CLINICALTRIALS"):
            raise RuntimeError("MG_SKIP_CLINICALTRIALS is set")
        if requests_module is None:
            import requests as requests_module
        params = {"query.cond": "Myasthenia Gravis", "pageSize": "100", "format": "json"}
        studies = []
        while True:
            response = requests_module.get("https://clinicaltrials.gov/api/v2/studies", params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            studies.extend(payload.get("studies") or [])
            token = payload.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        compact = [compact_raw_clinical_study(study) for study in studies]
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(), "source": "ClinicalTrials.gov API v2",
            "source_url": source_url, "studies": compact,
        }
        atomic_write_json(cache_path, payload)
        return compact, {"source": payload["source"], "source_url": source_url, "generated_at": payload["generated_at"], "mode": "live"}
    except Exception as exc:
        cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        return cached.get("studies") or [], {
            "source": cached.get("source", "ClinicalTrials.gov API v2"), "source_url": cached.get("source_url", source_url),
            "generated_at": cached.get("generated_at", ""), "mode": "cache" if cached else "unavailable", "warning": str(exc),
        }


def _phase_rank(phases):
    return max((PHASE_RANK.get(phase, 0) for phase in phases or []), default=0)


def _phase_label(phases):
    rank = _phase_rank(phases)
    return "III期" if rank >= 3 else "II/III期" if rank == 2.5 else "II期" if rank >= 2 else "I/II期" if rank >= 1.5 else "未标注"


def _canonical_intervention(name):
    low = re.sub(r"\s+", " ", str(name or "").strip().lower())
    for canonical, aliases, target_type, target, sponsor in CANONICAL_INTERVENTIONS:
        if any(alias in low for alias in aliases):
            return {"name": canonical, "target_type": target_type, "target": target, "sponsor_hint": sponsor}
    return None if any(term in low for term in EXCLUDE_INTERVENTIONS) else None


def _population(protocol):
    ident = protocol.get("identificationModule") or {}
    conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
    title = ident.get("briefTitle") or ""
    low = f"{' '.join(conditions)} {title}".lower()
    indication = "血清阴性 gMG" if "seronegative" in low else "AChR+ gMG" if "achr" in low and "general" in low else "Ocular Myasthenia Gravis" if "ocular" in low else "Generalized Myasthenia Gravis" if "general" in low or "gmg" in low else conditions[0] if conditions else "Myasthenia Gravis"
    details = [value for value, present in (("OMG", "ocular" in low), ("gMG", "general" in low or "gmg" in low), ("难治", "refractory" in low), ("血清阴性", "seronegative" in low)) if present]
    return indication, " · ".join(dict.fromkeys(details)) or "未标注"


def _compact_trial(study, canonical_name):
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    sponsor = protocol.get("sponsorCollaboratorsModule") or {}
    nct_id = ident.get("nctId") or ""
    indication, population = _population(protocol)
    return {
        "registry": "ClinicalTrials.gov", "registry_id": nct_id, "nct_id": nct_id,
        "title": ident.get("briefTitle") or "", "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        "status": status.get("overallStatus") or "", "status_label": STATUS_LABELS.get(status.get("overallStatus") or "", status.get("overallStatus") or "未标注"),
        "phases": design.get("phases") or [], "phase_label": _phase_label(design.get("phases") or []), "phase_rank": _phase_rank(design.get("phases") or []),
        "sponsor": (sponsor.get("leadSponsor") or {}).get("name", ""), "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "start": (status.get("startDateStruct") or {}).get("date", ""), "primary_completion": (status.get("primaryCompletionDateStruct") or {}).get("date", ""),
        "completion": (status.get("completionDateStruct") or {}).get("date", ""), "last_update": status.get("lastUpdateSubmitDate", ""),
        "indication": indication, "population": population, "canonical_drug": canonical_name,
    }


def build_clinical_pipeline_matrix(regulatory_map, *, studies=None, meta=None, cache_path=None, requests_module=None):
    if studies is None:
        if cache_path is None:
            raise ValueError("cache_path is required when studies are not supplied")
        studies, loaded_meta = load_clinicaltrials_studies(cache_path, requests_module=requests_module)
        meta = loaded_meta
    meta = dict(meta or {})
    approved = {name for name, item in regulatory_map.items() if item.get("status_class") == "approved"}
    groups = {}
    for study in studies:
        protocol = study.get("protocolSection") or {}
        design = protocol.get("designModule") or {}
        status = protocol.get("statusModule") or {}
        phases = design.get("phases") or []
        if design.get("studyType") != "INTERVENTIONAL" or status.get("overallStatus") not in ACTIVE_STATUSES:
            continue
        if not any(phase in {"PHASE1_PHASE2", "PHASE2", "PHASE2_PHASE3", "PHASE3"} for phase in phases):
            continue
        for intervention in (protocol.get("armsInterventionsModule") or {}).get("interventions") or []:
            if intervention.get("type") not in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}:
                continue
            canonical = _canonical_intervention(intervention.get("name"))
            if not canonical or canonical["name"] in approved:
                continue
            trial = _compact_trial(study, canonical["name"])
            group = groups.setdefault(canonical["name"], {**canonical, "trials": []})
            if all(item.get("nct_id") != trial.get("nct_id") for item in group["trials"]):
                group["trials"].append(trial)
    items = []
    status_rank = {"RECRUITING": 4, "ACTIVE_NOT_RECRUITING": 3, "NOT_YET_RECRUITING": 2, "ENROLLING_BY_INVITATION": 1}
    for item in groups.values():
        trials = sorted(item["trials"], key=lambda trial: (-trial["phase_rank"], -status_rank.get(trial["status"], 0), trial.get("last_update", "")), reverse=False)
        item["trials"] = trials[:5]
        item["highest_phase_rank"] = max((trial["phase_rank"] for trial in trials), default=0)
        item["highest_phase_label"] = _phase_label([phase for trial in trials for phase in trial["phases"]])
        item["study_count"] = len(trials)
        item["sponsors"] = [name for name, _ in Counter(trial.get("sponsor") or item["sponsor_hint"] for trial in trials).most_common(3) if name]
        item["status_summary"] = " / ".join(f"{label} {count}" for label, count in Counter(trial["status_label"] for trial in trials).most_common())
        item["latest_update"] = max((trial.get("last_update") for trial in trials), default="")
        item["stage_number"] = 3 if item["highest_phase_rank"] >= 3 else 2 if item["highest_phase_rank"] >= 2 else 1
        item["indication"] = trials[0]["indication"] if trials else "Myasthenia Gravis"
        item["population"] = trials[0]["population"] if trials else "未标注"
        item["key_trial"] = trials[0] if trials else {}
        items.append(item)
    order = {"FcRn": 1, "补体": 2, "B细胞": 3, "BAFF/APRIL": 4, "细胞治疗": 5, "神经肌接头": 6, "免疫调节": 7, "免疫耐受": 8, "待补充": 99}
    counts = Counter(item["target_type"] for item in items)
    for item in items:
        item["target_group_count"] = counts[item["target_type"]]
    items.sort(key=lambda item: (order.get(item["target_type"], 90), -item["highest_phase_rank"], item["name"]))
    meta.update({"active_statuses": [STATUS_LABELS[item] for item in sorted(ACTIVE_STATUSES)], "phase_rule": "ClinicalTrials.gov MG interventional Phase I/II+ active pipeline; registry evidence is not Oxford graded.", "item_count": len(items)})
    return {"meta": meta, "items": items}


# ── ChinaDrugTrials adapter ──────────────────────────────────────────

CDT_FIELD_ALIASES = {
    "registry_id": ("registry_id", "registration_number", "ctr_number"),
    "title": ("title", "drug_name", "study_title"),
    "drug_name": ("drug_name", "drug", "intervention_name"),
    "indication": ("indication", "disease", "target_disease"),
    "status": ("status", "recruitment_status", "study_status"),
    "phase": ("phase", "study_phase"),
    "sponsor": ("sponsor", "applicant", "company"),
    "registered_date": ("registered_date", "registration_date", "first_public_date"),
    "official_url": ("official_url", "url", "source_url"),
}


def normalize_china_drug_trials_record(source: dict[str, Any]) -> dict[str, Any]:
    """Normalize a ChinaDrugTrials record. Never fabricate fields."""
    values = {key: _first(source, aliases) for key, aliases in CDT_FIELD_ALIASES.items()}
    title = str(values["title"]).strip() or str(values["drug_name"]).strip()
    return {
        "registry": "ChinaDrugTrials",
        "registry_id": str(values["registry_id"]).strip(),
        "title": title,
        "drug_name": str(values["drug_name"]).strip(),
        "indication": str(values["indication"]).strip() or "Unknown",
        "status": str(values["status"]).strip() or "Unknown",
        "phase": str(values["phase"]).strip() or "Unknown",
        "sponsor": str(values["sponsor"]).strip(),
        "registered_date": str(values["registered_date"]).strip(),
        "official_url": str(values["official_url"]).strip(),
    }


def load_china_drug_trials_cache(path: Path) -> dict[str, Any]:
    """Load ChinaDrugTrials cache; return empty schema if unavailable."""
    if not path.exists():
        return {
            "schema_version": "1.0",
            "source": "ChinaDrugTrials.org.cn",
            "source_url": "https://www.chinadrugtrials.org.cn/",
            "mode": "unavailable",
            "records": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("records", [])
        payload.setdefault("mode", "cache")
        payload.setdefault("source", "ChinaDrugTrials.org.cn")
        return payload
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": "1.0",
            "source": "ChinaDrugTrials.org.cn",
            "source_url": "https://www.chinadrugtrials.org.cn/",
            "mode": "unavailable",
            "records": [],
        }


def refresh_china_drug_trials_cache(cache_path: Path, *, input_path: Path | None = None) -> dict[str, Any]:
    """Refresh from official export; preserve last-good cache on failure."""
    try:
        if input_path is None:
            cached = load_china_drug_trials_cache(cache_path)
            cached["mode"] = "cache"
            return cached
        raw_records = _load_manual(input_path)[0]
        by_id: dict[str, dict[str, Any]] = {}
        for raw in raw_records:
            record = normalize_china_drug_trials_record(raw)
            if not record["registry_id"] or not record["title"]:
                continue
            by_id[record["registry_id"]] = record
        if not by_id:
            raise ValueError("No valid ChinaDrugTrials records found")
        payload = {
            "schema_version": "1.0",
            "source": "ChinaDrugTrials.org.cn",
            "source_url": "https://www.chinadrugtrials.org.cn/",
            "mode": "manual",
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "records": sorted(by_id.values(), key=lambda item: item["registry_id"]),
        }
        atomic_write_json(cache_path, payload)
        return payload
    except Exception as exc:
        fallback = load_china_drug_trials_cache(cache_path)
        returned = dict(fallback)
        returned["mode"] = "cache"
        returned["warning"] = str(exc)
        return returned
