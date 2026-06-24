#!/usr/bin/env python3
"""
studyClassifier.py — MG 文献研究类型与证据等级统一分类器。

原则：
  1. 先识别真实研究设计，再映射证据等级。
  2. RCT 需要本研究存在随机分组/随机分配，不能只因摘要提到既往 RCT 或 subgroup analysis 升级。
  3. 先区分问题域：治疗/伤害、预后/预测模型、诊断/监测、机制/遗传不能混用同一条治疗证据梯子。
  4. 横断面、问卷、DCE、单臂真实世界、无外部对照的回顾性研究统一按 IV 级处理。
"""

from __future__ import annotations

import re


levelMap = {
    "ITC": "I",
    "Systematic Review": "I",
    "Systematic Review of Case Reports": "IV",
    "Systematic Review of Uncontrolled Studies": "IV",
    "RCT": "II",
    "Non-randomized controlled cohort": "III",
    "Adjusted Retrospective Cohort": "III",
    "Prognostic Inception Cohort": "II",
    "Prognostic Cohort": "III",
    "Poor-quality Prognostic Cohort": "IV",
    "Biomarker Prognostic Study": "III",
    "Prediction Model External Validation": "III",
    "Prediction Model Development": "IV",
    "Diagnostic Accuracy Study": "III",
    "Diagnostic Case-Control": "IV",
    "Scale Validation": "IV",
    "Pharmacovigilance": "IV",
    "Historical Control": "IV",
    "Case-Control": "IV",
    "Cross-Sectional": "IV",
    "Single Arm": "IV",
    "Case Report": "V",
    "Mechanistic/Genetic Association": "V",
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

prognosisTerms = [
    "prognosis",
    "prognostic",
    "risk factor",
    "risk factors",
    "predictor",
    "predictors",
    "progression",
    "generalization",
    "generalisation",
    "mortality",
    "survival",
    "complication",
    "complications",
]

treatmentEffectTerms = [
    "efficacy",
    "effectiveness",
    "safety",
    "therapeutic response",
    "treatment response",
    "clinical response",
    "clinical improvement",
    "retreatment",
    "steroid-sparing",
    "steroid sparing",
]

predictionModelTerms = [
    "prediction model",
    "predictive model",
    "prognostic model",
    "risk model",
    "immune model",
    "nomogram",
    "score model",
    "risk score",
    "online calculator",
    "machine learning model",
    "machine-learning model",
    "model development",
    "development and validation",
]

externalValidationTerms = [
    "external validation",
    "externally validated",
    "independent cohort",
    "independent validation",
]

internalValidationTerms = [
    "internal validation",
    "leave-one-out cross-validation",
    "leave one out cross validation",
    "loocv",
    "cross-validation",
    "cross validation",
    "training cohort",
    "modeling cohort",
    "modelling cohort",
    "randomly divided",
    "random split",
    "split into",
]

diagnosticTerms = [
    "diagnostic accuracy",
    "sensitivity",
    "specificity",
    "reference standard",
    "receiver operating characteristic",
    "roc curve",
    "auc",
    "monitoring test",
    "screening test",
]

scaleValidationTerms = [
    "scale validation",
    "questionnaire validation",
    "validation and clinical utility",
    "clinical utility",
]

pharmacovigilanceTerms = [
    "pharmacovigilance",
    "faers",
    "disproportionality",
    "post-marketing surveillance",
    "postmarketing surveillance",
]

mechanisticGeneticTerms = [
    "functional profiling",
    "antibody profiling",
    "genome-wide",
    "gwas",
    "genetic association",
    "polymorphism",
    "polymorphisms",
    "genomic",
    "polygenic",
    "mendelian randomization",
    "mendelian randomisation",
    "locus-level",
    "proteomic",
    "proteomics",
    "multi-omic",
    "multiomic",
    "microbiota",
    "microbiome",
    "flora",
    "metabolite",
    "metabolites",
    "cytokine",
    "pathogenesis",
    "mechanistic",
    "mechanism",
    "biomarker",
    "biomarkers",
]

biomarkerOutcomeTerms = [
    "therapeutic outcome",
    "therapeutic outcomes",
    "treatment outcome",
    "treatment outcomes",
    "treatment response",
    "clinical response",
    "clinical improvement",
    "clinical outcome",
    "clinical outcomes",
    "predictive biomarker",
    "predictive biomarkers",
    "predictive proteins",
    "response signature",
    "response signatures",
    "associated with response",
    "associate with clinical response",
    "progression-free survival",
    "progression free survival",
    "pfs",
    "unfavourable prognosis",
    "unfavorable prognosis",
    "prognosis",
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


def isSystematicReviewOfCaseEvidence(text: str) -> bool:
    if not word("systematic review", text):
        return False
    if hasPattern(text, r"\bsystematic review of\b.{0,100}\b(case reports?|case series)\b"):
        return True
    case_review_patterns = [
        r"\beligible studies included\b.{0,120}\b(case reports?|case series|single[- ]case)\b",
        r"\bincluded\b.{0,80}\b(case reports?|case series|single[- ]case)\b",
        r"\b(case reports?|case series)\b.{0,80}\bwere included\b",
    ]
    return any(hasPattern(text, pattern) for pattern in case_review_patterns)


def isSystematicReviewOfUncontrolledEvidence(text: str) -> bool:
    if not (word("systematic review", text) or word("meta-analysis", text)):
        return False
    if hasPattern(text, r"\bmeta-analysis of proportions\b"):
        return True
    uncontrolled_patterns = [
        r"\bsystematic review\b.{0,140}\b(single[- ]arm|uncontrolled|case reports?|case series)\b",
        r"\bmeta-analysis\b.{0,140}\b(single[- ]arm|uncontrolled|case reports?|case series)\b",
        r"\bincluded\b.{0,120}\b(single[- ]arm|uncontrolled|case reports?|case series)\b",
        r"\beligible studies\b.{0,120}\b(single[- ]arm|uncontrolled|case reports?|case series)\b",
    ]
    return any(hasPattern(text, pattern) for pattern in uncontrolled_patterns)


def isCaseReport(text: str, pubTypeText: str = "") -> bool:
    if "CASE REPORTS" in pubTypeText or hasAny(text, caseTerms):
        return True
    if hasPattern(text, r"\bin (a|an|one) patient with\b"):
        return True
    return bool(re.search(r"\bwe report (a|an|the)?\s*\d{0,3}[- ]?year[- ]old\b", text, re.I))


def isScaleValidation(text: str) -> bool:
    return (
        hasAny(text, scaleValidationTerms)
        or hasPattern(text, r"\b(validation|validate|validated|validating)\b.{0,90}\b(scale|questionnaire|omgrate|mg-qol|qol15|mg-qol15)\b")
        or hasPattern(text, r"\b(scale|questionnaire|omgrate|mg-qol|qol15|mg-qol15)\b.{0,90}\b(validation|validate|validated|validating)\b")
    )


def isPharmacovigilance(text: str) -> bool:
    return hasAny(text, pharmacovigilanceTerms)


def isTreatmentEffectQuestion(text: str) -> bool:
    return hasAny(text, treatmentEffectTerms)


def isSingleArmTreatmentStudy(text: str, pubTypeText: str = "") -> bool:
    if hasTrueComparator(text) or hasOwnRandomization(text):
        return False
    if not isTreatmentEffectQuestion(text):
        return False
    return (
        isRetrospective(text, pubTypeText)
        or isSingleArmExplicit(text)
        or hasPattern(text, r"\bpatients\b.{0,80}\b(treated with|received|underwent)\b")
        or hasPattern(text, r"\b(received|treated with)\b.{0,80}\b(efgartigimod|eculizumab|ravulizumab|telitacicept|rituximab|satralizumab|ivig)\b")
    )


def isPredictionModel(text: str) -> bool:
    return hasAny(text, predictionModelTerms) or (
        hasAny(text, ["predictive", "prediction", "predict", "predicts", "predicting"])
        and hasAny(text, ["model", "models", "nomogram", "machine learning", "machine-learning", "random forest", "lasso", "validation", "roc", "auc", "calculator"])
    )


def isPrognosticQuestion(text: str) -> bool:
    if isPredictionModel(text):
        return True
    if hasAny(text, ["risk factor", "risk factors", "predictor", "predictors", "prognosis", "prognostic", "generalization", "generalisation"]):
        return True
    if hasAny(text, ["mortality", "survival", "complication", "complications", "hazard ratio"]):
        return True
    return word("progression", text) and hasAny(text, ["risk", "predict", "associated with", "determinant", "determinants", "follow-up", "follow up", "longitudinal"])


def isDiagnosticQuestion(text: str) -> bool:
    if isScaleValidation(text):
        return True
    if hasAny(text, diagnosticTerms):
        return True
    return hasAny(text, ["repetitive nerve stimulation", "electrophysiological", "electrophysiology"]) and (
        hasAny(text, ["diagnostic", "distinguish", "differenti", "compare", "compared"])
        or hasTrueComparator(text)
    )


def isMechanisticGeneticQuestion(text: str) -> bool:
    return hasAny(text, mechanisticGeneticTerms)


def isBiomarkerPrognosticQuestion(text: str) -> bool:
    if isPredictionModel(text):
        return False
    if isSingleArmTreatmentStudy(text):
        return False
    return isMechanisticGeneticQuestion(text) and (
        hasAny(text, biomarkerOutcomeTerms)
        or hasPattern(text, r"\bpredict\w*\s+.+\b(response|outcome|improvement)\b")
    )


def hasExternalValidation(text: str) -> bool:
    if hasAny(text, externalValidationTerms):
        return True
    if word("validation cohort", text) and not hasAny(text, internalValidationTerms):
        return hasAny(text, ["external", "independent", "prospective", "multicenter", "multi-center", "multicentre"])
    return False


def isHighQualityPrognosticCohort(text: str) -> bool:
    if isCrossSectional(text):
        return False
    if not hasAny(text, ["cohort", "follow-up", "follow up", "longitudinal", "mortality", "survival"]):
        return False
    if hasAny(text, [
        "nationwide",
        "population-based",
        "population based",
        "matched controls",
        "matched cohort",
        "propensity score",
        "cox proportional hazards",
        "multivariable cox",
        "multivariate cox",
    ]):
        return True
    multicenter_patterns = [
        r"\bmulticente?r retrospective cohort\b",
        r"\bmulticentre retrospective cohort\b",
        r"\bmulticente?r cohort study\b",
        r"\bmulticentre cohort study\b",
        r"\bconducted a multicente?r retrospective cohort\b",
        r"\bconducted a multicentre retrospective cohort\b",
    ]
    return any(hasPattern(text, pattern) for pattern in multicenter_patterns)


def classifyPredictionModel(text: str, pubTypeText: str) -> str:
    if hasAny(text, internalValidationTerms):
        return "Prediction Model Development"
    if hasExternalValidation(text) and not isRetrospective(text, pubTypeText):
        return "Prediction Model External Validation"
    if hasExternalValidation(text) and hasPattern(text, r"\b(multi[- ]?center|multicentre|multicenter)\b"):
        return "Prediction Model External Validation"
    return "Prediction Model Development"


def classifyPrognosis(text: str, pubTypeText: str) -> str:
    if isPredictionModel(text):
        return classifyPredictionModel(text, pubTypeText)
    if word("inception cohort", text):
        return "Prognostic Inception Cohort"
    if isHighQualityPrognosticCohort(text):
        return "Prognostic Cohort"
    if isRetrospective(text, pubTypeText) and not hasAny(text, ["multicenter", "multi-center", "multicentre"]):
        return "Poor-quality Prognostic Cohort"
    if hasAny(text, ["cohort", "follow-up", "follow up", "longitudinal", "cox regression", "survival analysis"]):
        return "Prognostic Cohort" if not isCrossSectional(text) else "Cross-Sectional"
    if hasAny(text, ["progression-free survival", "overall survival", "hazard ratio"]):
        return "Prognostic Cohort"
    if isRetrospective(text, pubTypeText):
        return "Poor-quality Prognostic Cohort"
    return "Single Arm"


def classifyDiagnosis(text: str) -> str:
    if word("case-control", text) or hasPattern(text, r"\bpatients with .+ and .+ controls\b"):
        return "Diagnostic Case-Control"
    if isRetrospective(text) or hasAny(text, ["age-matched", "matched patients", "matched controls"]):
        return "Diagnostic Case-Control"
    if isScaleValidation(text):
        return "Scale Validation"
    return "Diagnostic Accuracy Study"


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

    if isSystematicReviewOfUncontrolledEvidence(text):
        return "Systematic Review of Uncontrolled Studies"
    if isSystematicReviewOfCaseEvidence(text):
        return "Systematic Review of Case Reports"

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
    if isSystematicReviewOfUncontrolledEvidence(text):
        return "Systematic Review of Uncontrolled Studies"
    if isSystematicReviewOfCaseEvidence(text):
        return "Systematic Review of Case Reports"
    if isCaseReport(text, pubTypeText):
        return "Case Report"
    if word("narrative review", titleText) or hasPattern(titleText, r"\(review\)"):
        return "Review"
    if isPredictionModel(text):
        return classifyPredictionModel(text, pubTypeText)
    if isBiomarkerPrognosticQuestion(text):
        return "Biomarker Prognostic Study"
    if "RANDOMIZED CONTROLLED TRIAL" in pubTypeText:
        return "RCT"
    if isRctAbstract(text, pubTypeIsRct=False):
        return "RCT"
    if isDiagnosticQuestion(text) and isScaleValidation(text):
        return classifyDiagnosis(text)
    if isPharmacovigilance(text):
        return "Pharmacovigilance"
    if isCrossSectional(text):
        return "Cross-Sectional"
    if isRetrospective(text, pubTypeText) and hasAdjustment(text):
        return "Adjusted Retrospective Cohort"
    if isSingleArmTreatmentStudy(text, pubTypeText):
        return "Single Arm"
    if isMechanisticGeneticQuestion(text) and not word("systematic review", text):
        return "Mechanistic/Genetic Association"
    if word("meta-analysis", text) or isItc(text):
        return "ITC"
    if word("systematic review", text):
        return "Systematic Review"
    if word("narrative review", text) or word("review", text):
        return "Review"
    if isPrognosticQuestion(text):
        return classifyPrognosis(text, pubTypeText)
    if isDiagnosticQuestion(text):
        return classifyDiagnosis(text)
    if isMechanisticGeneticQuestion(text):
        return "Mechanistic/Genetic Association"

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
    if isCohortUpgrade(text):
        return "Non-randomized controlled cohort"
    if isRetrospective(text, pubTypeText):
        return "Historical Control" if hasTrueComparator(text) else "Single Arm"
    if isSingleArmExplicit(text):
        return "Single Arm"
    if isObservational(text):
        return "Non-randomized controlled cohort" if isCohortUpgrade(text) else "Single Arm"
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
