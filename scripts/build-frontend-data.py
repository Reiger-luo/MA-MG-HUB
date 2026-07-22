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
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from common.io import atomic_write_json, atomic_write_js_global, load_js_global, load_json as read_json
from common.expert_outputs import build_expert_manifest, write_expert_outputs as write_expert_shards
from common.mg_relevance import assess_mg_core
from common import clinical_registry

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
EXPERT_CHINA_JS_PATH = DATA_DIR / "expert-profiles-china.js"
EXPERT_INTERNATIONAL_JS_PATH = DATA_DIR / "expert-profiles-international.js"
AUTHOR_INSTITUTION_INDEX_PATH = DATA_DIR / "pubmed-author-institution-index.json"
ENTITY_NORMALIZATION_INDEX_PATH = DATA_DIR / "pubmed-entity-normalization-index.json"
CHINA_REGULATORY_PATH = DATA_DIR / "china-regulatory-status.json"
CLINICALTRIALS_CACHE_PATH = DATA_DIR / "clinicaltrials-pipeline-cache.json"
CHICTR_CACHE_PATH = DATA_DIR / "chictr-trials-cache.json"
FRONTEND_QUICK_EXPERT_LIMIT = 20

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

CHINA_LOCATION_RULES = [
    ("上海", "上海", ["shanghai", "fudan", "huashan", "ruijin", "zhongshan hospital"]),
    ("北京", "北京", ["beijing", "peking", "xuanwu", "capital medical", "pumch", "peking union"]),
    ("广东", "广州", ["guangzhou", "guangdong", "sun yat-sen", "sun yat sen", "southern medical"]),
    ("湖南", "长沙", ["changsha", "hunan", "xiangya", "central south university"]),
    ("陕西", "西安", ["xian", "xi'an", "shaanxi", "tangdu", "air force medical", "fourth military"]),
    ("江苏", "徐州", ["xuzhou", "jiangsu"]),
    ("湖北", "武汉", ["wuhan", "hubei", "tongji hospital", "union hospital tongji medical"]),
    ("四川", "成都", ["chengdu", "sichuan", "west china"]),
    ("黑龙江", "哈尔滨", ["harbin", "heilongjiang"]),
    ("河南", "郑州", ["zhengzhou", "henan"]),
    ("山东", "济南", ["jinan", "shandong"]),
    ("浙江", "杭州", ["hangzhou", "zhejiang"]),
    ("天津", "天津", ["tianjin"]),
    ("重庆", "重庆", ["chongqing"]),
    ("辽宁", "沈阳", ["shenyang", "liaoning"]),
    ("吉林", "长春", ["changchun", "jilin"]),
    ("河北", "石家庄", ["shijiazhuang", "hebei"]),
    ("山西", "太原", ["taiyuan", "shanxi"]),
    ("安徽", "合肥", ["hefei", "anhui"]),
    ("福建", "福州", ["fuzhou", "fujian"]),
    ("江西", "南昌", ["nanchang", "jiangxi"]),
    ("广西", "南宁", ["nanning", "guangxi"]),
    ("云南", "昆明", ["kunming", "yunnan"]),
    ("贵州", "贵阳", ["guiyang", "guizhou"]),
    ("新疆", "乌鲁木齐", ["urumqi", "xinjiang"]),
    ("甘肃", "兰州", ["lanzhou", "gansu"]),
    ("台湾", "台湾", ["taiwan"]),
    ("香港", "香港", ["hong kong"]),
]

INTERNATIONAL_LOCATION_RULES = [
    ("美国", ["united states", "u.s.a", "america", "mayo clinic", "harvard", "stanford", "duke university", "johns hopkins", "nih", "boston", "new york"]),
    ("日本", ["japan", "tokyo", "osaka", "nagoya", "keio", "kyoto", "chiba", "tohoku", "kyushu"]),
    ("德国", ["germany", "berlin", "munich", "heidelberg", "hamburg", "hannover", "essen"]),
    ("英国", ["united kingdom", "england", "scotland", "london", "oxford", "cambridge", "manchester", "newcastle"]),
    ("法国", ["france", "paris", "marseille", "lyon", "strasbourg"]),
    ("意大利", ["italy", "rome", "milan", "pavia", "naples", "padua", "bologna"]),
    ("荷兰", ["netherlands", "amsterdam", "leiden", "rotterdam", "utrecht", "maastricht"]),
    ("加拿大", ["canada", "toronto", "montreal", "vancouver", "ottawa", "calgary"]),
    ("西班牙", ["spain", "barcelona", "madrid", "valencia", "seville"]),
    ("韩国", ["korea", "seoul", "yonsei", "sungkyunkwan", "hanyang"]),
    ("澳大利亚", ["australia", "sydney", "melbourne", "brisbane", "monash"]),
    ("瑞典", ["sweden", "stockholm", "gothenburg", "uppsala", "karolinska"]),
    ("丹麦", ["denmark", "copenhagen", "aarhus"]),
    ("比利时", ["belgium", "brussels", "leuven", "ghent"]),
    ("瑞士", ["switzerland", "zurich", "basel", "geneva", "lausanne"]),
    ("挪威", ["norway", "oslo", "bergen"]),
    ("芬兰", ["finland", "helsinki", "turku"]),
    ("奥地利", ["austria", "vienna", "innsbruck", "graz"]),
    ("希腊", ["greece", "athens", "thessaloniki"]),
    ("土耳其", ["turkey", "istanbul", "ankara", "izmir"]),
    ("以色列", ["israel", "jerusalem", "tel aviv", "haifa"]),
    ("印度", ["india", "delhi", "mumbai", "bangalore", "chennai"]),
    ("新加坡", ["singapore"]),
    ("泰国", ["thailand", "bangkok"]),
    ("巴西", ["brazil", "sao paulo", "rio de janeiro"]),
    ("墨西哥", ["mexico", "mexico city"]),
    ("阿根廷", ["argentina", "buenos aires"]),
    ("波兰", ["poland", "warsaw", "krakow"]),
    ("捷克", ["czech", "prague"]),
    ("俄罗斯", ["russia", "moscow", "st petersburg"]),
    ("伊朗", ["iran", "tehran"]),
    ("沙特阿拉伯", ["saudi arabia", "riyadh", "jeddah"]),
    ("埃及", ["egypt", "cairo"]),
]

