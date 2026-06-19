#!/usr/bin/env python3
"""
studyClassifier.py — MG 文献研究类型与证据等级统一分类器。

原则：
  1. 先识别真实研究设计，再映射证据等级。
  2. RCT 需要本研究存在随机分组/随机分配，不能只因摘要提到既往 RCT 或 subgroup analysis 升级。
  3. 横断面、问卷、DCE、单臂真实世界、无外部对照的回顾性研究统一按 IV 级处理。
"""

from __future__ import annotations

import re


levelMap = {
    "ITC": "I",
    "Systematic Review": "I",
    "RCT": "II",
    "Non-randomized controlled cohort": "III",
    "Adjusted Retrospective Cohort": "III",
    "Historical Control": "IV",
    "Case-Control": "IV",
    "Cross-Sectional": "IV",
    "Single Arm": "IV",
    "Case Report": "V",
    "Review": "VI",
    "Protocol": None,
    "HEOR": None,
    "Guideline/Consensus": None,
    "Practice Guideline": None,
    "Consensus Statement": None,
    "Animal Study": None,
    "In Vitro": None,
    "Comment": None,
    "Letter": None,
    "Editorial": None,
    "Unclassified": None,
    "Historical Article": None,
    "Biography": None,
    "News": None,
    "Lecture": None,
    "Patient Education": None,
    "Technical Report": None,
    "Conference Abstract": None,
    "Introductory Editorial": None,
    "Government Document": None,
    "Personal Narrative": None,
    "Fictional Work": None,
    "Webcast": None,
    "Portrait": None,
    "Legal Case": None,
}

protocolTerms = [
    "study protocol",
    "study protocols",
    "trial protocol",
    "trial protocols",
    "protocol for",
]

animalTerms = [
    "animal model",
    "eamg",
    "murine model",
    "rat model",
    "mouse model",
    "experimental autoimmune myasthenia",
    "rodent",
]

caseTerms = ["case report", "case reports", "case series"]
guidelineTerms = ["consensus", "guideline", "delphi"]
retractionTerms = [
    "retraction:",
    "retraction of:",
    "retraction note",
    "retracted article",
]

retroAdjustTerms = [
    "propensity score",
    "propensity-score",
    "inverse probability",
    "inverse-probability",
    "iptw",
    "psm",
    "doubly robust",
    "target trial emulation",
    "overlap weight",
    "g computation",
    "g-computation",
    "instrumental variable",
]

crossSectionalTerms = [
    "cross-sectional",
    "cross sectional",
    "cross-sectional survey",
    "cross sectional survey",
    "survey",
    "questionnaire",
    "discrete choice experiment",
    "willingness-to-pay",
    "willingness to pay",
]

observationalTerms = [
    "observational study",
    "real-world",
    "real world",
    "registry",
    "registry study",
    "cohort study",
    "prospective cohort",
    "retrospective cohort",
    "population-based study",
    "population based study",
    "nationwide cohort",
    "nationwide study",
    "post-marketing surveillance",
    "postmarketing surveillance",
    "pilot study",
    "pilot trial",
]

singleArmTerms = [
    "single-arm",
    "single arm",
    "single group",
    "single-center retrospective",
    "single-centre retrospective",
    "single center retrospective",
    "single centre retrospective",
    "extension study",
    "open-label extension",
]

rctContextTerms = [
    "trial",
    "open-label",
    "open label",
    "double-blind",
    "double blind",
    "placebo-controlled",
    "placebo controlled",
    "controlled trial",
    "comparative",
]

priorTrialContextTerms = [
    "prior",
    "previous",
    "previously",
    "published",
    "earlier",
    "complement",
    "complements",
    "complemented",
    "background",
]


def compactText(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def word(term: str, text: str) -> bool:
    """用非字母数字边界匹配短语，避免 control 命中 disease control 后被误升格。"""
    term = term.strip().lower()
    if not term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text, re.I))


def hasAny(text: str, terms: list[str]) -> bool:
    return any(word(term, text) for term in terms)


def hasPattern(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.I))


def isRetraction(text: str) -> bool:
    return hasAny(text, retractionTerms) or hasPattern(text, r"^retraction\b")


def isItc(text: str) -> bool:
    return hasAny(text, [
        "indirect comparison",
        "indirect treatment comparison",
        "matching-adjusted indirect comparison",
        "adjusted indirect comparison",
        "network meta-analysis",
        "network meta analysis",
        "maic",
        "itc",
        "nma",
    ])


def isHeor(text: str) -> bool:
    return hasAny(text, [
        "economic evaluation",
        "cost-effectiveness",
        "cost-utility",
        "cost effectiveness",
        "cost utility",
        "budget impact",
        "cost consequence",
        "cost minimization",
        "cost-benefit",
        "cost benefit",
        "cost analysis",
        "markov model",
        "health technology assessment",
        "quality-adjusted life year",
        "quality adjusted life year",
        "qaly",
        "icer",
    ])


