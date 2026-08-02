#!/usr/bin/env python3
"""
buildCommunityData.py — 生成 MA-MG-HUB 医学事务社区语义层。

当前只使用规则、统计和可解释关键词，不依赖 LLM 或 embeddings。
目标是保留可审计的数据层，通过医学事务 review 慢慢校准。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from common.io import atomic_write_json, atomic_write_js_global, atomic_write_text, load_js_global, load_json as read_json


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"
fullPath = dataDir / "literature-full.json"
recentJsPath = dataDir / "literature-recent.js"
ingestManifestPath = dataDir / "literature-ingest-latest.json"
taxonomyJsPath = dataDir / "communityTaxonomy.js"
assignmentIndexJsPath = dataDir / "communityAssignmentIndex.js"
legacyAssignmentsJsPath = dataDir / "communityAssignments.js"
recentAssignmentsJsPath = dataDir / "communityAssignmentsRecent.js"
cardsJsPath = dataDir / "communityCards.js"
weeklyJsPath = dataDir / "communityWeekly.js"
auditJsPath = dataDir / "communityAudit.js"
corpusPackPath = dataDir / "communityCorpusPack.jsonl"
candidatesPath = dataDir / "communityCandidates.json"
assignmentsJsonlPath = dataDir / "communityAssignments.jsonl"
reviewQueuePath = dataDir / "communityReviewQueue.json"

levelScore = {"I": 7, "II": 6, "III": 4, "IV": 3, "V": 2}
levelRank = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
semanticVersion = "2026.07-v4e-medical-affairs-signal"
weeklyEvidenceVersion = "2026.08-v1-true-ingest"
semanticMethod = "ruleBasedMedicalAffairsReview"

communitySpecs = [
    {
        "id": "fcrnTargetedTherapy",
        "title": "FcRn 靶向治疗",
        "definition": "围绕 FcRn 抑制剂疗效、安全性、用药路径、机制解释和同机制差异化的医学事务社区。",
        "boundary": "不包含未连接 MG 治疗问题的泛 FcRn 基础生物学研究。",
        "strongTerms": ["fcrn", "efgartigimod", "vyvgart", "rozanolixizumab", "nipocalimab", "batoclimab", "neonatal fc receptor"],
        "terms": ["igg recycling", "igg reduction", "argx-113", "fc receptor", "albumin"],
        "weakTerms": ["immunoglobulin g", "autoantibody clearance"],
        "representativeNodes": ["fcrnInhibition", "efgartigimod", "generalizedMg", "achrPositive"],
        "facets": ["drug", "mechanism", "rwe", "safety"],
        "mslUseCases": ["治疗定位", "机制沟通", "竞品问答", "疗效异质性讨论"],
    },
    {
        "id": "complementAndNovelTargets",
        "title": "补体与其他新靶点",
        "definition": "围绕补体抑制剂和其他新兴靶向治疗的疗效、安全性、维持治疗和机制区隔。",
        "boundary": "不把无 MG 治疗连接的普通补体机制文献作为核心证据。",
        "strongTerms": ["complement", "c5 inhibitor", "eculizumab", "ravulizumab", "zilucoplan", "cemdisiran", "terminal complement"],
        "terms": ["c5 inhibition", "meningococcal", "pozelimab", "classical complement", "alternative complement"],
        "weakTerms": ["novel target", "targeted therapy"],
        "representativeNodes": ["complementInhibition", "eculizumab", "ravulizumab", "zilucoplan", "achrPositive"],
        "facets": ["drug", "mechanism", "safety", "maintenance"],
        "mslUseCases": ["竞品定位", "感染风险沟通", "维持治疗讨论"],
    },
    {
        "id": "clinicalSubtypesStratification",
        "title": "临床亚型与人群分层",
        "definition": "围绕 AChR、MuSK、LRP4、血清阴性、眼肌型、儿童、老年、胸腺相关等 MG 亚型和人群分层。",
        "boundary": "单纯病例描述只有在提示特定亚型路径、诊断或治疗问题时进入核心。",
        "strongTerms": ["musk", "lrp4", "seronegative", "ocular myasthenia", "juvenile", "pediatric", "paediatric", "thymoma", "thymectomy"],
        "terms": ["achr", "acetylcholine receptor", "late-onset", "early-onset", "elderly", "very-late-onset", "anti-titin", "antibody-positive", "antibody negative", "childhood"],
        "weakTerms": ["subtype", "phenotype", "stratification", "population"],
        "representativeNodes": ["achrPositive", "muskPositive", "lrp4Positive", "seronegativeMg", "ocularMg", "juvenileMg"],
        "facets": ["population", "diagnosis", "treatmentPosition"],
        "mslUseCases": ["专家拜访前准备", "分层治疗讨论", "特殊人群证据检索"],
    },
    {
        "id": "efficacyBurdenOutcomes",
        "title": "疗效终点与疾病负担",
        "definition": "围绕 MG-ADL、QMG、MSE、生活质量、复发、危象、激素减量和疾病负担的证据社区。",
        "boundary": "只报告一般症状但没有清晰结局指标或负担指标的文献不作为核心。",
        "strongTerms": ["mg-adl", "qmg", "minimal symptom expression", "mse", "quality of life", "qol", "steroid-sparing", "prednisone"],
        "terms": ["fatigue", "burden", "remission", "relapse", "exacerbation", "myasthenic crisis", "mg-qol", "eq-5d", "health utility", "comparative efficacy", "long-term effect"],
        "weakTerms": ["outcome", "response", "improvement", "severity", "efficacy"],
        "representativeNodes": ["efficacyOutcome", "safetyOutcome", "myasthenicCrisis", "steroidSparing"],
        "facets": ["outcome", "patientValue", "endpoint"],
        "mslUseCases": ["疗效证据解读", "材料更新", "患者价值沟通"],
    },
    {
        "id": "safetyMedicationManagement",
        "title": "安全性与用药管理",
        "definition": "围绕 AE、感染、IgG、免疫原性、疫苗、妊娠、停药、换药和长期管理。",
        "boundary": "不把疗效主文献中的轻度 AE 提及自动升级为安全性核心证据。",
        "strongTerms": ["safety", "adverse", "infection", "tolerability", "hypogammaglobulinemia", "immunogenicity", "meningococcal"],
        "terms": ["vaccine", "vaccination", "igg", "headache", "pregnancy", "lactation", "discontinuation", "switching", "toxicity", "immune checkpoint inhibitor", "triple-m", "triple m", "mycophenolate", "mycophenolate mofetil"],
        "weakTerms": ["risk", "monitoring", "long-term"],
        "representativeNodes": ["safetyOutcome", "fcrnInhibition", "complementInhibition"],
        "facets": ["safety", "monitoring", "longTerm"],
        "mslUseCases": ["安全性沟通", "风险管理", "特殊人群追问"],
    },
    {
        "id": "diagnosisMonitoringPrediction",
        "title": "诊断、监测与预测",
        "definition": "围绕抗体检测、电生理、评分量表、生物标志物、预测模型和数字化监测。",
        "boundary": "基础机制研究只有在能支持诊断、监测或预测问题时进入本社区。",
        "strongTerms": ["diagnosis", "diagnostic", "electromyography", "single-fiber", "repetitive nerve stimulation", "biomarker", "prediction", "predictive model"],
        "terms": ["antibody test", "monitoring", "machine learning", "risk score", "neurofilament", "gfap", "cytokine", "digital twin", "model development"],
        "weakTerms": ["score", "scale", "classification"],
        "representativeNodes": ["biomarkerPathogenesis", "mgSubtypesAntibodies"],
        "facets": ["diagnosis", "monitoring", "prediction"],
        "mslUseCases": ["诊疗路径讨论", "专家教育", "预测工具审慎沟通"],
    },
    {
        "id": "mechanismTranslationalMedicine",
        "title": "机制与转化医学",
        "definition": "围绕发病机制、胸腺、B/T 细胞、细胞因子、组学、遗传和动物模型等转化研究。",
        "boundary": "不直接外推为临床疗效或治疗选择结论。",
        "strongTerms": ["pathogenesis", "mechanism", "thymus", "b cell", "b-cell", "t cell", "single-cell", "transcriptomic", "genetic", "animal model"],
        "terms": ["cytokine", "omics", "genomic", "proteomic", "microbiome", "experimental autoimmune", "immune profiling", "irf8"],
        "weakTerms": ["receptor", "immune", "inflammatory"],
        "representativeNodes": ["biomarkerPathogenesis", "bCellTargeting", "conventionalImmunosuppression"],
        "facets": ["mechanism", "translational", "basicScience"],
        "mslUseCases": ["机制沟通", "KOL 深访", "新靶点线索"],
    },
    {
        "id": "rweClinicalPathway",
        "title": "真实世界证据与临床路径",
        "definition": "围绕真实世界、注册队列、治疗路径、依从性、医疗资源和临床实践差异。",
        "boundary": "China 作为 geo facet，不自动把所有中国文献归入本社区；需要 RWE 或路径问题。",
        "strongTerms": ["real-world", "real world", "registry", "cohort", "observational", "retrospective", "treatment pattern", "clinical practice"],
        "terms": ["claims", "adherence", "resource utilization", "healthcare resource utilization", "hcru", "hospitalization", "pathway", "standard of care", "prospective cohort", "survey", "treatment characteristics", "current management", "single center experience"],
        "weakTerms": ["multicenter", "single-center", "follow-up"],
        "representativeNodes": ["realWorldEvidence", "chinaEvidence", "generalizedMg"],
        "facets": ["rwe", "clinicalPathway", "geo"],
        "mslUseCases": ["本土证据沟通", "路径优化", "真实世界局限解释"],
    },
    {
        "id": "guidelineHeorAccess",
        "title": "指南、共识与卫生经济",
        "definition": "围绕指南、共识、推荐、偏好、支付、成本效果、准入和价值证据。",
        "boundary": "价值和准入证据不能混同为疗效结论。",
        "strongTerms": ["guideline", "consensus", "recommendation", "health economic", "cost-effectiveness", "willingness-to-pay", "preference"],
        "terms": ["access", "reimbursement", "insurance", "value", "multi-criteria", "mcda", "eligibility", "treatment program", "health utility", "resource utilization", "cost", "economic"],
        "weakTerms": ["policy", "standardization"],
        "representativeNodes": ["guidelineEvidence", "realWorldEvidence"],
        "facets": ["guideline", "heor", "access", "patientValue"],
        "mslUseCases": ["准入支持", "标准化诊疗讨论", "患者价值沟通"],
    },
    {
        "id": "competitiveLandscapeIndirectComparison",
        "title": "竞争格局与间接比较",
        "definition": "围绕 NMA、ITC、跨药物比较、治疗选择框架和竞争定位。",
        "boundary": "无比较框架的单药研究不作为本社区核心，除非被用于竞争定位。",
        "strongTerms": ["network meta", "network meta-analysis", "nma", "indirect comparison", "indirect treatment comparison", "head-to-head"],
        "terms": ["comparative efficacy", "comparative effectiveness", "comparative safety", "active comparator", "monoclonal antibodies", "treatment choice", "treatment sequencing"],
        "weakTerms": ["competition", "positioning", "versus", "compared with", "comparison", "comparative", "rank"],
        "representativeNodes": ["fcrnInhibition", "complementInhibition", "metaEvidence"],
        "facets": ["competition", "comparison", "evidenceSynthesis"],
        "mslUseCases": ["竞品定位", "医学策略", "间接比较局限说明"],
    },
]

drugTermMap = {
    "efgartigimod": ["efgartigimod", "vyvgart", "argx-113"],
    "rozanolixizumab": ["rozanolixizumab"],
    "nipocalimab": ["nipocalimab"],
    "batoclimab": ["batoclimab"],
    "eculizumab": ["eculizumab"],
    "ravulizumab": ["ravulizumab"],
    "zilucoplan": ["zilucoplan"],
    "telitacicept": ["telitacicept", "rc18", "rc-18"],
    "rituximab": ["rituximab"],
    "inebilizumab": ["inebilizumab"],
}

populationTermMap = {
    "achrPositive": ["achr", "acetylcholine receptor"],
    "muskPositive": ["musk"],
    "lrp4Positive": ["lrp4"],
    "seronegativeMg": ["seronegative"],
    "ocularMg": ["ocular myasthenia", "ocular mg"],
    "juvenileMg": ["juvenile", "pediatric", "paediatric", "childhood"],
    "elderlyMg": ["elderly", "late-onset", "very-late-onset", "older"],
    "thymomaAssociatedMg": ["thymoma", "thymectomy", "thymic"],
}

stopWords = {
    "myasthenia", "gravis", "patients", "patient", "study", "case", "report",
    "review", "with", "from", "using", "after", "before", "among", "into",
    "clinical", "treatment", "therapy", "analysis", "disease", "based",
    "outcome", "outcomes", "generalized", "generalised", "chinese", "china",
    "mg", "and", "the", "for", "in", "of", "to", "a", "an",
}


def loadJson(path: Path):
    return read_json(path)


def loadPublicJs(path: Path, globalName: str):
    return load_js_global(path, globalName)


def loadArticles() -> tuple[list[dict], str, str]:
    """优先读取本地 full；没有 full 时回退到公开 recent。"""
    if fullPath.exists():
        rawData = loadJson(fullPath)
        articles = rawData if isinstance(rawData, list) else rawData.get("articles", [])
        return articles, "local_full_first", "data/literature-full.json"
    if recentJsPath.exists():
        return loadPublicJs(recentJsPath, "MG_LITERATURE_DATA"), "recent_fallback", "data/literature-recent.js"
    raise FileNotFoundError("需要 data/literature-full.json 或 data/literature-recent.js")


def loadIngestManifest() -> dict:
    """读取本周真实入库清单；缺失时宁可展示空周更，也不回退旧时间窗。"""
    if not ingestManifestPath.exists():
        return {
            "window_start": "",
            "window_end": "",
            "basis": "ingestManifestMissing",
            "added_pmids": [],
            "updated_pmids": [],
        }
    payload = loadJson(ingestManifestPath)
    return payload if isinstance(payload, dict) else {}


def parseDate(value: str | None):
    if not value:
        return None
    value = str(value).strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    match = re.search(r"((?:19|20)\d{2})[-/](\d{1,2})(?:[-/](\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day or 1))
    match = re.search(r"(19|20)\d{2}", value)
    if match:
        return datetime(int(match.group(0)), 1, 1)
    return None


def articleText(article: dict) -> str:
    parts = [
        article.get("title") or "",
        article.get("abstract") or "",
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]
    return "\n".join(parts).lower()


def titleText(article: dict) -> str:
    return str(article.get("title") or "").lower()


def evidenceScore(article: dict) -> float:
    level = article.get("evidence_level") or ""
    parsedDate = parseDate(article.get("entry_date") or article.get("pub_date"))
    yearScore = max(((parsedDate.year if parsedDate else 2000) - 2000), 0) / 10
    journalIf = article.get("journal_if") or 0
    try:
        journalIf = float(journalIf)
    except (TypeError, ValueError):
        journalIf = 0
    return levelScore.get(level, 0) * 100 + yearScore + min(journalIf, 30)


def compactArticle(article: dict) -> dict:
    pmid = str(article.get("pmid") or "")
    return {
        "pmid": pmid,
        "title": article.get("title") or "",
        "journal": article.get("journal") or "",
        "entry_date": article.get("entry_date") or "",
        "pub_date": article.get("pub_date") or "",
        "url": article.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""),
        "evidence_level": article.get("evidence_level"),
        "study_types": article.get("study_types") or [],
        "china_related": bool(article.get("china_related")),
        "journal_if": article.get("journal_if"),
    }


def termHit(text: str, term: str) -> bool:
    term = term.lower()
    if " " in term or "-" in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text, re.I) is not None


fcrnSpecificTerms = {
    "fcrn", "efgartigimod", "vyvgart", "rozanolixizumab", "nipocalimab",
    "batoclimab", "neonatal fc receptor", "argx-113",
}
fcrnProductTerms = {
    "efgartigimod", "vyvgart", "rozanolixizumab", "nipocalimab",
    "batoclimab", "argx-113",
}
complementSpecificTerms = {
    "complement", "c5 inhibitor", "eculizumab", "ravulizumab", "zilucoplan",
    "cemdisiran", "terminal complement", "c5 inhibition",
}
complementProductTerms = {
    "eculizumab", "ravulizumab", "zilucoplan", "cemdisiran",
}
comparisonFrameworkTerms = {
    "network meta", "network meta-analysis", "nma", "indirect comparison",
    "indirect treatment comparison", "comparative efficacy", "comparative effectiveness",
    "comparative safety", "head-to-head", "active comparator",
}
comparisonGeneralTerms = {"versus", " vs ", "comparison", "comparative", "rank", "ranking"}
targetedComparatorTerms = {
    "intravenous immunoglobulin", "ivig", "rituximab", "monoclonal antibodies",
    "biologics", "complement inhibitors", "fcrn blockers", "novel biologics",
    "standard of care", "lymphoplasmapheresis", "plasmapheresis", "double-filtration",
    "dfpp", "immunoglobulin", "corticosteroid", "steroid", "ofatumumab",
}
productEvidenceTerms = {
    "effectiveness", "efficacy", "safety", "response", "responses", "responder",
    "disease control", "clinical benefit", "steroid-sparing", "case series",
    "case report", "real-world", "real world", "meta-analysis", "phase 3",
    "trial", "randomized", "randomised", "extension", "predictor", "predictors",
    "therapeutic response", "rescue", "fast-acting", "observations under",
}
heorAccessTerms = {
    "cost", "cost-effectiveness", "economic", "health economic", "mcda",
    "multi-criteria", "value contribution", "value", "reimbursement", "access",
    "insurance", "willingness-to-pay", "health utility", "eligibility",
    "treatment program",
}
rweProtectionTerms = {
    "claims", "healthcare resource utilization", "resource utilization", "hcru",
    "treatment characteristics", "treatment pattern", "treatment patterns",
    "treatment utilization", "current management", "management and treatment",
    "clinical practice", "survey", "early versus late", "early vs late",
    "add-on therapy", "insufficient immunosuppressive treatment",
    "single center experience", "new therapies",
}
nonCompetitiveComparisonTerms = {
    "healthy controls", "healthy control", "versus healthy", "vs healthy",
    "thymectomy", "video-assisted", "thoracoscopic", "transsternal",
    "sternotomy", "robot-assisted", "robot assisted", "vats", "rats",
    "surgery", "surgical", "daily versus alternate day",
    "ocular and generalized", "ocular vs generalized", "based on antibody subtypes",
    "antibody subtypes", "healthy beliefs", "controlled study",
    "adaptive trial design", "methods and application", "incomplete longitudinal",
    "diagnostic yield", "antibody detection", "repetitive nerve stimulation findings",
    "iatrogenic botulism", "botulism compared with myasthenia gravis",
    "not an independent factor", "healthy controls",
}
safetySignalTerms = {
    "immune checkpoint inhibitor", "immune checkpoint inhibitors", "ici",
    "durvalumab", "olaparib", "triple m", "triple-m", "myositis",
    "myocarditis", "overlap syndrome", "faers", "pharmacovigilance",
    "mycophenolate mofetil", "mycophenolate", "immunosuppression",
    "cryptococcus", "cryptococcal", "opportunistic infection",
    "steroid toxicity", "glucocorticoid toxicity", "pregnancy", "postpartum",
    "exacerbation during pregnancy", "vaccine", "vaccination",
    "rare adverse events", "thrombosis", "thromboembolic", "venous thromboembolism",
    "pulmonary embolism", "infection", "tuberculosis", "cardiac herniation",
    "drug-induced", "induced by", "complication", "complications",
    "hypogammaglobulinemia", "covid-19 pneumonia",
}
diagnosisRoutingTerms = {
    "diagnostic", "diagnosis", "antibody detection", "diagnostic yield",
    "cell-based assay", "live cell-based assay", "repetitive nerve stimulation",
    "botulism compared with myasthenia gravis",
}
subtypeRoutingTerms = {
    "ocular and generalized", "ocular myasthenia", "generalized myasthenia",
    "antibody subtypes", "achr and musk", "anti-achr and anti-musk",
    "thymoma recurrence", "masaoka-koga", "subtypes",
}
incidentalScopeTerms = {
    "multiple sclerosis", "neuromuscular diseases", "neurological disorders",
    "autoimmune diseases", "skeletal muscle diseases", "lambert-eaton",
    "botulism", "pulmonary embolism", "headache", "stroke unit",
    "neurocritical care", "sexual health", "liposomes",
}
lowValuePublicationTerms = {
    "correction:", "correction to:", "comment on", "erratum",
}
broadTherapyReviewTerms = {
    "therapeutic approaches", "novel therapeutic approaches",
    "targeting autoimmunity", "conventional to novel", "management of dysphagia",
    "pharmacological and speech-language pathology management", "new therapies",
    "rescue therapy", "myasthenic crisis and emerging roles",
}
clinicalBroadPopulationTerms = {"achr", "acetylcholine receptor", "antibody-positive"}
clinicalIntentTerms = {
    "subtype", "subtypes", "phenotype", "phenotypes", "stratification",
    "classification", "spectrum", "predictor", "predictors", "predictive",
    "seronegative", "ocular", "juvenile", "pediatric", "paediatric",
    "childhood", "elderly", "late-onset", "early-onset", "very-late-onset",
    "thymoma", "thymectomy", "anti-titin", "musk", "lrp4",
}


def hitTerms(text: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if termHit(text, term))


def titleHitTerms(title: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if termHit(title, term))


def productHits(text: str) -> set[str]:
    hits = set()
    for drug, terms in drugTermMap.items():
        if any(termHit(text, term) for term in terms):
            hits.add(drug)
    return hits


def hasClinicalSubtypeIntent(text: str, title: str, hits: list[str]) -> bool:
    if any(termHit(title, term) for term in clinicalIntentTerms):
        return True
    if any(termHit(text, term) for term in clinicalIntentTerms):
        return True
    return any(term not in clinicalBroadPopulationTerms for term in hits)


def hasAnyTerm(text: str, terms: set[str]) -> bool:
    return any(termHit(text, term) for term in terms)


def hasHeorAccessIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, heorAccessTerms) or hasAnyTerm(text, {
        "cost-effectiveness", "health economic", "mcda", "multi-criteria",
        "reimbursement", "willingness-to-pay", "treatment program",
    })


def hasRweProtectionIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, rweProtectionTerms) or hasAnyTerm(text, {
        "claims database", "healthcare resource utilization", "hcru",
        "treatment characteristics", "current management",
    })


def hasProductEvidenceIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, productEvidenceTerms) or hasAnyTerm(text, {
        "primary endpoint", "secondary endpoint", "clinical improvement",
        "clinically meaningful", "minimal symptom expression",
    })


def hasBroadTherapyReviewIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, broadTherapyReviewTerms) or (
        "review" in text and hasAnyTerm(title, {"therapeutic", "management", "approaches"})
    )


def hasNonCompetitiveIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, nonCompetitiveComparisonTerms) or hasAnyTerm(text, {
        "versus healthy controls", "vs healthy controls", "surgical approach",
        "surgical technique", "video-assisted thoracoscopic", "robot-assisted",
    })


def hasDiagnosisRoutingIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, diagnosisRoutingTerms) or hasAnyTerm(text, {
        "diagnostic sensitivity", "diagnostic specificity", "diagnostic yield",
        "differential diagnosis", "electrophysiological", "seronegative",
    })


def hasSubtypeRoutingIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, subtypeRoutingTerms) or hasAnyTerm(text, {
        "ocular versus generalized", "ocular and generalized",
        "achr-mg", "musk-mg", "antibody-defined", "thymoma recurrence",
    })


def hasSafetyOverrideIntent(title: str, text: str) -> bool:
    return hasAnyTerm(title, safetySignalTerms) or hasAnyTerm(text, {
        "adverse event", "adverse events", "safety profile", "toxicity",
        "infection risk", "postoperative complication", "complication after",
    })


def hasTargetedComparisonIntent(title: str, text: str, products: set[str]) -> bool:
    if len(products) >= 2:
        return True
    if products and hasAnyTerm(title, targetedComparatorTerms) and hasAnyTerm(title, comparisonGeneralTerms):
        return True
    return hasAnyTerm(title, {
        "complement inhibitors and fcrn blockers",
        "novel biologics",
        "efgartigimod versus lymphoplasmapheresis",
        "ravulizumab or efgartigimod",
        "double-filtration plasmapheresis versus efgartigimod",
    })


def hasCompetitiveTreatmentIntent(title: str, text: str, products: set[str]) -> bool:
    if hasAnyTerm(title, comparisonFrameworkTerms):
        return True
    if hasTargetedComparisonIntent(title, text, products):
        return True
    if products and hasAnyTerm(title, comparisonGeneralTerms) and hasAnyTerm(title, targetedComparatorTerms):
        return True
    if len(products) >= 2 and hasAnyTerm(text, {"meta-analysis", "systematic review", "treatment approaches"}):
        return True
    return False


def hasMultiMechanismComparison(text: str, title: str, fcrnHits: list[str], complementHits: list[str]) -> bool:
    if not (fcrnHits and complementHits):
        return False
    comparisonTerms = comparisonFrameworkTerms | comparisonGeneralTerms | {"meta-analysis", "systematic review"}
    return hasAnyTerm(title, comparisonTerms) or hasAnyTerm(text, {"network meta-analysis", "meta-analysis"})


def hasMgFocusedTitle(title: str) -> bool:
    return hasAnyTerm(title, {
        "myasthenia gravis", "myasthenic", "gmg", "mg ", " mg", "achr-mg", "musk-mg",
    })


def isLowValuePublication(article: dict, title: str) -> bool:
    abstract = str(article.get("abstract") or "").strip()
    pubTypes = " ".join(article.get("pub_types") or article.get("publication_types") or []).lower()
    return hasAnyTerm(title, lowValuePublicationTerms) and not abstract and "correction" in (title + " " + pubTypes)


def isIncidentalMgScope(article: dict, title: str, text: str) -> bool:
    if "lambert-eaton" in title and "myasthenia gravis" not in title:
        return True
    if hasMgFocusedTitle(title):
        return False
    if hasAnyTerm(title, incidentalScopeTerms):
        return True
    mgMentions = len(re.findall(r"\bmyasthenia gravis\b|\bmyasthenic\b", text, re.I))
    if mgMentions <= 2 and hasAnyTerm(text, incidentalScopeTerms):
        return True
    return False


def calibrateCommunityScore(article: dict, spec: dict, score: float, hits: list[str]) -> float:
    """根据医学事务语义做可解释校准，避免宽泛关键词压过高特异治疗/比较信号。"""
    if not score:
        return score
    specId = spec["id"]
    text = articleText(article)
    title = titleText(article)
    products = productHits(text)
    fcrnHits = hitTerms(text, fcrnSpecificTerms)
    complementHits = hitTerms(text, complementSpecificTerms)
    titleFcrnHits = titleHitTerms(title, fcrnSpecificTerms)
    titleComplementHits = titleHitTerms(title, complementSpecificTerms)
    titleFcrnProductHits = titleHitTerms(title, fcrnProductTerms)
    titleComplementProductHits = titleHitTerms(title, complementProductTerms)
    heorIntent = hasHeorAccessIntent(title, text)
    rweProtectionIntent = hasRweProtectionIntent(title, text)
    productEvidenceIntent = hasProductEvidenceIntent(title, text)
    broadTherapyReviewIntent = hasBroadTherapyReviewIntent(title, text)
    multiMechanismComparison = hasMultiMechanismComparison(text, title, fcrnHits, complementHits)
    nonCompetitiveIntent = hasNonCompetitiveIntent(title, text)
    targetedComparisonIntent = hasTargetedComparisonIntent(title, text, products)
    competitiveTreatmentIntent = hasCompetitiveTreatmentIntent(title, text, products)
    diagnosisRoutingIntent = hasDiagnosisRoutingIntent(title, text)
    subtypeRoutingIntent = hasSubtypeRoutingIntent(title, text)
    safetyOverrideIntent = hasSafetyOverrideIntent(title, text)
    incidentalMgScope = isIncidentalMgScope(article, title, text)

    if specId == "fcrnTargetedTherapy" and fcrnHits:
        score += 5 + min(len(fcrnHits), 3) * 1.5
        if titleFcrnHits:
            score += 3
        if titleFcrnProductHits and productEvidenceIntent and not (heorIntent or rweProtectionIntent or multiMechanismComparison):
            score += 13
        elif titleFcrnProductHits and not (heorIntent or rweProtectionIntent):
            score += 4
        if titleFcrnProductHits and hasAnyTerm(title, {"versus standard of care", "new-onset"}):
            score += 16
        if heorIntent:
            score *= 0.55
        elif rweProtectionIntent and not productEvidenceIntent:
            score *= 0.65
        if broadTherapyReviewIntent and not titleFcrnProductHits:
            score *= 0.3
        if titleComplementProductHits and hasAnyTerm(text, {"poor response to efgartigimod", "poor early response to efgartigimod", "after efgartigimod"}):
            score *= 0.25
        if multiMechanismComparison:
            score *= 0.45
        if targetedComparisonIntent and len(products) >= 2:
            score *= 0.6
        if incidentalMgScope and not titleFcrnProductHits:
            score *= 0.35

    if specId == "complementAndNovelTargets" and complementHits:
        score += 5 + min(len(complementHits), 3) * 1.5
        if titleComplementHits:
            score += 3
        if titleComplementProductHits and productEvidenceIntent and not (heorIntent or rweProtectionIntent or multiMechanismComparison):
            score += 13
        elif titleComplementProductHits and not (heorIntent or rweProtectionIntent):
            score += 4
        if titleComplementProductHits and hasAnyTerm(title, {"real-life", "real-world", "observational study"}):
            score += 8
        if heorIntent:
            score *= 0.6
        elif rweProtectionIntent and not (titleComplementProductHits and productEvidenceIntent):
            score *= 0.7
        if broadTherapyReviewIntent and not titleComplementProductHits:
            score *= 0.3
        if titleComplementProductHits and hasAnyTerm(text, {"poor response to efgartigimod", "after efgartigimod"}):
            score += 6
        if multiMechanismComparison:
            score *= 0.45
        if targetedComparisonIntent and len(products) >= 2:
            score *= 0.6
        if nonCompetitiveIntent and not titleComplementProductHits:
            score *= 0.35
        if incidentalMgScope and not titleComplementProductHits:
            score *= 0.35

    if specId == "competitiveLandscapeIndirectComparison":
        frameworkHits = hitTerms(text, comparisonFrameworkTerms)
        generalHits = hitTerms(text, comparisonGeneralTerms)
        titleFrameworkHits = titleHitTerms(title, comparisonFrameworkTerms)
        titleGeneralHits = titleHitTerms(title, comparisonGeneralTerms)
        if targetedComparisonIntent:
            score += 20 + min(len(products), 2) * 2
            if titleGeneralHits:
                score += 2
        elif multiMechanismComparison:
            score += 18
        elif frameworkHits and competitiveTreatmentIntent:
            score += 8 + min(len(frameworkHits), 2) * 2
            if titleFrameworkHits:
                score += 3
        elif targetedComparisonIntent and generalHits:
            score += 7 + min(len(products), 3)
            if titleGeneralHits:
                score += 2
        elif len(products) >= 2 and ("meta-analysis" in text or "systematic review" in text):
            score += 4
        elif generalHits and not products:
            score *= 0.45
        if not competitiveTreatmentIntent:
            score *= 0.35
        if (diagnosisRoutingIntent or subtypeRoutingIntent or incidentalMgScope) and not competitiveTreatmentIntent:
            score *= 0.25
        if safetyOverrideIntent and not competitiveTreatmentIntent:
            score *= 0.2
        if broadTherapyReviewIntent:
            score *= 0.35
        if rweProtectionIntent and hasAnyTerm(title, {"early versus late", "real-world cohort", "multicenter real-world"}):
            score *= 0.6
        if nonCompetitiveIntent and not targetedComparisonIntent:
            score *= 0.2
        elif heorIntent and not targetedComparisonIntent:
            score *= 0.35
        if hasAnyTerm(title, {"plasma exchange", "daily versus alternate day"}) and not products:
            score *= 0.1

    if specId == "clinicalSubtypesStratification":
        specificTherapyHit = bool(fcrnHits or complementHits)
        hasIntent = hasClinicalSubtypeIntent(text, title, hits)
        broadOnly = bool(hits) and all(term in clinicalBroadPopulationTerms for term in hits)
        if broadOnly and specificTherapyHit:
            score *= 0.35
        elif broadOnly and not hasIntent:
            score *= 0.5
        elif specificTherapyHit and not hasIntent:
            score *= 0.65
        if subtypeRoutingIntent and not (titleFcrnProductHits or titleComplementProductHits):
            score += 8
        elif subtypeRoutingIntent:
            score += 2
        if hasAnyTerm(title, {"efficacy and safety", "randomized", "randomised", "placebo-controlled", "placebo controlled"}) and broadOnly:
            score *= 0.45
        if incidentalMgScope and not subtypeRoutingIntent:
            score *= 0.35

    if specId == "efficacyBurdenOutcomes":
        if hasAnyTerm(title, {"long-term effect", "comparative efficacy", "efficacy"}):
            score += 4
        if hasAnyTerm(title, {"randomized", "randomised", "placebo-controlled", "placebo controlled", "double-blind", "crossover trial"}):
            score += 8
        if safetyOverrideIntent and not hasAnyTerm(title, {"efficacy and safety", "effectiveness and safety"}):
            score *= 0.45
        if incidentalMgScope and not hasMgFocusedTitle(title):
            score *= 0.45

    if specId == "rweClinicalPathway":
        if rweProtectionIntent:
            score += 7
        if nonCompetitiveIntent and hasAnyTerm(title, {"thymectomy", "surgery", "surgical", "thoracoscopic", "robot-assisted", "vats", "rats"}):
            score += 6
        if hasAnyTerm(title, {"real-world", "real world"}) and hasAnyTerm(title, {"cohort", "retrospective", "multicenter"}):
            score += 3
        if hasAnyTerm(title, {"nationwide", "population-based", "registry", "register-based", "claims database"}):
            score += 5
        if incidentalMgScope and not (rweProtectionIntent or hasMgFocusedTitle(title)):
            score *= 0.45

    if specId == "guidelineHeorAccess":
        if heorIntent:
            score += 9
        if hasAnyTerm(title, {"cost", "economic", "mcda", "multi-criteria", "value contribution"}):
            score += 4
        if nonCompetitiveIntent and not hasAnyTerm(title, heorAccessTerms):
            score *= 0.45
        if incidentalMgScope and not heorIntent:
            score *= 0.35

    if specId == "diagnosisMonitoringPrediction":
        if diagnosisRoutingIntent:
            score += 8
        if hasAnyTerm(title, {"long-term effect", "randomized trial", "randomised trial"}):
            score *= 0.45
        if incidentalMgScope and not diagnosisRoutingIntent:
            score *= 0.35

    if specId == "safetyMedicationManagement":
        if hasAnyTerm(title, safetySignalTerms):
            score += 12
        elif hasAnyTerm(text, safetySignalTerms):
            score += 6
        if safetyOverrideIntent:
            score += 8
        if hasAnyTerm(title, {"faers", "pharmacovigilance", "safety profile"}):
            score += 14
        if competitiveTreatmentIntent and hasAnyTerm(title, comparisonGeneralTerms):
            score *= 0.45
        if hasAnyTerm(title, {"efficacy and safety", "effectiveness and safety"}) and not hasAnyTerm(title, {"faers", "pharmacovigilance", "safety profile"}):
            score *= 0.45
        if hasAnyTerm(title, {"long-term effect"}) and not hasAnyTerm(title, {"safety", "adverse", "toxicity"}):
            score *= 0.45
        if incidentalMgScope and not safetyOverrideIntent:
            score *= 0.45

    return score


def shouldForceUnassigned(article: dict, topId: str, topScore: float) -> bool:
    title = titleText(article)
    text = articleText(article)
    if hasAnyTerm(title, {"adaptive trial design", "methods and application", "incomplete longitudinal"}) and topScore < 20:
        return True
    if "lambert-eaton" in title and "myasthenia gravis" not in title and topScore < 10:
        return True
    if isLowValuePublication(article, title) and topScore < 12:
        return True
    if not hasMgFocusedTitle(title) and hasAnyTerm(title, incidentalScopeTerms) and topScore < 18:
        return True
    if isIncidentalMgScope(article, title, text) and topScore < 8:
        return True
    if not hasMgFocusedTitle(title) and topScore < 6 and topId not in {"guidelineHeorAccess"}:
        return True
    return False


def scoreCommunity(article: dict, spec: dict) -> tuple[float, list[str]]:
    text = articleText(article)
    title = titleText(article)
    score = 0.0
    hits = []
    for term in spec.get("strongTerms", []):
        if termHit(text, term):
            score += 4
            hits.append(term)
            if termHit(title, term):
                score += 1.5
    for term in spec.get("terms", []):
        if termHit(text, term):
            score += 2
            hits.append(term)
            if termHit(title, term):
                score += 0.8
    for term in spec.get("weakTerms", []):
        if termHit(text, term):
            score += 1
            hits.append(term)
    if article.get("evidence_level") in {"I", "II", "III"} and hits:
        score += 0.8
    score = calibrateCommunityScore(article, spec, score, sorted(set(hits)))
    return score, sorted(set(hits))


def detectFacets(article: dict, primaryCommunity: str) -> dict:
    text = articleText(article)
    productFacets = [
        drug for drug, terms in drugTermMap.items()
        if any(termHit(text, term) for term in terms)
    ]
    populationFacets = [
        population for population, terms in populationTermMap.items()
        if any(termHit(text, term) for term in terms)
    ]
    evidenceLevel = article.get("evidence_level") or "unclassified"
    studyTypes = article.get("study_types") or []
    geoFacets = ["China"] if article.get("china_related") else []
    chinaContext = []
    if article.get("china_related"):
        if primaryCommunity == "rweClinicalPathway":
            chinaContext.append("中国 RWE / 临床路径")
        if primaryCommunity == "guidelineHeorAccess":
            chinaContext.append("中国指南 / 准入 / 支付")
        if productFacets:
            chinaContext.append("中国产品证据")
    return {
        "products": productFacets,
        "populations": populationFacets,
        "geo": geoFacets,
        "evidence_level": evidenceLevel,
        "study_types": studyTypes,
        "maturity": evidenceMaturity(evidenceLevel),
        "china_context": chinaContext,
    }


def evidenceMaturity(level: str) -> str:
    if level in {"I", "II"}:
        return "high"
    if level in {"III", "IV"}:
        return "medium"
    if level == "V":
        return "early"
    return "unclassified"


def isGuidelineOrConsensus(article: dict) -> bool:
    """判断新增文献是否属于指南/共识类医学事务高优先级更新。"""
    text = " ".join([
        article.get("title") or "",
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]).lower()
    return any(term in text for term in ["guideline", "consensus", "recommendation", "practice guideline"])


def isRegulatoryOrAccessUpdate(article: dict) -> bool:
    """判断新增文献是否提示监管、准入或支付相关变化。"""
    titleMetaText = " ".join([
        article.get("title") or "",
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]).lower()
    titleMetaPatterns = [
        r"\bapproval\b",
        r"\bapproved\b",
        r"\bregulatory\b",
        r"\blabel\b",
        r"\bindication\b",
        r"\bnmpa\b",
        r"\bcde\b",
        r"\bnhsa\b",
        r"\breimbursement\b",
        r"\binsurance\b",
        r"\bnational reimbursement\b",
        r"\bdrug list\b",
        r"\bmarket access\b",
        r"\bexpanded access\b",
    ]
    if any(re.search(pattern, titleMetaText) for pattern in titleMetaPatterns):
        return True

    text = articleText(article)
    explicitAccessPatterns = [
        r"\bnmpa\b",
        r"\bcde\b",
        r"\bnhsa\b",
        r"\breimbursement\b",
        r"\binsurance\b",
        r"\bnational reimbursement\b",
        r"\bdrug list\b",
        r"\bmarket access\b",
        r"\bexpanded access\b",
    ]
    return any(re.search(pattern, text) for pattern in explicitAccessPatterns)


def isCaseReviewOrLowActionPublication(article: dict) -> bool:
    """病例、综述、信件等通常作为观察信号，不仅凭期刊 IF 进入高活跃。"""
    text = " ".join([
        article.get("title") or "",
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]).lower()
    return any(term in text for term in [
        "case report",
        "case series",
        "review",
        "letter",
        "comment",
        "editorial",
        "animal study",
    ])


def isImportantChinaEvidence(article: dict) -> bool:
    """判断新增中国证据是否足以触发医学事务高活跃提示。"""
    if not article.get("china_related"):
        return False
    evidenceLevel = article.get("evidence_level")
    if isCaseReviewOrLowActionPublication(article):
        return evidenceLevel in {"I", "II"}
    if evidenceLevel in {"I", "II", "III", "IV"}:
        return True
    try:
        journalIf = float(article.get("journal_if") or 0)
    except (TypeError, ValueError):
        journalIf = 0
    return journalIf >= 8


def isMedicalAffairsHighActivity(article: dict) -> bool:
    """高活跃：高等级证据、指南/共识、监管/准入或重要中国证据。"""
    return (
        article.get("evidence_level") in {"I", "II"}
        or isGuidelineOrConsensus(article)
        or isRegulatoryOrAccessUpdate(article)
        or isImportantChinaEvidence(article)
    )


def medicalAffairsSignalLevel(recentArticles: list[dict]) -> str:
    """统一医学事务活跃度：高活跃 / 观察 / 平稳。"""
    if any(isMedicalAffairsHighActivity(article) for article in recentArticles):
        return "active"
    if recentArticles:
        return "watch"
    return "quiet"


def assignArticle(article: dict) -> dict:
    scores = []
    matchedTerms = {}
    for spec in communitySpecs:
        score, hits = scoreCommunity(article, spec)
        if score:
            scores.append((spec["id"], score))
            matchedTerms[spec["id"]] = hits
    scores.sort(key=lambda item: item[1], reverse=True)
    pmid = str(article.get("pmid") or "")
    if not scores or scores[0][1] < 3:
        return {
            "pmid": pmid,
            "primary": "unassigned",
            "secondary": [],
            "confidence": "unassigned",
            "score": 0,
            "matched_terms": [],
            "facets": detectFacets(article, "unassigned"),
            "flags": ["unassigned"],
        }

    topId, topScore = scores[0]
    if shouldForceUnassigned(article, topId, topScore):
        return {
            "pmid": pmid,
            "primary": "unassigned",
            "secondary": [],
            "confidence": "unassigned",
            "score": 0,
            "matched_terms": [],
            "facets": detectFacets(article, "unassigned"),
            "flags": ["unassigned", "scopeReview"],
        }

    secondary = [
        {"community_id": communityId, "score": round(score, 1)}
        for communityId, score in scores[1:3]
        if score >= 4
    ]
    lead = topScore - (scores[1][1] if len(scores) > 1 else 0)
    confidence = "high" if topScore >= 10 and lead >= 3 else "medium" if topScore >= 6 else "low"
    flags = []
    if confidence == "low":
        flags.append("lowConfidence")
    if len(scores) > 1 and scores[1][1] >= topScore * 0.75 and scores[1][1] >= 4:
        flags.append("crossCommunityConflict")
    return {
        "pmid": pmid,
        "primary": topId,
        "secondary": secondary,
        "confidence": confidence,
        "score": round(topScore, 1),
        "matched_terms": matchedTerms.get(topId, []),
        "facets": detectFacets(article, topId),
        "flags": flags,
    }


def latestDate(articles: list[dict]) -> datetime:
    parsedDates = [
        parseDate(article.get("entry_date") or article.get("pub_date"))
        for article in articles
    ]
    parsedDates = [item for item in parsedDates if item]
    return max(parsedDates, default=datetime.now())


def withinWindow(article: dict, cutoff: datetime) -> bool:
    parsedDate = parseDate(article.get("entry_date") or article.get("pub_date"))
    return bool(parsedDate and parsedDate >= cutoff)


def articleSortKey(article: dict):
    parsedDate = parseDate(article.get("entry_date") or article.get("pub_date")) or datetime.min
    return (evidenceScore(article), parsedDate.timestamp())


def signalSortRank(signalLevel: str) -> int:
    return {"active": 0, "watch": 1, "quiet": 2}.get(signalLevel, 3)


def buildTaxonomy(generatedAt: str) -> dict:
    return {
        "generated_at": generatedAt,
        "version": semanticVersion,
        "method": semanticMethod,
        "source_note": "医学事务社区 taxonomy 基于全 MG PubMed full、规则关键词和人工 review 渐进校准。",
        "principles": [
            "全 MG PubMed full 为 source of truth。",
            "China 默认作为 geo facet，不作为平行主社区。",
            "社区是医学事务语义层，不等同于图谱 cluster。",
            "低置信度文献允许进入 unassigned / review queue。",
        ],
        "communities": [
            {
                "id": spec["id"],
                "title": spec["title"],
                "level": "primary",
                "definition": spec["definition"],
                "boundary": spec["boundary"],
                "representative_nodes": spec["representativeNodes"],
                "facets": spec["facets"],
                "msl_use_cases": spec["mslUseCases"],
                "terms": {
                    "strong": spec.get("strongTerms", []),
                    "normal": spec.get("terms", []),
                    "weak": spec.get("weakTerms", []),
                },
            }
            for spec in communitySpecs
        ],
    }


def buildCards(articles: list[dict], assignmentsByPmid: dict, weeklyAddedPmids: set[str], generatedAt: str) -> dict:
    groupedArticles = defaultdict(list)
    for article in articles:
        assignment = assignmentsByPmid.get(str(article.get("pmid") or ""))
        if assignment and assignment["primary"] != "unassigned":
            groupedArticles[assignment["primary"]].append(article)

    cards = []
    for spec in communitySpecs:
        communityArticles = groupedArticles.get(spec["id"], [])
        weeklyArticles = [article for article in communityArticles if str(article.get("pmid") or "") in weeklyAddedPmids]
        highEvidence = [article for article in communityArticles if article.get("evidence_level") in {"I", "II"}]
        chinaArticles = [article for article in communityArticles if article.get("china_related")]
        representativeArticles = sorted(communityArticles, key=articleSortKey, reverse=True)[:6]
        weeklyTopArticles = sorted(weeklyArticles, key=articleSortKey, reverse=True)[:4]
        evidenceCounter = Counter(article.get("evidence_level") or "未分类" for article in communityArticles)
        studyCounter = Counter(
            studyType
            for article in communityArticles
            for studyType in (article.get("study_types") or ["未标注"])
        )
        signalLevel = medicalAffairsSignalLevel(weeklyArticles)
        cards.append({
            "id": spec["id"],
            "title": spec["title"],
            "definition": spec["definition"],
            "boundary": spec["boundary"],
            "summary": buildCardSummary(spec, communityArticles, weeklyArticles, highEvidence, chinaArticles),
            "article_count": len(communityArticles),
            "weekly_new_count": len(weeklyArticles),
            "high_evidence_count": len(highEvidence),
            "china_count": len(chinaArticles),
            "china_ratio": round(len(chinaArticles) / len(communityArticles), 3) if communityArticles else 0,
            "signal_level": signalLevel,
            "evidence_profile": evidenceCounter.most_common(),
            "study_type_profile": studyCounter.most_common(6),
            "representative_nodes": spec["representativeNodes"],
            "msl_use_cases": spec["mslUseCases"],
            "representative_refs": [compactArticle(article) for article in representativeArticles],
            "weekly_refs": [compactArticle(article) for article in weeklyTopArticles],
            "limitations": "基于 PubMed title/abstract/metadata 的规则归类；社区边界需结合人工 review 持续校准。",
        })

    cards.sort(key=lambda item: (
        signalSortRank(item["signal_level"]),
        -item["high_evidence_count"],
        -item["weekly_new_count"],
        -item["article_count"],
    ))
    return {
        "generated_at": generatedAt,
        "version": semanticVersion,
        "weekly_evidence_version": weeklyEvidenceVersion,
        "method": semanticMethod,
        "cards": cards,
    }


def buildCardSummary(spec: dict, communityArticles: list[dict], weeklyArticles: list[dict], highEvidence: list[dict], chinaArticles: list[dict]) -> str:
    if not communityArticles:
        return f"{spec['title']} 暂未在当前数据源中形成稳定证据社区。"
    parts = [
        f"{spec['title']} 当前覆盖 {len(communityArticles)} 篇文献",
        f"其中高等级证据 {len(highEvidence)} 篇",
        f"中国相关 {len(chinaArticles)} 篇",
    ]
    if weeklyArticles:
        parts.append(f"本周真实入库新增 {len(weeklyArticles)} 篇，建议纳入情报检查")
    else:
        parts.append("本周暂无新入库文献，作为稳定知识底座维护")
    return "；".join(parts) + "。"


def buildWeekly(articles: list[dict], assignmentsByPmid: dict, ingestManifest: dict, generatedAt: str) -> dict:
    weeklyAddedPmids = {str(item) for item in ingestManifest.get("added_pmids") or []}
    recentArticles = [article for article in articles if str(article.get("pmid") or "") in weeklyAddedPmids]
    groupedRecent = defaultdict(list)
    for article in recentArticles:
        assignment = assignmentsByPmid.get(str(article.get("pmid") or ""))
        primary = assignment["primary"] if assignment else "unassigned"
        groupedRecent[primary].append(article)

    communityRows = []
    for spec in communitySpecs:
        items = groupedRecent.get(spec["id"], [])
        highEvidenceItems = [article for article in items if article.get("evidence_level") in {"I", "II"}]
        chinaItems = [article for article in items if article.get("china_related")]
        signalLevel = medicalAffairsSignalLevel(items)
        communityRows.append({
            "community_id": spec["id"],
            "title": spec["title"],
            "recent_count": len(items),
            "high_evidence_count": len(highEvidenceItems),
            "china_count": len(chinaItems),
            "signal_level": signalLevel,
            "top_refs": [compactArticle(article) for article in sorted(items, key=articleSortKey, reverse=True)[:4]],
        })
    communityRows.sort(key=lambda item: (
        signalSortRank(item["signal_level"]),
        -item["recent_count"],
    ))
    return {
        "generated_at": generatedAt,
        "weekly_evidence_version": weeklyEvidenceVersion,
        "window_start": ingestManifest.get("window_start") or "",
        "window_end": ingestManifest.get("window_end") or "",
        "basis": ingestManifest.get("basis") or "ingestManifestMissing",
        "method": semanticMethod,
        "recent_article_count": len(recentArticles),
        "unassigned_recent_count": len(groupedRecent.get("unassigned", [])),
        "communities": communityRows,
        "hot_communities": [item for item in communityRows if item["signal_level"] in {"active", "watch"}][:6],
    }


def buildAudit(articles: list[dict], assignments: list[dict], assignmentsByPmid: dict, latest: datetime, weeklyAddedPmids: set[str], generatedAt: str) -> tuple[dict, list[dict]]:
    articleByPmid = {str(article.get("pmid") or ""): article for article in articles}
    unassigned = [item for item in assignments if item["primary"] == "unassigned"]
    lowConfidence = [item for item in assignments if "lowConfidence" in item.get("flags", [])]
    conflicts = [item for item in assignments if "crossCommunityConflict" in item.get("flags", [])]
    recentUnassigned = [item for item in unassigned if item["pmid"] in weeklyAddedPmids]
    groupedCounts = Counter(item["primary"] for item in assignments if item["primary"] != "unassigned")
    oversizedCommunities = [
        {"community_id": communityId, "article_count": count}
        for communityId, count in groupedCounts.items()
        if count / max(len(assignments), 1) > 0.25
    ]
    staleCommunities = []
    for spec in communitySpecs:
        communityArticles = [
            articleByPmid.get(item["pmid"], {})
            for item in assignments
            if item["primary"] == spec["id"]
        ]
        if communityArticles and not any(withinWindow(article, latest - timedelta(days=90)) for article in communityArticles):
            staleCommunities.append({"community_id": spec["id"], "title": spec["title"]})

    emergingTerms = extractEmergingTerms([articleByPmid.get(item["pmid"], {}) for item in recentUnassigned])
    chinaOverlayGaps = buildChinaOverlayGaps(assignments, articleByPmid)
    reviewItems = buildReviewQueue(recentUnassigned, lowConfidence, conflicts, articleByPmid)
    audit = {
        "generated_at": generatedAt,
        "method": semanticMethod,
        "summary": {
            "total_articles": len(articles),
            "assigned_articles": len(assignments) - len(unassigned),
            "unassigned_articles": len(unassigned),
            "low_confidence_articles": len(lowConfidence),
            "conflict_articles": len(conflicts),
            "recent_unassigned_articles": len(recentUnassigned),
        },
        "health": {
            "status": "needsReview" if recentUnassigned or conflicts else "ok",
            "notes": [
                "当前为规则基线，taxonomy 和 assignment 需要后续医学事务 review。",
                "unassigned 不视为失败，是为了避免低置信度文献被强行归类。",
            ],
        },
        "unassigned_samples": sampleAssignments(unassigned, articleByPmid, 12),
        "low_confidence_samples": sampleAssignments(lowConfidence, articleByPmid, 12),
        "conflict_samples": sampleAssignments(conflicts, articleByPmid, 12),
        "oversized_communities": oversizedCommunities,
        "stale_communities": staleCommunities,
        "emerging_terms": emergingTerms,
        "china_overlay_gaps": chinaOverlayGaps,
    }
    return audit, reviewItems


def sampleAssignments(items: list[dict], articleByPmid: dict, limit: int) -> list[dict]:
    sortedItems = sorted(
        items,
        key=lambda item: articleSortKey(articleByPmid.get(item["pmid"], {})),
        reverse=True,
    )
    return [
        {
            "assignment": item,
            "article": compactArticle(articleByPmid.get(item["pmid"], {})),
        }
        for item in sortedItems[:limit]
    ]


def extractEmergingTerms(articles: list[dict]) -> list[dict]:
    counter = Counter()
    for article in articles:
        title = str(article.get("title") or "").lower()
        words = re.findall(r"[a-z][a-z0-9-]{3,}", title)
        for word in words:
            if word not in stopWords:
                counter[word] += 1
    return [
        {"term": term, "count": count}
        for term, count in counter.most_common(15)
    ]


def buildChinaOverlayGaps(assignments: list[dict], articleByPmid: dict) -> list[dict]:
    rows = []
    for spec in communitySpecs:
        communityItems = [item for item in assignments if item["primary"] == spec["id"]]
        if not communityItems:
            continue
        chinaCount = sum(1 for item in communityItems if articleByPmid.get(item["pmid"], {}).get("china_related"))
        if chinaCount == 0:
            rows.append({
                "community_id": spec["id"],
                "title": spec["title"],
                "gap": "当前规则归类下暂无中国相关文献，需要确认是证据缺口还是识别规则不足。",
            })
    return rows


def buildReviewQueue(recentUnassigned: list[dict], lowConfidence: list[dict], conflicts: list[dict], articleByPmid: dict) -> list[dict]:
    queue = []
    seen = set()
    for reason, items in [
        ("recentUnassigned", recentUnassigned),
        ("lowConfidence", lowConfidence),
        ("crossCommunityConflict", conflicts),
    ]:
        for item in items:
            pmid = item["pmid"]
            if pmid in seen:
                continue
            seen.add(pmid)
            queue.append({
                "reason": reason,
                "assignment": item,
                "article": compactArticle(articleByPmid.get(pmid, {})),
            })
    queue.sort(key=lambda item: articleSortKey(articleByPmid.get(item["assignment"]["pmid"], {})), reverse=True)
    return queue[:200]


def buildCandidates(cardsPayload: dict, auditPayload: dict, generatedAt: str) -> dict:
    candidates = []
    for card in cardsPayload.get("cards", []):
        candidates.append({
            "candidate_id": card["id"],
            "title": card["title"],
            "method": "seedTaxonomyRuleAggregate",
            "article_count": card["article_count"],
            "weekly_new_count": card["weekly_new_count"],
            "representative_nodes": card["representative_nodes"],
            "representative_pmids": [ref["pmid"] for ref in card["representative_refs"]],
            "confidence": "seed",
        })
    for term in auditPayload.get("emerging_terms", [])[:8]:
        candidates.append({
            "candidate_id": f"emerging_{term['term']}",
            "title": f"新兴候选：{term['term']}",
            "method": "recentUnassignedTitleTerm",
            "article_count": term["count"],
            "weekly_new_count": term["count"],
            "representative_nodes": [],
            "representative_pmids": [],
            "confidence": "low",
        })
    return {
        "generated_at": generatedAt,
        "method": semanticMethod,
        "candidates": candidates,
    }


def writeCorpusPack(articles: list[dict], assignmentsByPmid: dict) -> None:
    with corpusPackPath.open("w", encoding="utf-8") as output:
        for article in articles:
            pmid = str(article.get("pmid") or "")
            item = {
                "pmid": pmid,
                "title": article.get("title") or "",
                "abstract": article.get("abstract") or "",
                "journal": article.get("journal") or "",
                "entry_date": article.get("entry_date") or "",
                "pub_date": article.get("pub_date") or "",
                "evidence_level": article.get("evidence_level"),
                "study_types": article.get("study_types") or [],
                "china_related": bool(article.get("china_related")),
                "assignment": assignmentsByPmid.get(pmid),
            }
            output.write(json.dumps(item, ensure_ascii=False) + "\n")


def writeAssignmentsJsonl(assignments: list[dict]) -> None:
    with assignmentsJsonlPath.open("w", encoding="utf-8") as output:
        for item in assignments:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")


def writeJson(path: Path, payload: dict) -> None:
    atomic_write_json(path, payload)


def writeJs(path: Path, globalName: str, payload: dict) -> None:
    header = (
        "/* AUTO-GENERATED by scripts/buildCommunityData.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        " * 说明: 医学事务社区语义层，基于 PubMed title/abstract/metadata 的规则基线。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    atomic_write_js_global(path, globalName, payload, header)


def assignmentPublicItem(item: dict, article: dict) -> dict:
    return {
        "pmid": item["pmid"],
        "primary": item["primary"],
        "secondary": item["secondary"],
        "confidence": item["confidence"],
        "score": item["score"],
        "facets": item["facets"],
        "flags": item["flags"],
        "entry_date": article.get("entry_date") or "",
        "pub_date": article.get("pub_date") or "",
        "evidence_level": article.get("evidence_level"),
        "china_related": bool(article.get("china_related")),
    }


def assignmentShardFile(communityId: str) -> str:
    return f"communityAssignments-{communityId}.js"


def writeAssignmentShard(path: Path, communityId: str, payload: dict) -> None:
    header = (
        "/* AUTO-GENERATED by scripts/buildCommunityData.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        f" * 社区: {communityId}\n"
        " * 说明: 社区归类分片，按需加载，避免首屏加载全量 assignments。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    atomic_write_text(
        path,
        header +
        "window.MG_COMMUNITY_ASSIGNMENT_SHARDS = window.MG_COMMUNITY_ASSIGNMENT_SHARDS || {};\n" +
        f"window.MG_COMMUNITY_ASSIGNMENT_SHARDS[{json.dumps(communityId)}] = " +
        f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
    )


def writeRecentAssignments(path: Path, payload: dict) -> None:
    header = (
        "/* AUTO-GENERATED by scripts/buildCommunityData.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        " * 说明: 近一年社区归类明细，按需加载，供情报中心筛选使用。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    atomic_write_js_global(path, "MG_COMMUNITY_RECENT_ASSIGNMENTS", payload, header)


def buildAssignmentOutputs(assignments: list[dict], articles: list[dict], sourceMode: str, sourceFile: str, latest: datetime, generatedAt: str) -> tuple[dict, list[tuple[str, dict]], dict]:
    articleByPmid = {str(article.get("pmid") or ""): article for article in articles}
    groupedItems = defaultdict(list)
    for item in assignments:
        article = articleByPmid.get(item["pmid"], {})
        groupedItems[item["primary"]].append(assignmentPublicItem(item, article))

    recentCutoff = latest - timedelta(days=365)
    recentItems = []
    for item in assignments:
        article = articleByPmid.get(item["pmid"], {})
        if withinWindow(article, recentCutoff):
            recentItems.append(assignmentPublicItem(item, article))
    recentItems.sort(key=lambda item: (item.get("entry_date") or item.get("pub_date") or ""), reverse=True)
    confidenceCounts = Counter(item["confidence"] for item in assignments)
    primaryCounts = Counter(item["primary"] for item in assignments)
    shardPayloads = []
    shards = []
    for communityId, items in sorted(groupedItems.items()):
        items.sort(key=lambda item: (
            item.get("entry_date") or item.get("pub_date") or "",
            levelScore.get(item.get("evidence_level") or "", 0),
        ), reverse=True)
        filename = assignmentShardFile(communityId)
        shards.append({
            "community_id": communityId,
            "file": f"data/{filename}",
            "item_count": len(items),
            "size_hint": "lazy",
        })
        shardPayloads.append((communityId, {
            "generated_at": generatedAt,
            "version": semanticVersion,
            "method": semanticMethod,
            "community_id": communityId,
            "item_count": len(items),
            "items": items,
        }))

    indexPayload = {
        "generated_at": generatedAt,
        "version": semanticVersion,
        "method": semanticMethod,
        "source_mode": sourceMode,
        "source_file": sourceFile,
        "item_count": len(assignments),
        "recent_item_count": len(recentItems),
        "primary_counts": primaryCounts.most_common(),
        "confidence_counts": confidenceCounts.most_common(),
        "shards": shards,
        "recent_assignments_file": "data/communityAssignmentsRecent.js",
        "recent_items_preview": [
            {
                "pmid": item["pmid"],
                "primary": item["primary"],
                "confidence": item["confidence"],
                "entry_date": item["entry_date"],
                "evidence_level": item["evidence_level"],
                "china_related": item["china_related"],
            }
            for item in recentItems[:30]
        ],
        "loading_note": "首屏只加载 taxonomy/cards/weekly/audit；全量 assignments 已按社区拆分为 communityAssignments-*.js 分片，近一年 assignments 独立按需加载。",
    }
    recentPayload = {
        "generated_at": generatedAt,
        "version": semanticVersion,
        "method": semanticMethod,
        "source_mode": sourceMode,
        "source_file": sourceFile,
        "window_days": 365,
        "item_count": len(recentItems),
        "items": recentItems,
    }
    return indexPayload, shardPayloads, recentPayload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MA-MG-HUB community semantic data")
    parser.add_argument("--skip-local", action="store_true", help="不写本地 JSONL/中间产物，只生成前端 JS")
    args = parser.parse_args()

    articles, sourceMode, sourceFile = loadArticles()
    ingestManifest = loadIngestManifest()
    weeklyAddedPmids = {str(item) for item in ingestManifest.get("added_pmids") or []}
    generatedAt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latest = latestDate(articles)
    assignments = [assignArticle(article) for article in articles]
    assignmentsByPmid = {item["pmid"]: item for item in assignments}

    taxonomyPayload = buildTaxonomy(generatedAt)
    assignmentIndexPayload, assignmentShardPayloads, recentAssignmentsPayload = buildAssignmentOutputs(assignments, articles, sourceMode, sourceFile, latest, generatedAt)
    cardsPayload = buildCards(articles, assignmentsByPmid, weeklyAddedPmids, generatedAt)
    weeklyPayload = buildWeekly(articles, assignmentsByPmid, ingestManifest, generatedAt)
    auditPayload, reviewQueue = buildAudit(articles, assignments, assignmentsByPmid, latest, weeklyAddedPmids, generatedAt)
    candidatesPayload = buildCandidates(cardsPayload, auditPayload, generatedAt)

    writeJs(taxonomyJsPath, "MG_COMMUNITY_TAXONOMY", taxonomyPayload)
    writeJs(assignmentIndexJsPath, "MG_COMMUNITY_ASSIGNMENT_INDEX", assignmentIndexPayload)
    writeRecentAssignments(recentAssignmentsJsPath, recentAssignmentsPayload)
    if legacyAssignmentsJsPath.exists():
        legacyAssignmentsJsPath.unlink()
    for stalePath in dataDir.glob("communityAssignments-*.js"):
        stalePath.unlink()
    for communityId, payload in assignmentShardPayloads:
        writeAssignmentShard(dataDir / assignmentShardFile(communityId), communityId, payload)
    writeJs(cardsJsPath, "MG_COMMUNITY_CARDS", cardsPayload)
    writeJs(weeklyJsPath, "MG_COMMUNITY_WEEKLY", weeklyPayload)
    writeJs(auditJsPath, "MG_COMMUNITY_AUDIT", auditPayload)

    if not args.skip_local:
        writeCorpusPack(articles, assignmentsByPmid)
        writeAssignmentsJsonl(assignments)
        writeJson(candidatesPath, candidatesPayload)
        writeJson(reviewQueuePath, {"generated_at": generatedAt, "items": reviewQueue})

    print(f"✅ communityTaxonomy.js: {len(taxonomyPayload['communities'])} 个社区")
    print(f"✅ communityAssignmentIndex.js: {len(assignments)} 篇文献归类 · {len(assignmentShardPayloads)} 个分片")
    print(f"✅ communityCards.js: {len(cardsPayload['cards'])} 张社区卡")
    print(f"✅ communityAudit.js: {auditPayload['summary']['unassigned_articles']} 篇未归类")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