CANONICAL_INSTITUTION_RULES = [
    {
        "id": "huashan_hospital_fudan_university",
        "canonical": "Huashan Hospital, Fudan University",
        "terms": [
            "huashan hospital", "huashan rare disease", "national center for neurological disorders",
            "national centre for neurological disorders", "national center for neurological diseases",
            "national centre for neurological diseases", "national center for neurological disorders (ncnd)",
            "jing'an district centre hospital",
        ],
    },
    {
        "id": "tangdu_hospital_air_force_medical_university",
        "canonical": "Tangdu Hospital, Air Force Medical University",
        "terms": [
            "tangdu hospital",
            "second affiliated hospital of air force medical university",
            "second affiliated hospital of the air force medical university",
            "second affiliated hospital of fourth military medical university",
        ],
    },
    {
        "id": "xiangya_hospital_central_south_university",
        "canonical": "Xiangya Hospital, Central South University",
        "terms": ["xiangya hospital"],
    },
    {
        "id": "affiliated_hospital_xuzhou_medical_university",
        "canonical": "Affiliated Hospital of Xuzhou Medical University",
        "terms": ["xuzhou medical university"],
    },
    {
        "id": "first_affiliated_hospital_sun_yat_sen_university",
        "canonical": "First Affiliated Hospital of Sun Yat-sen University",
        "terms": ["first affiliated hospital of sun yat-sen university", "first affiliated hospital, sun yat-sen university"],
    },
    {
        "id": "second_affiliated_hospital_harbin_medical_university",
        "canonical": "Second Affiliated Hospital of Harbin Medical University",
        "terms": ["second affiliated hospital of harbin medical university"],
    },
    {
        "id": "west_china_hospital_sichuan_university",
        "canonical": "West China Hospital, Sichuan University",
        "terms": ["west china hospital", "west china school of nursing"],
    },
    {
        "id": "peking_university_first_hospital",
        "canonical": "Peking University First Hospital",
        "terms": ["peking university first hospital"],
    },
    {
        "id": "xuanwu_hospital_capital_medical_university",
        "canonical": "Xuanwu Hospital, Capital Medical University",
        "terms": ["xuanwu hospital"],
    },
    {
        "id": "tongji_hospital",
        "canonical": "Tongji Hospital",
        "terms": ["tongji hospital"],
    },
    {
        "id": "henan_institute_medical_pharmaceutical_sciences",
        "canonical": "Henan Institute of Medical and Pharmaceutical Sciences",
        "terms": ["henan institute of medical and pharmaceutical sciences"],
    },
    {
        "id": "peking_union_medical_college_hospital",
        "canonical": "Peking Union Medical College Hospital",
        "terms": ["peking union medical college hospital"],
    },
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
    "Gefurulimab": ["gefurulimab"],
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

CONFERENCE_SOURCE_FIELDS = [
    "source", "type", "category", "collection", "data_source", "source_type",
    "conference", "meeting", "event", "track",
]
CONFERENCE_SOURCE_TERMS = [
    "conference", "meeting", "congress", "symposium", "workshop",
    "aan ", "aanem", "ean ", "eular", "cmsc", "poster", "oral presentation",
]
CONFERENCE_PUB_TYPE_TERMS = [
    "meeting abstract", "conference abstract", "congress abstract", "published abstract",
]
CONFERENCE_TITLE_PATTERNS = [
    r"\bconference abstracts?\b",
    r"\bmeeting abstracts?\b",
    r"\bannual meeting\b",
    r"\bcongress abstracts?\b",
    r"\bposter presentation\b",
    r"\boral presentation\b",
]

KOL_ROLE_LABELS = {
    "first_author": "第一作者",
    "last_author": "末位作者",
    "corresponding_author": "通讯作者",
}

SIGNAL_CLUSTER_META = {
    "efgar": {
        "title": "Efgartigimod 证据继续向不同治疗节点和人群延伸",
        "type": "治疗证据",
        "tier": "efgar",
        "keywords": ["FcRn", "疗效", "安全性"],
    },
    "fcrn_competitor": {
        "title": "其他 FcRn 证据补充给药、长期获益与生活质量维度",
        "type": "竞品证据",
        "tier": "competitor_response",
        "keywords": ["FcRn", "疗效", "安全性"],
    },
    "complement": {
        "title": "补体通路证据继续扩展到长期治疗与给药便利性",
        "type": "竞品证据",
        "tier": "competitor_response",
        "keywords": ["补体", "疗效", "安全性"],
    },
    "other_targeted": {
        "title": "其他靶向机制在难治和特殊人群中形成治疗线索",
        "type": "竞品证据",
        "tier": "competitor_response",
        "keywords": ["疗效", "真实世界", "抗体分型"],
    },
    "comparative_treatment": {
        "title": "跨机制间接比较开始量化 MG 新疗法的相对效应",
        "type": "治疗比较",
        "tier": "competitor_response",
        "keywords": ["疗效", "安全性", "诊疗策略"],
    },
    "diagnostic_stratification": {
        "title": "抗体分型与诊断确认成为治疗定位的前置问题",
        "type": "诊疗进展",
        "tier": "disease_progress",
        "keywords": ["抗体分型", "诊疗策略", "疗效"],
    },
    "treatment_safety": {
        "title": "非 MG 用药暴露与长期激素负担强化安全监测需求",
        "type": "安全性",
        "tier": "disease_progress",
        "keywords": ["安全性", "疗效", "诊疗策略"],
    },
    "care_delivery": {
        "title": "院外沟通与跨专业认知暴露 MG 照护交付缺口",
        "type": "照护路径",
        "tier": "disease_progress",
        "keywords": ["诊疗策略", "真实世界", "安全性"],
    },
    "patient_burden": {
        "title": "患者负担、生活质量与治疗偏好进入 MG 证据评价",
        "type": "患者旅程",
        "tier": "disease_progress",
        "keywords": ["安全性", "疗效", "真实世界"],
    },
    "mechanism_biomarker": {
        "title": "机制与生物标志物研究继续解释 MG 亚型和疗效异质性",
        "type": "新机制",
        "tier": "disease_progress",
        "keywords": ["机制", "抗体分型", "疗效"],
    },
    "clinical_pathway": {
        "title": "围手术期、危象与误诊问题持续暴露临床路径缺口",
        "type": "临床路径",
        "tier": "disease_progress",
        "keywords": ["诊疗策略", "疗效", "真实世界"],
    },
    "real_world_outcomes": {
        "title": "真实世界研究补充长期结局、治疗路径与本土实践信息",
        "type": "真实世界",
        "tier": "disease_progress",
        "keywords": ["真实世界", "疗效", "安全性"],
    },
    "ocular_generalization": {
        "title": "抗体状态开始指引眼肌型 MG 的全身化风险与免疫治疗",
        "type": "真实世界",
        "tier": "disease_progress",
        "keywords": ["抗体分型", "真实世界", "诊疗策略"],
    },
    "critical_care": {
        "title": "HRR 提供 MG 合并脓毒症围术期死亡风险线索",
        "type": "风险分层",
        "tier": "disease_progress",
        "keywords": ["真实世界", "安全性", "诊疗策略"],
    },
    "disease_management": {
        "title": "MG 管理证据继续覆盖患者结局与临床决策问题",
        "type": "诊疗进展",
        "tier": "disease_progress",
        "keywords": ["疗效", "真实世界", "诊疗策略"],
    },
}

SIGNAL_TIER_LABELS = {
    "efgar": "efgar重点传递",
    "competitor_response": "竞品应对解读",
    "disease_progress": "疾病进展传递",
}

SIGNAL_CLUSTER_GAPS = {
    "efgar": {
        "before": "Efgartigimod 在围手术期、危重救援和特殊人群中的治疗节点仍主要依赖零散经验。",
        "filled": "新增研究开始提供这些非标准治疗节点中的患者过程与短期结局。",
        "remaining": "仍缺少对照研究、统一终点和足够随访，不能据此扩大常规适用场景。",
    },
    "fcrn_competitor": {
        "before": "其他 FcRn 抑制剂在亚洲人群中的疗效一致性和估计精度仍不清楚。",
        "filled": "新增亚组或延伸研究补充了区域人群、终点和安全性结果。",
        "remaining": "亚组样本量与置信区间仍限制结论，且不存在与 Efgartigimod 的头对头比较。",
    },
    "complement": {
        "before": "补体治疗的机制差异、给药便利性与长期获益尚缺少同一证据框架下的解释。",
        "filled": "新增研究补充了机制、治疗结局或给药路径的一项可核查结果。",
        "remaining": "跨研究设计与不同产品不可直接比较，长期安全性和人群选择仍需验证。",
    },
    "other_targeted": {
        "before": "非 FcRn 靶向治疗在真实世界相对现有免疫抑制路径能否增加获益，结论仍不稳定。",
        "filled": "新增对照与小样本研究同时给出了效应不足和个别快速改善的不同结果。",
        "remaining": "观察性偏倚、样本量和抗体亚型差异仍妨碍确定最佳治疗节点。",
    },
    "comparative_treatment": {
        "before": "多类 MG 新疗法缺少头对头试验，跨机制相对效应难以量化。",
        "filled": "新增网络荟萃分析在同一间接比较框架下量化了不同机制的疗效估计。",
        "remaining": "试验人群与设计异质性仍限制排序解释，不能替代头对头比较或长期安全性数据。",
    },
    "diagnostic_stratification": {
        "before": "抗体亚型和年龄分层能否改变诊断与治疗定位，缺少可量化的近期证据。",
        "filled": "新增研究补充了抗体分布、表型或分层结局数据。",
        "remaining": "检测完整性、选择偏倚和亚组样本量仍限制外推。",
    },
    "treatment_safety": {
        "before": "非 MG 用药诱发或加重 MG 的早期风险窗口，以及长期激素暴露的累积负担，仍缺少可执行的监测依据。",
        "filled": "新增病例、队列与自身对照研究把触发药物、时间窗和主要并发症进一步量化。",
        "remaining": "罕见事件多为病例级证据，长期风险受混杂影响，停药与监测策略仍需前瞻性验证。",
    },
    "care_delivery": {
        "before": "MG 患者在院外最常遇到什么问题、其他专科是否具备足够识别与用药知识，缺少量化证据。",
        "filled": "新增调查量化了院外咨询主题、响应紧迫性和跨专业知识缺口。",
        "remaining": "单中心调查不能证明教育或数字工具能改善患者结局，干预效果仍需验证。",
    },
    "patient_burden": {
        "before": "患者负担和依从性问题尚未充分转化为可执行的管理指标。",
        "filled": "新增研究补充了负担比例、相关因素或预测性能。",
        "remaining": "模型外部验证、干预可行性与不同医疗系统的可推广性仍未知。",
    },
    "mechanism_biomarker": {
        "before": "MG 机制候选与可用于临床分层的生物标志物之间仍有转化断层。",
        "filled": "新增组学和对照研究同时提供候选机制与阴性标志物结果。",
        "remaining": "探索性关联尚不能支持临床应用，候选指标仍需外部验证和纵向结局关联。",
    },
    "clinical_pathway": {
        "before": "胸腺手术方式、围手术期管理和长期缓解之间缺少一致的路径证据。",
        "filled": "新增队列补充了手术结局、危象和长期缓解数据。",
        "remaining": "非随机选择、术式差异和长期随访异质性仍限制路径推荐。",
    },
    "real_world_outcomes": {
        "before": "真实世界人群中的治疗选择、疾病进展与长期结局仍缺少对照和分层信息。",
        "filled": "新增队列提供了部分风险分层与治疗关联结果。",
        "remaining": "回顾性设计、残余混杂和单中心样本仍不能建立因果关系。",
    },
    "ocular_generalization": {
        "before": "眼肌型 MG 的抗体状态能否预测全身化，以及免疫治疗是否改变该风险，缺少分层数据。",
        "filled": "新增队列量化了抗体阳性与全身化风险，并提供免疫治疗相关的风险降低估计。",
        "remaining": "单中心回顾性样本不能确定最佳启动时机或具体免疫治疗方案，仍需前瞻性验证。",
    },
    "critical_care": {
        "before": "MG 合并脓毒症患者缺少简单可及的围术期死亡风险分层指标。",
        "filled": "新增重症数据库研究给出了 HRR 与围术期死亡风险的独立关联估计。",
        "remaining": "回顾性数据库与有限样本尚不足以确定临床阈值，模型仍需外部验证。",
    },
    "disease_management": {
        "before": "门诊外症状、用药风险和新机制进展尚未形成连续管理视角。",
        "filled": "新增研究把患者咨询、短期风险窗口或机制进展量化为可追踪问题。",
        "remaining": "不同证据类型不能直接合并为统一路径，仍需前瞻性验证。",
    },
}

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
    return read_json(path)


def load_public_js(path: Path, global_name: str):
    return load_js_global(path, global_name)


def payloadCount(payload):
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("item_count", "total_count", "count"):
            value = payload.get(key)
            if isinstance(value, int):
                return value
        items = payload.get("items")
        if isinstance(items, list):
            return len(items)
    return None


def semanticFullCountFromOutputs(full):
    """full 口径优先使用 raw full / full-index / community full 层。"""
    if full is not None:
        return len(full)
    candidates = [
        (DATA_DIR / "literature-full-index.js", "MG_LITERATURE_FULL_INDEX"),
        (DATA_DIR / "communityAssignmentIndex.js", "MG_COMMUNITY_ASSIGNMENT_INDEX"),
    ]
    for path, globalName in candidates:
        if not path.exists():
            continue
        try:
            count = payloadCount(load_public_js(path, globalName))
        except Exception:
            count = None
        if count:
            return count
    return None


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
        print("ℹ️  默认 preservation mode：复用已提交的专家 manifest 与区域分片。")

    # 默认构建只消费严格 recent；语义总量可从已发布 full-index/community 产物读取。
    total_count = semanticFullCountFromOutputs(full) or len(recent)

    return recent, full, total_count


def load_or_build_experts(full, recent):
    if full is not None:
        return build_experts(full, write_backend_index=True)
    if EXPERT_JS_PATH.exists():
        experts = dict(load_public_js(EXPERT_JS_PATH, "MG_EXPERT_PROFILES"))
        if EXPERT_CHINA_JS_PATH.exists():
            chinaShard = load_public_js(EXPERT_CHINA_JS_PATH, "MG_EXPERT_PROFILE_CHINA")
            experts["china_expert_index"] = chinaShard.get("items") or []
        if EXPERT_INTERNATIONAL_JS_PATH.exists():
            internationalShard = load_public_js(
                EXPERT_INTERNATIONAL_JS_PATH,
                "MG_EXPERT_PROFILE_INTERNATIONAL",
            )
            experts["international_expert_index"] = internationalShard.get("items") or []
        return experts
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
    return topics[:5]


def evidence_score(level):
    return {"I": 7, "II": 5, "III": 4, "IV": 3, "V": 2}.get(level or "", 0)


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


def is_conference_or_meeting_record(article):
    """文献级 signal-to-kol 只允许 PubMed literature，不纳入会议/会议信息源。"""
    source_blob = " ".join(str(article.get(field) or "") for field in CONFERENCE_SOURCE_FIELDS).lower()
    pub_type_blob = " ".join(article.get("pub_types") or []).lower()
    title = (article.get("title") or "").lower()
    if source_blob and any(term in f"{source_blob} " for term in CONFERENCE_SOURCE_TERMS):
        return True
    if any(term in pub_type_blob for term in CONFERENCE_PUB_TYPE_TERMS):
        return True
    return any(re.search(pattern, title) for pattern in CONFERENCE_TITLE_PATTERNS)


def author_roles(detail, total_authors):
    roles = []
    position = detail.get("position")
    try:
        position = int(position)
    except (TypeError, ValueError):
        position = None
    if detail.get("is_first") or position == 1:
        roles.append("first_author")
    if detail.get("is_last") or (total_authors and position == total_authors):
        roles.append("last_author")
    if detail.get("is_corresponding"):
        roles.append("corresponding_author")
    return roles


def location_hint(institution, raw_affiliations, article):
    raw_counter = Counter(raw_affiliations or [])
    if article.get("china_related") or is_china_author_institution_profile(institution, raw_counter):
        location = infer_china_location(institution, raw_counter)
        return {
            "region": "china",
            "country": "中国",
            "province": location.get("province", ""),
            "city": location.get("city", ""),
        }
    return {
        "region": "international",
        "country": infer_international_country(institution, raw_counter),
        "province": "",
        "city": "",
    }


def institution_from_affiliations(raw_affiliations):
    for affiliation in raw_affiliations or []:
        institution = normalize_institution(affiliation)
        if institution:
            return canonicalize_institution(institution, raw_affiliations)
    return canonicalize_institution("", raw_affiliations or [])


def build_kol_leads(article):
    """从本篇文献作者位次提取潜在 KOL 线索；不读取任何会议数据。"""
    details = article.get("author_affiliations") or []
    total_authors = len(details) or len(article.get("authors") or [])
    candidates = []
    if details:
        for detail in details:
            roles = author_roles(detail, total_authors)
            if not roles:
                continue
            candidates.append({
                "name": detail.get("name") or "",
                "position": detail.get("position"),
                "roles": roles,
                "raw_affiliations": detail.get("affiliations") or [],
                "emails": detail.get("emails") or [],
            })
    else:
        authors = article.get("authors") or []
        for idx, name in enumerate(authors, 1):
            roles = []
            if idx == 1:
                roles.append("first_author")
            if idx == len(authors):
                roles.append("last_author")
            if not roles:
                continue
            candidates.append({
                "name": name,
                "position": idx,
                "roles": roles,
                "raw_affiliations": article.get("affiliations") or [],
                "emails": [],
            })

    leads = []
    seen = set()
    for candidate in candidates:
        name = (candidate.get("name") or "").strip()
        if not name:
            continue
        raw_affiliations = candidate.get("raw_affiliations") or []
        canonical = institution_from_affiliations(raw_affiliations)
        institution = (canonical.get("name") or normalize_institution(raw_affiliations[0])) if raw_affiliations else (canonical.get("name") or "")
        key = (normalize_author_key(name), normalize_institution_key(institution))
        if key in seen:
            continue
        seen.add(key)
        loc = location_hint(institution, raw_affiliations, article)
        role_labels = [str(KOL_ROLE_LABELS.get(role) or role) for role in candidate.get("roles") or []]
        role_text = "/".join(role_labels) or "作者"
        leads.append({
            "name": name,
            "roles": role_labels,
            "position": candidate.get("position"),
            "institution": institution,
            "institution_key": canonical.get("key") or normalize_institution_key(institution),
            "country": loc["country"],
            "region": loc["region"],
            "province": loc["province"],
            "city": loc["city"],
            "emails": candidate.get("emails") or [],
            "rationale": f"本篇文献{role_text}，可作为该主题的 KOL 线索。",
        })
    return leads


def build_institution_leads(article, kol_leads):
    institutions = {}
    for row in article_author_rows(article):
        institution = row.get("canonical_institution") or row.get("institution") or ""
        key = row.get("canonical_institution_key") or normalize_institution_key(institution)
        if not institution or key == "institution_unresolved":
            continue
        bucket = institutions.setdefault(key, {
            "name": institution,
            "institution_key": key,
            "article_author_count": 0,
            "kol_names": set(),
            "raw_affiliations": [],
        })
        bucket["article_author_count"] += 1
        if row.get("name"):
            bucket["kol_names"].add(row["name"])
        bucket["raw_affiliations"].extend(row.get("raw_affiliations") or [])

    lead_name_by_inst = defaultdict(set)
    for lead in kol_leads:
        if lead.get("institution_key"):
            lead_name_by_inst[lead["institution_key"]].add(lead.get("name", ""))

    result = []
    for key, bucket in institutions.items():
        loc = location_hint(bucket["name"], bucket["raw_affiliations"], article)
        highlighted_names = sorted(name for name in lead_name_by_inst.get(key, set()) if name)
        result.append({
            "name": bucket["name"],
            "institution_key": key,
            "country": loc["country"],
            "region": loc["region"],
            "province": loc["province"],
            "city": loc["city"],
            "article_author_count": bucket["article_author_count"],
            "highlighted_kol_names": highlighted_names,
        })
    result.sort(key=lambda item: (-len(item["highlighted_kol_names"]), -item["article_author_count"], item["name"]))
    return result


def build_medical_affairs_bridge(article, topics, drugs, signal_type, strength):
    level = article.get("evidence_level") or "未分类"
    journal = article.get("journal") or "期刊待识别"
    if_text = f"IF {article.get('journal_if')}" if article.get("journal_if") else "IF 待补充"
    topic_set = set(topics or [])
    if "安全性" in topic_set:
        implication = "安全性证据更新，可用于与 KOL 讨论风险分层、监测和患者选择。"
        question = "该安全性发现是否会改变目标人群、监测频率或长期治疗排序？"
        action = "MSL 需准备 AE 定义、采集方式、发生率分母和与既有靶向治疗证据的差异。"
    elif drugs or {"FcRn", "补体", "B细胞"}.intersection(topic_set):
        drug_text = "、".join(drugs) if drugs else "靶向治疗"
        implication = f"{drug_text} 相关证据更新，可支持治疗定位、竞品区隔和患者分层讨论。"
        question = "该证据最适合影响哪一类患者、哪一个治疗节点或哪项竞品比较？"
        action = "MSL 需关联证据等级、终点、亚组和同机制/跨机制竞品信息。"
    elif "真实世界" in topic_set or article.get("china_related"):
        implication = "真实世界/本土证据更新，可补足临床路径、可及性和外推性的医学讨论。"
        question = "该真实世界结果与 RCT 或既有指南相比，新增了哪些落地信息？"
        action = "MSL 需整理研究设计、样本来源、治疗路径和可外推边界。"
    elif "机制" in topic_set or signal_type == "新机制":
        implication = "机制或生物标志物线索更新，可用于机制教育和专家深访问题设计。"
        question = "该机制线索是否能解释疗效异质性、抗体分型或未来联合研究方向？"
        action = "MSL 需准备机制图、关键实验/临床关联和可验证的专家问题。"
    elif "诊疗策略" in topic_set or signal_type == "新观点":
        implication = "综述/共识/诊疗观点更新，可用于校准医学叙事和专家共识差距。"
        question = "该观点与本地实践之间的最大差距和未满足需求是什么？"
        action = "MSL 需提炼推荐强度、证据来源和可用于圆桌讨论的争议点。"
    else:
        implication = "新增高价值文献信号，可作为专家沟通和后续证据追踪线索。"
        question = "该文献对当前 MG 诊疗路径或专家关注问题的增量价值是什么？"
        action = "MSL 需先确认研究类型、证据等级和与现有材料的关联。"
    return {
        "implication": implication,
        "suggested_kol_question": question,
        "msl_action": action,
        "evidence_context": f"证据 {level}；{journal}；{if_text}；{strength}信号。",
    }


def compact_article(article):
    assessment = assess_mg_core(article)
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
        "key_evidence": evidence_excerpt(article),
        "mg_core": assessment.is_core,
        "mg_core_reason": assessment.reason_code,
    }


