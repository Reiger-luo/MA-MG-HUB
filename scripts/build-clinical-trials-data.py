#!/usr/bin/env python3
"""从已审计缓存构建情报中心临床试验数据。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common.clinical_registry import load_china_drug_trials_cache
from scripts.common.io import atomic_write_json
from scripts.common.source_channels import _cdt_items, _chictr_items, _ct_items, deduplicate_trials


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CT_CACHE_PATH = DATA_DIR / "clinicaltrials-pipeline-cache.json"
CHICTR_CACHE_PATH = DATA_DIR / "chictr-trials-cache.json"
CHINA_DRUG_TRIALS_CACHE_PATH = DATA_DIR / "china-drug-trials-cache.json"
OUTPUT_PATH = DATA_DIR / "clinical-trials-data.js"
summaryOutputPath = DATA_DIR / "clinicalTrialsSummary.js"
# 周更对比基线：本地与 CI 均提交入仓库，保证下一次构建能还原上一期快照
WEEKLY_CHANGES_SNAPSHOT_PATH = DATA_DIR / "clinicaltrials-weekly-changes-snapshot.json"
WEEKLY_CHANGES_WINDOW_DAYS = 7

SOURCE_ORDER = ["ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials"]
INDICATION = "重症肌无力"

STATUS_MAP = {
    "RECRUITING": ("招募中", "recruiting"),
    "ENROLLING_BY_INVITATION": ("招募中", "recruiting"),
    "ACTIVE_NOT_RECRUITING": ("进行中", "active"),
    "COMPLETED": ("已完成", "completed"),
    "TERMINATED": ("已终止", "terminated"),
    "WITHDRAWN": ("已撤回", "terminated"),
    "SUSPENDED": ("暂停", "other"),
    "NOT_YET_RECRUITING": ("尚未招募", "recruiting"),
    "UNKNOWN": ("未知", "other"),
}

DRUG_CLASS_TERMS = (
    (
        "FcRn 拮抗剂",
        (
            "batoclimab",
            "efgartigimod",
            "rozanolixizumab",
            "nipocalimab",
            "m281",
            "imvt-1401",
            "imvt-1402",
            "fcrn antagonist",
            "fcrn inhibitor",
            "hbm9161",
            "hl161",
            "艾加莫德",
            "argx-113",
            "罗泽利昔珠单抗",
        ),
    ),
    (
        "补体抑制剂",
        (
            "eculizumab",
            "ravulizumab",
            "zilucoplan",
            "crovalimab",
            "complement inhibitor",
            "complement inhibition",
            "cemdisiran",
            "pozelimab",
            "依库珠单抗",
            "瑞利珠单抗",
            "alxn1720",
        ),
    ),
    (
        "B细胞/抗CD19/CD20",
        (
            "rituximab",
            "ocrelizumab",
            "inebilizumab",
            "telitacicept",
            "anti-cd19",
            "anti-cd20",
            "泰它西普",
            "sys6020",
            "bcma",
            "senl103",
            "car-t",
            "cizutamig",
        ),
    ),
    (
        "免疫抑制剂",
        (
            "mycophenolate",
            "azathioprine",
            "tacrolimus",
            "cyclosporine",
            "methotrexate",
            "cladribine",
            "remibrutinib",
            "lou064",
            "btk inhibitor",
            "硫唑嘌呤",
            "他克莫司",
            "克拉屈滨",
        ),
    ),
    ("胆碱酯酶抑制剂", ("pyridostigmine", "溴吡斯的明", "huperzine", "石杉碱甲", "edrophonium", "依酚氯铵")),
    (
        "免疫调节",
        (
            "plasma exchange",
            "plex",
            "ivig",
            "immunoglobulin",
            "immune globulin",
        ),
    ),
    (
        "IL-6 抑制剂",
        ("satralizumab", "萨特利珠单抗", "tocilizumab", "sar442168"),
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    """读取构建所需的本地 JSON 缓存。"""
    return json.loads(path.read_text(encoding="utf-8"))


def date_part(value: Any) -> str:
    """提取 ISO 日期部分，避免构建时间随运行时钟变化。"""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or "").strip())
    return match.group(1) if match else ""


def normalize_status(value: Any) -> tuple[str, str]:
    """将注册库状态统一为中文标签和前端样式类。"""
    raw_status = str(value or "").strip()
    status_key = re.sub(r"[\s-]+", "_", raw_status.upper())
    return STATUS_MAP.get(status_key, (raw_status, "other"))


def contains_term(text: str, term: str) -> bool:
    """短缩写使用词边界匹配，避免 PLEX 命中 complex 等单词。"""
    if term in {"m281", "plex", "ivig"}:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


def extract_drug_class(title: Any, drug_name: Any = "") -> str:
    """仅从归一化题名和药物名称提取药物机制分类。"""
    normalized = (str(title or "") + " " + str(drug_name or "")).lower()
    for drug_class, terms in DRUG_CLASS_TERMS:
        if any(contains_term(normalized, term) for term in terms):
            return drug_class
    return "其他"


def phase_label(value: Any) -> str:
    """将 CT.gov 或中文注册库的分期字段转为可读文本。"""
    if isinstance(value, list):
        values = [phase_label(item) for item in value if item]
        values = [item for item in values if item != "未标注"]
        return " / ".join(dict.fromkeys(values)) or "未标注"

    raw_phase = str(value or "").strip()
    phase_key = raw_phase.upper().replace(" ", "_")
    labels = {
        "EARLY_PHASE1": "Early Phase 1",
        "PHASE1": "Phase 1",
        "PHASE1_PHASE2": "Phase 1/2",
        "PHASE2": "Phase 2",
        "PHASE2_PHASE3": "Phase 2/3",
        "PHASE3": "Phase 3",
        "PHASE4": "Phase 4",
        "NA": "N/A",
        "N/A": "N/A",
        "UNKNOWN": "未标注",
    }
    return labels.get(phase_key, raw_phase or "未标注")


def ct_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 NCT 编号索引 CT.gov 中未进入轻量归一化结果的展示字段。"""
    result: dict[str, dict[str, Any]] = {}
    for study in payload.get("studies") or []:
        protocol = study.get("protocolSection") or {}
        identification = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        design = protocol.get("designModule") or {}
        sponsor = protocol.get("sponsorCollaboratorsModule") or {}
        registry_id = identification.get("nctId") or ""
        if not registry_id:
            continue
        result[registry_id] = {
            "phase": design.get("phases") or [],
            "sponsor": (sponsor.get("leadSponsor") or {}).get("name") or "",
            "start_date": (status.get("startDateStruct") or {}).get("date") or "",
            "registered_date": (
                (status.get("studyFirstPostDateStruct") or {}).get("date")
                or status.get("studyFirstSubmitDate")
                or ""
            ),
        }
    return result


