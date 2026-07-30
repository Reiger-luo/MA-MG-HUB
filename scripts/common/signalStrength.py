"""文献级信号强度规则。"""

from __future__ import annotations


EFGAR_TERMS = ("efgar", "vyvgart", "argx-113", "argx113", "艾加莫德")


def articleText(article):
    """拼接用于产品关键词识别的文献文本。"""
    parts = [
        article.get("title", ""),
        article.get("abstract", ""),
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]
    return " ".join(str(part) for part in parts).lower()


def isEfgarRelated(article):
    """识别 efgartigimod、商品名、研发代号和中文名。"""
    text = articleText(article)
    return any(term in text for term in EFGAR_TERMS)


def classifySignalStrength(article):
    """按强信号优先、efgar 中信号兜底的顺序返回文献级标签。"""
    evidenceLevel = str(article.get("evidence_level") or "")

    try:
        impactFactor = float(article.get("journal_if") or 0)
    except (TypeError, ValueError):
        impactFactor = 0.0

    if evidenceLevel in {"I", "II"} or (impactFactor >= 10 and evidenceLevel != "V"):
        return "强"
    if isEfgarRelated(article):
        return "中"
    if impactFactor >= 5 or evidenceLevel in {"III", "IV"} or article.get("china_related"):
        return "中"
    return "弱"