def write_js(name, global_name, payload):
    path = DATA_DIR / name
    atomic_write_js_global(path, global_name, payload)
    print(f"✅ {path.relative_to(PROJECT)}")


def mg_core_relevance(article, text=None):
    """兼容既有调用；实现由 common.mg_relevance 统一维护。"""
    assessment = assess_mg_core(article)
    legacy_reason = {
        "explicit_mg_title": "title_explicit_mg",
        "secondary_non_mg_disease_title": "secondary_disease_in_title",
        "repeated_mg_core_mentions": "repeated_mg_mentions",
        "single_background_mention": "mg_only_background_or_comparator",
        "no_mg_core_evidence": "mg_only_background_or_comparator",
    }.get(assessment.reason_code, assessment.reason_code)
    return assessment.is_core, legacy_reason


def literature_cluster_key(article, topics, drugs):
    """把单篇候选归入可解释的主题簇；药物优先于泛主题。"""
    text = text_of(article)
    title = str(article.get("title") or "").lower()
    if any(term in text for term in ("efgartigimod", "vyvgart", "argx-113", "argx113")):
        return "efgar"
    if any(drug in {"nipocalimab", "rozanolixizumab", "batoclimab"} for drug in drugs):
        return "fcrn_competitor"
    if has_any(title, ["network meta-analysis", "network meta analysis", "indirect treatment comparison"]):
        return "comparative_treatment"
    if has_any(text, ["dental practice", "dentist", "outside of visits", "remote monitoring", "care-related inquiries"]):
        return "care_delivery"
    if any(drug in {"eculizumab", "ravulizumab", "zilucoplan", "gefurulimab"} for drug in drugs) or has_any(
        text, ["cemdisiran", "c5 synthesis", "complement inhibitor", "nimble trial"]
    ):
        return "complement"
    if has_any(title, ["seronegative", "double-seronegative", "musk", "lrp4", "autoantibody"]):
        return "diagnostic_stratification"
    if drugs:
        return "other_targeted"
    if has_any(text, [
        "immune checkpoint", "myocarditis", "myositis", "fatal", "adverse event",
        "sglt-2", "sglt2", "statin initiation", "oral corticosteroid", "steroid exposure",
    ]):
        return "treatment_safety"
    if has_any(text, ["seronegative", "double-seronegative", "musk", "lrp4", "autoantibody", "misdiagnos"]):
        return "diagnostic_stratification"
    if has_any(text, ["quality of life", "patient preference", "treatment preference", "burden", "fatigue", "exercise", "caregiver"]):
        return "patient_burden"
    if has_any(text, ["biomarker", "cytokine", "proteomic", "pathogenesis", "signaling", "signalling"]):
        return "mechanism_biomarker"
    if has_any(title + " " + text, ["thymectomy", "thymoma", "preoperative", "myasthenic crisis", "rehabilitation"]):
        return "clinical_pathway"
    if "ocular myasthenia" in text and "generalization" in text:
        return "ocular_generalization"
    if "sepsis" in text and has_any(text, ["mortality", "death risk", "hemoglobin-to-red blood cell"]):
        return "critical_care"
    if has_any(text, RWE_TERMS):
        return "real_world_outcomes"
    return "disease_management"