def chictr_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 ChiCTR 编号索引起始日期等缓存字段。"""
    return {
        str(record.get("registry_id") or ""): {
            "start_date": record.get("start_date") or "",
            "registered_date": record.get("registered_date") or "",
        }
        for record in payload.get("records") or []
        if record.get("registry_id")
    }


def enrich_record(
    item: dict[str, Any],
    ct_details: dict[str, dict[str, Any]],
    chictr_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """补齐前端卡片、状态和筛选器所需字段。"""
    registry = str(item.get("registry") or item.get("source") or "")
    registry_id = str(item.get("registry_id") or item.get("id") or "")
    details = ct_details.get(registry_id, {}) if registry == "ClinicalTrials.gov" else chictr_details.get(registry_id, {})
    status = str(item.get("status") or "Unknown")
    status_label, status_class = normalize_status(status)
    linked_registries = sorted(
        item.get("linked_registries") or [],
        key=lambda linked: (
            str(linked.get("registry") or ""),
            str(linked.get("registry_id") or ""),
        ),
    )

    return {
        "registry": registry,
        "registry_id": registry_id,
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "status": status,
        "status_label": status_label,
        "status_class": status_class,
        "drug_class": extract_drug_class(item.get("title"), item.get("drug_name")),
        "drug_name": str(item.get("drug_name") or ""),
        "drug_names": split_combo_drugs(item.get("drug_names") or []),
        "indication": INDICATION,
        "phase_label": phase_label(details.get("phase", item.get("phase"))),
        "sponsor": str(item.get("sponsor") or details.get("sponsor") or ""),
        "start_date": str(item.get("start_date") or details.get("start_date") or ""),
        "readout_date": str(item.get("readout_date") or ""),
        "completion_date": str(item.get("completion_date") or ""),
        "registered_date": str(details.get("registered_date") or item.get("date") or ""),
        "linked_registries": linked_registries,
    }


def six_month_cutoff(reference: date) -> date:
    """计算自然月口径的六个月前日期。"""
    month_index = reference.year * 12 + reference.month - 1 - 6
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    month_lengths = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(reference.day, month_lengths[month - 1]))


def parse_iso_date(value: Any) -> date | None:
    """宽容解析 YYYY-MM-DD 日期。"""
    try:
        return date.fromisoformat(date_part(value))
    except ValueError:
        return None


def build_decision_signals(records: list[dict[str, Any]], generated_at: str) -> list[dict[str, str]]:
    """基于完整记录集生成稳定、可复核的决策信号。"""
    recruiting_keys = {"RECRUITING", "ENROLLING_BY_INVITATION"}
    recruiting_count = sum(
        re.sub(r"[\s-]+", "_", record.get("status", "").upper()) in recruiting_keys
        for record in records
    )

    known_class_counts = Counter(
        record["drug_class"] for record in records if record.get("drug_class") not in {"", "其他"}
    )
    if known_class_counts:
        leading_class, leading_count = sorted(
            known_class_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        class_detail = f"{leading_class}在可识别机制中最多，共 {leading_count} 项。"
    else:
        class_detail = "当前题名未识别出明确药物机制分类。"

    reference_date = parse_iso_date(generated_at)
    cutoff = six_month_cutoff(reference_date) if reference_date else None
    recent_count = sum(
        bool(registered_date and cutoff and cutoff <= registered_date <= reference_date)
        for registered_date in (parse_iso_date(record.get("registered_date")) for record in records)
    )

    return [
        {
            "title": "招募中试验",
            "detail": f"当前共有 {recruiting_count} 项招募中或邀请入组试验。",
            "tag": "招募",
        },
        {
            "title": "药物机制热点",
            "detail": class_detail,
            "tag": "药物分类",
        },
        {
            "title": "近 6 个月新登记",
            "detail": f"截至 {generated_at}，近 6 个月登记 {recent_count} 项试验。",
            "tag": "近期登记",
        },
    ]


PHASE_RANK = {
    "Early Phase 1": 0.5, "Phase 1": 1, "Phase 1/2": 1.5,
    "Phase 2": 2, "Phase 2/3": 2.5, "Phase 3": 3, "Phase 4": 4,
}

DRUG_CLASS_ORDER = [
    "FcRn 拮抗剂", "补体抑制剂", "B细胞/抗CD19/CD20",
    "IL-6 抑制剂", "免疫抑制剂", "胆碱酯酶抑制剂", "免疫调节", "其他",
]

# Canonical drug name mapping: lowercase alias → display name
DRUG_SYNONYMS: dict[str, str] = {
    # FcRn
    "efgartigimod": "Efgartigimod (艾加莫德)",
    "efgartigimod ph20 sc": "Efgartigimod (艾加莫德)",
    "efgartigimod alfa": "Efgartigimod (艾加莫德)",
    "efgartigimod iv": "Efgartigimod (艾加莫德)",
    "argx-113": "Efgartigimod (艾加莫德)",
    "argx-113-2308": "Efgartigimod (艾加莫德)",
    "艾加莫德": "Efgartigimod (艾加莫德)",
    "艾加莫德α注射液": "Efgartigimod (艾加莫德)",
    "艾加莫德α注射液（皮下注射）": "Efgartigimod (艾加莫德)",
    "艾加莫德 α 注射液": "Efgartigimod (艾加莫德)",
    "efgartigimod浓缩注射液": "Efgartigimod (艾加莫德)",
    "efgartigimod注射液": "Efgartigimod (艾加莫德)",
    "vyvgart": "Efgartigimod (艾加莫德)",
    "igamuratid": "Efgartigimod (艾加莫德)",
    "igamuratid α": "Efgartigimod (艾加莫德)",
    "rozanolixizumab": "Rozanolixizumab (罗泽利昔珠单抗)",
    "罗泽利昔珠单抗注射液": "Rozanolixizumab (罗泽利昔珠单抗)",
    "nipocalimab": "Nipocalimab (尼卡利单抗)",
    "nipocalimab注射液": "Nipocalimab (尼卡利单抗)",
    "hbm9161": "Batoclimab (巴托利单抗)",
    "hbm9161注射液": "Batoclimab (巴托利单抗)",
    "hbm9161 injection (680mg)": "Batoclimab (巴托利单抗)",
    "hbm9161(hl161bkn)注射液": "Batoclimab (巴托利单抗)",
    "hl161": "Batoclimab (巴托利单抗)",
    "imvt-1401": "Batoclimab (巴托利单抗)",
    "imvt-1402": "IMVT-1402",
    "batoclimab": "Batoclimab (巴托利单抗)",
    "m281": "Batoclimab (巴托利单抗)",
    "mom-m281": "Batoclimab (巴托利单抗)",
    # Complement
    "eculizumab": "Eculizumab (依库珠单抗)",
    "依库珠单抗": "Eculizumab (依库珠单抗)",
    "依库珠单抗注射液": "Eculizumab (依库珠单抗)",
    "ravulizumab": "Ravulizumab (瑞利珠单抗)",
    "瑞利珠单抗注射液": "Ravulizumab (瑞利珠单抗)",
    "alxn1720": "Ravulizumab (瑞利珠单抗)",
    "alxn1720注射液": "Ravulizumab (瑞利珠单抗)",
    "zilucoplan": "Zilucoplan (泽卢克布仑钠)",
    "zilucoplan (ra101495)": "Zilucoplan (泽卢克布仑钠)",
    "ra101495": "Zilucoplan (泽卢克布仑钠)",
    "zilbrysq": "Zilucoplan (泽卢克布仑钠)",
    "zylbrysq": "Zilucoplan (泽卢克布仑钠)",
    "crovalimab": "Crovalimab",
    "cemdisiran": "Cemdisiran",
    "pozelimab": "Pozelimab",
    # B-cell
    "telitacicept": "Telitacicept (泰它西普)",
    "泰它西普": "Telitacicept (泰它西普)",
    "泰它西普注射液": "Telitacicept (泰它西普)",
    "注射用泰它西普": "Telitacicept (泰它西普)",
    "tetanercept": "Telitacicept (泰它西普)",
    "rituximab": "Rituximab (利妥昔单抗)",
    "inebilizumab": "Inebilizumab",
    "inebilizumab 注射液": "Inebilizumab",
    "sys6020注射液": "SYS6020 (BCMA CAR-T)",
    "senl103自体t细胞注射液": "SENL103 (CAR-T)",
    "cizutamig": "Cizutamig",
    "cizutamig注射液": "Cizutamig",
    # IL-6
    "satralizumab": "Satralizumab (萨特利珠单抗)",
    "萨特利珠单抗注射液": "Satralizumab (萨特利珠单抗)",
    "sar442168": "SAR442168 (已终止)",
    # Immunosuppressants
    "remibrutinib": "Remibrutinib (LOU064)",
    "remibrutinib (lou064)": "Remibrutinib (LOU064)",
    "cladribine": "Cladribine (克拉屈滨)",
    "克拉屈滨胶囊": "Cladribine (克拉屈滨)",
    "azathioprine": "Azathioprine (硫唑嘌呤)",
    "硫唑嘌呤片": "Azathioprine (硫唑嘌呤)",
    "tacrolimus": "Tacrolimus (他克莫司)",
    "他克莫司胶囊": "Tacrolimus (他克莫司)",
    "shr-2173注射液": "SHR-2173",
    "b007注射液": "B007",
    # Cholinesterase
    "pyridostigmine": "Pyridostigmine (溴吡斯的明)",
    "溴吡斯的明片": "Pyridostigmine (溴吡斯的明)",
    "溴吡斯的明缓释片": "Pyridostigmine (溴吡斯的明)",
    "huperzine": "Huperzine A (石杉碱甲)",
    "石杉碱甲口服溶液": "Huperzine A (石杉碱甲)",
    "edrophonium": "Edrophonium (依酚氯铵)",
    "依酚氯铵注射液": "Edrophonium (依酚氯铵)",
    # Immunomodulation
    "ivig": "IVIg (静注人免疫球蛋白)",
    "gamma globulin": "IVIg (静注人免疫球蛋白)",
    "immunoglobulin": "IVIg (静注人免疫球蛋白)",
    "plasma exchange": "Plasma Exchange (血浆置换)",
    "plex": "Plasma Exchange (血浆置换)",
    # Corticosteroids / Other
    "methylprednisolone": "Methylprednisolone (甲泼尼龙)",
    "甲泼尼龙": "Methylprednisolone (甲泼尼龙)",
    "prednisone": "Prednisone (泼尼松)",
    "泼尼松": "Prednisone (泼尼松)",
    "mycophenolate": "Mycophenolate (吗替麦考酚酯)",
    "吗替麦考酚酯": "Mycophenolate (吗替麦考酚酯)",
    "belimumab": "Belimumab",
    "注射用重组人b淋巴细胞刺激因子受体－抗体融合蛋白": "Belimumab",
    "agamod": "Efgartigimod (艾加莫德)",
    "egamod": "Efgartigimod (艾加莫德)",
    "empasiprubart": "Empasiprubart",
    "ublituximab": "Ublituximab",
    "amifampridine": "Amifampridine (氨吡啶)",
    "3,4-diaminopyridine": "Amifampridine (氨吡啶)",
    "3,4-dap": "Amifampridine (氨吡啶)",
    "granulocyte-macrophage colony-stimulating factor": "GM-CSF",
    "gm-csf": "GM-CSF",
    "sargramostim": "GM-CSF",
}


# 安慰剂/对照干预名称子串，归一化时直接丢弃
_PLACEBO_TOKENS = ("placebo", "安慰剂", "生理盐水", "normal saline", "vehicle", "sham",
                   "sodium chloride", "氯化钠")

# 非药物干预关键词（手术/针灸/运动/教育/注册研究/生物标志物等）
_NON_DRUG_KEYWORDS = (
    "acupuncture", "针灸", "thymectomy", "胸腺切除", "surgery", "手术",
    "exercise", "运动", "education", "教育", "registry", "登记", "注册研究",
    "biomarker", "生物标志物", "transplant", "移植", "catgut", "埋线",
    "blood sample", "采血", "burden of disease", "疾病负担",
    "immune profile", "免疫谱", "auto-antibod", "自身抗体",
    "psyche", "心理", "standard of care", "常规治疗",
    "tonify", "补中", "益气", "健脾", "补肾", "升阳",
    "robotic", "机器人", "thoracoscopic", "胸腔镜",
    "vitaccess", "ide study", "inpatient",
    "treatment with", "medication", "hormone", "激素",
)

# 英语虚词（用于检测句子碎片）
_EN_FUNCTION_WORDS = {"the", "of", "in", "and", "with", "for", "by", "was",
                      "were", "is", "are", "a", "an", "on", "to", "from", "or"}

# 剂型/给药途径 token（模糊归一化时剥离）
_ROUTE_RE = re.compile(
    r"\b(?:iv|sc|im|oral|subcutaneous|intravenous|injection|infusion|solution"
    r"|注射液|注射用|浓缩|片|胶囊|口服溶液)\b",
    re.I,
)
# 剂量括号，如 (680mg) (10mg/kg, qweek *4 cycles)
_DOSE_PAREN_RE = re.compile(r"[(（][^)）]*(?:mg|ml|μg|mcg|kg|dose|剂量)[^)）]*[)）]", re.I)
# 裸剂量，如 340 mg
_DOSE_BARE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|ml|μg|mcg|g)\b", re.I)
# 联用分隔符
_COMBO_SPLIT_RE = re.compile(r"\s*[+＋]\s*|联合|联用")


def normalize_drug_name(raw: str) -> str:
    """Map raw drug name to canonical display name.

    三级匹配：精确 → 剥离剂型/剂量后精确 → 已知别名子串（最长优先）。
    安慰剂类名称返回空串。
    """
    if not raw:
        return ""
    key = raw.strip().lower()
    # 1. Exact
    if key in DRUG_SYNONYMS:
        return DRUG_SYNONYMS[key]
    # 2. Strip dose/route tokens then exact
    cleaned = _DOSE_PAREN_RE.sub("", key)
    cleaned = _DOSE_BARE_RE.sub("", cleaned)
    cleaned = _ROUTE_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,·、")
    if cleaned in DRUG_SYNONYMS:
        return DRUG_SYNONYMS[cleaned]
    # 3. Longest known alias as substring (wins over placebo discard)
    for alias in sorted(DRUG_SYNONYMS, key=len, reverse=True):
        if len(alias) >= 4 and alias in cleaned:
            return DRUG_SYNONYMS[alias]
    # 4. Placebo / non-drug interventions → discard
    if any(tok in key for tok in _PLACEBO_TOKENS):
        return ""
    if any(kw in key for kw in _NON_DRUG_KEYWORDS):
        return ""
    # 5. Sentence fragments / noise → discard
    result = raw.strip()
    words = result.split()
    # English sentence with function words → not a drug name
    if len(words) > 3:
        func_count = sum(1 for w in words if w.lower().strip(".,;:()") in _EN_FUNCTION_WORDS)
        if func_count >= 2:
            return ""
    # Long Chinese phrases without known drug tokens → not a drug name
    if len(result) > 12 and not re.search(r"[a-zA-Z]", result):
        return ""
    return result


def split_combo_drugs(raw_names: list[str]) -> list[str]:
    """拆分联用药物名称（+ / 联合）并逐个归一化，保留顺序去重。"""
    out: list[str] = []
    for raw in raw_names:
        for part in _COMBO_SPLIT_RE.split(str(raw)):
            norm = normalize_drug_name(part.strip())
            if norm and norm not in out:
                out.append(norm)
    return out


def _extract_drug_name(record: dict[str, Any]) -> str:
    """从记录中提取药物名称并归一化（fallback 路径）。"""
    drug = str(record.get("drug_name") or "").strip()
    if drug and drug != "NA":
        return normalize_drug_name(drug)
    # Fallback: try to extract from title
    title = str(record.get("title") or "")
    if not title:
        return record.get("registry_id", "Unknown")
    norm = normalize_drug_name(title)
    return norm if norm != title.strip() else title[:60]


def build_pipeline_matrix(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按药物机制分类 → 药物名称聚合为管线矩阵行。

    联用试验（drug_names 多个）会出现在每个药物行下（多标签可筛选）。
    """
    # Group by (drug_class, drug_name) — combo trials appear under each drug
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        names = rec.get("drug_names") or []
        if not names:
            names = [_extract_drug_name(rec)]
        names = [n for n in names if n]  # drop empty (placebo/noise filtered)
        if not names:
            continue  # no identifiable drug → skip from pipeline matrix
        for drug_name in dict.fromkeys(names):  # dedupe, preserve order
            # Derive drug_class from the drug name itself (not record-level title)
            drug_class = extract_drug_class("", drug_name)
            if drug_class == "其他":
                drug_class = rec.get("drug_class") or "其他"
            key = (drug_class, drug_name)
            groups.setdefault(key, []).append(rec)

    matrix = []
    for (drug_class, drug_name), trials in groups.items():
        # Determine highest phase
        phases = [t.get("phase_label", "未标注") for t in trials]
        phase_ranks = [PHASE_RANK.get(p, -1) for p in phases]
        best_idx = max(range(len(phase_ranks)), key=lambda i: phase_ranks[i])
        highest_phase = phases[best_idx] if phase_ranks[best_idx] >= 0 else "未标注"

        # Status summary
        status_counts = Counter(t.get("status_label", "未知") for t in trials)
        recruiting = status_counts.get("招募中", 0) + status_counts.get("尚未招募", 0)
        active = status_counts.get("进行中", 0)
        completed = status_counts.get("已完成", 0)
        terminated = status_counts.get("已终止", 0) + status_counts.get("已撤回", 0)

        # Source breakdown
        source_counts = Counter(t.get("registry", "") for t in trials)

        # Key trial (most recent or highest phase)
        key_trial = trials[best_idx]

        # Sponsors
        sponsors = sorted({t.get("sponsor", "") for t in trials if t.get("sponsor")})

        # Timeline: earliest start / latest readout / latest completion
        start_dates = sorted(d for d in (date_part(t.get("start_date")) for t in trials) if d)
        readout_dates = sorted(d for d in (date_part(t.get("readout_date")) for t in trials) if d)
        completion_dates = sorted(d for d in (date_part(t.get("completion_date")) for t in trials) if d)
        registered_dates = sorted(
            d for d in (date_part(t.get("registered_date") or t.get("start_date")) for t in trials) if d
        )

        matrix.append({
            "drug_class": drug_class,
            "name": drug_name,
            "highest_phase_label": highest_phase,
            "stage_number": PHASE_RANK.get(highest_phase, 0),
            "study_count": len(trials),
            "status_summary": f"招募 {recruiting} · 进行 {active} · 完成 {completed}" + (f" · 终止 {terminated}" if terminated else ""),
            "sponsors": sponsors[:3],
            "sources": dict(source_counts),
            "key_trial": {
                "registry": key_trial.get("registry", ""),
                "registry_id": key_trial.get("registry_id", ""),
                "title": key_trial.get("title", ""),
                "url": key_trial.get("url", ""),
            },
            "trials": [
                {
                    "registry": t.get("registry"),
                    "registry_id": t.get("registry_id"),
                    "title": t.get("title"),
                    "status_label": t.get("status_label"),
                    "status_class": t.get("status_class"),
                    "phase_label": t.get("phase_label"),
                    "start_date": date_part(t.get("start_date")),
                    "readout_date": date_part(t.get("readout_date")),
                    "completion_date": date_part(t.get("completion_date")),
                    "sponsor": t.get("sponsor"),
                    "url": t.get("url"),
                }
                for t in trials
            ],
            "timeline": {
                "start": start_dates[0] if start_dates else (registered_dates[0] if registered_dates else ""),
                "readout": readout_dates[-1] if readout_dates else "",
                "completion": completion_dates[-1] if completion_dates else "",
            },
            "first_registered": registered_dates[0] if registered_dates else "",
            "latest_registered": registered_dates[-1] if registered_dates else "",
            "linked_registries": [
                lr for t in trials for lr in (t.get("linked_registries") or [])
            ],
        })

    # Sort: drug class order → stage desc → study count desc
    class_rank = {c: i for i, c in enumerate(DRUG_CLASS_ORDER)}
    matrix.sort(key=lambda m: (
        class_rank.get(m["drug_class"], 99),
        -m["stage_number"],
        -m["study_count"],
        m["name"],
    ))
    return matrix


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    """装配前端要求的三来源数据结构，并返回 CT.gov 原始缓存供周更对比。"""
    ct_payload = load_json(CT_CACHE_PATH)
    chictr_payload = load_json(CHICTR_CACHE_PATH)
    china_payload = load_china_drug_trials_cache(CHINA_DRUG_TRIALS_CACHE_PATH)

    normalized_items = deduplicate_trials(
        _ct_items(ct_payload) + _chictr_items(chictr_payload) + _cdt_items(china_payload)
    )
    ct_details = ct_metadata(ct_payload)
    chictr_details = chictr_metadata(chictr_payload)
    records = [
        enrich_record(item, ct_details, chictr_details)
        for item in normalized_items
    ]
    records.sort(key=lambda record: (record["registry"], record["registry_id"]))

    records_by_source = {
        source: sorted(
            (record for record in records if record["registry"] == source),
            key=lambda record: record["registry_id"],
        )
        for source in SOURCE_ORDER
    }

    generated_at = date_part(ct_payload.get("generated_at")) or date_part(chictr_payload.get("last_verified"))
    ct_generated_at = date_part(ct_payload.get("generated_at"))
    chictr_generated_at = date_part(chictr_payload.get("last_verified") or chictr_payload.get("generated_at"))
    china_records = records_by_source["ChinaDrugTrials"]
    china_mode = str(china_payload.get("mode") or "unavailable")
    if not china_records:
        china_mode = "unavailable"

    sources = [
        {
            "source": "ClinicalTrials.gov",
            "meta": {
                "generated_at": ct_generated_at,
                "mode": str(ct_payload.get("mode") or "cache"),
            },
            "records": records_by_source["ClinicalTrials.gov"],
        },
        {
            "source": "ChiCTR",
            "meta": {
                "generated_at": chictr_generated_at,
                "mode": str(chictr_payload.get("mode") or "cache"),
                "warning": str(chictr_payload.get("warning") or ""),
            },
            "records": records_by_source["ChiCTR"],
        },
        {
            "source": "ChinaDrugTrials",
            "meta": {
                "generated_at": date_part(china_payload.get("generated_at") or china_payload.get("last_verified")),
                "mode": china_mode,
                "warning": str(
                    china_payload.get("warning")
                    or ("无已验证数据源" if not china_records else "")
                ),
            },
            "records": china_records,
        },
    ]

    pipeline_matrix = build_pipeline_matrix(records)

    payload = {
        "meta": {
            "generated_at": generated_at,
            "total_count": sum(len(source["records"]) for source in sources),
            "sources_order": SOURCE_ORDER,
        },
        "decision_signals": build_decision_signals(records, generated_at),
        "pipeline_matrix": pipeline_matrix,
        "sources": sources,
    }
    return payload, ct_payload