def isInVitro(text: str) -> bool:
    return (
        hasAny(text, ["in vitro", "cultured"])
        or hasPattern(text, r"\bcell (line|lines|culture|cultures)\b")
    )


def isRetrospective(text: str, pubTypeText: str = "") -> bool:
    return hasPattern(text, r"\bretrospectiv") or "RETROSPECTIVE" in pubTypeText


def isCrossSectional(text: str) -> bool:
    return hasAny(text, crossSectionalTerms)


def isSingleArmExplicit(text: str) -> bool:
    return hasAny(text, singleArmTerms)


def hasAdjustment(text: str) -> bool:
    return hasAny(text, retroAdjustTerms)


def hasTrueComparator(text: str) -> bool:
    """识别真实外部对照，排除 disease/symptom control 这类疗效状态描述。"""
    comparatorPatterns = [
        r"\b(control|comparison|comparator|placebo|reference|standard[- ]of[- ]care|usual[- ]care|routine[- ]care|sham)\s+(group|arm|cohort)\b",
        r"\b(group|arm|cohort)\s+(treated with|receiving)\s+placebo\b",
        r"\b(active comparator|matched control|historical control|external control)\b",
        r"\b(prospective|retrospective)?\s*comparative\s+(cohort\s+)?study\b",
        r"\bcase-control\b",
        r"\bnested case\b",
    ]
    return any(hasPattern(text, pattern) for pattern in comparatorPatterns)


def hasRctComparator(text: str) -> bool:
    """RCT 场景允许 versus/comparative，因为随机化语境已经提供强约束。"""
    return (
        hasTrueComparator(text)
        or hasAny(text, [
            "versus",
            "vs",
            "placebo",
            "placebo-controlled",
            "placebo controlled",
            "double-blind",
            "double blind",
            "comparative",
            "control group",
            "control arm",
        ])
    )


def hasOwnRandomization(text: str) -> bool:
    for match in re.finditer(r"\b(randomi[sz]ed|randomly assigned|randomly allocated|random allocation)\b", text, re.I):
        window = text[max(0, match.start() - 90):match.end() + 180]
        if hasAny(window, priorTrialContextTerms) and not hasAny(window, [
            "patients were randomized",
            "participants were randomized",
            "subjects were randomized",
            "randomly assigned",
            "randomly allocated",
        ]):
            continue
        return True
    return False


def hasDerivedRctAnalysis(text: str) -> bool:
    derivedTerms = ["post-hoc", "post hoc", "secondary analysis", "subgroup analysis", "subgroup analyses"]
    trialTerms = [
        "randomized controlled trial",
        "randomised controlled trial",
        "randomized trial",
        "randomised trial",
        "placebo-controlled trial",
        "placebo controlled trial",
        "double-blind trial",
        "double blind trial",
        "phase 2 trial",
        "phase ii trial",
        "phase 3 trial",
        "phase iii trial",
    ]
    if not hasAny(text, derivedTerms) or not hasAny(text, trialTerms):
        return False
    if isRetrospective(text) and hasAny(text, priorTrialContextTerms):
        return False
    return True


def isRctAbstract(text: str, pubTypeIsRct: bool = False) -> bool:
    if pubTypeIsRct:
        return True
    if isSingleArmExplicit(text):
        return False
    if hasDerivedRctAnalysis(text):
        return True

    hasRandomization = hasOwnRandomization(text)
    if hasRandomization and hasRctComparator(text) and hasAny(text, rctContextTerms):
        return True

    phasePattern = r"\bphase\s*(2|3|ii|iii|2/3|ii/iii|3/4|iii/iv)\b"
    if hasPattern(text, phasePattern) and hasRctComparator(text):
        return True
    return False


def isCohortUpgrade(text: str) -> bool:
    if isCrossSectional(text) or isSingleArmExplicit(text):
        return False
    if hasTrueComparator(text) and hasAny(text, ["prospective", "parallel", "cohort", "comparative study"]):
        return True
    if hasPattern(text, r"\bnon[- ]randomi[sz]ed\s+controlled\b"):
        return True
    return False


def isObservational(text: str) -> bool:
    return hasAny(text, observationalTerms) or isCrossSectional(text) or isSingleArmExplicit(text)