def evidence_excerpt(article, limit=320):
    """从摘要结果/结论段提取原文，避免 Signal-to-KOL 生成无证据数字。"""
    abstract = re.sub(r"\s+", " ", str(article.get("abstract") or "")).strip()
    if not abstract:
        return "摘要正文未提供，需阅读全文核查。"
    match = re.search(
        r"(?:findings|results|main results|outcomes|conclusions?|interpretation|implications?)\s*:\s*(.+?)(?=\s+(?:funding|limitations?|conclusions?|interpretation|implications?)\s*:|$)",
        abstract,
        flags=re.IGNORECASE,
    )
    excerpt = match.group(1).strip() if match else abstract
    if len(excerpt) > limit:
        excerpt = excerpt[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return excerpt


def aggregate_kol_leads(articles):
    buckets = {}
    for article in articles:
        for lead in build_kol_leads(article):
            key = (normalize_author_key(lead.get("name")), lead.get("institution_key") or "")
            bucket = buckets.setdefault(key, {**lead, "_pmids": set(), "_roles": set()})
            bucket["_pmids"].add(str(article.get("pmid") or ""))
            bucket["_roles"].update(lead.get("roles") or [])
            bucket["emails"] = sorted(set(bucket.get("emails") or []) | set(lead.get("emails") or []))
    result = []
    for bucket in buckets.values():
        pmids = {pmid for pmid in bucket.pop("_pmids") if pmid}
        roles = sorted(bucket.pop("_roles"), key=lambda role: ["第一作者", "末位作者", "通讯作者"].index(role) if role in ["第一作者", "末位作者", "通讯作者"] else 9)
        bucket["roles"] = roles
        bucket["article_count"] = len(pmids)
        bucket["rationale"] = f"在该信号的 {len(pmids)} 篇文献中担任" + "/".join(roles or ["关键作者"]) + "，作为作者线索待进一步核查。"
        result.append(bucket)
    result.sort(key=lambda item: (-item.get("article_count", 0), -len(item.get("roles") or []), item.get("name", "")))
    return result[:8]


def aggregate_institution_leads(articles, kol_leads):
    buckets = {}
    for article in articles:
        for institution in build_institution_leads(article, build_kol_leads(article)):
            key = institution.get("institution_key") or normalize_institution_key(institution.get("name"))
            if not key or key == "institution_unresolved":
                continue
            bucket = buckets.setdefault(key, {**institution, "_pmids": set(), "_authors": set(), "_kol": set()})
            bucket["_pmids"].add(str(article.get("pmid") or ""))
            bucket["_authors"].update(institution.get("highlighted_kol_names") or [])
    for lead in kol_leads:
        key = lead.get("institution_key")
        if key in buckets and lead.get("name"):
            buckets[key]["_kol"].add(lead["name"])
    result = []
    for bucket in buckets.values():
        pmids = {pmid for pmid in bucket.pop("_pmids") if pmid}
        authors = bucket.pop("_authors")
        kol_names = bucket.pop("_kol")
        bucket["article_count"] = len(pmids)
        bucket["highlighted_kol_names"] = sorted(authors | kol_names)
        result.append(bucket)
    result.sort(key=lambda item: (-item.get("article_count", 0), -len(item.get("highlighted_kol_names") or []), item.get("name", "")))
    return result[:8]


def cluster_strength(members):
    levels = {str(item.get("level") or "") for item in members}
    if levels.intersection({"I", "II"}):
        return "强"
    if any(item.get("score", 0) >= 12 for item in members) or len(members) >= 2:
        return "中"
    return "弱"


def build_cluster_signal(cluster_id, members, latest, signal_index):
    meta = SIGNAL_CLUSTER_META[cluster_id]
    members = sorted(members, key=lambda item: (-item["score"], -evidence_score(item.get("level")), item["date"], item["pmid"]))
    articles = [item["article"] for item in members]
    pmids = [str(article.get("pmid") or "") for article in articles if article.get("pmid")]
    refs = [compact_article(article) for article in articles]
    strength = cluster_strength(members)
    max_score = max(item["score"] for item in members)
    cluster_score = max_score + min(4, max(0, len(members) - 1) * 0.8)
    level_counts = Counter(item.get("level") or "未分类" for item in members)
    design_counts = Counter(
        str(item["article"].get("study_types", ["研究类型待补充"])[0])
        for item in members
    )
    level_text = "、".join(f"{level}级 {count}篇" for level, count in sorted(level_counts.items()))
    design_text = "、".join(f"{design} {count}篇" for design, count in design_counts.most_common(3))
    gap = SIGNAL_CLUSTER_GAPS[cluster_id]
    why_signal = f"{gap['filled']} 这使“{meta['title']}”从主题趋势变成可按结果逐项核查的近期变化。"
    boundary = (
        f"本簇包含 {design_text}；不同研究设计、终点和人群不可直接横向比较，"
        "下述结果均为摘要级定位，需回到全文核查。"
    )
    takeaway = f"{gap['filled']} 本期共有 {len(members)} 项研究结果，证据构成为 {level_text}。"
    top_members = members[: min(3, len(members))]
    messages = [
        f"摘要结果：{evidence_excerpt(item['article'])}"
        for item in top_members
    ]
    evidence_items = []
    for item in members:
        article = item["article"]
        design = " / ".join(str(value) for value in (article.get("study_types") or [])[:2]) or "研究设计待补充"
        evidence_items.append({
            "pmid": str(article.get("pmid") or ""),
            "finding": f"摘要结果原文：{evidence_excerpt(article)}",
            "gapContribution": f"为“{meta['title']}”补充了一项 {design} 结果，使该判断可定位到具体研究人群与结局。",
            "boundary": f"{design}，证据 {article.get('evidence_level') or '未分类'} 级；摘要级定位，因果解释与人群外推需核查全文。",
        })
    tier = meta["tier"]
    if tier == "efgar":
        why_kol = "该簇包含 efgartigimod 相关文献，应优先与 KOL 讨论其具体人群、终点和证据成熟度。"
    elif tier == "competitor_response":
        why_kol = "该簇涉及其他治疗机制；交流时应围绕机制、人群、终点、给药、安全性和证据成熟度与 efgar 做区隔，不暗示 head-to-head。"
    else:
        why_kol = "该簇提示诊疗、患者负担或机制层面的未满足问题，可用于向 KOL 提问并建立后续证据追踪。"
    talking_point = {
        "parentSignalId": f"L{signal_index:02d}",
        "parentSignalTitle": meta["title"],
        "priorityTier": tier,
        "priorityLabel": SIGNAL_TIER_LABELS[tier],
        "priorityRank": {"efgar": 0, "competitor_response": 1, "disease_progress": 2}[tier],
        "dimension": meta["type"],
        "title": meta["title"],
        "whyKol": why_kol,
        "kolScore": 5 if tier == "efgar" else (4 if len(members) >= 2 else 3),
        "keyMessages": messages[:3],
        "refs": refs[:4],
    }
    medical_affairs = {
        "implication": f"{len(members)} 篇 MG-core 文献形成“{meta['title']}”主题簇，可用于结构化 KOL 交流和后续证据追踪。",
        "suggested_kol_question": f"围绕“{meta['title']}”，哪项患者选择、治疗节点或监测问题最可能影响您当前的临床判断？",
        "msl_action": "会前逐篇核对研究人群、主要终点、效应值与全文限制，并准备同类证据对照。",
        "evidence_context": f"{level_text}；{design_text}；摘要级聚合。",
    }
    return {
        "id": f"L{signal_index:02d}",
        "date": max(item["date"] for item in members),
        "date_range": {"from": min(item["date"] for item in members), "to": max(item["date"] for item in members)},
        "type": meta["type"],
        "strength": strength,
        "title": meta["title"],
        "summary": meta["title"],
        "takeaway": takeaway,
        "whySignal": why_signal,
        "evidenceBoundary": boundary,
        "gapBefore": gap["before"],
        "gapFilled": gap["filled"],
        "remainingGap": gap["remaining"],
        "evidenceItems": evidence_items,
        "maUse": "用于 MSL briefing、KOL 问题设计和后续全文追踪；不替代逐篇医学核查。",
        "signalScore": max(1, min(5, round(2 + cluster_score / 10))),
        "related_pmids": pmids,
        "keywords": sorted(set(meta["keywords"] + [topic for item in members for topic in item["topics"]]))[:8],
        "drugs": sorted(set(drug for item in members for drug in item["drugs"])),
        "score": round(cluster_score, 2),
        "article_count": len(members),
        "china_related": any(bool(item["article"].get("china_related")) for item in members),
        "article": compact_article(members[0]["article"]),
        "refs": refs,
        "talkingPoints": [talking_point],
        "kolFocus": [talking_point],
        "medical_affairs": medical_affairs,
        "medical_affairs_implication": medical_affairs["implication"],
        "kol_leads": aggregate_kol_leads(articles),
        "institution_leads": aggregate_institution_leads(articles, aggregate_kol_leads(articles)),
        "signal_to_kol": {
            "source_artifact": "data/literature-recent.js",
            "scope": "literature_only",
            "analysis_model": "literature-signal-to-kol-v1",
            "aggregation": "mg_core_topic_cluster",
            "parent_signal_id": f"L{signal_index:02d}",
            "source_pmids": pmids,
            "auto_publish": True,
            "review_required": False,
        },
    }


def build_signals(recent):
    latest = max((parse_date(a.get("entry_date")) for a in recent if parse_date(a.get("entry_date"))), default=datetime.now())
    cutoff = latest - timedelta(days=14)
    candidates = defaultdict(list)
    topic_counter = Counter()
    excluded_conference_records = 0
    excluded_non_mg_core = Counter()

    for article in recent:
        dt = parse_date(article.get("entry_date"))
        if not dt or dt < cutoff:
            continue
        if is_conference_or_meeting_record(article):
            excluded_conference_records += 1
            continue
        text = text_of(article)
        assessment = assess_mg_core(article)
        if not assessment.is_core:
            excluded_non_mg_core[assessment.reason_code] += 1
            continue
        topics = infer_topics(article)
        level = article.get("evidence_level")
        if not level or is_low_value_signal(article, text):
            continue
        if_val = float(article.get("journal_if") or 0)
        drugs = sorted(drug.lower() for drug, words in DRUG_KEYWORDS.items() if has_any(text, words))
        case_report = is_case_report(article, text)
        drug_signal = has_drug_signal(text)
        safety_signal = has_safety_signal(text)
        high_value_signal = has_high_value_signal(text, topics)
        if case_report and not (drug_signal or safety_signal or article.get("china_related") or topics):
            continue
        if not high_value_signal and not drug_signal and not article.get("china_related"):
            continue
        strength = "弱"
        if level in {"I", "II"} or (if_val >= 10 and level != "V"):
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
        cluster_id = literature_cluster_key(article, topics, drugs)
        for topic in topics:
            topic_counter[topic] += 1
        candidates[cluster_id].append({
            "article": article,
            "date": dt.strftime("%Y-%m-%d"),
            "pmid": str(article.get("pmid") or ""),
            "level": level,
            "topics": topics,
            "drugs": drugs,
            "score": score,
        })

    tier_rank = {"efgar": 0, "competitor_response": 1, "disease_progress": 2}
    ordered_clusters = sorted(
        candidates.items(),
        key=lambda pair: (
            tier_rank[SIGNAL_CLUSTER_META[pair[0]]["tier"]],
            -max(item["score"] for item in pair[1]),
            pair[0],
        ),
    )
    signals = [build_cluster_signal(cluster_id, members, latest, idx) for idx, (cluster_id, members) in enumerate(ordered_clusters, 1)]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": 14,
        "source_artifact": "data/literature-recent.js",
        "source_policy": {
            "scope": "literature_only",
            "auto_publish": True,
            "review_required": False,
            "signal_count_unlimited": True,
            "analysis_model": "literature-signal-to-kol-v1",
            "aggregation": "mg_core_topic_cluster",
            "mg_core_policy": "title_explicit_or_repeated_mg_mentions_with_secondary_disease_guard",
            "excluded_non_mg_core": sum(excluded_non_mg_core.values()),
            "excluded_non_mg_core_by_reason": dict(excluded_non_mg_core),
            "excluded_conference_records": excluded_conference_records,
            "conference_meeting_policy": "excluded_by_source_type_pub_type_title_guard",
        },
        "topic_hotspots": [{"topic": k, "count": v} for k, v in topic_counter.most_common()],
        "signals": signals,
    }


