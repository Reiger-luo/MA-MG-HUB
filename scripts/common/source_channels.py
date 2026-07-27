"""独立来源信号频道构建器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import load_js_global
from .mg_relevance import assess_mg_core


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _js(path: Path, name: str, default: Any) -> Any:
    try:
        return load_js_global(path, name) if path.exists() else default
    except (OSError, ValueError):
        return default


def _safe_http_url(value: Any) -> str:
    value = str(value or "").strip()
    return value if value.startswith(("https://", "http://")) else ""


def _literature_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for signal in (payload or {}).get("signals") or []:
        article = signal.get("article") or {}
        if article.get("evidence_level") not in {"I", "II", "III", "IV", "V"}:
            continue
        items.append({
            "id": str(signal.get("id") or article.get("pmid") or ""),
            "title": signal.get("title") or signal.get("headline") or article.get("title") or "",
            "date": article.get("entry_date") or article.get("pub_date") or "",
            "status": signal.get("strength") or article.get("evidence_level") or "",
            "source": "PubMed",
            "url": _safe_http_url(article.get("url")),
            "evidence_level": article.get("evidence_level"),
        })
    return items


def _guideline_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": str(item.get("pmid") or ""),
        "title": item.get("title") or "",
        "date": item.get("entry_date") or item.get("pub_date") or "",
        "status": ", ".join(item.get("study_types") or []),
        "source": "PubMed · guideline/consensus cache",
        "url": _safe_http_url(item.get("url")) or (
            f"https://pubmed.ncbi.nlm.nih.gov/{item.get('pmid')}/" if item.get("pmid") else ""
        ),
    } for item in payload.get("records") or []]


def _regulatory_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": str(item.get("name") or ""),
        "title": item.get("name") or "",
        "date": item.get("last_verified") or item.get("status_date") or "",
        "status": item.get("status_label") or item.get("china_status") or "",
        "source": item.get("source_type") or payload.get("source_note") or "China regulatory",
        "url": _safe_http_url(item.get("source_url")),
    } for item in payload.get("drugs") or []]


def _ct_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for study in payload.get("studies") or []:
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
        relevance = assess_mg_core({
            "title": ident.get("briefTitle") or ident.get("officialTitle") or "",
            "keywords": conditions,
        })
        if not relevance.is_core:
            continue
        nct_id = ident.get("nctId") or ""
        # Extract drug name from interventions
        interventions = (protocol.get("armsInterventionsModule") or {}).get("interventions") or []
        drug_names = [
            iv.get("name", "").strip()
            for iv in interventions
            if iv.get("type") in {"DRUG", "BIOLOGICAL"} and iv.get("name")
        ]
        items.append({
            "id": nct_id,
            "registry": "ClinicalTrials.gov",
            "registry_id": nct_id,
            "secondary_ids": ident.get("orgStudyIdInfo", {}).get("id", "") and [ident["orgStudyIdInfo"]["id"]] or [],
            "title": ident.get("briefTitle") or ident.get("officialTitle") or "",
            "drug_name": drug_names[0] if drug_names else "",
            "date": status.get("lastUpdateSubmitDate") or "",
            "status": status.get("overallStatus") or "",
            "source": "ClinicalTrials.gov",
            "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        })
    return items


def _chictr_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": item.get("registry_id") or "",
        "registry": "ChiCTR",
        "registry_id": item.get("registry_id") or "",
        "secondary_ids": item.get("secondary_ids") or [],
        "title": item.get("title") or item.get("public_title") or "",
        "drug_name": _extract_chictr_drug(item),
        "date": item.get("date_registration") or item.get("registered_date") or "",
        "status": item.get("status") or item.get("recruitment_status") or "Unknown",
        "source": "ChiCTR",
        "url": _safe_http_url(item.get("official_url") or item.get("url")),
        "phase": item.get("phase") or "Unknown",
        "sponsor": item.get("sponsor") or item.get("primary_sponsor") or item.get("institution") or "",
    } for item in payload.get("records") or []]


def _extract_chictr_drug(item: dict[str, Any]) -> str:
    """Extract primary drug name from ChiCTR i_freetext intervention field."""
    import re as _re
    freetext = str(item.get("i_freetext") or "")
    if not freetext:
        return ""
    # Pattern: "Group name:Drug name;" — take first non-empty drug after colon
    for segment in freetext.split(";"):
        segment = segment.strip()
        if ":" in segment:
            drug = segment.split(":", 1)[1].strip()
            # Skip placeholders
            if drug and drug.lower() not in {"none", "na", "no", "n/a", "-"}:
                # Take first meaningful token(s) before dosage info
                drug = _re.split(r"\s+\d+\s*(mg|ml|μg|mcg)", drug)[0].strip()
                drug = _re.split(r"\s+(injection|infusion|capsule|tablet|solution)", drug, flags=_re.I)[0].strip()
                if len(drug) > 2:
                    return drug
    return ""


def _cdt_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": item.get("registry_id") or "",
        "registry": "ChinaDrugTrials",
        "registry_id": item.get("registry_id") or "",
        "secondary_ids": [],
        "title": item.get("title") or "",
        "drug_name": item.get("drug_name") or "",
        "date": item.get("registered_date") or "",
        "status": item.get("status") or "Unknown",
        "source": "ChinaDrugTrials",
        "url": _safe_http_url(item.get("official_url")),
        "phase": item.get("phase") or "Unknown",
        "sponsor": item.get("sponsor") or "",
    } for item in payload.get("records") or []]


def _normalize_title(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def deduplicate_trials(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅以真实交叉 ID 或高度归一化后的完整题名合并注册记录。"""
    result = []
    id_to_index: dict[str, int] = {}
    title_to_index: dict[str, int] = {}
    for item in items:
        ids = {str(item.get("registry_id") or "").lower()}
        ids.update(str(value).lower() for value in item.get("secondary_ids") or [])
        ids.discard("")
        title_key = _normalize_title(item.get("title") or "")
        match = next((id_to_index[value] for value in ids if value in id_to_index), None)
        if match is None and len(title_key) >= 40:
            match = title_to_index.get(title_key)
        if match is not None:
            existing = result[match]
            existing.setdefault("linked_registries", []).append({
                "registry": item.get("registry"), "registry_id": item.get("registry_id"), "url": item.get("url")
            })
            for value in ids:
                id_to_index[value] = match
            continue
        index = len(result)
        result.append(item)
        for value in ids:
            id_to_index[value] = index
        if len(title_key) >= 40:
            title_to_index[title_key] = index
    return result


