"""MG 指南/共识识别与可复现缓存。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import atomic_write_json, load_json
from .mg_relevance import assess_mg_core


# 标题本身即为指导性文件的措辞。PubMed 常把专家共识标成 Journal Article，
# 且 study_types 可能被误标（如 Single Arm），因此先看标题强信号。
_TITLE_GUIDANCE_RE = re.compile(
    r"\b(?:practical|practice|clinical|consensus)\s+guidance\b"
    r"|\b(?:expert opinion paper|expert opinion|expert consensus|expert statement)\b"
    r"|\b(?:position paper|position statement|consensus statement)\b",
    re.I,
)


def isGuidelineConsensus(article: dict[str, Any]) -> bool:
    """识别真正的指南/共识，避免把正文中提到 guideline 的论文误路由。"""
    title = str(article.get("title") or "").lower()
    # 强信号：题名即指导性文件，例如 "Practical Guidance ... Expert Opinion Paper"。
    if _TITLE_GUIDANCE_RE.search(title):
        return True

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


def syncGuidelineCacheFromLiterature(
    path: Path,
    articles: list[dict[str, Any]],
    *,
    replace: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    """周更 link：从公开文献流全量重扫指南/共识，幂等合并到权威缓存。

    只看已发布的公开文献层，不依赖当周抓取窗口，因此过去入库、当周不再出现的
    指南不会被漏掉；本函数只更新缓存，不改写指南差异 Top10 的语料或结论。
    """
    candidates = [
        item for item in articles or []
        if item.get("pmid") and isGuidelineConsensus(item) and assess_mg_core(item).is_core
    ]
    payload = updateGuidelineCache(path, candidates, replace=replace)
    counters = {
        "scanned": len(articles or []),
        "matched": len(candidates),
        "cache_total": len(payload.get("records") or []),
    }
    return payload, counters