def build_signal_summary(signals):
    """将规范化信号压缩为首页可直接消费的稳定汇总。"""
    normalized = [item for item in (signals or []) if isinstance(item, dict)]
    strength_counts = {"strong": 0, "medium": 0, "weak": 0}
    strength_keys = {"强": "strong", "中": "medium", "弱": "weak"}
    type_counts = Counter()
    topic_counts = Counter()
    type_order = {}
    topic_order = {}
    strong_themes = []

    for signal in normalized:
        strength_key = strength_keys.get(str(signal.get("strength") or ""), "weak")
        strength_counts[strength_key] += 1

        signal_type = str(signal.get("type") or "").strip()
        if signal_type:
            type_order.setdefault(signal_type, len(type_order))
            type_counts[signal_type] += 1

        seen_topics = set()
        for value in signal.get("keywords") or []:
            topic = str(value or "").strip()
            if not topic or topic in seen_topics:
                continue
            seen_topics.add(topic)
            topic_order.setdefault(topic, len(topic_order))
            topic_counts[topic] += 1

        title = str(signal.get("title") or signal.get("summary") or "").strip()
        if strength_key == "strong" and title and title not in strong_themes:
            strong_themes.append(title if len(title) <= 32 else title[:31].rstrip() + "…")

    def rank_counts(counts, order, limit):
        ranked = sorted(counts, key=lambda label: (-counts[label], order[label], label))
        return [{"label": label, "count": counts[label]} for label in ranked[:limit]]

    leading_types = rank_counts(type_counts, type_order, 3)
    top_topics = rank_counts(topic_counts, topic_order, 3)
    strong_themes = strong_themes[:2]
    total_count = len(normalized)
    overview_parts = [f"近 14 天共形成 {total_count} 条信号"]
    if leading_types:
        overview_parts.append(
            "信号类型以" + "、".join(
                f"{item['label']}（{item['count']} 条）" for item in leading_types[:2]
            ) + "为主"
        )
    if strong_themes:
        overview_parts.append("强信号聚焦" + "、".join(f"“{title}”" for title in strong_themes))
    else:
        overview_parts.append("本期暂无强信号")
    if top_topics:
        overview_parts.append("高频主题为" + "、".join(item["label"] for item in top_topics))

    return {
        "total_count": total_count,
        "strength_counts": strength_counts,
        "overview": "；".join(overview_parts) + "。",
        "leading_types": leading_types,
        "strong_themes": strong_themes,
        "top_topics": top_topics,
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
    allowedEvidenceLevels = {"I", "II", "III", "IV", "V"}
    articles = [
        article
        for article in recent
        if article.get("china_related")
        and article.get("evidence_level") in allowedEvidenceLevels
        and assess_mg_core(article).is_core
    ]
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
        "evidence": [{"level": k, "count": evidence[k]} for k in ["I", "II", "III", "IV", "V"] if evidence[k]],
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


def normalize_alias_text(value):
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def canonicalize_institution(institution, raw_affiliations):
    """将 PubMed 机构碎片映射到可稳定复用的机构实体。"""
    text = normalize_alias_text(" ".join([institution or ""] + (raw_affiliations or [])))
    for rule in CANONICAL_INSTITUTION_RULES:
        if any(term in text for term in rule["terms"]):
            return {
                "name": rule["canonical"],
                "key": normalize_institution_key(rule["canonical"]),
                "rule_id": rule["id"],
                "confidence": "high",
            }
    if institution:
        return {
            "name": institution,
            "key": normalize_institution_key(institution),
            "rule_id": "fallback_normalized_institution",
            "confidence": "medium",
        }
    return {
        "name": "",
        "key": "institution_unresolved",
        "rule_id": "unresolved",
        "confidence": "low",
    }


def infer_china_location(institution, raw_affiliation_counter):
    """从机构名和 affiliation 中粗略提取中国省份/城市，供前端筛选。"""
    raw_items = raw_affiliation_counter.keys() if hasattr(raw_affiliation_counter, "keys") else (raw_affiliation_counter or [])
    text = normalize_alias_text(" ".join([institution or ""] + list(raw_items)))
    for province, city, terms in CHINA_LOCATION_RULES:
        if any(term in text for term in terms):
            return {"province": province, "city": city}
    return {"province": "未识别", "city": ""}


def infer_international_country(institution, raw_affiliation_counter):
    """从国外机构名和 affiliation 中提取国家，供前端国家筛选。"""
    raw_items = raw_affiliation_counter.keys() if hasattr(raw_affiliation_counter, "keys") else (raw_affiliation_counter or [])
    text = normalize_alias_text(" ".join([institution or ""] + list(raw_items)))
    for country, terms in INTERNATIONAL_LOCATION_RULES:
        if any(term in text for term in terms):
            return country
    return "未识别"


def unique(values):
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def institution_raw_affiliation_groups(raw_affiliations):
    """保留机构碎片和来源 affiliation 的对应关系，避免多机构作者被误合并。"""
    groups = {}
    for raw_affiliation in raw_affiliations or []:
        institution = normalize_institution(raw_affiliation)
        if not institution:
            continue
        groups.setdefault(institution, []).append(raw_affiliation)
    if not groups:
        return [("", raw_affiliations or [])]
    return list(groups.items())


def article_author_rows(article):
    details = article.get("author_affiliations") or []
    if details:
        for detail in details:
            name = detail.get("name") or ""
            if not name:
                continue
            raw_affiliations = detail.get("affiliations") or []
            for institution, source_affiliations in institution_raw_affiliation_groups(raw_affiliations):
                canonical = canonicalize_institution(institution, source_affiliations)
                yield {
                    "name": name,
                    "position": detail.get("position"),
                    "institution": institution,
                    "canonical_institution": canonical["name"],
                    "canonical_institution_key": canonical["key"],
                    "institution_rule_id": canonical["rule_id"],
                    "institution_confidence": canonical["confidence"],
                    "raw_affiliations": source_affiliations,
                }
        return

    # 兼容旧数据：历史 full 只有第一作者机构，因此非第一作者先标为机构待识别。
    authors = article.get("authors") or []
    first_author_affiliations = article.get("affiliations") or []
    for idx, name in enumerate(authors, 1):
        raw_affiliations = first_author_affiliations if idx == 1 else []
        for institution, source_affiliations in institution_raw_affiliation_groups(raw_affiliations):
            canonical = canonicalize_institution(institution, source_affiliations)
            yield {
                "name": name,
                "position": idx,
                "institution": institution,
                "canonical_institution": canonical["name"],
                "canonical_institution_key": canonical["key"],
                "institution_rule_id": canonical["rule_id"],
                "institution_confidence": canonical["confidence"],
                "raw_affiliations": source_affiliations,
            }


def is_china_author_institution_profile(institution, raw_affiliation_counter):
    """判断作者-机构画像是否属于中国机构画像。"""
    text = " ".join([institution or ""] + list(raw_affiliation_counter.keys())).lower()
    if not text:
        return False
    return any(term in text for term in CHINA_PROFILE_TERMS)


def build_author_dominant_institutions(full):
    """为少量无机构作者行回填压倒性主机构，避免同一人被拆出空画像。"""
    article_sets = defaultdict(lambda: defaultdict(set))
    institution_names = defaultdict(lambda: defaultdict(Counter))
    for article in full:
        article_id = article.get("pmid") or id(article)
        seen = set()
        for row in article_author_rows(article):
            author_key = normalize_author_key(row["name"])
            institution_key = row.get("canonical_institution_key") or normalize_institution_key(row["institution"])
            if not author_key or institution_key == "institution_unresolved":
                continue
            pair = (author_key, institution_key)
            if pair in seen:
                continue
            seen.add(pair)
            article_sets[author_key][institution_key].add(article_id)
            institution_names[author_key][institution_key][row.get("canonical_institution") or row["institution"]] += 1

    dominant = {}
    for author_key, institution_map in article_sets.items():
        if not institution_map:
            continue
        resolved_pmids = set()
        for pmids in institution_map.values():
            resolved_pmids.update(pmids)
        ranked = sorted(institution_map.items(), key=lambda item: len(item[1]), reverse=True)
        top_key, top_pmids = ranked[0]
        top_count = len(top_pmids)
        if top_count >= 5 and top_count / max(1, len(resolved_pmids)) >= 0.75:
            dominant[author_key] = {
                "name": institution_names[author_key][top_key].most_common(1)[0][0],
                "key": top_key,
                "resolved_publications": top_count,
                "resolved_share": round(top_count / max(1, len(resolved_pmids)), 3),
            }
    return dominant


def build_experts(full, write_backend_index=False):
    profile_articles = defaultdict(dict)
    profile_names = defaultdict(Counter)
    profile_affiliations = defaultdict(Counter)
    profile_institution_aliases = defaultdict(Counter)
    profile_normalization_rules = defaultdict(Counter)
    profile_raw_affiliations = defaultdict(Counter)
    author_name_keys = Counter()
    institution_articles = defaultdict(dict)
    dominant_institutions = build_author_dominant_institutions(full)

    for article in full:
        seen_profile_keys = set()
        for row in article_author_rows(article):
            name = row["name"]
            author_key = normalize_author_key(name)
            institution = row.get("canonical_institution") or row["institution"]
            institution_key = row.get("canonical_institution_key") or normalize_institution_key(institution)
            rule_id = row.get("institution_rule_id")
            if institution_key == "institution_unresolved" and author_key in dominant_institutions:
                dominant = dominant_institutions[author_key]
                institution = dominant["name"]
                institution_key = dominant["key"]
                rule_id = "dominant_author_institution_backfill"
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
            if row.get("institution"):
                profile_institution_aliases[profile_key][row["institution"]] += 1
            if rule_id:
                profile_normalization_rules[profile_key][rule_id] += 1
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
        region = "china" if is_china_profile else "international"
        country = "中国" if is_china_profile else infer_international_country(institution, profile_raw_affiliations[profile_key])
        location = infer_china_location(institution, profile_raw_affiliations[profile_key]) if is_china_profile else {"province": "", "city": ""}
        china_profile_flags[profile_key] = is_china_profile
        all_profile_summaries.append({
            "profile_key": profile_key,
            "person_id": f"pubmed_person_{profile_key}",
            "author_key": profile_key.split("::", 1)[0],
            "canonical_institution_key": profile_key.split("::", 1)[1],
            "name_en": display_name,
            "primary_institution": institution,
            "affiliation": institution,
            "region": region,
            "country": country,
            "province": location["province"],
            "city": location["city"],
            "publications": len(articles),
            "china_related": sum(1 for a in articles if a.get("china_related")),
            "is_china_profile": is_china_profile,
            "institution_aliases": [
                {"name": k, "count": v}
                for k, v in profile_institution_aliases[profile_key].most_common(12)
            ],
            "normalization_rules": [
                {"rule_id": k, "count": v}
                for k, v in profile_normalization_rules[profile_key].most_common(5)
            ],
        })

    now = datetime.now()

    def build_compact_expert(profile_key, article_map, index_idx, region):
        """生成前端检索用精简画像，覆盖全部作者-机构画像。"""
        articles = list(article_map.values())
        author = profile_names[profile_key].most_common(1)[0][0]
        institution = profile_affiliations[profile_key].most_common(1)[0][0] if profile_affiliations[profile_key] else ""
        is_china_region = region == "china"
        country = "中国" if is_china_region else infer_international_country(institution, profile_raw_affiliations[profile_key])
        location = infer_china_location(institution, profile_raw_affiliations[profile_key]) if is_china_region else {"province": "", "city": ""}
        articles_sorted = sorted(articles, key=lambda a: parse_date(a.get("entry_date")) or datetime.min, reverse=True)
        recent_3y = [a for a in articles if (parse_date(a.get("entry_date")) or datetime.min) >= now - timedelta(days=365 * 3)]
        journals = Counter(a.get("journal") or "Unknown" for a in articles)
        highest_if = max(float(a.get("journal_if") or 0) for a in articles)
        topic_hits = Counter()
        for article in articles:
            for topic in infer_topics(article):
                topic_hits[topic] += 1
        interests = [[k, v] for k, v in topic_hits.most_common(8)]
        id_prefix = "expert_index" if is_china_region else "expert_global"
        recent_article = articles_sorted[0] if articles_sorted else {}
        return {
            "id": f"{id_prefix}_{index_idx:05d}",
            "region": region,
            "name_en": author,
            "affiliation": institution,
            **({"country": country} if not is_china_region else {}),
            "province": location["province"],
            "city": location["city"],
            "institution_aliases": [
                k for k, _ in profile_institution_aliases[profile_key].most_common(2)
            ],
            "metrics": [
                len(articles),
                len(recent_3y),
                round(highest_if, 1),
                len(journals),
                sum(1 for a in articles if a.get("china_related")),
            ],
            "interests": interests,
            "top_journals": [[k, v] for k, v in journals.most_common(2)],
            "timeline": [
                recent_article.get("pmid", ""),
                recent_article.get("title", ""),
                recent_article.get("journal", ""),
                recent_article.get("pub_date") or recent_article.get("entry_date", ""),
                recent_article.get("url", ""),
            ],
        }

    china_profile_items = [item for item in sorted_profiles if china_profile_flags.get(item[0])]
    international_profile_items = [item for item in sorted_profiles if not china_profile_flags.get(item[0])]
    china_expert_index = [
        build_compact_expert(profile_key, article_map, index_idx, "china")
        for index_idx, (profile_key, article_map) in enumerate(china_profile_items, 1)
    ]
    international_expert_index = [
        build_compact_expert(profile_key, article_map, index_idx, "international")
        for index_idx, (profile_key, article_map) in enumerate(international_profile_items, 1)
    ]

    def quick_expert_ids(items):
        ranked = sorted(
            items,
            key=lambda item: (
                item["metrics"][1],
                item["metrics"][0],
                item["metrics"][2],
            ),
            reverse=True,
        )
        return [item["id"] for item in ranked[:FRONTEND_QUICK_EXPERT_LIMIT]]

    quick_ids = {
        "china": quick_expert_ids(china_expert_index),
        "international": quick_expert_ids(international_expert_index),
        "all": quick_expert_ids(china_expert_index + international_expert_index),
    }

    if write_backend_index:
        write_author_institution_index(full, all_profile_summaries, institution_articles)
        write_entity_normalization_index(all_profile_summaries, institution_articles)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "profile_scope": "global_lightweight_author_institution_index",
            "frontend_quick_expert_limit": FRONTEND_QUICK_EXPERT_LIMIT,
            "total_authors": len(author_name_keys),
            "normalized_person_profiles": len(profile_articles),
            "author_institution_profiles": len(profile_articles),
            "china_author_identity_profiles": sum(1 for value in china_profile_flags.values() if value),
            "international_author_identity_profiles": sum(1 for value in china_profile_flags.values() if not value),
            "china_author_institution_profiles": sum(1 for value in china_profile_flags.values() if value),
            "institutions": len(institution_articles),
            "profiled_authors": 0,
            "indexed_experts": len(china_expert_index) + len(international_expert_index),
            "indexed_china_experts": len(china_expert_index),
            "indexed_international_experts": len(international_expert_index),
            "profiles_ge_10": sum(1 for v in profile_articles.values() if len(v) >= 10),
            "profiles_ge_20": sum(1 for v in profile_articles.values() if len(v) >= 20),
        },
        "experts": [],
        "quick_expert_ids": quick_ids,
        "china_expert_index": china_expert_index,
        "international_expert_index": international_expert_index,
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
                if (row.get("canonical_institution_key") or normalize_institution_key(row["institution"])) == institution_key:
                    names[row.get("canonical_institution") or row["institution"]] += 1
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
    atomic_write_json(AUTHOR_INSTITUTION_INDEX_PATH, payload)
    print(f"✅ {AUTHOR_INSTITUTION_INDEX_PATH.relative_to(PROJECT)}")