def pubTypeLastResort(pubTypeText: str) -> str:
    namedPubTypes = {
        "COMMENT": "Comment",
        "LETTER": "Letter",
        "EDITORIAL": "Editorial",
        "HISTORICAL ARTICLE": "Historical Article",
        "BIOGRAPHY": "Biography",
        "NEWS": "News",
        "LECTURE": "Lecture",
        "PATIENT EDUCATION HANDOUT": "Patient Education",
        "TECHNICAL REPORT": "Technical Report",
        "GOVERNMENT PUBLICATION": "Government Document",
        "LEGAL CASE": "Legal Case",
        "CONGRESS": "Conference Abstract",
        "CONFERENCE PROCEEDING": "Conference Abstract",
        "INTRODUCTORY JOURNAL ARTICLE": "Introductory Editorial",
        "FICTIONAL WORK": "Fictional Work",
        "WEBCAST": "Webcast",
        "PERSONAL NARRATIVE": "Personal Narrative",
        "PORTRAIT": "Portrait",
        "PRACTICE GUIDELINE": "Practice Guideline",
        "CONSENSUS DEVELOPMENT CONFERENCE": "Consensus Statement",
        "GUIDELINE": "Practice Guideline",
    }
    if "REVIEW" in pubTypeText and "SYSTEMATIC" not in pubTypeText:
        return "Review"
    if "CASE REPORTS" in pubTypeText:
        return "Case Report"
    if "COMPARATIVE STUDY" in pubTypeText:
        return "Historical Control"
    if "RETROSPECTIVE" in pubTypeText:
        return "Single Arm"
    for tag, label in namedPubTypes.items():
        if tag in pubTypeText:
            return label
    return "Unclassified"


def classifyStudyType(pubTypes, abstract: str | None = "", title: str | None = "") -> str:
    if isinstance(pubTypes, (list, tuple)):
        pubTypeRaw = "; ".join(str(item) for item in pubTypes)
    else:
        pubTypeRaw = str(pubTypes or "")

    pubTypeText = pubTypeRaw.upper()
    abstractText = compactText(abstract)
    titleText = compactText(title)
    text = compactText(f"{titleText} {abstractText}")
    hasAbstract = bool(abstractText)

    if isRetraction(text):
        return "Comment"

    # PubType 明确且不依赖摘要时先处理。
    if "META-ANALYSIS" in pubTypeText:
        return "ITC"
    if "SYSTEMATIC REVIEW" in pubTypeText:
        return "Systematic Review"
    if "CLINICAL TRIAL PROTOCOL" in pubTypeText:
        return "Protocol"
    if "REVIEW" in pubTypeText and "SYSTEMATIC" not in pubTypeText:
        if hasAbstract and (word("meta-analysis", text) or isItc(text)):
            return "ITC"
        if hasAbstract and word("systematic review", text):
            return "Systematic Review"
        return "Review"
    if "LETTER" in pubTypeText:
        return "Letter"
    if "EDITORIAL" in pubTypeText:
        return "Editorial"
    if "COMMENT" in pubTypeText:
        return "Comment"

    if hasAny(text, protocolTerms):
        return "Protocol"
    if hasAny(text, animalTerms):
        return "Animal Study"
    if word("meta-analysis", text) or isItc(text):
        return "ITC"
    if word("systematic review", text):
        return "Systematic Review"

    if "RANDOMIZED CONTROLLED TRIAL" in pubTypeText:
        return "RCT"
    if isRctAbstract(text, pubTypeIsRct=False):
        return "RCT"

    if "CASE REPORTS" in pubTypeText:
        if isCohortUpgrade(text) or (isRetrospective(text, pubTypeText) and hasAdjustment(text)):
            return "Non-randomized controlled cohort"
        if word("case-control", text) or word("nested case", text):
            return "Case-Control"
        if isRetrospective(text, pubTypeText):
            return "Historical Control" if hasTrueComparator(text) else "Single Arm"
        return "Case Report"

    if isRetrospective(text, pubTypeText) and hasAdjustment(text):
        return "Adjusted Retrospective Cohort"
    if word("case-control", text) or word("nested case", text) or "CASE-CONTROL" in pubTypeText or "CASE CONTROL" in pubTypeText:
        return "Case-Control"
    if isCrossSectional(text):
        return "Cross-Sectional"
    if isCohortUpgrade(text):
        return "Non-randomized controlled cohort"
    if isRetrospective(text, pubTypeText):
        return "Historical Control" if hasTrueComparator(text) else "Single Arm"
    if isSingleArmExplicit(text):
        return "Single Arm"
    if isObservational(text):
        return "Non-randomized controlled cohort" if isCohortUpgrade(text) else "Single Arm"
    if hasAny(text, caseTerms):
        return "Case Report"
    if isHeor(text):
        return "HEOR"
    if hasAny(text, guidelineTerms):
        return "Guideline/Consensus"
    if word("narrative review", text) or word("review", text):
        return "Review"
    if isInVitro(text):
        return "In Vitro"

    if not hasAbstract and titleText:
        if word("randomized", titleText) or word("randomised", titleText):
            return "RCT"
        if isCrossSectional(titleText):
            return "Cross-Sectional"
        if isRetrospective(titleText, pubTypeText):
            return "Historical Control" if hasTrueComparator(titleText) else "Single Arm"
        if hasAny(titleText, caseTerms):
            return "Case Report"

    return pubTypeLastResort(pubTypeText)


def evidenceLevelForType(studyType: str | None) -> str | None:
    return levelMap.get(studyType or "")


def classifyEvidence(article: dict) -> tuple[list[str], str | None]:
    studyType = classifyStudyType(
        article.get("pub_types") or [],
        article.get("abstract") or "",
        article.get("title") or "",
    )
    return ([studyType] if studyType else []), evidenceLevelForType(studyType)
