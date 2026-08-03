#!/usr/bin/env python3
"""
enrich-weekly-literature.py — 只富集每周新增 PubMed 文献。

边界：
  - 只处理 data/literature-weekly.json
  - 不读取、不写入 literature-full.json
  - 先补 study_types / evidence_level；无证据等级的新文献不进入后续周更
  - 有证据等级的文献再补 IF/新锐分区；只使用 assets/journal_metrics.json 已有缓存，不在周更流程里爬站
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from common.io import atomic_write_json
from common.guideline_consensus import isGuidelineConsensus, updateGuidelineCache
from common.mg_relevance import assess_mg_core
from studyClassifier import classifyEvidence


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
WEEKLY_PATH = DATA_DIR / "literature-weekly.json"
JOURNAL_METRICS_PATH = ASSETS_DIR / "journal_metrics.json"
GUIDELINE_CACHE_PATH = DATA_DIR / "guideline-consensus-cache.json"

MIN_ABSTRACT_CHARS = 80

CHINA_KEYWORDS = [
    "china",
    "chinese",
    "hong kong",
    "macau",
    "taiwan",
    "beijing",
    "shanghai",
    "guangzhou",
    "shenzhen",
    "chengdu",
    "wuhan",
    "xian",
    "xi'an",
    "hangzhou",
    "nanjing",
    "tianjin",
    "chongqing",
    "fudan",
    "peking union",
    "sun yat-sen",
    "zhejiang university",
    "sichuan university",
]


def loadJson(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def saveJson(path: Path, payload):
    atomic_write_json(path, payload)


def normalizeJournal(value: str | None):
    value = value or ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def loadJournalMetrics():
    cache = loadJson(JOURNAL_METRICS_PATH, {})
    normalized = {}
    for journal, metrics in cache.items():
        normalized[normalizeJournal(journal)] = metrics
    return cache, normalized


def getJournalMetrics(article, cache, normalized):
    journal = article.get("journal") or ""
    metrics = cache.get(journal)
    if not metrics:
        metrics = normalized.get(normalizeJournal(journal))
    if not metrics:
        return None
    if metrics.get("IF") in (None, "", 0, 0.0):
        return None
    return metrics


def hasAssessableAbstract(article):
    abstract = (article.get("abstract") or "").strip()
    return len(abstract) >= MIN_ABSTRACT_CHARS


def classifyStudy(article):
    """按统一分类器判定研究类型；摘要不足时仍允许安全的标题/PubType 兜底。"""
    return classifyEvidence(article)


def inferChinaRelated(article):
    affiliations = article.get("affiliations") or []
    text = " ".join(affiliations).lower()
    return any(keyword in text for keyword in CHINA_KEYWORDS)


def classifyArticle(article):
    classificationFilled = False

    if article.get("china_related") is None:
        article["china_related"] = inferChinaRelated(article)

    hasStudyTypes = bool(article.get("study_types"))
    hasEvidenceLevel = bool(article.get("evidence_level"))
    needsReclassify = article.get("evidence_level") in {"II", "III", "IV", "V", "VI"}
    if needsReclassify or (not hasStudyTypes and not hasEvidenceLevel):
        studyTypes, evidenceLevel = classifyStudy(article)
        article["study_types"] = studyTypes
        article["evidence_level"] = evidenceLevel
        classificationFilled = bool(studyTypes) or needsReclassify

    return classificationFilled


def enrichMetrics(article, cache, normalized):
    metricsFilled = False
    metrics = getJournalMetrics(article, cache, normalized)
    if metrics:
        if article.get("journal_if") is None:
            article["journal_if"] = metrics.get("IF")
            metricsFilled = True
        if article.get("journal_quartile") is None:
            article["journal_quartile"] = metrics.get("quartile") or metrics.get("CAS")
            metricsFilled = True
    return metricsFilled


def processArticles(articles, cache, normalized, guidelineCachePath=GUIDELINE_CACHE_PATH):
    """先执行 MG-core，再分类并应用 I–V 门控，同时路由指南/共识。"""
    kept = []
    guidelines = []
    counters = {
        "assessable": 0,
        "classified": 0,
        "metrics_filled": 0,
        "dropped_not_mg_core": 0,
        "dropped_no_evidence": 0,
        "routed_guideline_consensus": 0,
    }
    reason_codes = {}
    for source in articles:
        article = dict(source)
        assessment = assess_mg_core(article)
        article["mg_core"] = assessment.is_core
        article["mg_core_reason"] = assessment.reason_code
        reason_codes[assessment.reason_code] = reason_codes.get(assessment.reason_code, 0) + 1
        if not assessment.is_core:
            counters["dropped_not_mg_core"] += 1
            continue
        if hasAssessableAbstract(article):
            counters["assessable"] += 1
        counters["classified"] += int(classifyArticle(article))
        if isGuidelineConsensus(article):
            guidelines.append(article)
            counters["routed_guideline_consensus"] += 1
            continue
        if article.get("evidence_level") not in {"I", "II", "III", "IV", "V"}:
            counters["dropped_no_evidence"] += 1
            continue
        counters["metrics_filled"] += int(enrichMetrics(article, cache, normalized))
        kept.append(article)
    updateGuidelineCache(guidelineCachePath, guidelines)
    counters["mg_core_reason_codes"] = reason_codes
    return {"kept": kept, "guidelines": guidelines, "counters": counters}


def main():
    if not WEEKLY_PATH.exists():
        raise SystemExit(f"缺少 {WEEKLY_PATH}")

    articles = loadJson(WEEKLY_PATH, [])
    cache, normalized = loadJournalMetrics()
    result = processArticles(articles, cache, normalized)
    counters = result["counters"]
    saveJson(WEEKLY_PATH, result["kept"])
    print(f"✅ weekly 文献富集完成: {len(result['kept'])} / {len(articles)} 篇进入后续周更")
    print(f"   MG-core 排除: {counters['dropped_not_mg_core']} {counters['mg_core_reason_codes']}")
    print(f"   有可判断摘要: {counters['assessable']}")
    print(f"   补充研究类型/证据等级: {counters['classified']}")
    print(f"   指南/共识独立路由: {counters['routed_guideline_consensus']}")
    print(f"   无 I–V 证据等级剔除: {counters['dropped_no_evidence']}")
    print(f"   补充 IF/新锐分区: {counters['metrics_filled']}")


if __name__ == "__main__":
    main()
