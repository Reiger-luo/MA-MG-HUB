#!/usr/bin/env python3
"""
build-frontend-data.py — 生成 MA-MG-HUB 前端数据产物。

本脚本只读取公开 PubMed 文献数据，输出 GitHub Pages 可加载的 .js 文件。
敏感的专家内部标签、拜访记录不在这里生成，也不进入公开仓库。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - GitHub Actions 会安装 requests
    requests = None


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
FULL_PATH = DATA_DIR / "literature-full.json"
RECENT_JS_PATH = DATA_DIR / "literature-recent.js"
RECENT_JSON_CACHE_PATH = DATA_DIR / "literature-recent.json"
EXPERT_JS_PATH = DATA_DIR / "expert-profiles.js"
AUTHOR_INSTITUTION_INDEX_PATH = DATA_DIR / "pubmed-author-institution-index.json"
CHINA_REGULATORY_PATH = DATA_DIR / "china-regulatory-status.json"
CLINICALTRIALS_CACHE_PATH = DATA_DIR / "clinicaltrials-pipeline-cache.json"
EXPERT_PROFILE_LIMIT = 100

CHINA_PROFILE_TERMS = [
    "china", "chinese", "people's republic of china", "pr china",
    "hong kong", "macau", "taiwan",
    "beijing", "shanghai", "guangzhou", "shenzhen", "nanjing", "tianjin",
    "xian", "xi'an", "changsha", "wuhan", "jinan", "chengdu", "chongqing",
    "hangzhou", "xuzhou", "zhengzhou", "harbin", "qingdao", "xiamen",
    "kunming", "nanchang", "fuzhou", "suzhou", "wenzhou", "ningbo",
    "fudan", "peking", "tsinghua", "xiangya", "huashan", "xuanwu",
    "tangdu", "tongji", "west china", "sun yat-sen", "capital medical",
    "zhejiang university", "sichuan university", "shandong", "henan",
    "jiangsu", "hunan", "hubei", "guangdong", "pla general",
]

STOPWORDS = {
    "with", "from", "into", "using", "study", "case", "report", "review",
    "myasthenia", "gravis", "patients", "patient", "clinical", "disease",
    "treatment", "therapy", "analysis", "associated", "among", "after",
    "before", "during", "based", "results", "outcome", "outcomes",
    "china", "chinese", "generalized", "generalised", "mg",
}

TOPIC_DEFS = [
    ("FcRn", ["fcrn", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"]),
    ("补体", ["complement", "zilucoplan", "ravulizumab", "eculizumab", "c5 inhibitor"]),
    ("B细胞", ["b cell", "b-cell", "rituximab", "inebilizumab", "telitacicept", "blys", "april", "cd20", "cd19"]),
    ("抗体分型", ["seronegative", "musk", "achr", "lrp4", "autoantibody"]),
    ("真实世界", ["real-world", "registry", "observational", "retrospective", "control", "comparison", "comparative", "parallel", "comparator"]),
    ("安全性", ["safety", "adverse", "infection", "tolerability"]),
    ("疗效", ["efficacy", "outcome", "improvement", "response"]),
    ("机制", ["pathogenesis", "mechanism", "biomarker", "cytokine", "receptor"]),
    ("诊疗策略", ["guideline", "consensus", "recommendation", "treatment strategy"]),
]

DRUG_KEYWORDS = {
    "Efgartigimod": ["efgartigimod", "vyvgart"],
    "Rozanolixizumab": ["rozanolixizumab"],
    "Ravulizumab": ["ravulizumab"],
    "Eculizumab": ["eculizumab"],
    "Zilucoplan": ["zilucoplan"],
    "Nipocalimab": ["nipocalimab"],
    "Batoclimab": ["batoclimab"],
    "Telitacicept": ["telitacicept", "rc18", "rc-18"],
    "Rituximab": ["rituximab"],
}

SIGNAL_CORE_TOPICS = {"FcRn", "补体", "B细胞", "抗体分型", "真实世界", "安全性", "疗效", "机制", "诊疗策略"}
CASE_REPORT_TERMS = ["case report", "case reports", "case series"]
SAFETY_TERMS = [
    "adverse", "safety", "toxicity", "infection", "hepatitis", "liver failure",
    "myocarditis", "respiratory failure", "crisis", "fatal", "death", "severe",
]
RWE_TERMS = ["real-world", "real world", "retrospective", "observational", "registry", "cohort"]
HIGH_VALUE_TERMS = [
    "guideline", "consensus", "recommendation", "meta-analysis", "systematic review",
    "randomized", "randomised", "trial", "phase 2", "phase 3", "real-world",
    "registry", "biomarker", "pathogenesis", "mechanism",
]
LOW_VALUE_SIGNAL_TERMS = [
    "retraction:",
    "retracted article",
    "author's response",
    "response to comment",
    "comment on",
]

PIPELINE = [
    {"name": "Efgartigimod", "target": "FcRn", "route": "IV/SC", "status": "已上市", "owner": "argenx"},
    {"name": "Rozanolixizumab", "target": "FcRn", "route": "SC", "status": "已上市", "owner": "UCB"},
    {"name": "Nipocalimab", "target": "FcRn", "route": "IV", "status": "临床后期", "owner": "Johnson & Johnson"},
    {"name": "Batoclimab", "target": "FcRn", "route": "SC", "status": "临床开发", "owner": "Immunovant / Harbour"},
    {"name": "Zilucoplan", "target": "C5", "route": "SC", "status": "已上市", "owner": "UCB"},
    {"name": "Ravulizumab", "target": "C5", "route": "IV", "status": "已上市", "owner": "Alexion"},
    {"name": "Eculizumab", "target": "C5", "route": "IV", "status": "已上市", "owner": "Alexion"},
    {"name": "Telitacicept", "target": "BLyS/APRIL", "route": "SC", "status": "中国已上市", "owner": "RemeGen"},
    {"name": "Rituximab", "target": "CD20", "route": "IV", "status": "超说明书/研究", "owner": "Multiple"},
    {"name": "Inebilizumab", "target": "CD19", "route": "IV", "status": "研究线索", "owner": "Amgen"},
]

LANDSCAPE_CHANGE_SPECS = [
    {
        "id": "fcrn_response",
        "type": "机制与疗效",
        "title": "FcRn 疗效异质性更适合被机制化解释",
        "keywords": ["fcrn", "response", "autoantibody", "biomarker", "efgartigimod"],
        "why": "新增抗体功能、亚组或 response 相关 abstract 让 MSL 可以把“为什么有人反应不同”从经验问题转成机制问题。",
        "position": "AChR+ gMG、疗效预测、专家深访",
        "narrative": "机制沟通、疗效异质性、精准用药",
        "msl_action": "准备抗体分型、response 预测和 efgartigimod 机制相关 PMID。",
    },
    {
        "id": "china_rwe",
        "type": "中国证据",
        "title": "中国真实世界证据继续补足靶向治疗落地叙事",
        "keywords": ["china", "chinese", "real-world", "efgartigimod", "myasthenia"],
        "why": "中国 RWE 让证据沟通从国际 RCT 外推，逐步转向本土患者、用药路径和可及性讨论。",
        "position": "中国 gMG、RWE、准入与专家拜访",
        "narrative": "本土证据链、临床可及性、真实世界使用",
        "msl_action": "优先整理中国 RWE PMID，并标出终点定义和 AE 采集方式。",
    },
    {
        "id": "complement_competition",
        "type": "竞争定位",
        "title": "补体与 FcRn 的比较叙事继续升温",
        "keywords": ["complement", "fcrn", "efficacy", "safety", "comparison"],
        "why": "系统综述、NMA 或间接比较会直接影响 AChR+ gMG 靶向治疗的定位话术。",
        "position": "AChR+ gMG、靶向治疗选择",
        "narrative": "机制区隔、疗效/安全性平衡、治疗顺序",
        "msl_action": "准备比较研究的证据等级、纳入研究范围和 indirect comparison 局限。",
    },
    {
        "id": "safety_frame",
        "type": "安全性",
        "title": "安全性讨论从单药 AE 转向跨机制风险框架",
        "keywords": ["safety", "adverse", "infection", "fcrn", "complement"],
        "why": "药物警戒、真实世界和 meta-analysis 共同推动安全性沟通从事件列表转向风险分层。",
        "position": "特殊人群、长期管理、竞品比较",
        "narrative": "感染、IgG、补体相关风险、监测策略",
        "msl_action": "区分 RCT 主动采集、RWE 回顾性记录和 FAERS 药物警戒信号。",
    },
    {
        "id": "value_access",
        "type": "价值与准入",
        "title": "患者偏好与价值证据开始进入治疗格局判断",
        "keywords": ["preference", "willingness", "value", "cost", "access", "economic"],
        "why": "偏好、支付和价值研究会影响靶向治疗从“能不能用”转向“如何定位和持续使用”。",
        "position": "准入、支付、患者沟通",
        "narrative": "给药便利性、成本价值、长期负担",
        "msl_action": "把价值证据和临床疗效证据分开呈现，避免混成疗效结论。",
    },
]

CHINA_EVIDENCE_DIRECTION_SPECS = [
    {
        "id": "fcrnTargeted",
        "dimension": "FcRn 靶向治疗",
        "keywords": ["fcrn", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"],
        "analysis_angle": "看中国证据是否更多集中在真实世界、起效和复治周期，而非重复 RCT 结论。",
    },
    {
        "id": "complementTargeted",
        "dimension": "补体抑制",
        "keywords": ["complement", "zilucoplan", "ravulizumab", "eculizumab", "c5 inhibitor"],
        "analysis_angle": "看 AChR+ 人群、感染预防和长期维持证据在中外文献中的侧重点。",
    },
    {
        "id": "bCellBaffApril",
        "dimension": "B 细胞 / BAFF-APRIL",
        "keywords": ["b cell", "b-cell", "rituximab", "inebilizumab", "telitacicept", "blys", "april"],
        "analysis_angle": "看中国证据是否沉淀出本土已获批药物、难治亚型或机制探索方向。",
    },
    {
        "id": "realWorldPath",
        "dimension": "真实世界路径",
        "keywords": ["real-world", "registry", "observational", "retrospective", "cohort"],
        "analysis_angle": "看用药路径、联合治疗、减激素和随访终点是否具备本土实践差异信号。",
    },
    {
        "id": "safetyMonitoring",
        "dimension": "安全性与监测",
        "keywords": ["safety", "adverse", "infection", "tolerability", "pharmacovigilance", "faers"],
        "analysis_angle": "看中外证据是否在 AE 采集、感染风险、长期监测和停药原因上形成不同问题清单。",
    },
    {
        "id": "specialPopulation",
        "dimension": "特殊人群 / 亚型",
        "keywords": ["juvenile", "elderly", "pregnancy", "seronegative", "musk", "crisis", "new-onset"],
        "analysis_angle": "看中国证据是否更多补充儿童、老年、MuSK、血清阴性或危象管理场景。",
    },
    {
        "id": "biomarkerMechanism",
        "dimension": "机制与生物标志物",
        "keywords": ["biomarker", "autoantibody", "mechanism", "pathogenesis", "cytokine", "proteomic"],
        "analysis_angle": "看机制研究是否能转化为专家深访问题，而不是直接推导治疗路径差异。",
    },
]

CLINICALTRIALS_ACTIVE_STATUSES = {
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "NOT_YET_RECRUITING",
    "ENROLLING_BY_INVITATION",
}

CLINICALTRIALS_STATUS_LABELS = {
    "RECRUITING": "招募中",
    "ACTIVE_NOT_RECRUITING": "进行中/停止招募",
    "NOT_YET_RECRUITING": "尚未招募",
    "ENROLLING_BY_INVITATION": "邀请入组",
}

CLINICALTRIALS_PHASE_RANK = {
    "PHASE4": 4,
    "PHASE3": 3,
    "PHASE2_PHASE3": 2.5,
    "PHASE2": 2,
    "PHASE1_PHASE2": 1.5,
}

CLINICAL_PIPELINE_CANONICAL = [
    ("Batoclimab", ["batoclimab", "hbm9161", "hl161", "rvt-1401"], "FcRn", "FcRn", "Immunovant / Harbour"),
    ("IMVT-1402", ["imvt-1402"], "FcRn", "FcRn", "Immunovant"),
    ("B007", ["b007"], "待补充", "待补充", "Shanghai Jiaolian"),
    ("Iptacopan", ["iptacopan"], "补体", "Factor B", "Novartis"),
    ("Claseprubart", ["claseprubart", "dnth103"], "补体", "补体通路", "Dianthus"),
    ("Pozelimab/Cemdisiran", ["pozelimab", "cemdisiran"], "补体", "C5 / C5 siRNA", "Regeneron"),
    ("Empasiprubart", ["empasiprubart"], "补体", "C2", "argenx"),
    ("Inebilizumab", ["inebilizumab"], "B细胞", "CD19", "Amgen"),
    ("Remibrutinib", ["remibrutinib"], "B细胞", "BTK", "Novartis"),
    ("Blinatumomab", ["blinatumomab"], "B细胞", "CD19/CD3 BiTE", "Academic"),
    ("Povetacicept", ["povetacicept"], "BAFF/APRIL", "BAFF/APRIL", "Vertex"),
    ("Aritinercept", ["aritinercept"], "BAFF/APRIL", "APRIL/BAFF", "Aurinia"),
    ("Descartes-08", ["descartes-08", "decartes-08"], "细胞治疗", "BCMA CAR-T", "Cartesian"),
    ("CABA-201", ["caba-201"], "细胞治疗", "CD19 CAR-T", "Cabaletta"),
    ("KYV-101", ["kyv-101"], "细胞治疗", "CD19 CAR-T", "Kyverna"),
    ("BAFF-R CAR-T", ["baff-r cart", "baff-r car-t"], "细胞治疗", "BAFF-R CAR-T", "Academic"),
    ("NMD670", ["nmd670"], "神经肌接头", "ClC-1", "NMD Pharma"),
    ("Cladribine", ["cladribine"], "免疫调节", "淋巴细胞耗竭", "Merck KGaA"),
    ("Tocilizumab", ["tocilizumab"], "免疫调节", "IL-6R", "Academic"),
    ("CNP-106", ["cnp-106"], "免疫耐受", "抗原特异免疫耐受", "COUR"),
    ("IM-101", ["im-101"], "待补充", "待补充", "ImmunAbs"),
    ("SHR-2173", ["shr-2173"], "待补充", "待补充", "Hengrui"),
]

CLINICAL_PIPELINE_EXCLUDE_TERMS = [
    "placebo", "matching placebo", "prednisone", "prednisolone", "corticosteroid",
    "pyridostigmine", "azathioprine", "mycophenolate", "tacrolimus",
    "ivig", "immune globulin", "immunoglobulin", "hizentra", "igiv",
    "salbutamol", "amifampridine", "methotrexate", "leflunomide",
    "mycophenolate mofetil", "eculizumab", "ravulizumab", "zilucoplan",
    "efgartigimod", "rozanolixizumab", "nipocalimab", "telitacicept",
]

DRUG_POSITIONING = {
    "Efgartigimod": {
        "mechanism": "FcRn",
        "population": "AChR+ gMG 及真实世界扩展人群",
        "positioning": "快速、可逆 IgG 清除，适合围绕起效、周期治疗、中国 RWE 和 steroid-sparing 叙事展开。",
        "speed": "快",
        "convenience": "IV/SC",
        "safety": "感染、IgG 下降、特殊人群与长期多周期监测",
        "competition": "与 rozanolixizumab / nipocalimab 同属 FcRn 赛道，也与补体抑制剂争夺 AChR+ 靶向治疗定位。",
    },
    "Rozanolixizumab": {
        "mechanism": "FcRn",
        "population": "AChR+ / MuSK+ gMG",
        "positioning": "SC FcRn 方案，适合围绕给药便利性、PRO 和同机制差异比较展开。",
        "speed": "快",
        "convenience": "SC",
        "safety": "头痛、感染、IgG 相关监测",
        "competition": "与 efgartigimod、nipocalimab 形成 FcRn 内部比较。",
    },
    "Nipocalimab": {
        "mechanism": "FcRn",
        "population": "抗体阳性 gMG 及更广泛自身抗体疾病探索",
        "positioning": "临床后期 FcRn 方案，重点看证据成熟、适应证扩展和差异化临床终点。",
        "speed": "待观察",
        "convenience": "IV",
        "safety": "IgG 相关监测、长期安全性仍需积累",
        "competition": "作为后发 FcRn 方案，需要用证据成熟度和适应证策略建立定位。",
    },
    "Batoclimab": {
        "mechanism": "FcRn",
        "population": "gMG 及自身抗体疾病开发人群",
        "positioning": "SC FcRn 开发方案，关注疗效、白蛋白/脂质相关安全性和中国开发线索。",
        "speed": "待观察",
        "convenience": "SC",
        "safety": "白蛋白、脂质和 IgG 下降相关监测",
        "competition": "与已上市 FcRn 方案比较时需先区分证据阶段。",
    },
    "Zilucoplan": {
        "mechanism": "C5",
        "population": "AChR+ gMG",
        "positioning": "SC 补体抑制方案，强调 C5 通路、给药便利性和长期维持定位。",
        "speed": "较快",
        "convenience": "SC",
        "safety": "脑膜炎球菌疫苗、感染风险、补体抑制监测",
        "competition": "与 ravulizumab / eculizumab 同机制，也与 FcRn 在 AChR+ 人群形成机制区隔。",
    },
    "Ravulizumab": {
        "mechanism": "C5",
        "population": "AChR+ gMG",
        "positioning": "长效 C5 抑制剂，适合讨论维持治疗和输注间隔优势。",
        "speed": "较快",
        "convenience": "IV 长间隔",
        "safety": "脑膜炎球菌疫苗、感染风险、长期维持管理",
        "competition": "与 eculizumab 形成同机制迭代，与 FcRn 形成路径选择比较。",
    },
    "Eculizumab": {
        "mechanism": "C5",
        "population": "AChR+ 难治 gMG",
        "positioning": "补体赛道早期标杆，常作为机制和长期经验参照。",
        "speed": "较快",
        "convenience": "IV",
        "safety": "脑膜炎球菌疫苗、感染风险、长期维持管理",
        "competition": "作为补体抑制经验基准，被 ravulizumab / zilucoplan 和 FcRn 方案共同参照。",
    },
    "Telitacicept": {
        "mechanism": "BLyS/APRIL",
        "population": "AChR+ gMG（中国获批适应证）",
        "positioning": "B 细胞生存因子方向的中国已获批治疗选择，适合放在本土竞争格局与路径差异观察位。",
        "speed": "待观察",
        "convenience": "SC",
        "safety": "感染、免疫球蛋白变化和长期免疫调节风险需结合说明书与全文确认",
        "competition": "与 FcRn/补体不是同机制比较，更适合用于讨论中国可及治疗选择和 B 细胞方向定位。",
    },
    "Rituximab": {
        "mechanism": "CD20",
        "population": "MuSK+、难治 MG 等探索/经验场景",
        "positioning": "更多用于难治和特定亚型讨论，证据口径需区分回顾性、meta 和真实世界。",
        "speed": "慢",
        "convenience": "IV",
        "safety": "感染、免疫抑制、长期 B 细胞耗竭管理",
        "competition": "不是直接同线竞品，更像难治/特殊亚型治疗路径的一部分。",
    },
    "Inebilizumab": {
        "mechanism": "CD19",
        "population": "研究线索",
        "positioning": "B 细胞方向的新兴线索，当前更适合放在未来机制观察位。",
        "speed": "待观察",
        "convenience": "IV",
        "safety": "B 细胞耗竭相关感染与免疫监测",
        "competition": "现阶段不宜与成熟上市药物直接做疗效排序。",
    },
}

LIVING_ANSWER_SPECS = [
    {
        "id": "fcrnSteroidSparing",
        "category": "异议处理",
        "question": "FcRn 抑制剂是否已有 steroid-sparing 证据？",
        "keywords": ["efgartigimod", "steroid", "glucocorticoid", "prednisone"],
        "stance": "可谨慎回答",
        "short_answer": "已有真实世界和部分研究支持减激素趋势，但具体减量幅度、维持时间和患者选择仍需阅读全文确认。",
        "key_points": [
            "先区分 MG-ADL/QMG 改善与真正的糖皮质激素减量终点。",
            "真实世界研究更贴近临床路径，但回顾性设计和减量策略差异会影响可比性。",
            "沟通时应把 steroid-sparing 作为治疗价值维度，而不是单独疗效承诺。",
        ],
        "anchor_nodes": ["efgartigimod", "fcrnInhibition", "steroidSparing"],
    },
    {
        "id": "fcrnVsComplement",
        "category": "竞品比较",
        "question": "FcRn 抑制剂和补体抑制剂在 AChR+ gMG 中如何区隔？",
        "keywords": ["fcrn", "complement", "efficacy", "safety", "myasthenia"],
        "stance": "可谨慎回答",
        "short_answer": "二者都属于 AChR+ gMG 靶向治疗核心机制，但作用路径、适用叙事、给药方式和安全性监测重点不同。",
        "key_points": [
            "FcRn 叙事偏向可逆 IgG 清除、起效和周期管理。",
            "补体叙事偏向 C5 末端通路阻断、长期维持和疫苗/感染风险管理。",
            "间接比较和 NMA 可作为讨论入口，但不能替代头对头研究。",
        ],
        "anchor_nodes": ["fcrnInhibition", "complementInhibition", "achrPositive"],
    },
    {
        "id": "chinaRweEfgartigimod",
        "category": "中国证据",
        "question": "中国 efgartigimod 真实世界证据能支持哪些沟通点？",
        "keywords": ["china", "chinese", "efgartigimod", "real-world", "myasthenia"],
        "stance": "可积极回答",
        "short_answer": "中国 RWE 已能支持本土使用经验、起效观察和特殊人群讨论，但 AE 率和终点定义必须结合研究设计解释。",
        "key_points": [
            "优先说明患者来源、入组标准、终点定义和随访周期。",
            "中国 RWE 可补足国际 RCT 外推，但不应直接替代随机证据。",
            "安全性沟通要区分主动监测、回顾性记录和导致停药的事件。",
        ],
        "anchor_nodes": ["efgartigimod", "chinaEvidence", "realWorldEvidence"],
    },
    {
        "id": "responseHeterogeneity",
        "category": "机制解释",
        "question": "为什么 FcRn 治疗反应可能存在个体差异？",
        "keywords": ["fcrn", "response", "autoantibody", "biomarker", "clinical response"],
        "stance": "仅供提纲",
        "short_answer": "abstract 层面提示抗体特征、疾病亚型和免疫状态可能与反应差异相关，但目前更适合作为机制讨论线索。",
        "key_points": [
            "可从 AChR 抗体功能、抗体亚型和免疫细胞状态解释差异。",
            "预测性证据需要区分 biomarker association 与经过验证的预测模型。",
            "面向专家可作为深访问题，不宜包装成成熟分层用药工具。",
        ],
        "anchor_nodes": ["fcrnInhibition", "achrPositive", "mgSubtypesAntibodies"],
    },
    {
        "id": "targetedTherapySafety",
        "category": "安全性",
        "question": "靶向治疗安全性应该如何与传统免疫治疗区隔沟通？",
        "keywords": ["safety", "adverse", "infection", "fcrn", "complement"],
        "stance": "可谨慎回答",
        "short_answer": "可以按机制风险框架沟通：FcRn 关注 IgG/感染相关监测，补体关注疫苗和脑膜炎球菌等感染风险。",
        "key_points": [
            "安全性比较应优先引用 RCT、系统综述、药物警戒和 RWE 的不同证据等级。",
            "不同研究的 AE 采集方式差异很大，不能只比较表面发生率。",
            "特殊人群、长期用药和联合免疫抑制是 MSL 需要追问的重点。",
        ],
        "anchor_nodes": ["safetyOutcome", "fcrnInhibition", "complementInhibition"],
    },
    {
        "id": "earlyTargetedTherapy",
        "category": "治疗定位",
        "question": "MG 靶向治疗是否正在向更早期治疗位置移动？",
        "keywords": ["new-onset", "early", "targeted", "efgartigimod", "myasthenia"],
        "stance": "证据不足",
        "short_answer": "已有新发或早期干预线索，但 abstract 层面仍不足以支持广泛前移结论，应作为趋势观察。",
        "key_points": [
            "需要区分新发研究、早期反应研究和正式治疗路径推荐。",
            "治疗前移必须同时看疗效、安全性、成本价值和指南位置。",
            "目前更适合提示“证据正在出现”，不宜说“治疗范式已经改变”。",
        ],
        "anchor_nodes": ["generalizedMg", "efgartigimod", "rapidOnset"],
    },
]


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_public_js(path: Path, global_name: str):
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(global_name)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def regulatory_status_class(status: str):
    low = (status or "").lower()
    if "approved" in low:
        return "approved"
    if "review" in low or "accepted" in low or "submitted" in low:
        return "review"
    if "no nmpa" in low or "not tracked" in low or "not found" in low:
        return "none"
    return "unknown"


def load_china_regulatory_status():
    if not CHINA_REGULATORY_PATH.exists():
        return {}, {
            "generated_at": "",
            "source_note": "未找到中国监管状态数据源。",
            "source_file": str(CHINA_REGULATORY_PATH.relative_to(PROJECT)),
        }
    try:
        payload = load_json(CHINA_REGULATORY_PATH)
    except Exception as exc:
        print(f"⚠️  中国监管状态读取失败: {exc}")
        return {}, {
            "generated_at": "",
            "source_note": "中国监管状态数据源读取失败。",
            "source_file": str(CHINA_REGULATORY_PATH.relative_to(PROJECT)),
        }
    status_map = {}
    for item in payload.get("drugs", []):
        name = item.get("name")
        if not name:
            continue
        row = dict(item)
        row["status_class"] = regulatory_status_class(row.get("china_status", ""))
        status_map[name] = row
    return status_map, {
        "generated_at": payload.get("generated_at", ""),
        "source_note": payload.get("source_note", ""),
        "source_file": str(CHINA_REGULATORY_PATH.relative_to(PROJECT)),
    }


def load_articles_for_frontend(use_full_experts=False):
    if RECENT_JS_PATH.exists():
        recent = load_public_js(RECENT_JS_PATH, "MG_LITERATURE_DATA")
    elif RECENT_JSON_CACHE_PATH.exists():
        print("⚠️  literature-recent.js 不存在，临时使用本地 JSON cache。")
        recent = load_json(RECENT_JSON_CACHE_PATH)
    else:
        raise FileNotFoundError("需要 data/literature-recent.js")

    full = None
    if use_full_experts and FULL_PATH.exists():
        full = load_json(FULL_PATH)
    elif use_full_experts:
        print("⚠️  请求从 full 重建专家画像，但 literature-full.json 不存在，将复用已提交专家画像。")
    else:
        print("ℹ️  周更模式不读取 literature-full.json，将复用已提交的专家画像数据。")

    # 全库文献计数：直接从 literature-recent.js 中读取 MG_TOTAL_COUNT
    total_count = 0
    if RECENT_JS_PATH.exists():
        m = re.search(r"window\.MG_TOTAL_COUNT\s*=\s*(\d+)", RECENT_JS_PATH.read_text(encoding="utf-8"))
        if m:
            total_count = int(m.group(1))
    if not total_count:
        total_count = len(recent)

    return recent, full, total_count


def load_or_build_experts(full, recent):
    if full is not None:
        return build_experts(full, write_backend_index=True)
    if EXPERT_JS_PATH.exists():
        return load_public_js(EXPERT_JS_PATH, "MG_EXPERT_PROFILES")
    print("⚠️  expert-profiles.js 不存在，临时使用近一年公开数据生成专家画像。")
    return build_experts(recent)


def parse_date(value: str | None):
    if not value:
        return None
    value = value.strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    match = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?", value)
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
        )
    match = re.match(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day or 1))
    match = re.match(r"(\d{4})", value)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None


def text_of(article):
    parts = [
        article.get("title", ""),
        article.get("abstract", ""),
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]
    return " ".join(parts).lower()


def has_any(text, words):
    return any(word in text for word in words)


def infer_topics(article):
    text = text_of(article)
    topics = [label for label, words in TOPIC_DEFS if has_any(text, words)]
    if not topics and article.get("study_types"):
        topics.append(article["study_types"][0])
    return topics[:5]


def evidence_score(level):
    return {"I": 7, "II": 5, "III": 4, "IV": 3, "V": 2, "VI": 1}.get(level or "", 0)


def is_case_report(article, text):
    study_types = {str(item).lower() for item in article.get("study_types") or []}
    return "case report" in study_types or has_any(text, CASE_REPORT_TERMS)


def has_drug_signal(text):
    return any(has_any(text, words) for words in DRUG_KEYWORDS.values())


def has_safety_signal(text):
    return has_any(text, SAFETY_TERMS)


def has_high_value_signal(text, topics):
    return bool(SIGNAL_CORE_TOPICS.intersection(topics)) or has_any(text, HIGH_VALUE_TERMS)


def is_low_value_signal(article, text):
    pub_types = " ".join(article.get("pub_types") or []).lower()
    title = (article.get("title") or "").strip().lower()
    return has_any(f"{title} {pub_types} {text}", LOW_VALUE_SIGNAL_TERMS)


def compact_article(article):
    return {
        "pmid": article.get("pmid", ""),
        "title": article.get("title", ""),
        "journal": article.get("journal", ""),
        "entry_date": article.get("entry_date", ""),
        "pub_date": article.get("pub_date", ""),
        "url": article.get("url", ""),
        "evidence_level": article.get("evidence_level"),
        "journal_if": article.get("journal_if"),
        "journal_quartile": article.get("journal_quartile"),
        "china_related": bool(article.get("china_related")),
        "study_types": article.get("study_types") or [],
    }


def write_js(name, global_name, payload):
    path = DATA_DIR / name
    text = "window.%s = %s;\n" % (
        global_name,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    path.write_text(text, encoding="utf-8")
    print(f"✅ {path.relative_to(PROJECT)}")


def build_signals(recent):
    latest = max((parse_date(a.get("entry_date")) for a in recent if parse_date(a.get("entry_date"))), default=datetime.now())
    cutoff = latest - timedelta(days=14)
    signals = []
    topic_counter = Counter()
    for article in recent:
        dt = parse_date(article.get("entry_date"))
        if not dt or dt < cutoff:
            continue
        text = text_of(article)
        topics = infer_topics(article)
        for topic in topics:
            topic_counter[topic] += 1
        level = article.get("evidence_level")
        if not level or is_low_value_signal(article, text):
            continue
        if_val = float(article.get("journal_if") or 0)
        signal_type = "新证据"
        if has_any(text, ["guideline", "consensus", "recommendation", "review", "meta-analysis"]):
            signal_type = "新观点"
        if has_any(text, ["pathogenesis", "mechanism", "biomarker", "cytokine", "receptor", "autoantibody"]):
            signal_type = "新机制"
        # 匹配到的药物通用名（小写），可能为空列表
        drugs = sorted(
            drug.lower() for drug, words in DRUG_KEYWORDS.items()
            if has_any(text, words)
        )
        case_report = is_case_report(article, text)
        drug_signal = has_drug_signal(text)
        safety_signal = has_safety_signal(text)
        high_value_signal = has_high_value_signal(text, topics)

        # 病例报告保留在文献库，但只有涉及药物、安全性、中国相关或明确主题时才推入信号板。
        if case_report and not (drug_signal or safety_signal or article.get("china_related") or topics):
            continue
        if not high_value_signal and not drug_signal and not article.get("china_related"):
            continue
        # 强度分级
        #   强（任一）：证据 I/II 级；IF ≥ 10 且不是 V/VI 级低证据
        #   中（任一）：IF ≥ 5；证据 III/IV 级；中国相关
        #   弱：其余入选条目
        strength = "弱"
        if level in {"I", "II"} or (if_val >= 10 and level not in {"V", "VI"}):
            strength = "强"
        elif if_val >= 5 or level in {"III", "IV"} or article.get("china_related"):
            strength = "中"
        score = if_val + evidence_score(level) + (14 - (latest - dt).days) / 3
        if article.get("china_related"):
            score += 1.5
        if case_report:
            score -= 3
        if drug_signal:
            score += 1
        if safety_signal:
            score += 1
        if strength == "强":
            score += 10
        elif strength == "中":
            score += 4
        signals.append({
            "date": dt.strftime("%Y-%m-%d"),
            "type": signal_type,
            "strength": strength,
            "summary": article.get("title", ""),
            "related_pmids": [article.get("pmid", "")],
            "keywords": topics,
            "drugs": drugs,
            "score": round(score, 2),
            "article": compact_article(article),
        })
    strength_rank = {"强": 3, "中": 2, "弱": 1}
    signals.sort(key=lambda item: (-strength_rank.get(item["strength"], 0), -item["score"], item["date"]))
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": 14,
        "topic_hotspots": [{"topic": k, "count": v} for k, v in topic_counter.most_common(12)],
        "signals": signals[:80],
    }


def normalize_institution(affiliation):
    if not affiliation:
        return ""
    parts = [p.strip() for p in re.split(r"[,;]", affiliation) if p.strip()]
    strong_org_keywords = ["hospital", "university", "institute", "college", "center", "centre"]
    fallback_org_keywords = ["school", "clinic"]
    generic_prefixes = (
        "department ", "department of ", "division ", "division of ", "unit ",
        "unit of ", "service ", "service of ", "laboratory ", "laboratory of ",
        "faculty ", "faculty of ", "clinic for ",
    )

    def clean_part(value):
        return re.sub(r"^the\s+", "", value, flags=re.I).strip()[:120]

    def should_skip(value):
        low = value.lower()
        return "@" in value or "road" in low or "street" in low or low == "china"

    def is_generic_affiliated_hospital(value):
        low = clean_part(value).lower()
        return bool(re.fullmatch(r"(first|second|third|fourth|fifth)?\s*affiliated hospital", low))

    def is_generic_school(value):
        low = clean_part(value).lower()
        return low in {"college of medicine", "school of medicine", "faculty of medicine"}

    def nearby_context(index):
        candidates = parts[index + 1:index + 3] + parts[max(0, index - 2):index]
        for item in candidates:
            low = item.lower()
            if should_skip(item) or any(low.startswith(prefix) for prefix in generic_prefixes):
                continue
            if any(key in low for key in ["university", "institute", "hospital", "center", "centre"]):
                return clean_part(item)
        return ""

    for idx, part in enumerate(parts):
        low = part.lower()
        if should_skip(part):
            continue
        if any(key in low for key in strong_org_keywords):
            clean = clean_part(part)
            context = nearby_context(idx)
            if is_generic_affiliated_hospital(part) and context:
                return f"{clean} of {context}"[:120]
            if is_generic_school(part) and context:
                return f"{clean}, {context}"[:120]
            return clean[:90]
    for part in parts:
        low = part.lower()
        if should_skip(part):
            continue
        if any(key in low for key in fallback_org_keywords):
            return clean_part(part)[:90]
    for part in parts:
        low = part.lower()
        if "@" in part or any(low.startswith(prefix) for prefix in generic_prefixes):
            continue
        if low in {"china", "usa", "united states", "italy", "japan", "germany", "france", "uk"}:
            continue
        return clean_part(part)[:90]
    return ""


def build_rank_items(counts, article_map, limit=10, article_limit=10):
    items = []
    for name, count in counts.most_common(limit):
        refs = sorted(
            article_map.get(name, []),
            key=lambda a: parse_date(a.get("entry_date")) or datetime.min,
            reverse=True,
        )
        items.append({
            "name": name,
            "count": count,
            "articles": [compact_article(a) for a in refs[:article_limit]],
        })
    return items


def build_china(recent):
    articles = [a for a in recent if a.get("china_related")]
    monthly = Counter()
    evidence = Counter()
    quartiles = Counter()
    journals = Counter()
    institutions = Counter()
    journal_articles = defaultdict(list)
    institution_articles = defaultdict(list)
    for article in articles:
        dt = parse_date(article.get("entry_date"))
        if dt:
            monthly[dt.strftime("%Y-%m")] += 1
        evidence[article.get("evidence_level") or "未分类"] += 1
        quartile = article.get("journal_quartile")
        if quartile:
            match = re.match(r"([1-4])", str(quartile))
            if match:
                quartiles[f"{match.group(1)}区"] += 1
        journal = article.get("journal") or "Unknown"
        journals[journal] += 1
        journal_articles[journal].append(article)
        for affiliation in article.get("affiliations") or []:
            inst = normalize_institution(affiliation)
            if inst:
                institutions[inst] += 1
                institution_articles[inst].append(article)
    articles.sort(key=lambda a: parse_date(a.get("entry_date")) or datetime.min, reverse=True)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "recent_year_articles": len(articles),
            "high_evidence": sum(1 for a in articles if a.get("evidence_level") in {"I", "II"}),
            "top_journal": journals.most_common(1)[0][0] if journals else "",
        },
        "monthly": [{"month": k, "count": monthly[k]} for k in sorted(monthly)],
        "evidence": [{"level": k, "count": evidence[k]} for k in ["I", "II", "III", "IV", "V", "VI"] if evidence[k]],
        "quartile": [{"level": k, "count": quartiles[k]} for k in ["1区", "2区", "3区", "4区"] if quartiles[k]],
        "top_journals": build_rank_items(journals, journal_articles, limit=10),
        "top_institutions": build_rank_items(institutions, institution_articles, limit=12),
        "pubmed_articles": [compact_article(a) for a in articles[:120]],
        "manual_updates": load_manual_china_updates(),
    }


def load_manual_china_updates():
    path = DATA_DIR / "china-manual.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("manual_updates", [])
    except Exception:
        return []


def tokenize(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
    return [w for w in words if w not in STOPWORDS and not w.isdigit()]


def normalize_author_key(name):
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def normalize_institution_key(name):
    value = (name or "").lower()
    value = re.sub(r"department of [^,;]+", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value or "institution_unresolved"


def unique(values):
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def article_author_rows(article):
    details = article.get("author_affiliations") or []
    if details:
        for detail in details:
            name = detail.get("name") or ""
            if not name:
                continue
            raw_affiliations = detail.get("affiliations") or []
            institutions = unique(normalize_institution(aff) for aff in raw_affiliations)
            if not institutions:
                institutions = [""]
            for institution in institutions:
                yield {
                    "name": name,
                    "position": detail.get("position"),
                    "institution": institution,
                    "raw_affiliations": raw_affiliations,
                }
        return

    # 兼容旧数据：历史 full 只有第一作者机构，因此非第一作者先标为机构待识别。
    authors = article.get("authors") or []
    first_author_affiliations = article.get("affiliations") or []
    for idx, name in enumerate(authors, 1):
        raw_affiliations = first_author_affiliations if idx == 1 else []
        institutions = unique(normalize_institution(aff) for aff in raw_affiliations) or [""]
        for institution in institutions:
            yield {
                "name": name,
                "position": idx,
                "institution": institution,
                "raw_affiliations": raw_affiliations,
            }


def is_china_author_institution_profile(institution, raw_affiliation_counter):
    """判断作者-机构画像是否属于中国机构画像。"""
    text = " ".join([institution or ""] + list(raw_affiliation_counter.keys())).lower()
    if not text:
        return False
    return any(term in text for term in CHINA_PROFILE_TERMS)


def build_experts(full, write_backend_index=False):
    profile_articles = defaultdict(dict)
    profile_names = defaultdict(Counter)
    profile_affiliations = defaultdict(Counter)
    profile_raw_affiliations = defaultdict(Counter)
    author_name_keys = Counter()
    institution_articles = defaultdict(dict)

    for article in full:
        seen_profile_keys = set()
        for row in article_author_rows(article):
            name = row["name"]
            author_key = normalize_author_key(name)
            institution = row["institution"]
            institution_key = normalize_institution_key(institution)
            profile_key = f"{author_key}::{institution_key}"
            author_name_keys[author_key] += 1
            if profile_key in seen_profile_keys:
                continue
            seen_profile_keys.add(profile_key)
            profile_articles[profile_key][article.get("pmid") or id(article)] = article
            profile_names[profile_key][name] += 1
            if institution:
                profile_affiliations[profile_key][institution] += 1
                institution_articles[institution_key][article.get("pmid") or id(article)] = article
            for raw_aff in row["raw_affiliations"]:
                profile_raw_affiliations[profile_key][raw_aff] += 1

    sorted_profiles = sorted(profile_articles.items(), key=lambda item: len(item[1]), reverse=True)
    profiles = []
    all_profile_summaries = []
    china_profile_flags = {}
    for profile_key, article_map in sorted_profiles:
        articles = list(article_map.values())
        display_name = profile_names[profile_key].most_common(1)[0][0]
        institution = profile_affiliations[profile_key].most_common(1)[0][0] if profile_affiliations[profile_key] else ""
        is_china_profile = is_china_author_institution_profile(institution, profile_raw_affiliations[profile_key])
        china_profile_flags[profile_key] = is_china_profile
        all_profile_summaries.append({
            "profile_key": profile_key,
            "name_en": display_name,
            "affiliation": institution,
            "publications": len(articles),
            "china_related": sum(1 for a in articles if a.get("china_related")),
            "is_china_profile": is_china_profile,
        })

    candidates = [
        item for item in sorted_profiles
        if china_profile_flags.get(item[0])
    ][:EXPERT_PROFILE_LIMIT]

    for idx, (profile_key, article_map) in enumerate(candidates, 1):
        articles = list(article_map.values())
        author = profile_names[profile_key].most_common(1)[0][0]
        institution = profile_affiliations[profile_key].most_common(1)[0][0] if profile_affiliations[profile_key] else ""
        articles_sorted = sorted(articles, key=lambda a: parse_date(a.get("entry_date")) or datetime.min, reverse=True)
        now = datetime.now()
        recent_3y = [a for a in articles if (parse_date(a.get("entry_date")) or datetime.min) >= now - timedelta(days=365 * 3)]
        journals = Counter(a.get("journal") or "Unknown" for a in articles)
        highest_if = max(float(a.get("journal_if") or 0) for a in articles)
        coauthors = Counter()
        words = Counter()
        for article in articles:
            for co in article.get("authors") or []:
                if co and co != author:
                    coauthors[co] += 1
            words.update(tokenize((article.get("title") or "") + " " + (article.get("abstract") or "")))
        topic_hits = Counter()
        for article in articles:
            for topic in infer_topics(article):
                topic_hits[topic] += 1
        interests = [{"term": k, "count": v} for k, v in (topic_hits or words).most_common(10)]
        institution_aliases = [{"name": k, "count": v} for k, v in profile_affiliations[profile_key].most_common(8)]
        raw_affiliations = [{"name": k, "count": v} for k, v in profile_raw_affiliations[profile_key].most_common(8)]
        profiles.append({
            "id": f"expert_{idx:03d}",
            "profile_key": profile_key,
            "author_key": profile_key.split("::", 1)[0],
            "institution_key": profile_key.split("::", 1)[1],
            "identity_basis": "pubmed_author_institution",
            "identity_status": "pubmed_unverified",
            "profile_scope": "china_author_institution",
            "name_en": author,
            "name_zh": "",
            "affiliation": institution,
            "institution_aliases": institution_aliases,
            "raw_affiliations": raw_affiliations,
            "metrics": {
                "total_publications": len(articles),
                "recent_3y_publications": len(recent_3y),
                "highest_if": round(highest_if, 1),
                "journal_count": len(journals),
                "china_related": sum(1 for a in articles if a.get("china_related")),
            },
            "interests": interests,
            "top_journals": [{"name": k, "count": v} for k, v in journals.most_common(6)],
            "collaborators": [{"name": k, "count": v} for k, v in coauthors.most_common(8)],
            "timeline": [compact_article(a) for a in articles_sorted[:8]],
            "public_tags": [item["term"] for item in interests[:4]],
        })

    if write_backend_index:
        write_author_institution_index(full, all_profile_summaries, institution_articles)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "profile_scope": "china_author_institution_top_publications",
            "profile_limit": EXPERT_PROFILE_LIMIT,
            "total_authors": len(author_name_keys),
            "author_institution_profiles": len(profile_articles),
            "china_author_institution_profiles": sum(1 for value in china_profile_flags.values() if value),
            "institutions": len(institution_articles),
            "profiled_authors": len(profiles),
            "profiles_ge_10": sum(1 for v in profile_articles.values() if len(v) >= 10),
            "profiles_ge_20": sum(1 for v in profile_articles.values() if len(v) >= 20),
        },
        "experts": profiles,
    }


def write_author_institution_index(articles, profile_summaries, institution_articles):
    institutions = []
    for institution_key, article_map in institution_articles.items():
        if institution_key == "institution_unresolved":
            continue
        refs = list(article_map.values())
        names = Counter()
        for article in refs:
            for row in article_author_rows(article):
                if normalize_institution_key(row["institution"]) == institution_key:
                    names[row["institution"]] += 1
        institutions.append({
            "institution_key": institution_key,
            "name": names.most_common(1)[0][0] if names else "",
            "publication_count": len(refs),
            "china_related": sum(1 for a in refs if a.get("china_related")),
        })
    institutions.sort(key=lambda item: item["publication_count"], reverse=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "data/literature-full.json",
        "summary": {
            "articles": len(articles),
            "author_institution_profiles": len(profile_summaries),
            "institutions": len(institutions),
        },
        "author_institution_profiles": profile_summaries,
        "institutions": institutions,
    }
    AUTHOR_INSTITUTION_INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✅ {AUTHOR_INSTITUTION_INDEX_PATH.relative_to(PROJECT)}")


def match_articles(articles, keywords, limit=12):
    scored = []
    min_hits = max(2, len(keywords) - 1)  # at most 1 keyword can miss
    for article in articles:
        text = text_of(article)
        hits = sum(1 for word in keywords if word in text)
        if hits < min_hits:
            continue
        if_val = float(article.get("journal_if") or 0)
        score = hits * 5 + evidence_score(article.get("evidence_level")) + if_val / 2
        scored.append((score, parse_date(article.get("entry_date")) or datetime.min, article))
    scored.sort(key=lambda item: (-item[0], item[1]), reverse=False)
    scored = sorted(scored, key=lambda item: (-item[0], -item[1].timestamp()))
    return [compact_article(item[2]) for item in scored[:limit]]


def latest_entry_date(articles):
    return max((parse_date(a.get("entry_date")) for a in articles if parse_date(a.get("entry_date"))), default=datetime.now())


def score_articles_flexible(articles, keywords, min_hits=1, within_days=None):
    latest = latest_entry_date(articles)
    cutoff = latest - timedelta(days=within_days) if within_days else None
    scored = []
    for article in articles:
        dt = parse_date(article.get("entry_date")) or datetime.min
        if cutoff and dt < cutoff:
            continue
        text = text_of(article)
        hits = sum(1 for word in keywords if word in text)
        if "china" in keywords or "chinese" in keywords:
            hits += 1 if article.get("china_related") else 0
        if hits < min_hits:
            continue
        if_val = float(article.get("journal_if") or 0)
        age_bonus = max(0, 45 - (latest - dt).days) / 15 if dt != datetime.min else 0
        score = hits * 5 + evidence_score(article.get("evidence_level")) + if_val / 3 + age_bonus
        if article.get("china_related"):
            score += 1
        scored.append((score, dt, article))
    scored.sort(key=lambda item: (-item[0], -item[1].timestamp()))
    return scored


def match_articles_flexible(articles, keywords, limit=8, min_hits=1, within_days=None):
    scored = score_articles_flexible(articles, keywords, min_hits=min_hits, within_days=within_days)
    return [compact_article(item[2]) for item in scored[:limit]]


def best_evidence_level(refs):
    rank = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    levels = [ref.get("evidence_level") for ref in refs if ref.get("evidence_level") in rank]
    if not levels:
        return "未分类"
    return sorted(levels, key=lambda level: rank[level])[0]


def evidence_maturity(refs):
    best = best_evidence_level(refs)
    if best in {"I", "II"}:
        return "成熟"
    if best in {"III", "IV"}:
        return "积累中"
    if refs:
        return "早期线索"
    return "待补充"


def depth_label(count):
    if count >= 3:
        return "较厚"
    if count >= 1:
        return "有限"
    return "待补充"


def evidence_depth_label(total_count, rwe_count):
    if total_count >= 50 or (total_count >= 20 and rwe_count >= 5):
        return "充分"
    if total_count >= 10 or rwe_count >= 2:
        return "少量"
    if total_count >= 1:
        return "有限"
    return "有限"


def china_evidence_depth_label(china_count):
    if china_count >= 30:
        return "充分"
    if china_count >= 10:
        return "少量"
    return "有限"


def is_rwe_like_article(article):
    return has_any(text_of(article), RWE_TERMS)


def refs_with_recent_window(refs, days=30):
    dates = [parse_date(ref.get("entry_date")) for ref in refs if parse_date(ref.get("entry_date"))]
    if not dates:
        return []
    cutoff = max(dates) - timedelta(days=days)
    return [ref for ref in refs if (parse_date(ref.get("entry_date")) or datetime.min) >= cutoff]


def build_china_evidence_direction_comparison(recent):
    latest = latest_entry_date(recent)
    cutoff = latest - timedelta(days=365)
    directions = []
    for spec in CHINA_EVIDENCE_DIRECTION_SPECS:
        china_scored = []
        non_china_scored = []
        for article in recent:
            dt = parse_date(article.get("entry_date")) or datetime.min
            if dt < cutoff:
                continue
            text = text_of(article)
            hits = sum(1 for word in spec["keywords"] if word in text)
            if hits < 1:
                continue
            if_val = float(article.get("journal_if") or 0)
            age_bonus = max(0, 365 - (latest - dt).days) / 120 if dt != datetime.min else 0
            score = hits * 5 + evidence_score(article.get("evidence_level")) + if_val / 3 + age_bonus
            bucket = china_scored if article.get("china_related") else non_china_scored
            bucket.append((score, dt, article))
        china_scored.sort(key=lambda item: (-item[0], -item[1].timestamp()))
        non_china_scored.sort(key=lambda item: (-item[0], -item[1].timestamp()))
        china_count = len(china_scored)
        non_china_count = len(non_china_scored)
        total = china_count + non_china_count
        china_share = round(china_count / total * 100, 1) if total else 0
        if china_count and china_share >= 30:
            signal = "中国相关证据占比偏高，值得阅读全文判断是否有本土路径沉淀。"
        elif china_count:
            signal = "已有中国相关线索，但更适合作为情报入口而非差异结论。"
        else:
            signal = "近一年未见明确中国相关 abstract，暂不形成中外比较判断。"
        directions.append({
            "id": spec["id"],
            "dimension": spec["dimension"],
            "analysis_angle": spec["analysis_angle"],
            "china_count": china_count,
            "non_china_count": non_china_count,
            "china_share": china_share,
            "signal": signal,
            "china_refs": [compact_article(item[2]) for item in china_scored[:4]],
            "non_china_refs": [compact_article(item[2]) for item in non_china_scored[:4]],
        })
    return {
        "window_start": cutoff.strftime("%Y-%m-%d"),
        "window_end": latest.strftime("%Y-%m-%d"),
        "source": "近一年 PubMed abstract 与元数据",
        "directions": directions,
    }


def phase_rank(phases):
    return max((CLINICALTRIALS_PHASE_RANK.get(phase, 0) for phase in phases or []), default=0)


def phase_label(phases):
    rank = phase_rank(phases)
    if rank >= 3:
        return "III期"
    if rank == 2.5:
        return "II/III期"
    if rank >= 2:
        return "II期"
    if rank >= 1.5:
        return "I/II期"
    return "未标注"


def clinical_status_label(status):
    return CLINICALTRIALS_STATUS_LABELS.get(status or "", status or "未标注")


def canonical_clinical_intervention(name):
    low = re.sub(r"\s+", " ", (name or "").strip().lower())
    if not low:
        return None
    for canonical, aliases, target_type, target_detail, sponsor_hint in CLINICAL_PIPELINE_CANONICAL:
        if any(alias in low for alias in aliases):
            return {
                "name": canonical,
                "target_type": target_type,
                "target": target_detail,
                "sponsor_hint": sponsor_hint,
            }
    if any(term in low for term in CLINICAL_PIPELINE_EXCLUDE_TERMS):
        return None
    return None


def fetch_clinicaltrials_mg_studies():
    if os.environ.get("MG_SKIP_CLINICALTRIALS"):
        raise RuntimeError("MG_SKIP_CLINICALTRIALS is set")
    if requests is None:
        raise RuntimeError("requests is not installed")
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": "Myasthenia Gravis",
        "pageSize": "100",
        "format": "json",
    }
    studies = []
    while True:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        studies.extend(payload.get("studies") or [])
        token = payload.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
    return studies


def compact_raw_clinical_study(study):
    protocol = study.get("protocolSection") or {}
    return {
        "protocolSection": {
            "identificationModule": protocol.get("identificationModule") or {},
            "statusModule": protocol.get("statusModule") or {},
            "sponsorCollaboratorsModule": protocol.get("sponsorCollaboratorsModule") or {},
            "conditionsModule": protocol.get("conditionsModule") or {},
            "designModule": protocol.get("designModule") or {},
            "armsInterventionsModule": protocol.get("armsInterventionsModule") or {},
            "eligibilityModule": protocol.get("eligibilityModule") or {},
        }
    }


def load_clinicaltrials_studies():
    source_url = "https://clinicaltrials.gov/search?cond=Myasthenia%20Gravis"
    try:
        studies = [compact_raw_clinical_study(study) for study in fetch_clinicaltrials_mg_studies()]
        payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "ClinicalTrials.gov API v2",
            "source_url": source_url,
            "studies": studies,
        }
        CLINICALTRIALS_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return studies, {
            "source": payload["source"],
            "source_url": source_url,
            "generated_at": payload["generated_at"],
            "mode": "live",
        }
    except Exception as exc:
        if CLINICALTRIALS_CACHE_PATH.exists():
            payload = load_json(CLINICALTRIALS_CACHE_PATH)
            print(f"⚠️  ClinicalTrials.gov 读取失败，使用缓存: {exc}")
            return payload.get("studies") or [], {
                "source": payload.get("source", "ClinicalTrials.gov API v2 cache"),
                "source_url": payload.get("source_url", source_url),
                "generated_at": payload.get("generated_at", ""),
                "mode": "cache",
                "warning": str(exc),
            }
        print(f"⚠️  ClinicalTrials.gov 读取失败，且无缓存: {exc}")
        return [], {
            "source": "ClinicalTrials.gov API v2",
            "source_url": source_url,
            "generated_at": "",
            "mode": "unavailable",
            "warning": str(exc),
        }


def normalize_age(value):
    if not value:
        return ""
    return str(value).replace("Years", "岁").replace("Year", "岁").replace("Months", "个月").replace("Month", "个月")


def simplify_clinical_indication(conditions, title):
    joined = " ".join(conditions or [])
    low = f"{joined} {title or ''}".lower()
    if "seronegative" in low:
        return "血清阴性 gMG"
    if ("achr" in low or "acetylcholine receptor" in low) and ("generalized" in low or "generalised" in low or "gmg" in low):
        return "AChR+ gMG"
    if "ocular" in low:
        return "Ocular Myasthenia Gravis"
    if "generalized" in low or "generalised" in low or "gmg" in low:
        return "Generalized Myasthenia Gravis"
    if "refractory" in low:
        return "Refractory Myasthenia Gravis"
    if conditions:
        return conditions[0]
    return "Myasthenia Gravis"


def infer_trial_population(protocol):
    ident = protocol.get("identificationModule") or {}
    conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
    eligibility = protocol.get("eligibilityModule") or {}
    title = ident.get("briefTitle", "")
    condition_text = simplify_clinical_indication(conditions, title)
    title_low = title.lower()
    details = []
    min_age = normalize_age(eligibility.get("minimumAge", ""))
    max_age = normalize_age(eligibility.get("maximumAge", ""))
    if min_age and max_age:
        details.append(f"{min_age}-{max_age}")
    elif min_age:
        details.append(f"≥{min_age}")
    elif max_age:
        details.append(f"≤{max_age}")
    if eligibility.get("sex") and eligibility.get("sex") != "ALL":
        details.append(eligibility.get("sex"))
    if "pediatric" in title_low or "children" in title_low or "adolescent" in title_low:
        details.append("儿童/青少年")
    if "ocular" in title_low:
        details.append("OMG")
    elif "generalized" in title_low or "generalised" in title_low or "gmg" in title_low:
        details.append("gMG")
    if "refractory" in title_low:
        details.append("难治")
    if "seronegative" in title_low:
        details.append("血清阴性")
    return {
        "indication": condition_text,
        "population": " · ".join(dict.fromkeys([item for item in details if item])) or "未标注",
    }


def compact_clinical_trial(study, canonical_name):
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    sponsor = protocol.get("sponsorCollaboratorsModule") or {}
    lead_sponsor = (sponsor.get("leadSponsor") or {}).get("name", "")
    nct_id = ident.get("nctId", "")
    population = infer_trial_population(protocol)
    return {
        "nct_id": nct_id,
        "title": ident.get("briefTitle", ""),
        "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        "status": status.get("overallStatus", ""),
        "status_label": clinical_status_label(status.get("overallStatus", "")),
        "phases": design.get("phases") or [],
        "phase_label": phase_label(design.get("phases") or []),
        "phase_rank": phase_rank(design.get("phases") or []),
        "sponsor": lead_sponsor,
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "start": (status.get("startDateStruct") or {}).get("date", ""),
        "primary_completion": (status.get("primaryCompletionDateStruct") or {}).get("date", ""),
        "completion": (status.get("completionDateStruct") or {}).get("date", ""),
        "last_update": status.get("lastUpdateSubmitDate", ""),
        "indication": population["indication"],
        "population": population["population"],
        "canonical_drug": canonical_name,
    }


def build_clinical_pipeline_matrix(regulatory_map):
    studies, meta = load_clinicaltrials_studies()
    approved_names = {
        name for name, item in regulatory_map.items()
        if item.get("status_class") == "approved"
    }
    groups = {}
    for study in studies:
        protocol = study.get("protocolSection") or {}
        design = protocol.get("designModule") or {}
        status = protocol.get("statusModule") or {}
        if design.get("studyType") != "INTERVENTIONAL":
            continue
        overall_status = status.get("overallStatus", "")
        if overall_status not in CLINICALTRIALS_ACTIVE_STATUSES:
            continue
        phases = design.get("phases") or []
        if not any(phase in {"PHASE1_PHASE2", "PHASE2", "PHASE2_PHASE3", "PHASE3"} for phase in phases):
            continue
        interventions = (protocol.get("armsInterventionsModule") or {}).get("interventions") or []
        for intervention in interventions:
            if intervention.get("type") not in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}:
                continue
            canonical = canonical_clinical_intervention(intervention.get("name", ""))
            if not canonical or canonical["name"] in approved_names:
                continue
            trial = compact_clinical_trial(study, canonical["name"])
            group = groups.setdefault(canonical["name"], {
                "name": canonical["name"],
                "target_type": canonical["target_type"],
                "target": canonical["target"],
                "sponsor_hint": canonical["sponsor_hint"],
                "trials": [],
            })
            if all(existing.get("nct_id") != trial.get("nct_id") for existing in group["trials"]):
                group["trials"].append(trial)

    items = []
    status_rank = {
        "RECRUITING": 4,
        "ACTIVE_NOT_RECRUITING": 3,
        "NOT_YET_RECRUITING": 2,
        "ENROLLING_BY_INVITATION": 1,
    }
    for item in groups.values():
        trials = sorted(
            item["trials"],
            key=lambda trial: (
                -trial.get("phase_rank", 0),
                -status_rank.get(trial.get("status", ""), 0),
                -(parse_date(trial.get("last_update")) or datetime.min).timestamp(),
            ),
        )
        item["trials"] = trials[:5]
        highest_phase_rank = max((trial.get("phase_rank", 0) for trial in trials), default=0)
        highest_phase_label = phase_label([phase for trial in trials for phase in trial.get("phases", [])])
        sponsors = Counter(trial.get("sponsor") or item["sponsor_hint"] for trial in trials)
        status_counts = Counter(trial.get("status_label", "未标注") for trial in trials)
        item["highest_phase_rank"] = highest_phase_rank
        item["highest_phase_label"] = highest_phase_label
        item["study_count"] = len(trials)
        item["sponsors"] = [name for name, _ in sponsors.most_common(3) if name]
        item["status_summary"] = " / ".join(f"{label} {count}" for label, count in status_counts.most_common())
        item["latest_update"] = max((trial.get("last_update") for trial in trials if trial.get("last_update")), default="")
        item["stage_number"] = 4 if highest_phase_rank >= 4 else 3 if highest_phase_rank >= 3 else 2 if highest_phase_rank >= 2 else 1
        item["indication"] = trials[0].get("indication", "Myasthenia Gravis") if trials else "Myasthenia Gravis"
        item["population"] = trials[0].get("population", "未标注") if trials else "未标注"
        item["key_trial"] = trials[0] if trials else {}
        items.append(item)

    target_order = {
        "FcRn": 1,
        "补体": 2,
        "B细胞": 3,
        "BAFF/APRIL": 4,
        "细胞治疗": 5,
        "神经肌接头": 6,
        "免疫调节": 7,
        "免疫耐受": 8,
        "待补充": 99,
    }
    target_counts = Counter(item.get("target_type", "待补充") for item in items)
    for item in items:
        item["target_group_count"] = target_counts.get(item.get("target_type", "待补充"), 1)
    items.sort(key=lambda item: (
        target_order.get(item.get("target_type", "待补充"), 90),
        -item.get("highest_phase_rank", 0),
        item["name"],
    ))
    meta.update({
        "active_statuses": [CLINICALTRIALS_STATUS_LABELS[item] for item in sorted(CLINICALTRIALS_ACTIVE_STATUSES)],
        "phase_rule": "纳入 ClinicalTrials.gov 中 MG 相关、Interventional、Drug/Biological、Phase I/II 及以上且仍在招募/进行/尚未招募的未获批中国治疗对象。",
        "item_count": len(items),
    })
    return {
        "meta": meta,
        "items": items,
    }


def build_landscape(recent):
    questions = [
        ("Efgartigimod 在 gMG 的长期疗效", ["efgartigimod", "long-term", "efficacy", "adapt"]),
        ("FcRn 拮抗剂安全性谱", ["fcrn", "safety", "infection", "adverse"]),
        ("Rozanolixizumab 疗效与患者报告结局", ["rozanolixizumab", "efficacy", "patient-reported", "mycaring"]),
        ("补体抑制剂在 MG 的定位", ["complement", "zilucoplan", "ravulizumab", "eculizumab", "efficacy"]),
        ("血清阴性 MG 的诊断与疾病特征", ["seronegative", "diagnosis", "characteristics"]),
        ("真实世界治疗策略", ["real-world", "registry", "retrospective", "treatment"]),
    ]
    matrices = []
    for question, keywords in questions:
        refs = match_articles(recent, keywords, limit=8)
        matrices.append({
            "question": question,
            "verified": False,
            "summary": "基于近一年 PubMed 文献的自动证据聚合，请核对引用原文。",
            "evidence_matrix": [
                {
                    "type": "支持",
                    "level": ref.get("evidence_level") or "未分类",
                    "source": ref.get("journal", ""),
                    "pmid": ref.get("pmid", ""),
                    "key_finding": ref.get("title", ""),
                    "limitations": "自动提取，来源待确认",
                }
                for ref in refs[:5]
            ],
            "references": refs,
        })

    monthly_changes = []
    for spec in LANDSCAPE_CHANGE_SPECS:
        refs = match_articles_flexible(recent, spec["keywords"], limit=5, min_hits=1, within_days=45)
        monthly_changes.append({
            "id": spec["id"],
            "type": spec["type"],
            "title": spec["title"],
            "why_it_matters": spec["why"],
            "treatment_position": spec["position"],
            "competitive_narrative": spec["narrative"],
            "msl_action": spec["msl_action"],
            "references": refs,
            "top_pmids": [ref.get("pmid") for ref in refs[:3] if ref.get("pmid")],
        })

    competitive_pipeline = []
    all_competitive_matrix = []
    approved_competitive_matrix = []
    regulatory_map, regulatory_meta = load_china_regulatory_status()
    for item in PIPELINE:
        drug_keywords = DRUG_KEYWORDS.get(item["name"], [item["name"].lower()])
        matched_articles = [entry[2] for entry in score_articles_flexible(recent, drug_keywords, min_hits=1)]
        refs = [compact_article(article) for article in matched_articles[:6]]
        profile = DRUG_POSITIONING.get(item["name"], {})
        total_count = len(matched_articles)
        rwe_count = sum(1 for article in matched_articles if is_rwe_like_article(article))
        china_count = sum(1 for article in matched_articles if article.get("china_related"))
        row = {
            **item,
            "mechanism": profile.get("mechanism", item["target"]),
            "population": profile.get("population", "待补充"),
            "positioning": profile.get("positioning", "待补充"),
            "speed": profile.get("speed", "待观察"),
            "convenience": profile.get("convenience", item["route"]),
            "safety": profile.get("safety", "需结合说明书与原文确认"),
            "competition": profile.get("competition", "待补充"),
            "evidence_maturity": evidence_maturity(refs),
            "best_evidence_level": best_evidence_level(refs),
            "rwe_depth": depth_label(rwe_count),
            "china_depth": depth_label(china_count),
            "evidence_summary": {
                "overall_depth": evidence_depth_label(total_count, rwe_count),
                "china_depth": china_evidence_depth_label(china_count),
                "abstract_count": total_count,
                "rwe_count": rwe_count,
                "china_count": china_count,
            },
            "china_regulatory": regulatory_map.get(item["name"], {
                "name": item["name"],
                "china_status": "Not tracked",
                "status_label": "待接入",
                "status_date": "",
                "china_indication": "等待 NMPA/CDE 状态源补充。",
                "cde_status": "Not tracked",
                "source_type": "",
                "source_url": "",
                "secondary_url": "",
                "last_verified": "",
                "status_class": "unknown",
            }),
            "references": refs,
        }
        competitive_pipeline.append(row)
        all_competitive_matrix.append(row)
        if row["china_regulatory"].get("status_class") == "approved":
            approved_competitive_matrix.append(row)

    clinical_pipeline = build_clinical_pipeline_matrix(regulatory_map)

    living_answers = []
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for spec in LIVING_ANSWER_SPECS:
        refs = match_articles_flexible(recent, spec["keywords"], limit=8, min_hits=1)
        added = refs_with_recent_window(refs, days=30)
        living_answers.append({
            "id": spec["id"],
            "category": spec["category"],
            "question": spec["question"],
            "stance": spec["stance"],
            "short_answer": spec["short_answer"],
            "key_points": spec["key_points"],
            "evidence_strength": best_evidence_level(refs),
            "last_updated": generated_at[:10],
            "evidence_window": "近一年公开 PubMed abstract",
            "answer_version": generated_at[:10].replace("-", ".") + "-v1",
            "source_pmids": [ref.get("pmid") for ref in refs if ref.get("pmid")],
            "added_papers": added,
            "references": refs,
            "anchor_nodes": spec["anchor_nodes"],
            "abstract_limitation": "本答案基于标题、摘要和元数据生成，只适合作为 MSL 准备提纲；疗效数值、亚组、安全性发生率和正式医学表述需阅读全文后确认。",
        })

    return {
        "generated_at": generated_at,
        "overview": {
            "month_change_count": len(monthly_changes),
            "competitive_count": len(approved_competitive_matrix),
            "clinical_pipeline_count": len(clinical_pipeline.get("items") or []),
            "living_answer_count": len(living_answers),
            "positioning": "诊治格局是战略解释层：把近期证据、全库关系和竞争定位转成 MSL 可扫描的治疗格局判断。",
        },
        "monthly_changes": monthly_changes,
        "competitive_matrix": approved_competitive_matrix,
        "approved_competitive_matrix": approved_competitive_matrix,
        "all_competitive_matrix": all_competitive_matrix,
        "clinical_pipeline_matrix": clinical_pipeline.get("items") or [],
        "clinical_pipeline_meta": clinical_pipeline.get("meta") or {},
        "china_regulatory_status": regulatory_meta,
        "living_answers": living_answers,
        "china_landscape": {
            "principle": "中外证据方向可由近一年 PubMed abstract 自动提示；真正的诊治差异必须等待指南/共识全文、说明书、准入和原文核对后沉淀。",
            "guideline_consensus_slot": {
                "title": "指南/共识与路径差异",
                "status": "waiting_for_source",
                "status_label": "等待接口",
                "note": "等待全球核心指南/共识处理完成后接入；这里将沉淀推荐强度、治疗顺序、适用人群和路径差异，不由 abstract 自动下结论。",
                "expected_inputs": [
                    "中国指南/专家共识全文结构化数据",
                    "国际核心指南/共识全文结构化数据",
                    "NMPA 说明书、医保/准入和适应证范围",
                    "MSL 阅读全文后的关键差异摘录",
                ],
            },
            "evidence_direction_comparison": build_china_evidence_direction_comparison(recent),
        },
        "evidence_questions": matrices,
        "china_difference": [
            {"dimension": "获批状态", "china": "手动维护为主", "global": "多产品已上市/后期开发", "gap": "时间差与适应症范围差"},
            {"dimension": "指南推荐", "china": "需结合中国指南与共识更新", "global": "指南/共识持续纳入新机制治疗", "gap": "证据积累与支付环境不同"},
            {"dimension": "医保覆盖", "china": "需手动维护医保与准入状态", "global": "按市场差异显著", "gap": "支付路径差异"},
        ],
        "competitive_pipeline": competitive_pipeline,
    }


def build_modules(recent, landscape):
    modules = []
    specs = [
        ("module_pharmacology_fcrn", "药理机制", "FcRn 通路机制", ["fcrn", "efgartigimod", "rozanolixizumab", "mechanism"]),
        ("module_clinical_efgartigimod", "临床数据", "Efgartigimod 临床证据", ["efgartigimod", "efficacy", "adapt"]),
        ("module_safety_fcrn", "安全性", "FcRn 拮抗剂安全性", ["fcrn", "safety", "infection", "adverse"]),
        ("module_competitive_fcrn", "竞品对比", "FcRn 产品对比", ["efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"]),
        ("module_real_world", "真实世界", "MG 真实世界证据", ["real-world", "registry", "observational", "retrospective"]),
        ("module_guideline", "指南比较", "MG 指南与共识", ["guideline", "consensus", "recommendation"]),
    ]
    for mid, mtype, title, keywords in specs:
        refs = match_articles(recent, keywords, limit=8)
        modules.append({
            "id": mid,
            "type": mtype,
            "title": title,
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "verified": False,
            "placeholder": len(refs) == 0,
            "summary": "自动从近一年文献提取的模块草稿，请核对引用原文后使用。",
            "claims": [
                {"text": ref.get("title", ""), "pmid": ref.get("pmid", ""), "evidence_level": ref.get("evidence_level") or "未分类"}
                for ref in refs[:4]
            ],
            "references": refs,
        })
    templates = [
        {"id": "weekly_brief", "name": "文献速递简报", "modules": ["module_clinical_efgartigimod", "module_safety_fcrn", "module_real_world"]},
        {"id": "visit_material", "name": "拜访材料", "modules": ["module_pharmacology_fcrn", "module_clinical_efgartigimod", "module_competitive_fcrn"]},
        {"id": "competitive_response", "name": "竞品应对", "modules": ["module_competitive_fcrn", "module_safety_fcrn"]},
        {"id": "internal_strategy", "name": "医学部内部", "modules": ["module_guideline", "module_real_world", "module_competitive_fcrn"]},
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "modules": modules,
        "templates": templates,
        "compliance_rules": [
            {"id": "pmid_required", "label": "每条声明必须绑定 PMID", "type": "rule"},
            {"id": "source_confirmed", "label": "正式使用前建议确认引用来源", "type": "workflow"},
            {"id": "placeholder_block", "label": "资料不足模块不得进入最终材料", "type": "rule"},
            {"id": "claim_source_check", "label": "适应症、疗效、安全性结论需核对原文", "type": "rule"},
        ],
    }


def build_dashboard(recent, signals, experts, china, landscape, modules, total_count):
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_articles": total_count,
            "recent_articles": len(recent),
            "china_articles": china["summary"]["recent_year_articles"],
            "signals": len(signals["signals"]),
            "experts": len(experts["experts"]),
            "modules": len(modules["modules"]),
        },
        "top_signals": signals["signals"][:5],
        "work_items": [
            {"type": "文献", "label": "近 14 天信号", "count": len(signals["signals"]), "href": "/MA-MG-HUB/pages/literature.html"},
            {"type": "专家", "label": "已构建专家画像", "count": len(experts["experts"]), "href": "/MA-MG-HUB/pages/msl.html"},
            {"type": "模块", "label": "MSL 内容模块", "count": sum(1 for m in modules["modules"] if not m["verified"]), "href": "/MA-MG-HUB/pages/msl.html"},
            {"type": "证据", "label": "待确认证据矩阵", "count": len(landscape["evidence_questions"]), "href": "/MA-MG-HUB/pages/landscape.html"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Build public frontend data bundles")
    parser.add_argument("--rebuild-experts-from-full", action="store_true", help="手动从本地 full 快照重建专家画像")
    args = parser.parse_args()

    recent, full, total_count = load_articles_for_frontend(use_full_experts=args.rebuild_experts_from_full)
    signals = build_signals(recent)
    china = build_china(recent)
    experts = load_or_build_experts(full, recent)
    landscape = build_landscape(recent)
    modules = build_modules(recent, landscape)
    dashboard = build_dashboard(recent, signals, experts, china, landscape, modules, total_count)

    write_js("signals-weekly.js", "MG_SIGNALS_DATA", signals)
    write_js("china-intelligence.js", "MG_CHINA_DATA", china)
    write_js("expert-profiles.js", "MG_EXPERT_PROFILES", experts)
    write_js("landscape-data.js", "MG_LANDSCAPE_DATA", landscape)
    write_js("content-modules.js", "MG_CONTENT_MODULES", modules)
    write_js("dashboard-data.js", "MG_DASHBOARD_DATA", dashboard)


if __name__ == "__main__":
    main()
