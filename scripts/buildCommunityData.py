#!/usr/bin/env python3
"""
buildCommunityData.py — 生成 MA-MG-HUB 医学事务社区语义层。

第一版只使用规则、统计和可解释关键词，不依赖 LLM 或 embeddings。
目标是先跑通可审计的数据层，再把模型和图算法作为后续增强接入。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"
fullPath = dataDir / "literature-full.json"
recentJsPath = dataDir / "literature-recent.js"
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

levelScore = {"I": 7, "II": 6, "III": 4, "IV": 3, "V": 2, "VI": 1}
levelRank = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

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
        "strongTerms": ["achr", "acetylcholine receptor", "musk", "lrp4", "seronegative", "ocular myasthenia", "juvenile", "pediatric", "paediatric", "thymoma", "thymectomy"],
        "terms": ["late-onset", "early-onset", "elderly", "very-late-onset", "anti-titin", "antibody-positive", "antibody negative", "childhood"],
        "weakTerms": ["subtype", "phenotype", "stratification"],
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
        "terms": ["fatigue", "burden", "remission", "relapse", "exacerbation", "myasthenic crisis", "mg-qol", "eq-5d", "health utility"],
        "weakTerms": ["outcome", "response", "improvement", "severity"],
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
        "terms": ["vaccine", "vaccination", "igg", "headache", "pregnancy", "lactation", "discontinuation", "switching", "toxicity"],
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
        "terms": ["claims", "adherence", "resource utilization", "hospitalization", "pathway", "standard of care", "prospective cohort"],
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
        "terms": ["access", "reimbursement", "insurance", "value", "health utility", "resource utilization", "cost", "economic"],
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
        "strongTerms": ["network meta", "network meta-analysis", "nma", "indirect comparison", "comparative efficacy", "versus", "compared with"],
        "terms": ["comparison", "comparative", "monoclonal antibodies", "rank", "treatment choice", "head-to-head"],
        "weakTerms": ["competition", "positioning"],
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
    return json.loads(path.read_text(encoding="utf-8"))


def loadPublicJs(path: Path, globalName: str):
    text = path.read_text(encoding="utf-8")
    pattern = rf"window\.{re.escape(globalName)}\s*=\s*(.*?);\s*(?:window\.|$)"
    match = re.search(pattern, text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def loadArticles() -> tuple[list[dict], str, str]:
    """优先读取本地 full；没有 full 时回退到公开 recent。"""
    if fullPath.exists():
        rawData = loadJson(fullPath)
        articles = rawData if isinstance(rawData, list) else rawData.get("articles", [])
        return articles, "local_full_first", "data/literature-full.json"
    if recentJsPath.exists():
        return loadPublicJs(recentJsPath, "MG_LITERATURE_DATA"), "recent_fallback", "data/literature-recent.js"
    raise FileNotFoundError("需要 data/literature-full.json 或 data/literature-recent.js")


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
    if level in {"V", "VI"}:
        return "early"
    return "unclassified"


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


def buildTaxonomy(generatedAt: str) -> dict:
    return {
        "generated_at": generatedAt,
        "version": "2026.06-v4a-rule-baseline",
        "method": "ruleBasedBaseline",
        "source_note": "医学事务社区 taxonomy 初版，基于 v4.0 规划和规则关键词；后续由候选社区、LLM 仲裁和人工 review 迭代。",
        "principles": [
            "全 MG PubMed full 为 source of truth；efgar-wiki 只作为策展样板和覆盖校验。",
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


def buildCards(articles: list[dict], assignmentsByPmid: dict, latest: datetime, generatedAt: str) -> dict:
    groupedArticles = defaultdict(list)
    for article in articles:
        assignment = assignmentsByPmid.get(str(article.get("pmid") or ""))
        if assignment and assignment["primary"] != "unassigned":
            groupedArticles[assignment["primary"]].append(article)

    recentCutoff = latest - timedelta(days=14)
    cards = []
    for spec in communitySpecs:
        communityArticles = groupedArticles.get(spec["id"], [])
        recentArticles = [article for article in communityArticles if withinWindow(article, recentCutoff)]
        highEvidence = [article for article in communityArticles if article.get("evidence_level") in {"I", "II"}]
        chinaArticles = [article for article in communityArticles if article.get("china_related")]
        representativeArticles = sorted(communityArticles, key=articleSortKey, reverse=True)[:6]
        recentTopArticles = sorted(recentArticles, key=articleSortKey, reverse=True)[:4]
        evidenceCounter = Counter(article.get("evidence_level") or "未分类" for article in communityArticles)
        studyCounter = Counter(
            studyType
            for article in communityArticles
            for studyType in (article.get("study_types") or ["未标注"])
        )
        signalLevel = "active" if len(recentArticles) >= 3 or any(a.get("evidence_level") in {"I", "II"} for a in recentArticles) else "watch" if recentArticles else "quiet"
        cards.append({
            "id": spec["id"],
            "title": spec["title"],
            "definition": spec["definition"],
            "boundary": spec["boundary"],
            "summary": buildCardSummary(spec, communityArticles, recentArticles, highEvidence, chinaArticles),
            "article_count": len(communityArticles),
            "recent_14d_count": len(recentArticles),
            "high_evidence_count": len(highEvidence),
            "china_count": len(chinaArticles),
            "china_ratio": round(len(chinaArticles) / len(communityArticles), 3) if communityArticles else 0,
            "signal_level": signalLevel,
            "evidence_profile": evidenceCounter.most_common(),
            "study_type_profile": studyCounter.most_common(6),
            "representative_nodes": spec["representativeNodes"],
            "msl_use_cases": spec["mslUseCases"],
            "representative_refs": [compactArticle(article) for article in representativeArticles],
            "recent_refs": [compactArticle(article) for article in recentTopArticles],
            "limitations": "基于 PubMed title/abstract/metadata 的规则归类；社区边界需结合 LLM 仲裁和人工 review 持续校准。",
        })

    cards.sort(key=lambda item: (-item["recent_14d_count"], -item["high_evidence_count"], -item["article_count"]))
    return {
        "generated_at": generatedAt,
        "version": "2026.06-v4a-rule-baseline",
        "method": "ruleBasedBaseline",
        "cards": cards,
    }


def buildCardSummary(spec: dict, communityArticles: list[dict], recentArticles: list[dict], highEvidence: list[dict], chinaArticles: list[dict]) -> str:
    if not communityArticles:
        return f"{spec['title']} 暂未在当前数据源中形成稳定证据社区。"
    parts = [
        f"{spec['title']} 当前覆盖 {len(communityArticles)} 篇文献",
        f"其中高等级证据 {len(highEvidence)} 篇",
        f"中国相关 {len(chinaArticles)} 篇",
    ]
    if recentArticles:
        parts.append(f"近 14 天新增 {len(recentArticles)} 篇，建议纳入本周情报检查")
    else:
        parts.append("近 14 天暂无明显新增，作为稳定知识底座维护")
    return "；".join(parts) + "。"


def buildWeekly(articles: list[dict], assignmentsByPmid: dict, latest: datetime, generatedAt: str) -> dict:
    windowStart = latest - timedelta(days=14)
    recentArticles = [article for article in articles if withinWindow(article, windowStart)]
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
        signalLevel = "high" if highEvidenceItems else "medium" if len(items) >= 3 else "low" if items else "quiet"
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
        {"high": 0, "medium": 1, "low": 2, "quiet": 3}.get(item["signal_level"], 4),
        -item["recent_count"],
    ))
    return {
        "generated_at": generatedAt,
        "window_start": windowStart.strftime("%Y-%m-%d"),
        "window_end": latest.strftime("%Y-%m-%d"),
        "method": "ruleBasedBaseline",
        "recent_article_count": len(recentArticles),
        "unassigned_recent_count": len(groupedRecent.get("unassigned", [])),
        "communities": communityRows,
        "hot_communities": [item for item in communityRows if item["signal_level"] in {"high", "medium"}][:6],
    }


def buildAudit(articles: list[dict], assignments: list[dict], assignmentsByPmid: dict, latest: datetime, generatedAt: str) -> tuple[dict, list[dict]]:
    articleByPmid = {str(article.get("pmid") or ""): article for article in articles}
    unassigned = [item for item in assignments if item["primary"] == "unassigned"]
    lowConfidence = [item for item in assignments if "lowConfidence" in item.get("flags", [])]
    conflicts = [item for item in assignments if "crossCommunityConflict" in item.get("flags", [])]
    latestCutoff = latest - timedelta(days=14)
    recentUnassigned = [item for item in unassigned if withinWindow(articleByPmid.get(item["pmid"], {}), latestCutoff)]
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
        "method": "ruleBasedBaseline",
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
                "第一版为规则基线，taxonomy 和 assignment 需要后续 LLM / 人工 review。",
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
            "recent_14d_count": card["recent_14d_count"],
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
            "recent_14d_count": term["count"],
            "representative_nodes": [],
            "representative_pmids": [],
            "confidence": "low",
        })
    return {
        "generated_at": generatedAt,
        "method": "ruleBasedBaseline",
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def writeJs(path: Path, globalName: str, payload: dict) -> None:
    header = (
        "/* AUTO-GENERATED by scripts/buildCommunityData.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        " * 说明: 医学事务社区语义层，基于 PubMed title/abstract/metadata 的规则基线。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    path.write_text(
        header + f"window.{globalName} = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


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
    path.write_text(
        header +
        "window.MG_COMMUNITY_ASSIGNMENT_SHARDS = window.MG_COMMUNITY_ASSIGNMENT_SHARDS || {};\n" +
        f"window.MG_COMMUNITY_ASSIGNMENT_SHARDS[{json.dumps(communityId)}] = " +
        f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


def writeRecentAssignments(path: Path, payload: dict) -> None:
    header = (
        "/* AUTO-GENERATED by scripts/buildCommunityData.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        " * 说明: 近一年社区归类明细，按需加载，供情报中心筛选使用。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    path.write_text(
        header + f"window.MG_COMMUNITY_RECENT_ASSIGNMENTS = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


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
            "file": f"/MA-MG-HUB/data/{filename}",
            "item_count": len(items),
            "size_hint": "lazy",
        })
        shardPayloads.append((communityId, {
            "generated_at": generatedAt,
            "version": "2026.06-v4a-rule-baseline",
            "method": "ruleBasedBaseline",
            "community_id": communityId,
            "item_count": len(items),
            "items": items,
        }))

    indexPayload = {
        "generated_at": generatedAt,
        "version": "2026.06-v4a-rule-baseline",
        "method": "ruleBasedBaseline",
        "source_mode": sourceMode,
        "source_file": sourceFile,
        "item_count": len(assignments),
        "recent_item_count": len(recentItems),
        "primary_counts": primaryCounts.most_common(),
        "confidence_counts": confidenceCounts.most_common(),
        "shards": shards,
        "recent_assignments_file": "/MA-MG-HUB/data/communityAssignmentsRecent.js",
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
        "version": "2026.06-v4a-rule-baseline",
        "method": "ruleBasedBaseline",
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
    generatedAt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latest = latestDate(articles)
    assignments = [assignArticle(article) for article in articles]
    assignmentsByPmid = {item["pmid"]: item for item in assignments}

    taxonomyPayload = buildTaxonomy(generatedAt)
    assignmentIndexPayload, assignmentShardPayloads, recentAssignmentsPayload = buildAssignmentOutputs(assignments, articles, sourceMode, sourceFile, latest, generatedAt)
    cardsPayload = buildCards(articles, assignmentsByPmid, latest, generatedAt)
    weeklyPayload = buildWeekly(articles, assignmentsByPmid, latest, generatedAt)
    auditPayload, reviewQueue = buildAudit(articles, assignments, assignmentsByPmid, latest, generatedAt)
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
