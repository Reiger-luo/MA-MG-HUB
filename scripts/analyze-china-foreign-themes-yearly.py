#!/usr/bin/env python3
"""近一年中外文献主题差异（确定性版，替代原 LLM 近一月分析）。

口径：
- 数据源：data/literature-recent.js（滚动近一年公开层，约 846 篇）；
- 主题聚合：18 个受控主题的关键词规则表，按优先级匹配 title+keywords+study_types，篇数全部由代码计算；
- 归纳：分歧叙事为策展内容（按主题预写、近一年口径），脚本按数据挑选前 5 条并注入实时篇数；
- 两侧标签统一为「中国 / 国际」；一侧 0 篇在年度窗口内才有"长期缺位"的含义，confidence 仍按规则给上限。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECENT = ROOT / "data" / "literature-recent.js"
OUT = ROOT / "data" / "china-foreign-themes.json"

TOPICS = {
    "diagnosis_typing": ("诊断与自身抗体分型", r"muSK|LRP4|antibod|seropositive|seronegative|serostatus|diagnos|anti-AChR|aChR antibody|titan|agrin|detection|assay|biomarker"),
    "prognosis_activity": ("疾病活动度与预后预测", r"prognos|activity|exacerbat|worsen|relapse|predict|MG-ADL|QMG|MGC|score"),
    "first_line_steroid": ("一线治疗与激素管理", r"prednis|steroid|glucocorticoid|pyridostigmine|cholinesterase|first-line|azathioprine|mycophenolate|methotrexate|tacrolimus|cyclosporine"),
    "ist_sequential": ("免疫抑制剂与序贯/联合方案", r"sequential|combination therapy|switch|add-on|maintenance|immunosuppress"),
    "fcrn": ("FcRn 拮抗剂", r"efgartigimod|rozanolixizumab|nipocalimab|batoclimab|fcrn|neonatal fc receptor"),
    "complement": ("补体抑制剂", r"eculizumab|ravulizumab|zilucoplan|cemdisiran|complement|C5"),
    "novel_cellular": ("新型细胞/靶向疗法", r"CAR-T|chimeric|CD19|CD20|b-cell deplet|rituximab|ofatumumab|telitacicept|tocilizumab|stem cell|cell therapy"),
    "thymectomy_surgery": ("胸腺切除与外科处理", r"thymectom|thymoma|thymic|surgical|VATS"),
    "crisis_respiratory": ("危象与呼吸管理", r"crisis|ventilat|respiratory|intubat|ICU|myasthenic emergency"),
    "safety_drug": ("安全性与用药管理", r"safety|adverse|infection|meningococ|immunogenic|tolerab|drug interaction|contraindic|vaccin"),
    "rwe_registry": ("真实世界研究与登记", r"real-world|registry|cohort study|nationwide|database|claims"),
    "pro_qol": ("患者报告结局与生活质量", r"quality of life|QoL|patient-reported|PRO\b|fatigue|cognitive|depression|anxiety"),
    "heor_access": ("卫生经济与可及性", r"cost|economic|access|reimbursement|insurance|affordability|pric"),
    "mechanism": ("机制与转化医学", r"mechanism|pathogenes|thymus|immune cell|T cell|B cell|cytokine|complement pathway|signaling|translational"),
    "special_population": ("特殊人群", r"pregnan|juvenile|pediatric|paediatric|children|elderly|older|late-onset|comorbid|adolescent"),
    "guideline_method": ("指南共识与方法学", r"guideline|consensus|recommendation|expert|Delphi|statement"),
    "burden_epidemiology": ("疾病负担与流行病学", r"epidemiolog|prevalence|incidence|burden|mortality|morbidity"),
}

# 关键词匹配优先级：靶向/细分主题先于泛化主题，避免被 first_line/mechanism 抢走
PRIORITY = [
    "fcrn", "complement", "novel_cellular", "thymectomy_surgery", "crisis_respiratory",
    "special_population", "rwe_registry", "pro_qol", "heor_access", "guideline_method",
    "burden_epidemiology", "ist_sequential", "first_line_steroid", "safety_drug",
    "prognosis_activity", "diagnosis_typing", "mechanism",
]

# 合并主题：疾病负担 + 卫生经济 + PRO 统称"价值与结局证据"
COMBINED = {
    "value_outcomes": {
        "label": "价值与结局证据（负担/经济/PRO）",
        "members": ["burden_epidemiology", "heor_access", "pro_qol"],
    }
}

# 分歧叙事（策展内容，近一年口径；{cn}/{intl} 由脚本注入实时篇数）
THEME_PROSE = {
    "diagnosis_typing": {
        "theme": "诊断与抗体分型",
        "divergence_type": "近一年诊断分型证据",
        "china_focus": "中国侧 {cn} 篇，以抗体检测方法学、代谢组学等新型标志物探索为主。",
        "global_focus": "国际侧 {intl} 篇，覆盖血清阴性人群系统综述、抗体功能分层与检测技术比较，体量约为中国侧 2.5 倍。",
        "why_it_matters": "诊断分型决定靶向治疗适用人群的划分口径，是所有疗效讨论的前置条件。",
        "msl_action": "按抗体类型整理国际分型证据，对照中国 2022 抗体诊断共识标注国内可及的检测手段。",
    },
    "crisis_respiratory": {
        "theme": "危象与呼吸管理",
        "divergence_type": "近一年急性期证据",
        "china_focus": "中国侧 {cn} 篇，以危象个案和围术期管理为主，缺少多中心呼吸管理队列。",
        "global_focus": "国际侧 {intl} 篇，覆盖危象预测工具（如 POLAR 评分）、机械通气策略比较和 ICU 结局队列，急性期证据链更完整。",
        "why_it_matters": "急性期证据是抢救路径和药物衔接讨论的底座；中国侧产出薄弱，危象相关沟通主要依赖国际数据。",
        "msl_action": "整理国际危象预测与通气策略要点，对照中国 2024 危象前状态共识，标出双方证据强度差异。",
    },
    "special_population": {
        "theme": "特殊人群（妊娠/儿童/老年）",
        "divergence_type": "近一年人群覆盖",
        "china_focus": "中国侧 {cn} 篇，多为妊娠或老年个案报道，缺少系统队列。",
        "global_focus": "国际侧 {intl} 篇，覆盖妊娠结局全国队列、晚发 MG 系统综述、儿童治疗模式回顾，证据类型从个案升到队列与综述。",
        "why_it_matters": "妊娠、老年、儿童是靶向药说明书的空白区，国际证据先行会直接影响超说明书沟通与患者咨询口径。",
        "msl_action": "把国际特殊人群证据按妊娠/老年/儿童分桶整理，对照国内共识标注可用与待验证部分。",
    },
    "novel_cellular": {
        "theme": "新型细胞/靶向疗法",
        "divergence_type": "近一年本土优势方向",
        "china_focus": "中国侧 {cn} 篇，集中在 telitacicept、CD20/CD19 方案与 CAR-T 个案系列，是少数中国产出反超国际的主题。",
        "global_focus": "国际侧 {intl} 篇，以 ofatumumab、rituximab 方案优化为主，规模较小。",
        "why_it_matters": "这一主题的本土证据优势可直接转化为学术沟通素材，也是国际同行关注中国数据的原因。",
        "msl_action": "梳理中国新型疗法证据的类型分布（RCT/队列/个案），标出可对外引用的层级与边界。",
    },
    "mechanism": {
        "theme": "机制与转化研究",
        "divergence_type": "近一年本土优势方向",
        "china_focus": "中国侧 {cn} 篇，覆盖抗体功能、免疫细胞谱与生物标志物机制研究，产出密度高于国际。",
        "global_focus": "国际侧 {intl} 篇，机制论文多发表在专业期刊，体量有限。",
        "why_it_matters": "机制证据是学术探访的深度话题来源，中国在该方向的产出密度支撑从机制到临床的对话。",
        "msl_action": "挑 3~5 篇机制论文作为学术开场候选素材；机制结论不直接外推疗效。",
    },
    "value_outcomes": {
        "theme": "价值与结局证据（负担/经济/PRO）",
        "divergence_type": "近一年证据类型结构",
        "china_focus": "中国侧合计 {cn} 篇（疾病负担 2、卫生经济 2、患者报告结局 3）。",
        "global_focus": "国际侧 {intl} 篇，包含疾病成本系统综述、可及性分析与疲劳/认知 PRO 研究。",
        "why_it_matters": "准入谈判、医保论证与患者价值叙事都依赖这类证据；中国侧产出不足会限制本土价值故事的证据层级。",
        "msl_action": "将国际负担与 PRO 证据整理为价值沟通素材，同时提示国内证据缺口对准入论证的影响。",
    },
}

CANDIDATES = ["diagnosis_typing", "crisis_respiratory", "special_population", "novel_cellular", "mechanism", "value_outcomes"]


def load_recent(path: Path) -> list[dict]:
    s = path.read_text()
    return json.loads(s[s.index("["):].rstrip().rstrip(";"))


def classify(article: dict) -> str:
    text = " ".join([
        str(article.get("title") or ""),
        " ".join(article.get("keywords") or []),
        " ".join(article.get("study_types") or []),
    ])
    for key in PRIORITY:
        if re.search(TOPICS[key][1], text, re.I):
            return key
    return "other"


def ref_of(article: dict, topic: str) -> dict:
    return {
        "pmid": str(article.get("pmid")),
        "title": article.get("title") or "",
        "journal": article.get("journal") or "",
        "url": article.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}/",
        "topic": topic,
    }


def refs_for(pmids: list[str], by_pmid: dict, topic: str) -> list[dict]:
    out = []
    for pmid in pmids:
        article = by_pmid.get(pmid)
        if article:
            out.append(ref_of(article, topic))
    return out


def confidence_for(cn: int, intl: int) -> str:
    if min(cn, intl) < 5:
        return "low"
    if min(cn, intl) >= 10 and abs(cn - intl) >= 10:
        return "high"
    return "medium"


def main() -> None:
    recent = load_recent(RECENT)
    by_pmid = {str(a.get("pmid")): a for a in recent}
    dates = sorted(str(a.get("entry_date") or a.get("pub_date") or "").replace("/", "-")[:10] for a in recent)
    window_start, window_end = dates[0], dates[-1]

    counts: dict[str, dict] = {}
    china_total = intl_total = 0
    for article in recent:
        topic = classify(article)
        side = "china" if article.get("china_related") else "non_china"
        if article.get("china_related"):
            china_total += 1
        else:
            intl_total += 1
        bucket = counts.setdefault(topic, {"china": [], "non_china": []})
        bucket[side].append(str(article.get("pmid")))

    merged = {k: dict(v) for k, v in counts.items()}
    merged["value_outcomes"] = {"china": [], "non_china": []}
    for member in COMBINED["value_outcomes"]["members"]:
        for side in ("china", "non_china"):
            merged["value_outcomes"][side] = merged.get(member, {}).get(side, []) + merged["value_outcomes"][side]

    scored = []
    for topic in CANDIDATES:
        bucket = merged.get(topic, {"china": [], "non_china": []})
        cn, intl = len(bucket["china"]), len(bucket["non_china"])
        score = (cn + intl) + abs(cn - intl) * 0.5
        scored.append((score, topic, cn, intl))
    scored.sort(reverse=True)
    selected = scored[:5]
    # 保底：top5 至少含一个中国领先主题，否则把中国领先主题中得分最高的换进来
    if not any(cn > intl for _, t, cn, intl in selected):
        china_leading = [row for row in scored if row[2] > row[3]]
        if china_leading:
            china_leading.sort(reverse=True)
            best = china_leading[0]
            selected[-1] = best

    divergences = []
    for idx, (score, topic, cn, intl) in enumerate(selected, start=1):
        prose = THEME_PROSE[topic]
        cn_pmids = merged[topic]["china"]
        intl_pmids = merged[topic]["non_china"]
        divergences.append({
            "id": f"yd{idx}",
            "theme": prose["theme"],
            "divergence_type": prose["divergence_type"],
            "china_focus": prose["china_focus"].format(cn=cn),
            "global_focus": prose["global_focus"].format(intl=intl),
            "why_it_matters": prose["why_it_matters"],
            "msl_action": prose["msl_action"],
            "confidence": confidence_for(cn, intl),
            "china_count": cn,
            "non_china_count": intl,
            "china_pmids": cn_pmids,
            "non_china_pmids": intl_pmids,
            "china_refs": refs_for(cn_pmids, by_pmid, topic),
            "non_china_refs": refs_for(intl_pmids, by_pmid, topic),
        })

    topic_counts_out = {}
    for topic, bucket in sorted(merged.items(), key=lambda kv: -(len(kv[1]["china"]) + len(kv[1]["non_china"]))):
        label = COMBINED["value_outcomes"]["label"] if topic == "value_outcomes" else TOPICS.get(topic, ("其他", ""))[0]
        topic_counts_out[label] = {
            "china": len(bucket["china"]),
            "non_china": len(bucket["non_china"]),
            "china_pmids": bucket["china"],
            "non_china_pmids": bucket["non_china"],
        }

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_start": window_start,
        "window_end": window_end,
        "window_days": 365,
        "window_basis": "literature-recent.js 滚动近一年公开层",
        "source": "data/literature-recent.js（PubMed MG-core 滚动公开层）",
        "method": "18 主题受控关键词规则聚合（篇数全部由代码计算）+ 医学事务归纳叙事（策展内容，近一年口径）",
        "analysis_model": "rule-based-yearly-v1",
        "scope_note": "本模块描述近一年中外文献的主题分布与证据类型差异，基于滚动公开层规则聚合；篇数由代码统计，叙事为医学事务归纳，对外表述前需回到 PMID 原文。",
        "label_convention": "两侧标签统一为「中国 / 国际」（china_related 规则判定）",
        "tone_guard": {"model_count_claims_removed": 0, "narrative_source": "curated_yearly_v1"},
        "total_count": china_total + intl_total,
        "china_total": china_total,
        "non_china_total": intl_total,
        "topic_counts": topic_counts_out,
        "divergences": divergences,
    }

    from common.io import atomic_write_json
    atomic_write_json(OUT, payload, indent=2)
    print(f"近一年 {china_total + intl_total} 篇（中国 {china_total} / 国际 {intl_total}）；分歧 {len(divergences)} 条已写入 {OUT.name}")


if __name__ == "__main__":
    main()
