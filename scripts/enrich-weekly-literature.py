#!/usr/bin/env python3
"""
enrich-weekly-literature.py — 只富集每周新增 PubMed 文献。

边界：
  - 只处理 data/literature-weekly.json
  - 不读取、不写入 literature-full.json
  - 先补 study_types / evidence_level；无证据等级的新文献不进入后续周更
  - 有证据等级的文献再补 IF/CAS；只使用 assets/journal_metrics.json 已有缓存，不在周更流程里爬站
"""

from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
WEEKLY_PATH = DATA_DIR / "literature-weekly.json"
JOURNAL_METRICS_PATH = ASSETS_DIR / "journal_metrics.json"

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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def articleText(article):
    parts = [
        article.get("title") or "",
        article.get("abstract") or "",
        " ".join(article.get("pub_types") or []),
    ]
    return " ".join(parts).lower()


def pubTypeText(article):
    return " ".join(article.get("pub_types") or []).lower()


def hasAssessableAbstract(article):
    abstract = (article.get("abstract") or "").strip()
    return len(abstract) >= MIN_ABSTRACT_CHARS


def matchAny(text, patterns):
    return any(re.search(pattern, text) for pattern in patterns)


def classifyStudy(article):
    """按公开字段粗分类；摘要不足时不强行给证据等级。"""
    if not hasAssessableAbstract(article):
        return [], None

    text = articleText(article)
    pubTypes = pubTypeText(article)
    combined = f"{pubTypes} {text}"

    if matchAny(combined, [r"\bmeta-analysis\b", r"\bsystematic review\b"]):
        return ["Systematic Review"], "I"
    if matchAny(combined, [
        r"\brandomi[sz]ed controlled trial\b",
        r"\brandomi[sz]ed\b",
        r"\bplacebo-controlled\b",
        r"\bdouble-blind\b",
        r"\bphase\s*(2|3|ii|iii)\b.*\btrial\b",
    ]):
        return ["RCT"], "II"
    if matchAny(combined, [
        r"\bprospective cohort\b",
        r"\bretrospective cohort\b",
        r"\bcohort study\b",
        r"\bobservational study\b",
        r"\breal-world\b",
        r"\bregistry\b",
        r"\bcross-sectional\b",
        r"\bmulticenter retrospective\b",
        r"\bcase-control\b",
    ]):
        if "case-control" in combined:
            return ["Case-Control"], "IV"
        if matchAny(combined, [
            r"\bcontrol\b", r"\bcontrols\b", r"\bcontrolled\b",
            r"\bcontrol group\b", r"\bcontrol arm\b",
            r"\bcomparison group\b", r"\bcomparison arm\b",
            r"\bcomparator\b", r"\breference group\b",
            r"\bplacebo\b", r"\bparallel\b",
            r"\bstandard of care\b", r"\bstandard treatment\b",
            r"\bstandard therapy\b", r"\busual care\b",
            r"\bsupportive care\b", r"\bbest supportive care\b"
        ]):
            return ["Non-randomized controlled cohort"], "III"
        return ["Single Arm"], "IV"
    if matchAny(combined, [r"\bsingle-arm\b", r"\bopen-label\b", r"\bextension study\b"]):
        return ["Single Arm"], "IV"
    if matchAny(combined, [r"\bcase report\b", r"\bcase reports\b", r"\bcase series\b"]):
        return ["Case Report"], "V"
    if matchAny(combined, [r"\bpractice guideline\b", r"\bguideline\b", r"\bconsensus\b"]):
        return ["Guideline/Consensus"], None
    if matchAny(combined, [r"\breview\b", r"\bnarrative review\b"]):
        return ["Review"], "VI"
    if matchAny(combined, [r"\bin vitro\b", r"\banimal study\b", r"\bmouse model\b", r"\bmice\b"]):
        return ["In Vitro"], None
    if matchAny(combined, [r"\beditorial\b", r"\bcomment\b", r"\bletter\b"]):
        return ["Comment"], None
    return ["Unclassified"], None


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
    needsReclassify = article.get("evidence_level") == "III"
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
            article["journal_quartile"] = metrics.get("CAS")
            metricsFilled = True
    return metricsFilled


def main():
    if not WEEKLY_PATH.exists():
        raise SystemExit(f"缺少 {WEEKLY_PATH}")

    articles = loadJson(WEEKLY_PATH, [])
    cache, normalized = loadJournalMetrics()
    classified = 0
    metricsFilled = 0
    assessable = 0
    kept = []
    droppedNoEvidence = 0

    for article in articles:
        if hasAssessableAbstract(article):
            assessable += 1
        didClassify = classifyArticle(article)
        classified += int(didClassify)
        if not article.get("evidence_level"):
            droppedNoEvidence += 1
            continue
        didMetrics = enrichMetrics(article, cache, normalized)
        metricsFilled += int(didMetrics)
        kept.append(article)

    saveJson(WEEKLY_PATH, kept)
    print(f"✅ weekly 文献富集完成: {len(kept)} / {len(articles)} 篇进入后续周更")
    print(f"   有可判断摘要: {assessable}")
    print(f"   补充研究类型/证据等级: {classified}")
    print(f"   无证据等级剔除: {droppedNoEvidence}")
    print(f"   补充 IF/CAS: {metricsFilled}")


if __name__ == "__main__":
    main()