def write_entity_normalization_index(profile_summaries, institution_articles):
    institutions = []
    for institution_key, article_map in institution_articles.items():
        if institution_key == "institution_unresolved":
            continue
        refs = list(article_map.values())
        institutions.append({
            "institution_key": institution_key,
            "publication_count": len(refs),
            "china_related": sum(1 for article in refs if article.get("china_related")),
        })
    institutions.sort(key=lambda item: item["publication_count"], reverse=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "data/literature-full.json",
        "strategy": "author_key + canonical_institution_key",
        "normalization_rules": CANONICAL_INSTITUTION_RULES,
        "summary": {
            "person_profiles": len(profile_summaries),
            "china_person_profiles": sum(1 for item in profile_summaries if item.get("is_china_profile")),
            "canonical_institutions": len(institutions),
        },
        "person_profiles": profile_summaries,
        "canonical_institutions": institutions,
    }
    atomic_write_json(ENTITY_NORMALIZATION_INDEX_PATH, payload)
    print(f"✅ {ENTITY_NORMALIZATION_INDEX_PATH.relative_to(PROJECT)}")


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


def select_module_references(articles, spec, used_pmids):
    """按模块边界挑选文献，尽量避免不同模块复用同一 PMID。"""
    scored = score_articles_flexible(
        articles,
        spec["keywords"],
        min_hits=spec.get("min_hits", 1),
        within_days=spec.get("within_days"),
    )
    excludes = spec.get("exclude_keywords", [])
    required_any = spec.get("required_keywords", [])
    required_all = spec.get("required_all_keywords", [])
    refs = []
    for _, _, article in scored:
        text = text_of(article)
        pmid = article.get("pmid") or re.sub(r"\W+", "", article.get("title", "").lower())
        if pmid in used_pmids:
            continue
        if required_any and not any(term in text for term in required_any):
            continue
        if required_all and any(term not in text for term in required_all):
            continue
        if excludes and any(term in text for term in excludes):
            continue
        refs.append(compact_article(article))
        used_pmids.add(pmid)
        if len(refs) >= spec.get("limit", 8):
            break
    return refs


