#!/usr/bin/env python3
"""
buildLandscapeInsights.py — 生成动态诊治格局洞察。

本脚本不在前端调用 LLM。它读取已经生成的社区周更、社区卡片、知识图谱和
既有诊治格局数据，输出可公开、可回退、可追溯的静态洞察产物。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from common.io import atomic_write_js_global, load_js_global


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"


COMMUNITY_PROFILES: dict[str, dict[str, Any]] = {
    "efficacyBurdenOutcomes": {
        "change_type": "疗效与疾病负担",
        "title": "疗效与疾病负担证据正在转向更可操作的结局解释",
        "treatment_position": "疗效评估、PRO、疾病负担和患者沟通",
        "competitive_narrative": "不同机制治疗的价值不只来自改善幅度，也来自终点、负担和可持续性。",
        "msl_action": "准备新增高等级疗效/PRO/负担 PMID，区分临床终点、患者报告结局和经济负担证据。",
        "new_frame": "本轮新增证据强化了疗效、生活质量或疾病负担的可量化讨论。",
    },
    "competitiveLandscapeIndirectComparison": {
        "change_type": "竞争格局",
        "title": "靶向治疗比较证据正在影响治疗定位讨论",
        "treatment_position": "AChR+ gMG、靶向治疗选择、机制区隔和治疗顺序",
        "competitive_narrative": "NMA、间接比较或真实世界对照会直接改变 FcRn、补体和其他机制的定位叙事。",
        "msl_action": "准备比较研究的纳入标准、证据等级、终点定义和 indirect comparison 局限。",
        "new_frame": "本轮新增比较性证据让治疗格局从单药证据转向跨机制定位。",
    },
    "safetyMedicationManagement": {
        "change_type": "安全性与管理",
        "title": "安全性讨论更适合按风险管理框架组织",
        "treatment_position": "长期管理、特殊人群、感染/IgG/免疫抑制风险和监测策略",
        "competitive_narrative": "安全性不应只列 AE，而要区分 RCT、RWE、药物警戒和病例信号的证据边界。",
        "msl_action": "准备风险来源、监测建议和证据等级，避免把药物警戒信号包装成发生率结论。",
        "new_frame": "本轮安全性信号提示需要按证据来源和风险类型重组话术。",
    },
    "fcrnTargetedTherapy": {
        "change_type": "FcRn 治疗",
        "title": "FcRn 证据更新继续围绕应答、用药路径和差异化",
        "treatment_position": "AChR+ gMG、应答预测、周期治疗、给药便利性和真实世界路径",
        "competitive_narrative": "FcRn 内部差异化需要同时看机制、给药、应答异质性和真实世界持续使用。",
        "msl_action": "准备 FcRn 新增 PMID，尤其是 response marker、RWE、给药路径和安全性边界。",
        "new_frame": "本轮 FcRn 证据继续把讨论从能否有效推进到谁更可能获益、如何管理疗程。",
    },
    "complementAndNovelTargets": {
        "change_type": "补体与新靶点",
        "title": "补体和新靶点证据提示路径选择需要分层",
        "treatment_position": "AChR+ gMG、补体抑制、B 细胞/新机制和难治人群",
        "competitive_narrative": "补体、新靶点和 FcRn 的竞争不只是疗效比较，也包括人群、速度、安全性和可及性。",
        "msl_action": "准备补体/新靶点新增证据，标出机制、人群、证据等级和是否可直接用于定位判断。",
        "new_frame": "本轮新增证据让补体和新靶点继续作为治疗路径分层的重要输入。",
    },
    "rweClinicalPathway": {
        "change_type": "真实世界与路径",
        "title": "真实世界证据正在把格局判断拉回临床路径",
        "treatment_position": "本土实践、换药/序贯、持续治疗、医保准入和中心路径",
        "competitive_narrative": "RWE 让治疗格局不只比较药物，而要解释真实患者如何进入、维持或切换治疗。",
        "msl_action": "整理新增 RWE PMID，优先标注样本量、中心来源、对照方式和终点采集方式。",
        "new_frame": "本轮新增 RWE 让格局判断更接近真实路径和患者管理问题。",
    },
    "diagnosisMonitoringPrediction": {
        "change_type": "诊断监测与预测",
        "title": "诊断、监测和预测信号增强患者分层逻辑",
        "treatment_position": "患者识别、疗效预测、抗体/生物标志物和随访监测",
        "competitive_narrative": "预测和监测证据会影响治疗启动、评估周期和专家对精准用药的期待。",
        "msl_action": "准备诊断/预测相关 PMID，明确哪些指标只是关联线索，哪些可能影响治疗决策。",
        "new_frame": "本轮新增证据增强了从诊断到治疗评估的分层解释。",
    },
    "clinicalSubtypesStratification": {
        "change_type": "亚型与人群",
        "title": "亚型与人群分层仍是治疗解释的底座",
        "treatment_position": "AChR/MuSK/LRP4、眼肌型/全身型、胸腺瘤相关 MG 和特殊人群",
        "competitive_narrative": "任何治疗定位都需要先回答适用人群，而不是把所有 MG 文献合并成一个平均叙事。",
        "msl_action": "准备新增亚型/人群 PMID，用于专家访谈时界定患者分层和证据外推边界。",
        "new_frame": "本轮新增文献继续提醒诊治格局必须先按人群拆开。",
    },
    "mechanismTranslationalMedicine": {
        "change_type": "机制与转化",
        "title": "机制与转化证据为治疗差异提供解释线索",
        "treatment_position": "免疫机制、抗体功能、细胞通路和治疗反应解释",
        "competitive_narrative": "机制证据不直接等同于临床优劣，但能解释为何不同机制可能服务不同患者问题。",
        "msl_action": "准备机制 PMID，并把 abstract 线索与临床结论边界分开呈现。",
        "new_frame": "本轮机制证据为疗效异质性和治疗差异提供新的解释入口。",
    },
    "guidelineHeorAccess": {
        "change_type": "指南/HEOR/准入",
        "title": "价值、准入和指南证据开始影响治疗格局判断",
        "treatment_position": "支付、可及性、患者偏好、指南推荐和路径落地",
        "competitive_narrative": "治疗竞争不只发生在疗效终点，也发生在价值、便利性和可及性证据中。",
        "msl_action": "准备 HEOR/指南/偏好证据，避免把价值证据误写成疗效证据。",
        "new_frame": "本轮新增证据提示价值和准入因素正在进入治疗格局讨论。",
    },
}


LEVEL_SCORE = {"I": 6, "II": 5, "III": 4, "IV": 3, "V": 2, "VI": 1}
SIGNAL_SCORE = {"high": 12, "medium": 6, "low": 2, "active": 10, "watch": 6, "quiet": 1}


def load_js(filename: str, global_name: str) -> Any:
    path = DATA_DIR / filename
    return load_js_global(path, global_name)


def maybe_load_js(filename: str, global_name: str) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return load_js(filename, global_name)


def compact_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "pmid": str(ref.get("pmid") or ""),
        "title": ref.get("title") or "",
        "journal": ref.get("journal") or "",
        "entry_date": ref.get("entry_date") or "",
        "pub_date": ref.get("pub_date") or "",
        "url": ref.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{ref.get('pmid')}/" if ref.get("pmid") else ""),
        "evidence_level": ref.get("evidence_level") or "",
        "study_types": ref.get("study_types") or [],
        "china_related": bool(ref.get("china_related")),
        "journal_if": ref.get("journal_if"),
    }


def ref_score(ref: dict[str, Any]) -> float:
    level = LEVEL_SCORE.get(str(ref.get("evidence_level") or ""), 0)
    journal_if = ref.get("journal_if")
    if not isinstance(journal_if, (int, float)):
        journal_if = 0
    china_bonus = 1.5 if ref.get("china_related") else 0
    return level * 10 + min(float(journal_if), 15) + china_bonus


def unique_refs(refs: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    by_pmid: dict[str, dict[str, Any]] = {}
    for ref in refs:
        compact = compact_ref(ref)
        pmid = compact.get("pmid")
        if not pmid:
            continue
        if pmid not in by_pmid or ref_score(compact) > ref_score(by_pmid[pmid]):
            by_pmid[pmid] = compact
    return sorted(by_pmid.values(), key=ref_score, reverse=True)[:limit]


def community_score(item: dict[str, Any], card: dict[str, Any]) -> float:
    return (
        int(item.get("recent_count") or 0) * 4
        + int(item.get("high_evidence_count") or 0) * 8
        + int(item.get("china_count") or 0) * 2
        + SIGNAL_SCORE.get(str(item.get("signal_level") or ""), 0)
        + int(card.get("recent_14d_count") or 0) * 1.5
    )


def confidence_for(item: dict[str, Any], refs: list[dict[str, Any]]) -> str:
    high_refs = sum(1 for ref in refs if str(ref.get("evidence_level") or "") in {"I", "II", "III"})
    if high_refs >= 2 or (item.get("signal_level") == "high" and high_refs >= 1):
        return "high"
    if refs and int(item.get("recent_count") or 0) >= 2:
        return "medium"
    return "low"


def node_profile(graph: dict[str, Any], community_id: str) -> list[dict[str, Any]]:
    nodes = [
        node for node in graph.get("nodes") or []
        if node.get("dominant_community_id") == community_id
    ]
    nodes.sort(key=lambda node: (
        -int(node.get("article_count") or 0),
        node.get("title") or node.get("id") or "",
    ))
    return [
        {
            "id": node.get("id") or "",
            "title": node.get("title") or node.get("id") or "",
            "type": node.get("type") or "",
            "article_count": node.get("article_count") or 0,
            "confidence": node.get("community_confidence") or node.get("confidence") or "",
        }
        for node in nodes[:4]
    ]


def edge_profile(graph: dict[str, Any], community_id: str) -> list[dict[str, Any]]:
    edges = [
        edge for edge in graph.get("edges") or []
        if edge.get("dominant_community_id") == community_id
    ]
    edges.sort(key=lambda edge: (
        -float(edge.get("evidence_score") or 0),
        -int(edge.get("article_count") or 0),
    ))
    return [
        {
            "id": edge.get("id") or "",
            "from": edge.get("from") or "",
            "to": edge.get("to") or "",
            "relation": edge.get("relation") or "",
            "article_count": edge.get("article_count") or 0,
            "best_evidence_level": edge.get("best_evidence_level") or "",
        }
        for edge in edges[:3]
    ]


def wiki_topics_for(coverage: dict[str, Any], community_id: str) -> list[dict[str, Any]]:
    topics = []
    for topic in coverage.get("topic_coverage") or []:
        if topic.get("primary_community_id") == community_id:
            topics.append(topic)
            continue
        for community in topic.get("communities") or []:
            if community.get("community_id") == community_id:
                topics.append(topic)
                break
    topics.sort(key=lambda item: (item.get("confidence") != "high", item.get("title") or ""))
    return [
        {
            "topic_id": topic.get("topic_id") or "",
            "title": topic.get("title") or "",
            "confidence": topic.get("confidence") or "",
            "updated": topic.get("updated") or "",
        }
        for topic in topics[:3]
    ]


def build_insight(
    item: dict[str, Any],
    card: dict[str, Any],
    graph: dict[str, Any],
    coverage: dict[str, Any],
    window_label: str,
) -> dict[str, Any]:
    community_id = item.get("community_id") or item.get("id") or ""
    profile = COMMUNITY_PROFILES.get(community_id, {})
    title = profile.get("title") or f"{item.get('title') or community_id} 出现新的月度信号"
    recent_refs = unique_refs((item.get("top_refs") or []) + (card.get("recent_refs") or []), limit=6)
    if not recent_refs:
        fill_refs = unique_refs((card.get("representative_refs") or []), limit=3)
        refs = unique_refs(recent_refs + fill_refs, limit=6)
    else:
        refs = recent_refs
    nodes = node_profile(graph, community_id)
    if not nodes:
        nodes = [
            {
                "id": node_id,
                "title": node_id,
                "type": "graphNode",
                "article_count": 0,
                "confidence": "",
            }
            for node_id in (card.get("representative_nodes") or [])[:4]
        ]
    edges = edge_profile(graph, community_id)
    recent_count = int(item.get("recent_count") or 0)
    high_count = int(item.get("high_evidence_count") or 0)
    china_count = int(item.get("china_count") or 0)
    why = (
        f"{window_label} 该社区新增 {recent_count} 篇文献，其中高等级证据 {high_count} 篇、"
        f"中国相关 {china_count} 篇；社区信号等级为 {item.get('signal_level') or '未标注'}。"
    )
    what_new = profile.get("new_frame") or f"本轮新增证据让 {item.get('title') or community_id} 成为需要重新扫描的医学事务问题。"
    return {
        "id": f"{community_id}-{datetime.now().strftime('%Y%m')}",
        "title": title,
        "change_type": profile.get("change_type") or item.get("title") or "社区变化",
        "type": profile.get("change_type") or item.get("title") or "社区变化",
        "selection_reason": why,
        "what_is_new": what_new,
        "why_it_matters": f"{what_new} {why}",
        "community_ids": [community_id],
        "community_titles": [item.get("title") or card.get("title") or community_id],
        "knowledge_nodes": nodes,
        "knowledge_edges": edges,
        "wiki_topics": wiki_topics_for(coverage, community_id),
        "treatment_position": profile.get("treatment_position") or "医学事务问题识别与证据沟通",
        "competitive_narrative": profile.get("competitive_narrative") or "需结合证据等级、社区边界和全文核对后进入正式叙事。",
        "msl_action": profile.get("msl_action") or "准备新增 PMID、图谱节点和社区边界，作为专家拜访前的问题清单。",
        "msl_action_items": [
            {"label": "证据包", "detail": "优先阅读高等级 PMID，并记录终点、人群和局限。"},
            {"label": "专家追问", "detail": profile.get("treatment_position") or "确认该社区变化是否影响本中心实践。"},
            {"label": "合规边界", "detail": "所有疗效、安全性和比较性表述必须回到 PMID 原文。"},
        ],
        "references": refs,
        "top_pmids": [ref.get("pmid") for ref in refs[:3] if ref.get("pmid")],
        "evidence_summary": {
            "recent_count": recent_count,
            "high_evidence_count": high_count,
            "china_count": china_count,
            "reference_count": len(refs),
            "signal_level": item.get("signal_level") or "",
            "community_article_count": card.get("article_count") or 0,
        },
        "confidence": confidence_for(item, refs),
        "limitations": "基于 PubMed abstract、社区归类和图谱元数据生成；不替代 PMID 全文阅读、说明书或指南原文。",
    }


def fallback_insights(landscape: dict[str, Any]) -> list[dict[str, Any]]:
    insights = []
    for change in landscape.get("monthly_changes") or []:
        insight = dict(change)
        insight["change_type"] = change.get("type") or "格局变化"
        insight["selection_reason"] = "社区动态产物缺失，回退到既有固定格局变化。"
        insight["what_is_new"] = change.get("why_it_matters") or ""
        insight["community_ids"] = []
        insight["community_titles"] = []
        insight["knowledge_nodes"] = []
        insight["knowledge_edges"] = []
        insight["wiki_topics"] = []
        insight["confidence"] = "low"
        insight["limitations"] = "fallback 结果，仅供页面兜底。"
        insights.append(insight)
    return insights


def build_payload() -> dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    landscape = maybe_load_js("landscape-data.js", "MG_LANDSCAPE_DATA") or {}
    weekly = maybe_load_js("communityWeekly.js", "MG_COMMUNITY_WEEKLY") or {}
    cards_payload = maybe_load_js("communityCards.js", "MG_COMMUNITY_CARDS") or {}
    graph = maybe_load_js("knowledge-graph.js", "MG_KNOWLEDGE_GRAPH") or {}
    coverage = maybe_load_js("wikiTopicCoverage.js", "MG_WIKI_TOPIC_COVERAGE") or {}

    cards = {card.get("id"): card for card in cards_payload.get("cards") or []}
    communities = weekly.get("hot_communities") or weekly.get("communities") or []
    window_start = weekly.get("window_start") or ""
    window_end = weekly.get("window_end") or ""
    window_label = f"{window_start} 至 {window_end}" if window_start and window_end else "本轮周更窗口"

    candidates = []
    for item in communities:
        community_id = item.get("community_id") or item.get("id")
        if not community_id or community_id == "unassigned":
            continue
        card = cards.get(community_id) or {}
        refs = (item.get("top_refs") or []) + (card.get("recent_refs") or [])
        if not refs:
            continue
        candidates.append((community_score(item, card), item, card))

    candidates.sort(key=lambda row: (-row[0], row[1].get("title") or ""))
    selected = candidates[:6]
    insights = [
        build_insight(item, card, graph, coverage, window_label)
        for _, item, card in selected
    ]
    if not insights:
        insights = fallback_insights(landscape)

    reference_pmids = sorted({
        ref.get("pmid")
        for insight in insights
        for ref in insight.get("references") or []
        if ref.get("pmid")
    })

    payload = {
        "generated_at": generated_at,
        "version": "2026.07-phase4-mvp",
        "method": "rulesFirstCommunityGraphDynamicInsights",
        "llm_status": "not_required_for_mvp",
        "source_note": "由社区周更、社区卡片、知识图谱、wiki 覆盖和既有诊治格局数据离线生成；前端只展示静态产物。",
        "window_start": window_start,
        "window_end": window_end,
        "summary": {
            "insight_count": len(insights),
            "high_confidence_count": sum(1 for item in insights if item.get("confidence") == "high"),
            "community_count": len({cid for item in insights for cid in item.get("community_ids") or []}),
            "reference_count": len(reference_pmids),
            "phase5_action_count": sum(len(item.get("msl_action_items") or []) for item in insights),
            "fallback_used": not bool(selected),
        },
        "insights": insights,
        "guardrails": [
            "每条洞察必须保留 PMID、社区、图谱节点和限制说明。",
            "unassigned 文献不直接生成诊治格局结论。",
            "前端不调用 LLM；如后续接入模型，只能生成同 schema 结果并通过 PMID 校验。",
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    output = DATA_DIR / "landscapeInsights.js"
    atomic_write_js_global(output, "MG_LANDSCAPE_INSIGHTS", payload)
    print(
        "✅ landscape insights written:",
        output.relative_to(PROJECT),
        f"({payload['summary']['insight_count']} insights)",
    )


if __name__ == "__main__":
    main()
