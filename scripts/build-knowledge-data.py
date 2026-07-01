#!/usr/bin/env python3
"""
build-knowledge-data.py - 从 full PubMed abstract 库生成 MG 知识图谱与证据矩阵。

本脚本不读取 efgartigimod-wiki。它使用本地 literature-full.json 作为知识底座，
从标题、摘要、发表类型、研究类型和证据等级中抽取主题节点、关系边和 PMID 证据。

用法:
    python scripts/build-knowledge-data.py
    python scripts/build-knowledge-data.py --input data/literature-full.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"
defaultInputPath = dataDir / "literature-full.json"
recentJsPath = dataDir / "literature-recent.js"
defaultOutputPath = dataDir / "knowledge-graph.js"
graphHealthJsPath = dataDir / "graphHealth.js"
communityAssignmentsJsonlPath = dataDir / "communityAssignments.jsonl"
communityTaxonomyJsPath = dataDir / "communityTaxonomy.js"
communityCardsJsPath = dataDir / "communityCards.js"
communityRecentAssignmentsJsPath = dataDir / "communityAssignmentsRecent.js"

levelScore = {"I": 7, "II": 5, "III": 4, "IV": 3, "V": 2, "VI": 1}
levelRank = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
priorityNodeIds = {
    "efgartigimod",
    "rozanolixizumab",
    "nipocalimab",
    "batoclimab",
    "telitacicept",
    "eculizumab",
    "ravulizumab",
    "zilucoplan",
    "cemdisiran",
    "rituximab",
    "fcrnInhibition",
    "complementInhibition",
    "baffAprilModulation",
}


conceptDefs = [
    {
        "id": "myastheniaGravis",
        "title": "Myasthenia Gravis",
        "type": "disease",
        "summary": "MG 全库文献底座的中心疾病节点，连接亚型、治疗机制、结局指标与证据类型。",
        "patterns": [r"\bmyasthenia gravis\b"],
    },
    {
        "id": "generalizedMg",
        "title": "Generalized MG",
        "type": "population",
        "summary": "全身型 MG 相关研究，常与新型靶向治疗、MG-ADL/QMG 终点和真实世界证据相连。",
        "patterns": [r"\bgeneralized myasthenia gravis\b", r"\bgeneralised myasthenia gravis\b", r"\bgMG\b"],
    },
    {
        "id": "ocularMg",
        "title": "Ocular MG",
        "type": "population",
        "summary": "眼肌型 MG 相关诊断、预后、转归和治疗策略文献。",
        "patterns": [r"\bocular myasthenia\b", r"\bocular MG\b"],
    },
    {
        "id": "myasthenicCrisis",
        "title": "Myasthenic Crisis",
        "type": "population",
        "summary": "MG 危象和呼吸受累相关证据，常涉及 IVIg、血浆置换和快速起效治疗。",
        "patterns": [r"\bmyasthenic crisis\b", r"\brespiratory failure\b", r"\bventilat"],
    },
    {
        "id": "refractoryMg",
        "title": "Refractory MG",
        "type": "population",
        "summary": "难治性 MG 相关研究，常用于定位靶向治疗、联合治疗和后线治疗策略。",
        "patterns": [r"\brefractory\b", r"\btreatment-resistant\b", r"\bresistant myasthenia"],
    },
    {
        "id": "thymomaAssociatedMg",
        "title": "Thymoma-associated MG",
        "type": "population",
        "summary": "胸腺瘤相关 MG、胸腺病理和围手术期管理相关文献。",
        "patterns": [r"\bthymoma\b", r"\bthymic\b", r"\bthymectomy\b"],
    },
    {
        "id": "juvenileMg",
        "title": "Juvenile MG",
        "type": "population",
        "summary": "儿童和青少年 MG 相关诊断、治疗和结局证据。",
        "patterns": [r"\bjuvenile myasthenia\b", r"\bchildhood myasthenia\b", r"\bpediatric\b", r"\bpaediatric\b"],
    },
    {
        "id": "achrPositive",
        "title": "AChR-positive MG",
        "type": "population",
        "summary": "AChR 抗体阳性 MG，是多项 FcRn、补体和终点研究的主要人群。",
        "patterns": [r"\bAChR\b", r"\bacetylcholine receptor\b"],
    },
    {
        "id": "muskPositive",
        "title": "MuSK-positive MG",
        "type": "population",
        "summary": "MuSK 抗体阳性 MG，常与 B 细胞靶向、利妥昔单抗和特殊治疗响应相关。",
        "patterns": [r"\bMuSK\b", r"\bmuscle-specific kinase\b"],
    },
    {
        "id": "lrp4Positive",
        "title": "LRP4-positive MG",
        "type": "population",
        "summary": "LRP4 抗体相关 MG 与血清阴性谱系、抗体检测和机制研究相连。",
        "patterns": [r"\bLRP4\b", r"\blow-density lipoprotein receptor-related protein 4\b"],
    },
    {
        "id": "seronegativeMg",
        "title": "Seronegative MG",
        "type": "population",
        "summary": "血清阴性 MG 相关诊断和治疗证据，摘要层面需注意抗体检测方法差异。",
        "patterns": [r"\bseronegative\b", r"\btriple-seronegative\b"],
    },
    {
        "id": "chinaEvidence",
        "title": "China Evidence",
        "type": "population",
        "summary": "中国相关 MG 研究、真实世界数据、指南共识和本土临床实践证据。",
        "patterns": [r"\bChina\b", r"\bChinese\b"],
    },
    {
        "id": "fcrnInhibition",
        "title": "FcRn Inhibition",
        "type": "mechanism",
        "summary": "通过阻断 neonatal Fc receptor 加速 IgG 清除的治疗机制。",
        "patterns": [r"\bFcRn\b", r"\bneonatal Fc receptor\b", r"\bIgG recycling\b"],
    },
    {
        "id": "complementInhibition",
        "title": "Complement Inhibition",
        "type": "mechanism",
        "summary": "补体通路抑制，尤其是 C5 抑制相关治疗机制。",
        "patterns": [r"\bcomplement\b", r"\bC5 inhibitor\b", r"\bterminal complement\b"],
    },
    {
        "id": "bCellTargeting",
        "title": "B-cell / Plasma-cell Targeting",
        "type": "mechanism",
        "summary": "B 细胞、浆细胞或 CD19/CD20/BCMA 方向的免疫靶向策略。",
        "patterns": [r"\bB-cell\b", r"\bB cell\b", r"\bplasma cell\b", r"\bCD20\b", r"\bCD19\b", r"\bBCMA\b"],
    },
    {
        "id": "baffAprilModulation",
        "title": "BAFF / APRIL Modulation",
        "type": "mechanism",
        "summary": "靶向 BLyS/BAFF 与 APRIL 通路的 B 细胞生存信号调节策略，主要连接泰它西普等 TACI-Fc 类治疗证据。",
        "patterns": [
            r"\bBAFF\b",
            r"\bBLyS\b",
            r"\bB lymphocyte stimulator\b",
            r"\bBAFF\s*/\s*APRIL\b",
            r"\bAPRIL\s*/\s*BAFF\b",
            r"\ba proliferation-inducing ligand\b",
            r"\bTACI[- ]Fc\b",
        ],
    },
    {
        "id": "conventionalImmunosuppression",
        "title": "Conventional Immunosuppression",
        "type": "mechanism",
        "summary": "传统免疫抑制治疗策略的上位节点，具体药物由子节点承接。",
        "patterns": [r"\bconventional immunosuppress", r"\bimmunosuppress(?:ion|ive|ant|ants)?\b", r"\bsteroid-sparing agent", r"\bnonsteroidal immunosuppress"],
    },
    {
        "id": "rapidRescue",
        "title": "Rapid Rescue Therapy",
        "type": "mechanism",
        "summary": "IVIg、血浆置换和危象场景中的快速救援治疗。",
        "patterns": [r"\bIVIg\b", r"\bintravenous immunoglobulin\b", r"\bplasma exchange\b", r"\bplasmapheresis\b", r"\brescue therap"],
    },
    {
        "id": "biomarkerPathogenesis",
        "title": "Biomarker & Pathogenesis",
        "type": "mechanism",
        "summary": "生物标志物和疾病发生机制的上位节点，抗体、遗传和免疫细胞信号由子节点承接。",
        "patterns": [r"\bbiomarker\b", r"\bpathogenesis\b"],
    },
    {
        "id": "autoantibodyPathway",
        "title": "Autoantibody Pathway",
        "type": "mechanism",
        "summary": "AChR、MuSK、LRP4 等自身抗体谱系、抗体滴度和抗体功能相关机制。",
        "patterns": [r"\bautoantibod", r"\bantibody titer", r"\bantibody titre", r"\bserostatus\b", r"\bantibody-positive\b"],
    },
    {
        "id": "cytokineImmuneSignature",
        "title": "Cytokine / Immune Signature",
        "type": "mechanism",
        "summary": "细胞因子、免疫细胞谱系和单细胞免疫特征相关机制研究。",
        "patterns": [r"\bcytokine\b", r"\bimmune cell", r"\bT-cell\b", r"\bT cell\b", r"\bsingle-cell\b", r"\binterleukin\b"],
    },
    {
        "id": "geneticSusceptibility",
        "title": "Genetic Susceptibility",
        "type": "mechanism",
        "summary": "遗传易感性、HLA、GWAS 和多态性相关 MG 机制证据。",
        "patterns": [r"\bgenetic\b", r"\bHLA\b", r"\bGWAS\b", r"\bpolymorphism\b", r"\bgenotype\b"],
    },
    {
        "id": "efgartigimod",
        "title": "Efgartigimod",
        "type": "drug",
        "summary": "FcRn 抑制剂，MG 文献中涉及 RCT、真实世界、安全性和跨人群定位。",
        "patterns": [r"\befgartigimod\b", r"\bVyvgart\b", r"\bARGX-113\b"],
    },
    {
        "id": "rozanolixizumab",
        "title": "Rozanolixizumab",
        "type": "drug",
        "summary": "皮下注射 FcRn 抑制剂，常见于 MycarinG、患者报告结局和安全性研究。",
        "patterns": [r"\brozanolixizumab\b", r"\bRystiggo\b"],
    },
    {
        "id": "nipocalimab",
        "title": "Nipocalimab",
        "type": "drug",
        "summary": "FcRn 靶向候选/上市后证据扩展药物，涉及后期临床和间接比较研究。",
        "patterns": [r"\bnipocalimab\b"],
    },
    {
        "id": "batoclimab",
        "title": "Batoclimab",
        "type": "drug",
        "summary": "FcRn 靶向候选药物，主要连接临床开发和机制类别证据。",
        "patterns": [r"\bbatoclimab\b"],
    },
    {
        "id": "telitacicept",
        "title": "Telitacicept / 泰它西普",
        "type": "drug",
        "summary": "BLyS/APRIL 双靶点 TACI-Fc 融合蛋白，连接 B 细胞通路、疗效、安全性和中国证据。",
        "patterns": [r"\btelitacicept\b", r"\bRC18\b", r"\bRC-18\b", r"\bTai'?ai\b", r"泰它西普"],
    },
    {
        "id": "eculizumab",
        "title": "Eculizumab",
        "type": "drug",
        "summary": "C5 补体抑制剂，MG 靶向治疗和真实世界比较中的重要节点。",
        "patterns": [r"\beculizumab\b", r"\bSoliris\b"],
    },
    {
        "id": "ravulizumab",
        "title": "Ravulizumab",
        "type": "drug",
        "summary": "长效 C5 补体抑制剂，常与补体治疗便利性、疗效和安全性相关。",
        "patterns": [r"\bravulizumab\b", r"\bUltomiris\b"],
    },
    {
        "id": "zilucoplan",
        "title": "Zilucoplan",
        "type": "drug",
        "summary": "皮下注射 C5 抑制剂，连接补体治疗、给药路径和特殊变异病例。",
        "patterns": [r"\bzilucoplan\b"],
    },
    {
        "id": "cemdisiran",
        "title": "Cemdisiran",
        "type": "drug",
        "summary": "补体通路 RNAi 治疗线索，连接 NIMBLE 等临床研究。",
        "patterns": [r"\bcemdisiran\b"],
    },
    {
        "id": "rituximab",
        "title": "Rituximab",
        "type": "drug",
        "summary": "CD20 靶向 B 细胞治疗，尤其与 MuSK+ MG 和难治性 MG 相关。",
        "patterns": [r"\brituximab\b", r"\banti-CD20\b"],
    },
    {
        "id": "pyridostigmine",
        "title": "Pyridostigmine",
        "type": "drug",
        "summary": "胆碱酯酶抑制剂，MG 对症治疗和基础治疗路径节点。",
        "patterns": [r"\bpyridostigmine\b", r"\bcholinesterase inhibitor\b"],
    },
    {
        "id": "corticosteroids",
        "title": "Corticosteroids",
        "type": "drug",
        "summary": "糖皮质激素治疗节点，常与减量、长期安全性和免疫抑制策略相连。",
        "patterns": [r"\bcorticosteroid", r"\bsteroid\b", r"\bprednisone\b", r"\bprednisolone\b"],
    },
    {
        "id": "azathioprineMycophenolate",
        "title": "Azathioprine / Mycophenolate",
        "type": "drug",
        "summary": "硫唑嘌呤和麦考酚酸酯等常规免疫抑制剂，承接非激素长期维持治疗证据。",
        "patterns": [r"\bazathioprine\b", r"\bmycophenolate\b", r"\bmycophenolic acid\b"],
    },
    {
        "id": "calcineurinInhibitors",
        "title": "Calcineurin Inhibitors",
        "type": "drug",
        "summary": "他克莫司、环孢素等钙调神经磷酸酶抑制剂相关 MG 治疗证据。",
        "patterns": [r"\btacrolimus\b", r"\bcyclosporine\b", r"\bciclosporin\b", r"\bcalcineurin inhibitor"],
    },
    {
        "id": "ivig",
        "title": "IVIg",
        "type": "drug",
        "summary": "静脉注射免疫球蛋白，常用于危象、围手术期和快速救援治疗。",
        "patterns": [r"\bIVIg\b", r"\bintravenous immunoglobulin\b"],
    },
    {
        "id": "plasmaExchange",
        "title": "Plasma Exchange",
        "type": "drug",
        "summary": "血浆置换/血浆分离相关救援治疗节点。",
        "patterns": [r"\bplasma exchange\b", r"\bplasmapheresis\b", r"\bPLEX\b"],
    },
    {
        "id": "mgAdl",
        "title": "MG-ADL",
        "type": "outcome",
        "summary": "MG Activities of Daily Living，是新药研究和真实世界研究常用终点。",
        "patterns": [r"\bMG-ADL\b", r"\bActivities of Daily Living\b"],
    },
    {
        "id": "qmg",
        "title": "QMG",
        "type": "outcome",
        "summary": "Quantitative Myasthenia Gravis score，是 MG 临床研究重要量表。",
        "patterns": [r"\bQMG\b", r"\bQuantitative Myasthenia\b"],
    },
    {
        "id": "mgQol",
        "title": "MG-QOL / QoL",
        "type": "outcome",
        "summary": "生活质量和患者报告结果相关终点。",
        "patterns": [r"\bMG-QOL\b", r"\bquality of life\b", r"\bQoL\b", r"\bpatient-reported\b"],
    },
    {
        "id": "steroidSparing",
        "title": "Steroid-sparing",
        "type": "outcome",
        "summary": "减少糖皮质激素暴露相关结局，常用于真实世界和长期治疗价值讨论。",
        "patterns": [r"\bsteroid-sparing\b", r"\bsteroid sparing\b", r"\bsteroid reduction\b", r"\bglucocorticoid reduction\b"],
    },
    {
        "id": "safetyOutcome",
        "title": "Safety / Adverse Events",
        "type": "outcome",
        "summary": "总体安全性、不良事件、耐受性、免疫原性和药物警戒相关证据。",
        "patterns": [r"\bsafety\b", r"\badverse event", r"\btolerability\b", r"\bpharmacovigilance\b", r"\bFAERS\b"],
    },
    {
        "id": "infectionRisk",
        "title": "Infection Risk",
        "type": "outcome",
        "summary": "感染、机会性感染、脑膜炎球菌风险和免疫抑制相关感染安全性。",
        "patterns": [r"\binfection\b", r"\binfectious\b", r"\bopportunistic infection", r"\bmeningococcal\b"],
    },
    {
        "id": "infusionInjectionReactions",
        "title": "Infusion / Injection Reactions",
        "type": "outcome",
        "summary": "输注反应、注射部位反应、过敏和给药相关耐受性事件。",
        "patterns": [r"\binfusion reaction", r"\binfusion-related", r"\binjection-site", r"\binjection site", r"\bhypersensitivity\b"],
    },
    {
        "id": "rapidOnset",
        "title": "Rapid Onset / Response",
        "type": "outcome",
        "summary": "起效速度、早期应答和症状快速改善相关证据。",
        "patterns": [r"\brapid\b", r"\bearly response\b", r"\bonset\b", r"\bwithin \d+ days\b"],
    },
    {
        "id": "longTermDurability",
        "title": "Long-term Durability",
        "type": "outcome",
        "summary": "长期疗效、维持治疗、多周期治疗和持续应答相关证据。",
        "patterns": [r"\blong-term\b", r"\blong term\b", r"\bdurability\b", r"\bmaintenance\b", r"\bextension study\b"],
    },
    {
        "id": "rctEvidence",
        "title": "RCT Evidence",
        "type": "evidence",
        "summary": "随机对照试验和 III/II 期临床研究证据。",
        "patterns": [r"\brandomi[sz]ed\b", r"\bplacebo-controlled\b", r"\bphase 2\b", r"\bphase 3\b", r"\bRCT\b"],
    },
    {
        "id": "metaEvidence",
        "title": "Meta-analysis / ITC",
        "type": "evidence",
        "summary": "系统综述、meta-analysis、网络 meta 和间接比较证据。",
        "patterns": [r"\bmeta-analysis\b", r"\bsystematic review\b", r"\bnetwork meta\b", r"\bindirect comparison\b", r"\bITC\b"],
    },
    {
        "id": "realWorldEvidence",
        "title": "Real-world Evidence",
        "type": "evidence",
        "summary": "真实世界、队列、注册登记、索赔数据库和观察性研究证据。",
        "patterns": [r"\breal-world\b", r"\breal world\b", r"\bregistry\b", r"\bcohort\b", r"\bobservational\b", r"\bretrospective\b", r"\bclaims\b"],
    },
    {
        "id": "guidelineEvidence",
        "title": "Guideline / Consensus",
        "type": "evidence",
        "summary": "指南、共识和推荐相关证据。",
        "patterns": [r"\bguideline\b", r"\bconsensus\b", r"\brecommendation\b", r"\bguidance\b"],
    },
    {
        "id": "caseEvidence",
        "title": "Case Evidence",
        "type": "evidence",
        "summary": "病例报告和病例系列，适合作为信号线索而非强结论。",
        "patterns": [r"\bcase report\b", r"\bcase series\b"],
    },
    {
        "id": "pharmacovigilanceEvidence",
        "title": "Pharmacovigilance",
        "type": "evidence",
        "summary": "FAERS、药物警戒和安全性数据库分析。",
        "patterns": [r"\bFAERS\b", r"\bpharmacovigilance\b", r"\bdisproportionality\b"],
    },
]


def loadArticles(inputPath: Path) -> tuple[list[dict], str]:
    """读取 full JSON；若 full 不存在，则回退到公开 recent.js。"""
    if inputPath.exists():
        rawData = json.loads(inputPath.read_text(encoding="utf-8"))
        if isinstance(rawData, list):
            return rawData, str(inputPath.relative_to(projectPath))
        if isinstance(rawData, dict):
            articles = rawData.get("articles") or rawData.get("items") or []
            return articles, str(inputPath.relative_to(projectPath))
    if recentJsPath.exists():
        jsText = recentJsPath.read_text(encoding="utf-8")
        match = re.search(r"window\.MG_LITERATURE_DATA\s*=\s*(.*?);\s*(?:window\.MG_TOTAL_COUNT|$)", jsText, re.S)
        if not match:
            raise ValueError("无法解析 data/literature-recent.js")
        return json.loads(match.group(1)), str(recentJsPath.relative_to(projectPath))
    raise FileNotFoundError(f"找不到输入数据: {inputPath}")


def loadJsPayload(path: Path, globalName: str) -> dict:
    """读取前端 JS 产物中的 JSON payload。"""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(globalName)}\s*=\s*(.*?);\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path.relative_to(projectPath)}")
    return json.loads(match.group(1))


def loadCommunityContext() -> dict:
    """读取社区 taxonomy、卡片和 full 级别 assignment 中间产物。"""
    taxonomy = {}
    cardsPayload = {}
    if communityTaxonomyJsPath.exists():
        try:
            taxonomy = loadJsPayload(communityTaxonomyJsPath, "MG_COMMUNITY_TAXONOMY")
        except Exception as exc:
            print(f"⚠️  无法读取 communityTaxonomy.js，图谱社区标题将降级: {exc}", file=sys.stderr)
    if communityCardsJsPath.exists():
        try:
            cardsPayload = loadJsPayload(communityCardsJsPath, "MG_COMMUNITY_CARDS")
        except Exception as exc:
            print(f"⚠️  无法读取 communityCards.js，图谱健康社区计数将降级: {exc}", file=sys.stderr)

    communities = taxonomy.get("communities") or []
    titles = {item.get("id"): item.get("title") or item.get("id") for item in communities if item.get("id")}
    order = [item.get("id") for item in communities if item.get("id")]
    cardCounts = {
        item.get("id"): item.get("article_count") or 0
        for item in (cardsPayload.get("cards") or [])
        if item.get("id")
    }

    assignmentsByPmid = {}
    assignmentSource = "none"
    if communityAssignmentsJsonlPath.exists():
        with communityAssignmentsJsonlPath.open("r", encoding="utf-8") as inputFile:
            for line in inputFile:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                pmid = str(item.get("pmid") or "").strip()
                if pmid:
                    assignmentsByPmid[pmid] = item
        assignmentSource = str(communityAssignmentsJsonlPath.relative_to(projectPath))
    elif communityRecentAssignmentsJsPath.exists():
        try:
            recentPayload = loadJsPayload(communityRecentAssignmentsJsPath, "MG_COMMUNITY_RECENT_ASSIGNMENTS")
            for item in recentPayload.get("items") or []:
                pmid = str(item.get("pmid") or "").strip()
                if pmid:
                    assignmentsByPmid[pmid] = item
            assignmentSource = str(communityRecentAssignmentsJsPath.relative_to(projectPath))
        except Exception as exc:
            print(f"⚠️  无法读取 communityAssignmentsRecent.js，图谱社区映射将为空: {exc}", file=sys.stderr)

    return {
        "taxonomy": taxonomy,
        "community_titles": titles,
        "community_order": order,
        "community_card_counts": cardCounts,
        "assignments_by_pmid": assignmentsByPmid,
        "assignment_source": assignmentSource,
    }


def compilePatterns():
    """预编译概念词典中的正则。"""
    compiled = {}
    for item in conceptDefs:
        compiled[item["id"]] = [re.compile(pattern, re.I) for pattern in item["patterns"]]
    return compiled


def articleText(article: dict) -> str:
    """合并标题、摘要和元数据，作为摘要级抽取输入。"""
    parts = [
        article.get("title") or "",
        article.get("abstract") or "",
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]
    return "\n".join(parts)


def parseYear(article: dict) -> int:
    """从 pub_date 或 entry_date 提取年份。"""
    for key in ("pub_date", "entry_date"):
        value = str(article.get(key) or "")
        match = re.search(r"(19|20)\d{2}", value)
        if match:
            return int(match.group(0))
    return 0


def evidenceScore(article: dict) -> float:
    """根据证据等级、年份和 IF 计算排序分。"""
    level = article.get("evidence_level")
    score = levelScore.get(level or "", 0)
    year = parseYear(article)
    journalIf = article.get("journal_if") or 0
    try:
        journalIf = float(journalIf)
    except (TypeError, ValueError):
        journalIf = 0
    return score * 100 + max(year - 2000, 0) + min(journalIf, 30) / 10


def compactArticle(article: dict) -> dict:
    """压缩前端需要的 PMID 引用字段。"""
    return {
        "pmid": article.get("pmid") or "",
        "title": article.get("title") or "",
        "journal": article.get("journal") or "",
        "pub_date": article.get("pub_date") or "",
        "entry_date": article.get("entry_date") or "",
        "url": article.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}/" if article.get("pmid") else ""),
        "evidence_level": article.get("evidence_level"),
        "study_types": article.get("study_types") or [],
        "pub_types": article.get("pub_types") or [],
        "journal_if": article.get("journal_if"),
        "journal_quartile": article.get("journal_quartile"),
        "china_related": bool(article.get("china_related")),
    }


def latestArticleDate(pmids: list[str], articleByPmid: dict[str, dict]) -> str:
    """返回一组 PMID 中最新的 entry_date / pub_date 原始文本。"""
    latest = None
    latestText = ""
    for pmid in pmids:
        article = articleByPmid.get(pmid) or {}
        rawDate = article.get("entry_date") or article.get("pub_date") or ""
        parsedDate = parseDateValue(rawDate)
        if parsedDate and (latest is None or parsedDate > latest):
            latest = parsedDate
            latestText = rawDate
    return latestText


def matchedConceptIds(article: dict, compiledPatterns: dict[str, list[re.Pattern]]) -> list[str]:
    """返回一篇文献命中的概念节点。"""
    text = articleText(article)
    matched = []
    for conceptId, patterns in compiledPatterns.items():
        if any(pattern.search(text) for pattern in patterns):
            matched.append(conceptId)

    if article.get("china_related") and "chinaEvidence" not in matched:
        matched.append("chinaEvidence")

    studyTypes = " ".join(article.get("study_types") or []).lower()
    pubTypes = " ".join(article.get("pub_types") or []).lower()
    metaText = f"{studyTypes} {pubTypes}"
    metaRules = {
        "rctEvidence": ["rct", "randomized", "randomised", "clinical trial"],
        "metaEvidence": ["itc", "meta-analysis", "systematic review"],
        "realWorldEvidence": ["single arm", "cohort", "observational", "cross-sectional", "real-world"],
        "guidelineEvidence": ["guideline", "consensus", "practice guideline"],
        "caseEvidence": ["case report", "case reports"],
        "pharmacovigilanceEvidence": ["pharmacovigilance"],
    }
    for conceptId, terms in metaRules.items():
        if conceptId not in matched and any(term in metaText for term in terms):
            matched.append(conceptId)

    return matched


def relationLabel(sourceType: str, targetType: str) -> str:
    """基于节点类型给共现边一个可读关系名。"""
    pair = {sourceType, targetType}
    if pair == {"drug", "mechanism"}:
        return "机制关联"
    if "drug" in pair and "population" in pair:
        return "研究人群"
    if "drug" in pair and "outcome" in pair:
        return "报告结局"
    if "drug" in pair and "evidence" in pair:
        return "证据类型"
    if "mechanism" in pair and "population" in pair:
        return "关联人群"
    if "mechanism" in pair and "outcome" in pair:
        return "关联结局"
    if "population" in pair and "outcome" in pair:
        return "人群结局"
    if "disease" in pair and "population" in pair:
        return "亚型/人群"
    if "evidence" in pair:
        return "证据类型"
    return "摘要共现"


def relationSourceType(sourceType: str, targetType: str) -> str:
    """标记关系来源层级。"""
    if "evidence" in {sourceType, targetType}:
        return "metadataConfirmed"
    return "abstractMentioned"


def relationConfidence(articleCount: int, bestLevel: str | None, highLevelCount: int) -> str:
    """用数量和证据等级给摘要级关系打置信标签。"""
    if articleCount >= 12 and highLevelCount >= 2:
        return "high"
    if articleCount >= 5 or bestLevel in {"I", "II"}:
        return "medium"
    return "low"


def buildGraph(articles: list[dict], communityContext: dict | None = None) -> dict:
    """生成节点、边、证据矩阵和引用索引。"""
    communityContext = communityContext or {}
    compiledPatterns = compilePatterns()
    conceptsById = {item["id"]: item for item in conceptDefs}
    nodeArticleIds = defaultdict(list)
    edgeArticleIds = defaultdict(list)
    articleByPmid = {}

    for article in articles:
        pmid = str(article.get("pmid") or "").strip()
        if not pmid:
            continue
        matchedIds = matchedConceptIds(article, compiledPatterns)
        matchedIds = [item for item in matchedIds if item in conceptsById]
        if "myastheniaGravis" not in matchedIds:
            continue
        if len(matchedIds) < 2:
            continue

        articleByPmid[pmid] = article
        for conceptId in matchedIds:
            nodeArticleIds[conceptId].append(pmid)

        uniqueIds = sorted(set(matchedIds))
        for index, sourceId in enumerate(uniqueIds):
            for targetId in uniqueIds[index + 1:]:
                sourceType = conceptsById[sourceId]["type"]
                targetType = conceptsById[targetId]["type"]
                if sourceType == "evidence" and targetType == "evidence":
                    continue
                edgeKey = tuple(sorted((sourceId, targetId)))
                edgeArticleIds[edgeKey].append(pmid)

    includedIds = [
        conceptId
        for conceptId, pmids in nodeArticleIds.items()
        if len(set(pmids)) >= minNodeArticles(conceptsById[conceptId]["type"])
    ]
    includedIds = sorted(set(includedIds), key=lambda item: (-len(set(nodeArticleIds[item])), item))

    nodes = []
    for conceptId in includedIds:
        concept = conceptsById[conceptId]
        pmids = uniqueList(nodeArticleIds[conceptId])
        refs = topReferences(pmids, articleByPmid, limit=8)
        levels = Counter((articleByPmid[pmid].get("evidence_level") or "未分级") for pmid in pmids if pmid in articleByPmid)
        studyTypes = Counter()
        for pmid in pmids:
            for studyType in articleByPmid.get(pmid, {}).get("study_types") or []:
                studyTypes[studyType] += 1
        nodes.append({
            "id": conceptId,
            "title": concept["title"],
            "type": concept["type"],
            "summary": concept["summary"],
            "article_count": len(pmids),
            "evidence_levels": dict(sorted(levels.items(), key=lambda item: levelRank.get(item[0], 99))),
            "top_study_types": [item[0] for item in studyTypes.most_common(4)],
            "confidence": nodeConfidence(len(pmids), levels),
            "source_type": "abstractMentioned",
            "updated": latestArticleDate(pmids, articleByPmid),
        })

    includedSet = {node["id"] for node in nodes}
    edges = []
    for edgeKey, pmidsRaw in edgeArticleIds.items():
        sourceId, targetId = edgeKey
        if sourceId not in includedSet or targetId not in includedSet:
            continue
        pmids = uniqueList(pmidsRaw)
        if len(pmids) < minEdgeArticles(conceptsById[sourceId]["type"], conceptsById[targetId]["type"]):
            continue
        refs = topReferences(pmids, articleByPmid, limit=6)
        bestLevel = bestEvidenceLevel(pmids, articleByPmid)
        highLevelCount = sum(1 for pmid in pmids if articleByPmid.get(pmid, {}).get("evidence_level") in {"I", "II"})
        sourceType = conceptsById[sourceId]["type"]
        targetType = conceptsById[targetId]["type"]
        edges.append({
            "id": f"{sourceId}__{targetId}",
            "from": sourceId,
            "to": targetId,
            "relation": relationLabel(sourceType, targetType),
            "source_type": relationSourceType(sourceType, targetType),
            "confidence": relationConfidence(len(pmids), bestLevel, highLevelCount),
            "article_count": len(pmids),
            "best_evidence_level": bestLevel or "未分级",
            "evidence_score": round(sum(evidenceScore(articleByPmid[pmid]) for pmid in pmids if pmid in articleByPmid), 1),
            "pmids": [ref["pmid"] for ref in refs],
        })

    allEdges = sorted(edges, key=lambda item: (-item["evidence_score"], -item["article_count"], item["from"], item["to"]))
    nonEvidenceEdges = [
        edge for edge in allEdges
        if conceptsById[edge["from"]]["type"] != "evidence" and conceptsById[edge["to"]]["type"] != "evidence"
    ][:120]
    evidenceEdges = [
        edge for edge in allEdges
        if conceptsById[edge["from"]]["type"] == "evidence" or conceptsById[edge["to"]]["type"] == "evidence"
    ][:25]
    priorityEdges = []
    for nodeId in priorityNodeIds:
        nodeEdges = [
            edge for edge in allEdges
            if nodeId in {edge["from"], edge["to"]}
            and conceptsById[edge["from"]]["type"] != "evidence"
            and conceptsById[edge["to"]]["type"] != "evidence"
        ][:priorityEdgeLimit(nodeId)]
        priorityEdges.extend(nodeEdges)
    selectedEdges = uniqueEdges(nonEvidenceEdges + priorityEdges + evidenceEdges)
    coverageEdges = coverageEdgesForNodes(includedIds, selectedEdges, allEdges, conceptsById)
    bridgeEdges = semanticBridgeEdgesForNodes(includedIds, selectedEdges + coverageEdges, allEdges, conceptsById)
    coreEdges = uniqueEdges(selectedEdges + coverageEdges + bridgeEdges)
    coreEdges = sorted(coreEdges, key=lambda item: (-item["evidence_score"], -item["article_count"], item["from"], item["to"]))
    coreEdgeIds = {edge["id"] for edge in coreEdges}
    allEdgeIds = {edge["id"] for edge in allEdges}
    for edge in allEdges:
        edge["in_core_graph"] = edge["id"] in coreEdgeIds
    nodeReferences = {node["id"]: topReferences(uniqueList(nodeArticleIds[node["id"]]), articleByPmid, limit=10) for node in nodes}
    edgeReferences = {
        edge["id"]: topReferences(uniqueList(edgeArticleIds[tuple(sorted((edge["from"], edge["to"]))) ]), articleByPmid, limit=8)
        for edge in allEdges
    }

    annotateCommunityLayer(nodes, allEdges, nodeArticleIds, edgeArticleIds, communityContext)
    applyLayout(nodes)
    matrixRows = buildEvidenceMatrix(allEdges, nodeReferences, edgeReferences, conceptsById, allEdgeIds)
    stats = buildStats(articles, nodes, coreEdges, matrixRows, articleByPmid, allEdges)
    stats["community_assignment_source"] = communityContext.get("assignment_source") or "none"

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "full PubMed abstract library",
        "stats": stats,
        "nodes": nodes,
        "edges": coreEdges,
        "all_edges": allEdges,
        "node_references": nodeReferences,
        "edge_references": edgeReferences,
        "evidence_matrix": matrixRows,
    }


def minNodeArticles(nodeType: str) -> int:
    """不同节点类型设置不同最低文献量，保留稀有但重要的新药。"""
    return {
        "disease": 1,
        "drug": 2,
        "mechanism": 5,
        "population": 5,
        "outcome": 4,
        "evidence": 8,
    }.get(nodeType, 5)


def priorityEdgeLimit(nodeId: str) -> int:
    """重点新增节点保留更多上下文边，避免前端看起来像孤立点。"""
    if nodeId in {"telitacicept", "baffAprilModulation"}:
        return 16
    return 10


def minGraphDegree(nodeType: str) -> int:
    """前端图谱最少可见边数，防止重要节点被边裁剪成孤点。"""
    if nodeType == "evidence":
        return 2
    return 4


def requiredSemanticBridgeTypes(nodeType: str) -> tuple[str, ...]:
    """需要优先保留药物/机制桥接的节点类型。"""
    if nodeType in {"evidence", "outcome", "population"}:
        return ("drug", "mechanism")
    return ()


def semanticBridgeEdgesForNodes(includedIds: list[str], selectedEdges: list[dict], allEdges: list[dict], conceptsById: dict) -> list[dict]:
    """为证据、结局和人群节点补足药物/机制桥接边。"""
    selectedIds = {edge["id"] for edge in selectedEdges}
    linkedTargetTypes = defaultdict(set)
    includedSet = set(includedIds)

    for edge in selectedEdges:
        sourceId = edge["from"]
        targetId = edge["to"]
        sourceType = conceptsById[sourceId]["type"]
        targetType = conceptsById[targetId]["type"]
        if targetType in requiredSemanticBridgeTypes(sourceType):
            linkedTargetTypes[sourceId].add(targetType)
        if sourceType in requiredSemanticBridgeTypes(targetType):
            linkedTargetTypes[targetId].add(sourceType)

    bridgeEdges = []
    for nodeId in includedIds:
        requiredTypes = requiredSemanticBridgeTypes(conceptsById[nodeId]["type"])
        if not requiredTypes:
            continue
        missingTypes = [targetType for targetType in requiredTypes if targetType not in linkedTargetTypes[nodeId]]
        for targetType in missingTypes:
            for edge in allEdges:
                if edge["id"] in selectedIds or nodeId not in {edge["from"], edge["to"]}:
                    continue
                otherId = edge["to"] if edge["from"] == nodeId else edge["from"]
                if otherId not in includedSet or conceptsById[otherId]["type"] != targetType:
                    continue
                bridgeEdges.append(edge)
                selectedIds.add(edge["id"])
                linkedTargetTypes[nodeId].add(targetType)
                break
    return bridgeEdges


def coverageEdgesForNodes(includedIds: list[str], selectedEdges: list[dict], allEdges: list[dict], conceptsById: dict) -> list[dict]:
    """为低连接节点补充最高分关系边。"""
    selectedIds = {edge["id"] for edge in selectedEdges}
    degree = Counter()
    for edge in selectedEdges:
        degree[edge["from"]] += 1
        degree[edge["to"]] += 1

    coverageEdges = []
    for nodeId in includedIds:
        targetDegree = minGraphDegree(conceptsById[nodeId]["type"])
        if degree[nodeId] >= targetDegree:
            continue
        for edge in allEdges:
            if edge["id"] in selectedIds or nodeId not in {edge["from"], edge["to"]}:
                continue
            coverageEdges.append(edge)
            selectedIds.add(edge["id"])
            degree[edge["from"]] += 1
            degree[edge["to"]] += 1
            if degree[nodeId] >= targetDegree:
                break
    return coverageEdges


def minEdgeArticles(sourceType: str, targetType: str) -> int:
    """边的最低文献量，药物相关边允许更低以保留管线信号。"""
    if "drug" in {sourceType, targetType}:
        return 2
    if "evidence" in {sourceType, targetType}:
        return 5
    return 4


def uniqueList(items: list[str]) -> list[str]:
    """保序去重。"""
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def communityProfileForPmids(pmids: list[str], communityContext: dict) -> dict:
    """根据 PMID assignment 计算节点或边的 dominant community。"""
    assignmentsByPmid = communityContext.get("assignments_by_pmid") or {}
    titles = communityContext.get("community_titles") or {}
    uniquePmids = uniqueList([str(pmid) for pmid in pmids if pmid])
    counter = Counter()
    for pmid in uniquePmids:
        assignment = assignmentsByPmid.get(pmid) or {}
        primary = assignment.get("primary")
        if primary and primary != "unassigned":
            counter[primary] += 1

    total = len(uniquePmids)
    mapped = sum(counter.values())
    if not counter:
        return {
            "dominant_community_id": None,
            "dominant_community_title": "",
            "community_profile": [],
            "community_mapped_articles": 0,
            "community_coverage_ratio": 0,
            "community_confidence": "unmapped",
        }

    topId, topCount = counter.most_common(1)[0]
    dominantShare = topCount / max(mapped, 1)
    confidence = "high" if topCount >= 10 and dominantShare >= 0.45 else "medium" if topCount >= 3 else "low"
    profile = [
        {
            "community_id": communityId,
            "title": titles.get(communityId, communityId),
            "count": count,
            "mapped_ratio": round(count / max(mapped, 1), 3),
            "total_ratio": round(count / max(total, 1), 3),
        }
        for communityId, count in counter.most_common(4)
    ]
    return {
        "dominant_community_id": topId,
        "dominant_community_title": titles.get(topId, topId),
        "community_profile": profile,
        "community_mapped_articles": mapped,
        "community_coverage_ratio": round(mapped / max(total, 1), 3),
        "community_confidence": confidence,
    }


def annotateCommunityLayer(nodes: list[dict], edges: list[dict], nodeArticleIds: dict, edgeArticleIds: dict, communityContext: dict) -> None:
    """把社区语义层写回图谱节点和关系。"""
    for node in nodes:
        node.update(communityProfileForPmids(nodeArticleIds.get(node["id"], []), communityContext))
    for edge in edges:
        edgeKey = tuple(sorted((edge["from"], edge["to"])))
        edge.update(communityProfileForPmids(edgeArticleIds.get(edgeKey, []), communityContext))


def topReferences(pmids: list[str], articleByPmid: dict[str, dict], limit: int) -> list[dict]:
    """为节点或关系选出最值得前端展示的 PMID。"""
    refs = [articleByPmid[pmid] for pmid in pmids if pmid in articleByPmid]
    refs.sort(key=evidenceScore, reverse=True)
    return [compactArticle(article) for article in refs[:limit]]


def bestEvidenceLevel(pmids: list[str], articleByPmid: dict[str, dict]) -> str | None:
    """返回一组 PMID 中最高证据等级。"""
    levels = [articleByPmid[pmid].get("evidence_level") for pmid in pmids if articleByPmid.get(pmid, {}).get("evidence_level")]
    if not levels:
        return None
    return sorted(levels, key=lambda level: levelRank.get(level, 99))[0]


def nodeConfidence(articleCount: int, levels: Counter) -> str:
    """节点置信度只代表摘要库覆盖厚度，不代表结论强度。"""
    highLevelCount = sum(levels.get(level, 0) for level in ("I", "II"))
    if articleCount >= 40 and highLevelCount >= 3:
        return "high"
    if articleCount >= 12 or highLevelCount >= 1:
        return "medium"
    return "low"


def applyLayout(nodes: list[dict]) -> None:
    """按节点类型分簇生成稳定 SVG 坐标。"""
    clusterCenters = {
        "disease": (550, 350),
        "drug": (230, 360),
        "mechanism": (550, 145),
        "population": (850, 330),
        "outcome": (560, 585),
        "evidence": (900, 560),
    }
    clusterRadius = {
        "disease": 42,
        "drug": 170,
        "mechanism": 140,
        "population": 150,
        "outcome": 135,
        "evidence": 105,
    }
    byType = defaultdict(list)
    for node in nodes:
        byType[node["type"]].append(node)
    for nodeType, items in byType.items():
        items.sort(key=lambda item: (-item["article_count"], item["title"]))
        centerX, centerY = clusterCenters.get(nodeType, (550, 350))
        radius = clusterRadius.get(nodeType, 120)
        if len(items) == 1:
            items[0]["x"] = centerX
            items[0]["y"] = centerY
            continue
        for index, node in enumerate(items):
            angle = (2 * math.pi * index / len(items)) - math.pi / 2
            localRadius = 0 if nodeType == "disease" and index == 0 else radius * (0.52 + 0.48 * ((index % 3) / 2))
            node["x"] = round(centerX + localRadius * math.cos(angle), 1)
            node["y"] = round(centerY + localRadius * math.sin(angle), 1)


def buildEvidenceMatrix(edges: list[dict], nodeReferences: dict, edgeReferences: dict, conceptsById: dict, edgeIds: set[str]) -> list[dict]:
    """把图谱关系转为可筛选的证据矩阵。"""
    rows = []
    for edge in edges:
        if edge["id"] not in edgeIds:
            continue
        sourceId, targetId = normalizeMatrixDirection(edge["from"], edge["to"], conceptsById)
        source = conceptsById[sourceId]
        target = conceptsById[targetId]
        if "evidence" in {source["type"], target["type"]}:
            continue
        if {source["type"], target["type"]} == {"disease", "mechanism"}:
            continue
        if {source["type"], target["type"]} == {"disease", "outcome"}:
            continue
        if {source["type"], target["type"]} == {"disease", "drug"} and edge["article_count"] > 120:
            continue
        refs = edgeReferences.get(edge["id"], [])
        rows.append({
            "id": edge["id"],
            "source": source["title"],
            "source_id": sourceId,
            "source_type": source["type"],
            "target": target["title"],
            "target_id": targetId,
            "target_type": target["type"],
            "relation": edge["relation"],
            "source_level": edge["source_type"],
            "confidence": edge["confidence"],
            "article_count": edge["article_count"],
            "best_evidence_level": edge["best_evidence_level"],
            "key_pmids": [ref["pmid"] for ref in refs[:4]],
            "references": refs[:4],
            "dominant_community_id": edge.get("dominant_community_id"),
            "dominant_community_title": edge.get("dominant_community_title"),
            "community_profile": edge.get("community_profile") or [],
            "community_ids": [item["community_id"] for item in edge.get("community_profile") or []],
            "limitation": "基于 PubMed 标题/摘要和元数据共现；疗效数值、亚组与安全性发生率需阅读全文确认。",
        })
    rows.sort(key=lambda item: (
        item["source_type"] != "drug",
        levelRank.get(item["best_evidence_level"], 99),
        -item["article_count"],
    ))
    return rows[:180]


def uniqueEdges(items: list[dict]) -> list[dict]:
    """保序去重边。"""
    seen = set()
    output = []
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        output.append(item)
    return output


def normalizeMatrixDirection(sourceId: str, targetId: str, conceptsById: dict) -> tuple[str, str]:
    """让矩阵行按更符合阅读习惯的方向展示。"""
    priority = {
        "drug": 0,
        "mechanism": 1,
        "population": 2,
        "outcome": 3,
        "disease": 4,
        "evidence": 5,
    }
    sourceType = conceptsById[sourceId]["type"]
    targetType = conceptsById[targetId]["type"]
    if priority.get(sourceType, 9) <= priority.get(targetType, 9):
        return sourceId, targetId
    return targetId, sourceId


def buildStats(articles: list[dict], nodes: list[dict], graphEdges: list[dict], matrixRows: list[dict], articleByPmid: dict, allEdges: list[dict] | None = None) -> dict:
    """生成页面顶栏统计。"""
    allEdges = allEdges or graphEdges
    evidenceArticles = [article for article in articleByPmid.values() if article.get("evidence_level")]
    highEvidence = [article for article in evidenceArticles if article.get("evidence_level") in {"I", "II"}]
    latestEntry = max((str(article.get("entry_date") or "") for article in articleByPmid.values()), default="")
    return {
        "total_articles": len(articles),
        "matched_articles": len(articleByPmid),
        "evidence_articles": len(evidenceArticles),
        "high_evidence_articles": len(highEvidence),
        "total_nodes": len(nodes),
        "edges": len(graphEdges),
        "graph_edges": len(graphEdges),
        "all_edges": len(allEdges),
        "evidence_matrix_rows": len(matrixRows),
        "community_mapped_nodes": sum(1 for node in nodes if node.get("dominant_community_id")),
        "community_mapped_edges": sum(1 for edge in allEdges if edge.get("dominant_community_id")),
        "community_mapped_graph_edges": sum(1 for edge in graphEdges if edge.get("dominant_community_id")),
        "latest_entry_date": latestEntry,
        "abstract_source": True,
    }


def parseDateValue(value: str | None):
    """宽松解析 entry_date / pub_date，用于图谱健康度。"""
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


def buildGraphHealth(graphData: dict, communityContext: dict) -> dict:
    """生成图谱健康度摘要，供数据状态页和后续诊治格局读取。"""
    nodes = graphData.get("nodes") or []
    graphEdges = graphData.get("edges") or []
    edges = graphData.get("all_edges") or graphEdges
    stats = graphData.get("stats") or {}
    matchedArticles = stats.get("matched_articles") or 0
    communityTitles = communityContext.get("community_titles") or {}
    communityOrder = communityContext.get("community_order") or []
    cardCounts = communityContext.get("community_card_counts") or {}
    nodesById = {node["id"]: node for node in nodes}

    nodeCommunityCounts = Counter(node.get("dominant_community_id") for node in nodes if node.get("dominant_community_id"))
    edgeCommunityCounts = Counter(edge.get("dominant_community_id") for edge in edges if edge.get("dominant_community_id"))
    nodeDegree = Counter()
    semanticBridgeTypes = defaultdict(set)
    for edge in edges:
        nodeDegree[edge["from"]] += 1
        nodeDegree[edge["to"]] += 1
        source = nodesById.get(edge["from"])
        target = nodesById.get(edge["to"])
        if not source or not target:
            continue
        if target["type"] in requiredSemanticBridgeTypes(source["type"]):
            semanticBridgeTypes[source["id"]].add(target["type"])
        if source["type"] in requiredSemanticBridgeTypes(target["type"]):
            semanticBridgeTypes[target["id"]].add(source["type"])

    oversizedNodes = [
        {
            "node_id": node["id"],
            "title": node["title"],
            "type": node["type"],
            "article_count": node.get("article_count") or 0,
            "corpus_ratio": round((node.get("article_count") or 0) / max(matchedArticles, 1), 3),
            "dominant_community_id": node.get("dominant_community_id"),
            "dominant_community_title": node.get("dominant_community_title"),
        }
        for node in nodes
        if node.get("type") != "disease" and (node.get("article_count") or 0) / max(matchedArticles, 1) >= 0.18
    ]
    oversizedNodes.sort(key=lambda item: item["article_count"], reverse=True)

    weakEdges = [
        {
            "edge_id": edge["id"],
            "from": edge["from"],
            "to": edge["to"],
            "relation": edge.get("relation"),
            "article_count": edge.get("article_count") or 0,
            "confidence": edge.get("confidence"),
            "dominant_community_id": edge.get("dominant_community_id"),
            "dominant_community_title": edge.get("dominant_community_title"),
        }
        for edge in edges
        if edge.get("confidence") == "low" or (edge.get("article_count") or 0) <= 3
    ]
    weakEdges.sort(key=lambda item: (item["article_count"], item["edge_id"]))

    isolatedNodes = [
        {
            "node_id": node["id"],
            "title": node["title"],
            "type": node["type"],
            "article_count": node.get("article_count") or 0,
            "dominant_community_id": node.get("dominant_community_id"),
            "dominant_community_title": node.get("dominant_community_title"),
        }
        for node in nodes
        if nodeDegree[node["id"]] == 0
    ]
    isolatedNodes.sort(key=lambda item: (-item["article_count"], item["node_id"]))

    lowConnectivityNodes = [
        {
            "node_id": node["id"],
            "title": node["title"],
            "type": node["type"],
            "degree": nodeDegree[node["id"]],
            "article_count": node.get("article_count") or 0,
            "dominant_community_id": node.get("dominant_community_id"),
            "dominant_community_title": node.get("dominant_community_title"),
        }
        for node in nodes
        if 0 < nodeDegree[node["id"]] < minGraphDegree(node["type"])
    ]
    lowConnectivityNodes.sort(key=lambda item: (item["degree"], -item["article_count"], item["node_id"]))

    semanticBridgeGaps = [
        {
            "node_id": node["id"],
            "title": node["title"],
            "type": node["type"],
            "missing_target_types": [
                targetType
                for targetType in requiredSemanticBridgeTypes(node["type"])
                if targetType not in semanticBridgeTypes[node["id"]]
            ],
            "article_count": node.get("article_count") or 0,
            "dominant_community_id": node.get("dominant_community_id"),
            "dominant_community_title": node.get("dominant_community_title"),
        }
        for node in nodes
        if requiredSemanticBridgeTypes(node["type"])
    ]
    semanticBridgeGaps = [item for item in semanticBridgeGaps if item["missing_target_types"]]
    semanticBridgeGaps.sort(key=lambda item: (-item["article_count"], item["node_id"]))

    staleCutoff = datetime.now() - timedelta(days=365)
    staleNodes = []
    for node in nodes:
        updated = parseDateValue(node.get("updated"))
        if updated and updated < staleCutoff:
            staleNodes.append({
                "node_id": node["id"],
                "title": node["title"],
                "type": node["type"],
                "updated": node.get("updated") or "",
                "dominant_community_id": node.get("dominant_community_id"),
                "dominant_community_title": node.get("dominant_community_title"),
            })
    staleNodes.sort(key=lambda item: item["updated"])

    communityCoverage = []
    for communityId in communityOrder:
        communityCoverage.append({
            "community_id": communityId,
            "title": communityTitles.get(communityId, communityId),
            "article_count": cardCounts.get(communityId, 0),
            "dominant_node_count": nodeCommunityCounts.get(communityId, 0),
            "dominant_edge_count": edgeCommunityCounts.get(communityId, 0),
        })
    communityCoverage.sort(key=lambda item: (-item["dominant_node_count"], -item["dominant_edge_count"], item["title"]))

    unmappedNodes = [node for node in nodes if not node.get("dominant_community_id")]
    unmappedEdges = [edge for edge in edges if not edge.get("dominant_community_id")]
    return {
        "generated_at": graphData.get("generated_at"),
        "method": "communityAnnotatedAbstractGraph",
        "assignment_source": communityContext.get("assignment_source") or "none",
        "summary": {
            "total_nodes": len(nodes),
            "community_mapped_nodes": len(nodes) - len(unmappedNodes),
            "unmapped_nodes": len(unmappedNodes),
            "total_edges": len(edges),
            "graph_edges": len(graphEdges),
            "community_mapped_edges": len(edges) - len(unmappedEdges),
            "community_mapped_graph_edges": sum(1 for edge in graphEdges if edge.get("dominant_community_id")),
            "unmapped_edges": len(unmappedEdges),
            "oversized_nodes": len(oversizedNodes),
            "weak_edges": len(weakEdges),
            "isolated_nodes": len(isolatedNodes),
            "low_connectivity_nodes": len(lowConnectivityNodes),
            "semantic_bridge_gaps": len(semanticBridgeGaps),
            "stale_nodes": len(staleNodes),
        },
        "health": {
            "status": "needsReview" if oversizedNodes or unmappedNodes or isolatedNodes or semanticBridgeGaps else "ok",
            "notes": [
                "图谱为 abstract-level 关系，社区映射来自后台 community assignment，不代表全文级因果关系。",
                "过大节点、孤立节点、语义桥接缺口或弱边提示概念词典、边裁剪或社区边界需要 review。",
            ],
        },
        "oversized_nodes": oversizedNodes[:10],
        "isolated_nodes": isolatedNodes[:12],
        "low_connectivity_nodes": lowConnectivityNodes[:12],
        "semantic_bridge_gaps": semanticBridgeGaps[:12],
        "weak_edges": weakEdges[:12],
        "stale_nodes": staleNodes[:12],
        "community_coverage": communityCoverage,
        "unmapped_node_samples": [
            {
                "node_id": node["id"],
                "title": node["title"],
                "type": node["type"],
                "article_count": node.get("article_count") or 0,
            }
            for node in sorted(unmappedNodes, key=lambda item: -(item.get("article_count") or 0))[:10]
        ],
    }


def writeJs(data: dict, outputPath: Path, sourceLabel: str) -> None:
    """写出前端可直接加载的 JS 数据文件。"""
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* AUTO-GENERATED by scripts/build-knowledge-data.py\n"
        f" * 来源: {sourceLabel}\n"
        f" * 生成时间: {data['generated_at']}\n"
        " * 说明: 基于 PubMed abstract 和元数据派生，非全文级结论。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    outputPath.write_text(header + f"window.MG_KNOWLEDGE_GRAPH = {payload};\n", encoding="utf-8")
    print(f"✅ 已生成 {outputPath.relative_to(projectPath)} ({outputPath.stat().st_size // 1024} KB)")


def writeGraphHealthJs(data: dict) -> None:
    """写出图谱健康度前端产物。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* AUTO-GENERATED by scripts/build-knowledge-data.py\n"
        f" * 生成时间: {data.get('generated_at', '')}\n"
        " * 说明: 图谱健康度和社区覆盖摘要，供数据状态页和诊治格局使用。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    graphHealthJsPath.write_text(header + f"window.MG_GRAPH_HEALTH = {payload};\n", encoding="utf-8")
    print(f"✅ 已生成 {graphHealthJsPath.relative_to(projectPath)} ({graphHealthJsPath.stat().st_size // 1024} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=str(defaultInputPath), help="输入 full PubMed JSON，默认 data/literature-full.json")
    parser.add_argument("--out", default=str(defaultOutputPath), help="输出 .js 路径")
    args = parser.parse_args()

    inputPath = Path(args.input)
    if not inputPath.is_absolute():
        inputPath = projectPath / inputPath
    outputPath = Path(args.out)
    if not outputPath.is_absolute():
        outputPath = projectPath / outputPath

    try:
        articles, sourceLabel = loadArticles(inputPath)
        communityContext = loadCommunityContext()
        graphData = buildGraph(articles, communityContext)
        graphHealth = buildGraphHealth(graphData, communityContext)
        writeJs(graphData, outputPath, sourceLabel)
        writeGraphHealthJs(graphHealth)
        stats = graphData["stats"]
        print(
            "   文献: {matched}/{total} 命中 · 节点: {nodes} · 关系: {allEdges}/{graphEdges} 全量/主图 · 矩阵: {matrix} · 社区节点: {communityNodes}".format(
                matched=stats["matched_articles"],
                total=stats["total_articles"],
                nodes=stats["total_nodes"],
                allEdges=stats.get("all_edges", stats["edges"]),
                graphEdges=stats.get("graph_edges", stats["edges"]),
                matrix=stats["evidence_matrix_rows"],
                communityNodes=stats.get("community_mapped_nodes", 0),
            )
        )
        return 0
    except Exception as exc:
        print(f"❌ 知识库数据生成失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