def best_evidence_level(refs):
    rank = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
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

    clinical_pipeline = clinical_registry.build_clinical_pipeline_matrix(
        regulatory_map,
        cache_path=CLINICALTRIALS_CACHE_PATH,
        requests_module=requests,
    )
    chictr_payload = clinical_registry.load_chictr_cache(CHICTR_CACHE_PATH)
    registry_signals = clinical_registry.normalize_registry_trials(
        read_json(CLINICALTRIALS_CACHE_PATH) if CLINICALTRIALS_CACHE_PATH.exists() else {},
        chictr_payload,
    )

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
        "trial_registry_signals": registry_signals,
        "chictr_meta": {
            "source": chictr_payload.get("source"),
            "mode": chictr_payload.get("mode", "cache"),
            "last_verified": chictr_payload.get("last_verified", ""),
            "count": len(chictr_payload.get("records") or []),
            "evidence_policy": "registry records do not receive Oxford evidence levels",
        },
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
        {
            "id": "module_academic_mechanism",
            "category": "纯学术探讨",
            "type": "机制分型",
            "title": "抗体分型与发病机制",
            "keywords": ["autoantibody", "achr", "musk", "lrp4", "pathogenic", "biomarker", "mechanism", "pathogenesis"],
            "required_keywords": ["autoantibody", "achr", "musk", "lrp4", "pathogenic", "biomarker", "mechanism", "pathogenesis"],
            "exclude_keywords": [
                "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab", "eculizumab", "ravulizumab", "zilucoplan",
                "trial", "efficacy", "safety", "treatment", "therapeutic", "inhibitor", "phase 2", "phase 3",
            ],
            "purpose": "用于非产品化学术开场，讨论 AChR/MuSK/LRP4、抗体功能和潜在生物标志物。",
            "boundary": "不承担具体产品疗效或竞品比较结论。",
        },
        {
            "id": "module_academic_china_rwe",
            "category": "纯学术探讨",
            "type": "中国实践",
            "title": "中国真实世界与患者价值",
            "keywords": ["china", "chinese", "real-world", "preference", "willingness", "cohort", "registry", "burden"],
            "required_keywords": ["china", "chinese"],
            "exclude_keywords": [
                "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab", "eculizumab", "ravulizumab", "zilucoplan",
                "phase 2", "phase 3", "placebo-controlled", "randomized", "randomised", "car-t", "bcma",
            ],
            "purpose": "用于讨论中国患者路径、偏好、负担和本土真实世界证据缺口。",
            "boundary": "不直接引申为产品获益或准入结论。",
        },
        {
            "id": "module_academic_guideline",
            "category": "纯学术探讨",
            "type": "诊疗路径",
            "title": "诊疗路径与共识问题",
            "keywords": ["guideline", "consensus", "recommendation", "delphi", "clinical practice"],
            "required_keywords": ["guideline", "consensus", "recommendation", "delphi"],
            "exclude_keywords": ["stroke unit", "plasma exchange", "dysphagia"],
            "purpose": "用于梳理指南、共识和临床路径中的未决问题，适合做开放式探访。",
            "boundary": "不替代指南原文解读，不做超适应症推荐。",
        },
        {
            "id": "module_product_efg_efficacy",
            "category": "产品相关",
            "type": "疗效与人群",
            "title": "Efgartigimod 疗效与适用人群",
            "keywords": ["efgartigimod", "efficacy", "response", "adapt", "clinical effectiveness", "subgroup", "steroid-sparing"],
            "required_all_keywords": ["efgartigimod"],
            "required_keywords": ["efficacy", "response", "adapt", "clinical effectiveness", "subgroup", "steroid-sparing"],
            "exclude_keywords": ["melanoma", "pembrolizumab", "car t", "car-t", "bcma", "autoimmune encephalitis"],
            "purpose": "用于把 efgartigimod 疗效、应答特征和患者选择问题接入专家兴趣。",
            "boundary": "不与安全性模块重复展开不良事件管理。",
        },
        {
            "id": "module_product_efg_safety",
            "category": "产品相关",
            "type": "安全性与管理",
            "title": "Efgartigimod 安全性与用药管理",
            "keywords": ["efgartigimod", "safety", "infection", "adverse", "tolerability", "monitoring", "immunoglobulin", "ivig", "pharmacovigilance", "faers"],
            "required_all_keywords": ["efgartigimod"],
            "required_keywords": ["safety", "infection", "adverse", "tolerability", "monitoring", "immunoglobulin", "ivig", "pharmacovigilance", "faers"],
            "exclude_keywords": ["melanoma", "pembrolizumab", "car t", "car-t", "bcma", "autoimmune encephalitis"],
            "min_hits": 2,
            "purpose": "用于讨论感染、IgG 变化、停药/再治疗和真实世界用药管理。",
            "boundary": "不重复疗效终点和竞品定位。",
        },
        {
            "id": "module_product_landscape",
            "category": "产品相关",
            "type": "治疗格局",
            "title": "靶向治疗格局与竞品定位",
            "keywords": ["rozanolixizumab", "nipocalimab", "batoclimab", "ravulizumab", "eculizumab", "zilucoplan", "complement", "fcrn", "indirect comparison"],
            "required_keywords": ["rozanolixizumab", "nipocalimab", "batoclimab", "ravulizumab", "eculizumab", "zilucoplan", "complement", "fcrn"],
            "exclude_keywords": ["dysphagia", "speech-language"],
            "purpose": "用于讨论 FcRn、补体和其他靶向治疗在证据层级、机制和定位上的差异。",
            "boundary": "不替代头对头研究，不做未证实优劣断言。",
        },
    ]
    used_pmids = set()
    for spec in specs:
        refs = select_module_references(recent, spec, used_pmids)
        modules.append({
            "id": spec["id"],
            "category": spec["category"],
            "type": spec["type"],
            "title": spec["title"],
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "verified": False,
            "placeholder": len(refs) == 0,
            "summary": spec["purpose"],
            "purpose": spec["purpose"],
            "boundary": spec["boundary"],
            "keywords": spec["keywords"],
            "claims": [
                {"text": ref.get("title", ""), "pmid": ref.get("pmid", ""), "evidence_level": ref.get("evidence_level") or "未分类"}
                for ref in refs[:4]
            ],
            "references": refs,
        })
    templates = [
        {"id": "weekly_brief", "name": "文献速递简报", "modules": ["module_academic_china_rwe", "module_product_efg_efficacy", "module_product_efg_safety"]},
        {"id": "visit_material", "name": "拜访材料", "modules": ["module_academic_mechanism", "module_product_efg_efficacy", "module_product_landscape"]},
        {"id": "academic_probe", "name": "纯学术探访", "modules": ["module_academic_mechanism", "module_academic_china_rwe", "module_academic_guideline"]},
        {"id": "product_discussion", "name": "产品相关沟通", "modules": ["module_product_efg_efficacy", "module_product_efg_safety", "module_product_landscape"]},
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "design": "6 个模块按医学事务场景拆分为 3 个纯学术探讨和 3 个产品相关，文献 PMID 尽量不跨模块重复。",
            "academic_modules": 3,
            "product_modules": 3,
        },
        "modules": modules,
        "templates": templates,
        "compliance_rules": [
            {"id": "pmid_required", "label": "每条声明必须绑定 PMID", "type": "rule"},
            {"id": "source_confirmed", "label": "正式使用前建议确认引用来源", "type": "workflow"},
            {"id": "placeholder_block", "label": "资料不足模块不得进入最终材料", "type": "rule"},
            {"id": "claim_source_check", "label": "适应症、疗效、安全性结论需核对原文", "type": "rule"},
        ],
    }


