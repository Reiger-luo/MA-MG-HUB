"""可复用的 MG-core 相关性判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


EXPLICIT_MG = re.compile(
    r"\b(myasthenia\s+gravis|generalized\s+myasthenia|generalised\s+myasthenia|"
    r"ocular\s+myasthenia|myasthenic\s+crisis|immune[- ]checkpoint[- ]inhibitor[- ]associated\s+myasthenia|myasthenia)\b",
    re.I,
)
MG_ABBREVIATION = re.compile(r"\b(?:gMG|MG)\b")
SECONDARY_DISEASE_TITLE = re.compile(
    r"(?:\b(gastrointestinal|gastric|colorectal|pancreatic|hepatocellular|lung|breast)\b.*\b(cancer|carcinoma|malignan|neoplasm)|"
    r"\b(chronic inflammatory demyelinating polyneuropathy|cidp|multiple sclerosis|stiff[- ]person syndrome|lambert[- ]eaton)\b)",
    re.I,
)


@dataclass(frozen=True)
class MgCoreAssessment:
    is_core: bool
    reason_code: str
    mention_count: int


def _metadata_terms(article: dict[str, Any]) -> list[str]:
    values = []
    for key in ("mesh_terms", "mesh", "keywords", "keyword_list"):
        raw = article.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        for item in raw:
            if isinstance(item, dict):
                item = item.get("term") or item.get("name") or item.get("descriptor") or ""
            values.append(str(item))
    return values


def assess_mg_core(article: dict[str, Any]) -> MgCoreAssessment:
    """识别研究主体，排除比较项、背景句和非 MG 疾病题名。"""
    title = str(article.get("title") or "")
    abstract = str(article.get("abstract") or "")
    title_explicit = bool(EXPLICIT_MG.search(title) or MG_ABBREVIATION.search(title))
    if title_explicit:
        return MgCoreAssessment(True, "explicit_mg_title", 1)
    if SECONDARY_DISEASE_TITLE.search(title):
        return MgCoreAssessment(False, "secondary_non_mg_disease_title", 0)

    metadata = _metadata_terms(article)
    if any(EXPLICIT_MG.fullmatch(term.strip()) for term in metadata):
        return MgCoreAssessment(True, "reliable_mg_metadata", 1)

    combined = f"{title}\n{abstract}"
    mentions = len(EXPLICIT_MG.findall(combined)) + len(MG_ABBREVIATION.findall(combined))
    if mentions >= 2:
        return MgCoreAssessment(True, "repeated_mg_core_mentions", mentions)
    if mentions == 1:
        return MgCoreAssessment(False, "single_background_mention", mentions)
    return MgCoreAssessment(False, "no_mg_core_evidence", 0)


def filter_mg_core(articles: list[dict[str, Any]]):
    kept = []
    excluded = []
    counters: dict[str, int] = {}
    for article in articles:
        assessment = assess_mg_core(article)
        counters[assessment.reason_code] = counters.get(assessment.reason_code, 0) + 1
        enriched = dict(article)
        enriched["mg_core"] = assessment.is_core
        enriched["mg_core_reason"] = assessment.reason_code
        (kept if assessment.is_core else excluded).append(enriched)
    return kept, excluded, counters