def ct_titles_from_payload(ct_payload: dict[str, Any]) -> dict[str, str]:
    """按 NCT 编号索引 CT.gov 研究官方标题（缺失时退回简短标题）。"""
    titles: dict[str, str] = {}
    for study in ct_payload.get("studies") or []:
        ident = (study.get("protocolSection") or {}).get("identificationModule") or {}
        nct_id = str(ident.get("nctId") or "").strip()
        if not nct_id:
            continue
        titles[nct_id] = str(ident.get("officialTitle") or ident.get("briefTitle") or "").strip()
    return titles


def _ct_snapshot_entry(study: dict[str, Any]) -> dict[str, Any]:
    """从单条 CT.gov 研究中提取周更对比所需的最小字段。"""
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    arms = protocol.get("armsInterventionsModule") or {}
    nct_id = str(ident.get("nctId") or "").strip()
    if not nct_id:
        return {}
    # 从 intervention 列表提取药物名称并归一化
    drug_names: list[str] = []
    for iv in (arms.get("interventions") or []):
        if str(iv.get("type") or "").upper() in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}:
            name = normalize_drug_name(str(iv.get("name") or ""))
            if name and name not in drug_names:
                drug_names.append(name)
    # 样本量信息（用于周更变化摘要）
    enrollment = design.get("enrollmentInfo") or {}
    enrollment_count = enrollment.get("count")
    enrollment_type = str(enrollment.get("type") or "").strip()
    # 关键日期和地点数（用于周更变化摘要）
    primary_completion = date_part((status.get("primaryCompletionDateStruct") or {}).get("date"))
    completion = date_part((status.get("completionDateStruct") or {}).get("date"))
    locations_count = len((protocol.get("contactsLocationsModule") or {}).get("locations") or [])
    return {
        "registry_id": nct_id,
        "status": str(status.get("overallStatus") or "").strip(),
        "first_post_date": date_part((status.get("studyFirstPostDateStruct") or {}).get("date")),
        "last_update_date": date_part((status.get("lastUpdatePostDateStruct") or {}).get("date")),
        "results_post_date": date_part((status.get("resultsFirstPostDateStruct") or {}).get("date")),
        "phase_label": phase_label(design.get("phases") or []),
        "drug_names": drug_names,
        "enrollment_count": enrollment_count,
        "enrollment_type": enrollment_type,
        "primary_completion_date": primary_completion,
        "completion_date": completion,
        "locations_count": locations_count,
    }


