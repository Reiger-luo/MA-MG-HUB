"""MG 指南/共识识别与可复现缓存。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import atomic_write_json, load_json
from .mg_relevance import assess_mg_core


def isGuidelineConsensus(article: dict[str, Any]) -> bool:
    """识别真正的指南/共识，避免把正文中提到 guideline 的论文误路由。"""
    labels = " ".join(article.get("study_types") or []).lower()
    if not any(term in labels for term in ("guideline", "consensus", "practice guidance")):
        return False

    publication_types = {
        str(item).strip().lower()
        for item in article.get("pub_types") or []
    }
    if publication_types.intersection({
        "guideline",
        "practice guideline",
        "consensus statement",
    }):
        return True

    title = str(article.get("title") or "").lower()
    if re.search(r"\bconsensus\b", title):
        return True
    if re.search(r"\bguidance\b", title) and any(
        marker in title
        for marker in ("management", "treatment", "diagnosis", "clinical", "practice")
    ):
        return True
    if re.search(r"\bguidelines?\b", title) and any(
        marker in title
        for marker in (
            "clinical",
            "practice",
            "management",
            "treatment",
            "diagnosis",
            "association",
            "international",
            "efns",
            "use of",
        )
    ):
        return True
    return False


def updateGuidelineCache(
    path: Path,
    records: list[dict[str, Any]],
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """按 PMID 幂等更新 MG-core 指南/共识缓存，并使用稳定顺序写入。"""
    existing = load_json(path) if path.exists() else {}
    candidates = ([] if replace else list(existing.get("records") or [])) + list(records)
    byPmid = {
        str(item.get("pmid")): item
        for item in candidates
        if (
            item.get("pmid")
            and isGuidelineConsensus(item)
            and assess_mg_core(item).is_core
        )
    }
    ordered = sorted(
        byPmid.values(),
        key=lambda item: (
            item.get("entry_date") or item.get("pub_date") or "",
            str(item.get("pmid") or ""),
        ),
        reverse=True,
    )[:500]
    payload = {
        "schema_version": "1.0",
        "source": "MG-core PubMed guideline/consensus records outside evidence literature",
        "records": ordered,
    }
    atomic_write_json(path, payload)
    return payload