def build_source_signals(
    *, literature_signals_path: Path, guideline_cache_path: Path, regulatory_path: Path,
    clinicaltrials_path: Path, chictr_path: Path, conference_path: Path,
) -> dict[str, Any]:
    literature = _js(literature_signals_path, "MG_SIGNALS_DATA", {})
    guidelines = _json(guideline_cache_path, {})
    regulatory = _json(regulatory_path, {})
    clinicaltrials = _json(clinicaltrials_path, {})
    chictr = _json(chictr_path, {})
    conference = _json(conference_path, {})
    conference_items = [{
        "id": str(item.get("id") or item.get("abstractId") or item.get("abstract_id") or ""),
        "title": item.get("title") or "",
        "date": item.get("date") or conference.get("generated_at") or "",
        "status": item.get("priority") or item.get("evidenceBoundary") or "摘要级",
        "source": item.get("conference") or item.get("meeting") or "Conference",
        "url": _safe_http_url(item.get("url") or item.get("sourceUrl")),
    } for item in (conference.get("abstracts") or conference.get("items") or [])][:40]
    trials = deduplicate_trials(_ct_items(clinicaltrials) + _chictr_items(chictr))
    generated_at = (
        literature.get("generated_at")
        or clinicaltrials.get("generated_at")
        or conference.get("generated_at")
        or regulatory.get("generated_at")
        or chictr.get("last_verified")
        or ""
    )
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "channels": [
            {"id": "literatureEvidence", "label": "文献证据", "evidence_required": True, "sources": ["PubMed"], "items": _literature_items(literature)},
            {"id": "guidelineConsensus", "label": "指南 / 共识", "evidence_required": False, "sources": ["PubMed cache"], "items": _guideline_items(guidelines)},
            {"id": "chinaRegulatory", "label": "中国监管", "evidence_required": False, "sources": ["NMPA", "CDE", "NHSA"], "items": _regulatory_items(regulatory)},
            {"id": "trialRegistry", "label": "试验注册", "evidence_required": False, "sources": ["ClinicalTrials.gov", "ChiCTR"], "items": trials},
            {"id": "conference", "label": "会议线索", "evidence_required": False, "sources": ["Conference primary sources"], "items": conference_items},
        ],
    }