def load_knowledge_dashboard_stats():
    """读取知识库已生成统计；失败时返回空值，避免 dashboard 强依赖知识图谱构建顺序。"""
    path = DATA_DIR / "knowledge-graph.js"
    if not path.exists():
        return {}
    try:
        payload = load_js_global(path, "MG_KNOWLEDGE_GRAPH")
    except ValueError:
        return {}
    stats = payload.get("stats", {})
    return {
        "generated_at": payload.get("generated_at", ""),
        "matched_articles": stats.get("matched_articles", 0),
        "evidence_articles": stats.get("evidence_articles", 0),
        "nodes": stats.get("total_nodes", 0),
        "edges": stats.get("edges", 0),
        "matrix_rows": stats.get("evidence_matrix_rows", 0),
    }


def build_dashboard(recent, signals, experts, china, landscape, modules, total_count):
    expert_count = experts.get("summary", {}).get("indexed_experts", len(experts.get("experts", [])))
    expert_summary = experts.get("summary", {})
    module_summary = modules.get("summary", {})
    landscape_overview = landscape.get("overview", {})
    knowledge_stats = load_knowledge_dashboard_stats()
    expert_manifest = build_expert_manifest(experts)
    initial_expert_payload = json.dumps(expert_manifest, ensure_ascii=False, separators=(",", ":"))
    if experts.get("china_expert_index"):
        initial_expert_payload += json.dumps(
            {"items": experts.get("china_expert_index") or []},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    expert_payload_mb = round(
        len(initial_expert_payload) / 1024 / 1024,
        1,
    )
    pipeline_policy = {
        "label": "周更管线",
        "value": "每周日 23:00",
        "note": "PubMed 周更、证据分级、IF/CAS、前端数据同步",
        "href": "pages/data-ops.html",
    }
    section_cards = [
        {
            "id": "literature",
            "title": "情报中心",
            "href": "pages/literature.html",
            "metric": f"{len(signals['signals'])} 条信号",
            "summary": "近一年文献、近 14 天信号、主题热点和中国相关证据。",
            "facts": [
                f"近一年 {len(recent)} 篇",
                f"中国相关 {china['summary']['recent_year_articles']} 篇",
                f"强信号 {sum(1 for item in signals['signals'] if item.get('strength') == '强')} 条",
            ],
        },
        {
            "id": "landscape",
            "title": "诊治格局",
            "href": "pages/landscape.html",
            "metric": f"{landscape_overview.get('living_answer_count', len(landscape.get('living_answers', [])))} 个判断",
            "summary": landscape_overview.get("positioning", "将近期证据转译成治疗格局、竞争定位和中国实践差异。"),
            "facts": [
                f"格局变化 {landscape_overview.get('month_change_count', len(landscape.get('monthly_changes', [])))} 条",
                f"临床管线 {landscape_overview.get('clinical_pipeline_count', len(landscape.get('clinical_pipeline_matrix', [])))} 项",
                f"证据问题 {len(landscape.get('evidence_questions', []))} 个",
            ],
        },
        {
            "id": "knowledge",
            "title": "知识库",
            "href": "pages/knowledge.html",
            "metric": f"{knowledge_stats.get('nodes', 0)} 个节点",
            "summary": "基于 PubMed abstract 的知识图谱、证据矩阵和专题层。",
            "facts": [
                f"命中文献 {knowledge_stats.get('matched_articles', 0)} 篇",
                f"关系 {knowledge_stats.get('edges', 0)} 条",
                f"证据矩阵 {knowledge_stats.get('matrix_rows', 0)} 行",
            ],
        },
        {
            "id": "msl",
            "title": "MSL 工作台",
            "href": "pages/msl.html",
            "metric": f"{expert_count} 位作者画像",
            "summary": "专家画像、拜访助手、学术/产品信息模块和文献清单生成。",
            "facts": [
                f"中国 {expert_summary.get('indexed_china_experts', 0)} 位",
                f"国外 {expert_summary.get('indexed_international_experts', 0)} 位",
                f"内容模块 {len(modules.get('modules', []))} 个",
            ],
        },
        {
            "id": "data",
            "title": "数据状态",
            "href": "pages/data-ops.html",
            "metric": "周更可追踪",
            "summary": "数据源、构建产物、运行日志和前端数据文件状态。",
            "facts": [
                "GitHub Pages 数据产物",
                "PubMed + ClinicalTrials",
                "公开数据不含拜访记录",
            ],
        },
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_articles": total_count,
            "recent_articles": len(recent),
            "china_articles": china["summary"]["recent_year_articles"],
            "signals": len(signals["signals"]),
            "experts": expert_count,
            "modules": len(modules["modules"]),
            "landscape_questions": len(landscape.get("evidence_questions", [])),
            "knowledge_nodes": knowledge_stats.get("nodes", 0),
        },
        "stat_cards": [
            {"label": "近一年文献", "value": len(recent), "note": f"full {total_count} 篇"},
            {"label": "14 天信号", "value": len(signals["signals"]), "note": "规则评分候选"},
            {"label": "中国证据", "value": china["summary"]["recent_year_articles"], "note": f"高等级 {china['summary'].get('high_evidence', 0)} 篇"},
            {"label": "作者画像", "value": expert_count, "note": f"中国 {expert_summary.get('indexed_china_experts', 0)} / 国外 {expert_summary.get('indexed_international_experts', 0)}"},
            {"label": "MSL 模块", "value": len(modules["modules"]), "note": f"学术 {module_summary.get('academic_modules', 0)} / 产品 {module_summary.get('product_modules', 0)}"},
            {"label": "知识节点", "value": knowledge_stats.get("nodes", 0), "note": f"矩阵 {knowledge_stats.get('matrix_rows', 0)} 行"},
        ],
        "sections": section_cards,
        "workflows": [
            pipeline_policy,
            {
                "label": "专家画像",
                "value": f"{expert_summary.get('frontend_quick_expert_limit', 20)} 位快捷候选",
                "note": "首页和 MSL 默认只渲染快捷候选，搜索时进入全量索引。",
                "href": "pages/msl.html",
            },
            {
                "label": "内容模块",
                "value": f"{module_summary.get('academic_modules', 0)} 学术 + {module_summary.get('product_modules', 0)} 产品",
                "note": "拜访助手将专家兴趣、近期信号和模块文献合并生成建议。",
                "href": "pages/msl.html",
            },
        ],
        "data_health": [
            {"label": "专家前端索引", "value": f"首屏约 {expert_payload_mb} MB，按区域分片", "state": "ok"},
            {"label": "知识图谱", "value": f"{knowledge_stats.get('nodes', 0)} 节点", "state": "ok" if knowledge_stats.get("nodes") else "warn"},
            {"label": "证据矩阵", "value": f"{knowledge_stats.get('matrix_rows', 0)} 行", "state": "ok" if knowledge_stats.get("matrix_rows") else "warn"},
            {"label": "周更策略", "value": "增量更新", "state": "ok"},
        ],
        "signal_summary": build_signal_summary(signals["signals"]),
        "top_signals": signals["signals"][:5],
        "work_items": [
            {"type": "文献", "label": "近 14 天信号", "count": len(signals["signals"]), "href": "pages/literature.html"},
            {"type": "专家", "label": "已构建专家画像", "count": expert_count, "href": "pages/msl.html"},
            {"type": "模块", "label": "MSL 内容模块", "count": sum(1 for m in modules["modules"] if not m["verified"]), "href": "pages/msl.html"},
            {"type": "证据", "label": "待确认证据矩阵", "count": len(landscape["evidence_questions"]), "href": "pages/landscape.html"},
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
    if args.rebuild_experts_from_full and full is not None:
        write_expert_shards(experts, DATA_DIR)
        print(f"✅ {EXPERT_JS_PATH.relative_to(PROJECT)} + 2 regional shards")
    else:
        print("ℹ️  preservation mode：未改写 expert manifest 与两个区域分片。")
    write_js("landscape-data.js", "MG_LANDSCAPE_DATA", landscape)
    write_js("content-modules.js", "MG_CONTENT_MODULES", modules)
    write_js("dashboard-data.js", "MG_DASHBOARD_DATA", dashboard)


if __name__ == "__main__":
    main()