def build_ct_snapshot(ct_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """构建当前 CT.gov 对比快照，按 NCT 编号索引。"""
    snapshot: dict[str, dict[str, Any]] = {}
    for study in ct_payload.get("studies") or []:
        entry = _ct_snapshot_entry(study)
        if entry:
            snapshot[entry["registry_id"]] = entry
    return snapshot


def load_baseline_ct_snapshot(snapshot_path: Path | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    """读取上一期 CT.gov 快照。优先本地快照文件，其次 git HEAD 版本。

    返回 (快照字典, 快照日期)；两者都不可用时返回 ({}, "")，
    本次构建将作为首次基线，下一期起自动产出变化。
    """
    path = snapshot_path or WEEKLY_CHANGES_SNAPSHOT_PATH
    payload: dict[str, Any] | None = None
    if path.is_file():
        try:
            payload = load_json(path)
        except (OSError, ValueError):
            payload = None
    if payload is None:
        try:
            rel_path = path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return {}, ""
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{rel_path}"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return {}, ""
        if result.returncode != 0 or not result.stdout.strip():
            return {}, ""
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}, ""
    if not isinstance(payload, dict):
        return {}, ""
    entries = payload.get("entries") or {}
    snapshot_date = date_part(payload.get("snapshot_date"))
    return {str(key): value for key, value in entries.items()}, snapshot_date


def _describe_field_changes(
    previous: dict[str, Any] | None,
    entry: dict[str, Any],
) -> str:
    """对比两期快照的可观测字段，生成一句话变化摘要。

    覆盖：状态变化、样本量变化、阶段变化、药物名称变化；
    全部一致时返回空字符串（由调用方兜底为"其他字段更新"）。
    """
    prev = previous or {}
    parts: list[str] = []

    # 状态变化
    from_status = str(prev.get("status") or "").strip()
    to_status = str(entry.get("status") or "").strip()
    if from_status and to_status and from_status != to_status:
        parts.append(f"状态：{normalize_status(from_status)[0]} → {normalize_status(to_status)[0]}")

    # 样本量变化
    prev_count = prev.get("enrollment_count")
    cur_count = entry.get("enrollment_count")
    if prev_count is not None and cur_count is not None and prev_count != cur_count:
        suffix = "（预估）" if str(entry.get("enrollment_type") or "").upper() == "ESTIMATED" else ""
        parts.append(f"样本量：{prev_count} → {cur_count}{suffix}")

    # 阶段变化
    prev_phase = str(prev.get("phase_label") or "").strip()
    cur_phase = str(entry.get("phase_label") or "").strip()
    if prev_phase and cur_phase and prev_phase != cur_phase:
        parts.append(f"阶段：{prev_phase} → {cur_phase}")

    # 药物名称变化（新增/删除干预）
    prev_drugs = [str(d) for d in (prev.get("drug_names") or [])]
    cur_drugs = [str(d) for d in (entry.get("drug_names") or [])]
    added_drugs = [d for d in cur_drugs if d not in prev_drugs]
    removed_drugs = [d for d in prev_drugs if d not in cur_drugs]
    if added_drugs:
        parts.append("新增干预：" + "、".join(added_drugs[:2]))
    if removed_drugs:
        parts.append("移除干预：" + "、".join(removed_drugs[:2]))

    # 主要完成日期变化
    prev_pcd = str(prev.get("primary_completion_date") or "").strip()
    cur_pcd = str(entry.get("primary_completion_date") or "").strip()
    if prev_pcd and cur_pcd and prev_pcd != cur_pcd:
        parts.append(f"主要完成日期：{prev_pcd} → {cur_pcd}")

    # 研究地点数变化
    prev_locs = prev.get("locations_count")
    cur_locs = entry.get("locations_count")
    if prev_locs is not None and cur_locs is not None and prev_locs != cur_locs:
        parts.append(f"研究地点：{prev_locs} → {cur_locs} 个")

    return "；".join(parts)


def diff_ct_weekly_changes(
    current: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    reference_date: date | None,
    ct_titles: dict[str, str],
    previous_snapshot_at: str = "",
) -> dict[str, Any]:
    """对比两期 CT.gov 快照，提炼近 WEEKLY_CHANGES_WINDOW_DAYS 天的变化要点。"""
    window_days = WEEKLY_CHANGES_WINDOW_DAYS
    window_start = reference_date - timedelta(days=window_days) if reference_date else None

    def within_window(value: Any) -> bool:
        parsed = parse_iso_date(value)
        return bool(parsed and window_start and reference_date and window_start <= parsed <= reference_date)

    def url_of(registry_id: str) -> str:
        return f"https://clinicaltrials.gov/study/{registry_id}"

    def trial_meta_of(registry_id: str) -> tuple[str, str]:
        """从当前快照取条目的药物名称和阶段标签。"""
        entry = current.get(registry_id) or {}
        names = entry.get("drug_names") or []
        drug = names[0] if names else ""
        phase = entry.get("phase_label") or ""
        return drug, phase

    def format_meta_suffix(registry_id: str) -> str:
        drug, phase = trial_meta_of(registry_id)
        parts = [p for p in (drug, phase) if p]
        return " · ".join(parts) if parts else ""

    added = [
        {
            "registry_id": registry_id,
            "title": ct_titles.get(registry_id, ""),
            "first_post_date": entry.get("first_post_date", ""),
            "url": url_of(registry_id),
            **dict(zip(("drug_name", "phase_label"), trial_meta_of(registry_id))),
        }
        for registry_id, entry in current.items()
        if registry_id not in baseline and within_window(entry.get("first_post_date"))
    ]
    added.sort(key=lambda item: (item["first_post_date"], item["registry_id"]), reverse=True)

    status_changes = []
    for registry_id, entry in current.items():
        previous = baseline.get(registry_id)
        if not previous:
            continue
        from_status = str(previous.get("status") or "")
        to_status = str(entry.get("status") or "")
        if not to_status or from_status == to_status or not within_window(entry.get("last_update_date")):
            continue
        drug, phase = trial_meta_of(registry_id)
        from_label = normalize_status(from_status)[0]
        to_label = normalize_status(to_status)[0]
        status_changes.append({
            "registry_id": registry_id,
            "title": ct_titles.get(registry_id, ""),
            "from_status": from_status,
            "to_status": to_status,
            "from_label": from_label,
            "to_label": to_label,
            "updated_date": entry.get("last_update_date", ""),
            "url": url_of(registry_id),
            "change_summary": f"状态：{from_label} → {to_label}",
            "drug_name": drug,
            "phase_label": phase,
        })
    status_changes.sort(key=lambda item: (item["updated_date"], item["registry_id"]), reverse=True)

    results_posted = []
    for registry_id, entry in current.items():
        results_date = entry.get("results_post_date") or ""
        if not within_window(results_date):
            continue
        previous = baseline.get(registry_id) or {}
        if previous.get("results_post_date") == results_date:
            continue  # 上一期快照已记录过同一结果发布日期
        drug, phase = trial_meta_of(registry_id)
        results_posted.append({
            "registry_id": registry_id,
            "title": ct_titles.get(registry_id, ""),
            "results_post_date": results_date,
            "url": url_of(registry_id),
            "drug_name": drug,
            "phase_label": phase,
        })
    results_posted.sort(key=lambda item: (item["results_post_date"], item["registry_id"]), reverse=True)

    status_ids = {change["registry_id"] for change in status_changes}
    added_ids = {item["registry_id"] for item in added}
    results_ids = {item["registry_id"] for item in results_posted}
    updated = []
    for registry_id, entry in current.items():
        if registry_id in status_ids or registry_id in added_ids or registry_id in results_ids:
            continue
        if not within_window(entry.get("last_update_date")):
            continue
        previous = baseline.get(registry_id)
        summary = _describe_field_changes(previous, entry) or "其他字段更新"
        drug, phase = trial_meta_of(registry_id)
        updated.append({
            "registry_id": registry_id,
            "title": ct_titles.get(registry_id, ""),
            "updated_date": entry.get("last_update_date", ""),
            "url": url_of(registry_id),
            "change_summary": summary,
            "drug_name": drug,
            "phase_label": phase,
        })
    updated.sort(key=lambda item: (item["updated_date"], item["registry_id"]), reverse=True)

    removed = sorted(registry_id for registry_id in baseline if registry_id not in current)

    return {
        "schema_version": "1.0",
        "source": "ClinicalTrials.gov",
        "generated_at": reference_date.isoformat() if reference_date else "",
        "previous_snapshot_at": previous_snapshot_at,
        "window_days": window_days,
        "window_start": window_start.isoformat() if window_start else "",
        "added_count": len(added),
        "status_change_count": len(status_changes),
        "results_posted_count": len(results_posted),
        "updated_count": len(updated),
        "removed_count": len(removed),
        "added": added[:6],
        "status_changes": status_changes[:6],
        "results_posted": results_posted[:6],
        "updated": updated[:5],
        "removed": removed[:10],
    }


def build_weekly_changes(ct_payload: dict[str, Any], generated_at: str) -> dict[str, Any]:
    """生成 CT.gov 周更变化要点，并原子更新对比基线快照。"""
    current = build_ct_snapshot(ct_payload)
    reference_date = parse_iso_date(generated_at)
    baseline, previous_snapshot_at = load_baseline_ct_snapshot()
    changes = diff_ct_weekly_changes(
        current,
        baseline,
        reference_date,
        ct_titles_from_payload(ct_payload),
        previous_snapshot_at=previous_snapshot_at,
    )
    snapshot_date = date_part(ct_payload.get("generated_at")) or (generated_at or "")
    atomic_write_json(
        WEEKLY_CHANGES_SNAPSHOT_PATH,
        {
            "schema_version": "1.0",
            "source": "ClinicalTrials.gov",
            "snapshot_date": snapshot_date,
            "entry_count": len(current),
            "entries": current,
        },
    )
    return changes


def build_trial_insights(ct_payload: dict[str, Any], records: list[dict[str, Any]], reference_date: date | None) -> dict[str, Any]:
    """提炼首页试验全景洞察：人群分布、阶段集中度、近 6 月新开趋势。"""
    # 人群分布：从 CT.gov eligibilityModule.stdAges 提取
    populationCounts: Counter[str] = Counter()
    for study in ct_payload.get("studies") or []:
        protocol = study.get("protocolSection") or {}
        eligibility = protocol.get("eligibilityModule") or {}
        std_ages = eligibility.get("stdAges") or []
        if not std_ages:
            populationCounts["未标注"] += 1
            continue
        for age_key in std_ages:
            label = {"CHILD": "含儿童/青少年", "ADULT": "含成人", "OLDER_ADULT": "含老年"}.get(
                str(age_key).upper(), str(age_key)
            )
            populationCounts[label] += 1

    # 阶段集中度：按 records 中已归一化的 phase_label 统计（合并"未标注"与"N/A"）
    phaseCounts: Counter[str] = Counter()
    for record in records:
        phase = str(record.get("phase_label") or "未标注")
        if phase in {"N/A", "NA"}:
            phase = "未标注"
        phaseCounts[phase] += 1

    # 近 6 月新开趋势：按 registered_date 落在窗口内计数 + 药物分布 top3
    cutoff = six_month_cutoff(reference_date) if reference_date else None
    recent_drug_counts: Counter[str] = Counter()
    recent_phase_counts: Counter[str] = Counter()
    recent_count = 0
    for record in records:
        registered = parse_iso_date(record.get("registered_date"))
        if not (registered and cutoff and reference_date and cutoff <= registered <= reference_date):
            continue
        recent_count += 1
        drug = str(record.get("drug_name") or record.get("drug_class") or "")
        if drug and drug != "其他":
            recent_drug_counts[drug] += 1
        phase = str(record.get("phase_label") or "未标注")
        recent_phase_counts[phase] += 1

    population_items = [
        {"label": label, "count": count}
        for label, count in populationCounts.most_common(6)
    ]
    phase_items = [
        {"label": label, "count": count}
        for label, count in phaseCounts.most_common(8)
    ]
    recent_drug_items = [
        {"label": label, "count": count}
        for label, count in recent_drug_counts.most_common(3)
    ]
    recent_phase_items = [
        {"label": label, "count": count}
        for label, count in recent_phase_counts.most_common(3)
    ]

    return {
        "population_distribution": population_items,
        "phase_concentration": phase_items,
        "recent_registrations": {
            "count": recent_count,
            "top_drugs": recent_drug_items,
            "top_phases": recent_phase_items,
        },
    }


def buildSummaryPayload(
    payload: dict[str, Any],
    weeklyChanges: dict[str, Any] | None = None,
    trialInsights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成首页使用的轻量三源试验摘要，避免加载完整矩阵。"""
    records = [
        record
        for source in payload.get("sources", [])
        for record in source.get("records", [])
    ]
    recruitingKeys = {"RECRUITING", "ENROLLING_BY_INVITATION"}
    recruitingCount = sum(
        re.sub(r"[\s-]+", "_", str(record.get("status") or "").upper()) in recruitingKeys
        for record in records
    )
    knownClassCounts = Counter(
        record["drug_class"]
        for record in records
        if record.get("drug_class") not in {"", "其他"}
    )
    leadingMechanism = {}
    if knownClassCounts:
        leadingLabel, leadingCount = sorted(
            knownClassCounts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        leadingMechanism = {"label": leadingLabel, "count": leadingCount}

    generatedAt = str((payload.get("meta") or {}).get("generated_at") or "")
    referenceDate = parse_iso_date(generatedAt)
    cutoff = six_month_cutoff(referenceDate) if referenceDate else None
    recentRegistrationCount = sum(
        bool(registeredDate and cutoff and cutoff <= registeredDate <= referenceDate)
        for registeredDate in (parse_iso_date(record.get("registered_date")) for record in records)
    )
    sourceCounts = [
        {
            "source": source.get("source") or "",
            "count": len(source.get("records") or []),
            "mode": (source.get("meta") or {}).get("mode") or "",
        }
        for source in payload.get("sources", [])
    ]
    return {
        "meta": payload.get("meta") or {},
        "pipeline_matrix_count": len(payload.get("pipeline_matrix") or []),
        "recruiting_count": recruitingCount,
        "recent_registration_count": recentRegistrationCount,
        "leading_mechanism": leadingMechanism,
        "source_counts": sourceCounts,
        "decision_signals": payload.get("decision_signals") or [],
        "weekly_changes": weeklyChanges or {},
        "trial_insights": trialInsights or {},
    }


def main() -> None:
    """生成可由浏览器直接加载的 JavaScript 数据文件。"""
    payload, ctPayload = build_payload()
    output = "window.MG_CLINICAL_TRIALS_DATA = " + json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ) + ";\n"
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    generatedAt = str((payload.get("meta") or {}).get("generated_at") or "")
    weeklyChanges = build_weekly_changes(ctPayload, generatedAt)
    referenceDate = parse_iso_date(generatedAt)
    records = [record for source in payload.get("sources", []) for record in source.get("records", [])]
    trialInsights = build_trial_insights(ctPayload, records, referenceDate)
    summaryPayload = buildSummaryPayload(payload, weeklyChanges, trialInsights)
    summaryOutput = "window.MG_CLINICAL_TRIALS_SUMMARY = " + json.dumps(
        summaryPayload,
        ensure_ascii=False,
        indent=2,
    ) + ";\n"
    summaryOutputPath.write_text(summaryOutput, encoding="utf-8")
    print(f"Wrote {payload['meta']['total_count']} records to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote dashboard summary to {summaryOutputPath.relative_to(PROJECT_ROOT)}")
    print(
        "Weekly changes (ClinicalTrials.gov): "
        f"+{weeklyChanges['added_count']} new · "
        f"{weeklyChanges['status_change_count']} status · "
        f"{weeklyChanges['results_posted_count']} results · "
        f"{weeklyChanges['updated_count']} updated · "
        f"-{weeklyChanges['removed_count']} removed"
    )


if __name__ == "__main__":
    main()
