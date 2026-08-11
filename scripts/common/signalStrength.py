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
    """按证据设计提供强度基线；产品、地区和期刊声望不直接抬高价值。"""
    evidenceLevel = str(article.get("evidence_level") or "")
    if evidenceLevel in {"I", "II"}:
        return "强"
    if evidenceLevel in {"III", "IV"}:
        return "中"
    return "弱"
