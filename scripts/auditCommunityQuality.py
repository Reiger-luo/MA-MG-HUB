#!/usr/bin/env python3
"""生成社区语义层质量审计报告。

该脚本只做审计，不修改 taxonomy 或 assignment。目的：把 oversized、low confidence、
conflict、topic 覆盖和疑似漏归类问题整理成可 review 的报告，为下一轮规则修正提供依据。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"
reportDir = projectPath / "report"
taxonomyPath = dataDir / "communityTaxonomy.js"
cardsPath = dataDir / "communityCards.js"
auditPath = dataDir / "communityAudit.js"
topicCoveragePath = dataDir / "wikiTopicCoverage.js"
fullIndexPath = dataDir / "literature-full-index.js"
assignmentJsonlPath = dataDir / "communityAssignments.jsonl"


def loadJs(path: Path, globalName: str):
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(globalName)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path.relative_to(projectPath)}")
    return json.loads(match.group(1))


def loadShardPayload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_COMMUNITY_ASSIGNMENT_SHARDS\[[^\]]+\]\s*=\s*(\{.*\});\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path.relative_to(projectPath)}")
    return json.loads(match.group(1))


def loadAssignments() -> list[dict]:
    if assignmentJsonlPath.exists():
        with assignmentJsonlPath.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    assignments = []
    for path in sorted(dataDir.glob("communityAssignments-*.js")):
        if path.name == "communityAssignmentsRecent.js":
            continue
        payload = loadShardPayload(path)
        assignments.extend(payload.get("items") or [])
    return assignments


def communityTitleMap(taxonomy: dict, cards: dict) -> dict[str, str]:
    titleById = {}
    for item in taxonomy.get("communities") or []:
        titleById[item["id"]] = item.get("title") or item["id"]
    for card in cards.get("cards") or []:
        titleById[card["id"]] = card.get("title") or titleById.get(card["id"], card["id"])
    titleById["unassigned"] = "未归类"
    return titleById


def indexById(items: list[dict], key: str) -> dict:
    return {item[key]: item for item in items if item.get(key)}


def loadArticleIndex() -> dict[str, dict]:
    if not fullIndexPath.exists():
        return {}
    payload = loadJs(fullIndexPath, "MG_LITERATURE_FULL_INDEX")
    return {str(item.get("pmid")): item for item in payload.get("items") or [] if item.get("pmid")}


def formatRate(value: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{value / total * 100:.1f}%".replace(".0%", "%")


def markdownTable(headers: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def articleLabel(pmid: str, articleByPmid: dict[str, dict]) -> str:
    article = articleByPmid.get(str(pmid)) or {}
    title = article.get("title") or ""
    shortTitle = title[:92] + "..." if len(title) > 95 else title
    return f"PMID {pmid}" + (f" — {shortTitle}" if shortTitle else "")


def termsForCommunity(taxonomy: dict, communityId: str) -> dict:
    for item in taxonomy.get("communities") or []:
        if item.get("id") == communityId:
            return item.get("terms") or {}
    return {}


def hasProductSignal(assignment: dict, productTerms: set[str]) -> bool:
    products = {str(item).lower() for item in (assignment.get("facets") or {}).get("products") or []}
    matchedTerms = {str(item).lower() for item in assignment.get("matched_terms") or []}
    return bool((products | matchedTerms) & productTerms)


def buildAuditReport(outputPath: Path) -> dict:
    taxonomy = loadJs(taxonomyPath, "MG_COMMUNITY_TAXONOMY")
    cards = loadJs(cardsPath, "MG_COMMUNITY_CARDS")
    communityAudit = loadJs(auditPath, "MG_COMMUNITY_AUDIT")
    topicCoverage = loadJs(topicCoveragePath, "MG_WIKI_TOPIC_COVERAGE")
    assignments = loadAssignments()
    articleByPmid = loadArticleIndex()

    titleById = communityTitleMap(taxonomy, cards)
    cardsById = indexById(cards.get("cards") or [], "id")
    coverageById = indexById(topicCoverage.get("community_coverage") or [], "community_id")
    total = len(assignments)
    primaryCounts = Counter(item.get("primary") or "unassigned" for item in assignments)
    lowCounts = Counter((item.get("primary") or "unassigned") for item in assignments if item.get("confidence") == "low")
    conflictItems = [item for item in assignments if "crossCommunityConflict" in (item.get("flags") or [])]
    conflictCounts = Counter(item.get("primary") or "unassigned" for item in conflictItems)
    unassignedCount = primaryCounts.get("unassigned", 0)

    conflictPairCounts: Counter = Counter()
    conflictPairExamples: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in conflictItems:
        primary = item.get("primary") or "unassigned"
        for secondary in (item.get("secondary") or [])[:2]:
            secondaryId = secondary.get("community_id")
            if not secondaryId:
                continue
            pair = (primary, secondaryId)
            conflictPairCounts[pair] += 1
            if len(conflictPairExamples[pair]) < 3:
                conflictPairExamples[pair].append(str(item.get("pmid")))

    fcrnTerms = termsForCommunity(taxonomy, "fcrnTargetedTherapy")
    fcrnProductTerms = {term.lower() for term in (fcrnTerms.get("strong") or []) if term.lower() not in {"fcrn", "neonatal fc receptor"}}
    fcrnLeakage = [
        item for item in assignments
        if item.get("primary") != "fcrnTargetedTherapy" and hasProductSignal(item, fcrnProductTerms)
    ]

    complementTerms = {term.lower() for term in termsForCommunity(taxonomy, "complementAndNovelTargets").get("strong") or []}
    complementLeakage = [
        item for item in assignments
        if item.get("primary") != "complementAndNovelTargets" and hasProductSignal(item, complementTerms)
    ]

    communityRows = []
    for communityId, count in primaryCounts.most_common():
        card = cardsById.get(communityId) or {}
        coverage = coverageById.get(communityId) or {}
        communityRows.append([
            titleById.get(communityId, communityId),
            count,
            formatRate(count, total),
            lowCounts.get(communityId, 0),
            conflictCounts.get(communityId, 0),
            coverage.get("topic_count", 0),
            card.get("recent_14d_count", 0),
        ])

    conflictRows = []
    for (primary, secondaryId), count in conflictPairCounts.most_common(12):
        examples = "；".join(conflictPairExamples[(primary, secondaryId)])
        conflictRows.append([
            titleById.get(primary, primary),
            titleById.get(secondaryId, secondaryId),
            count,
            examples,
        ])

    oversizedRows = [
        row for row in communityRows
        if isinstance(row[1], int) and total and row[1] / total >= 0.25
    ]
    lowRatioRows = []
    for communityId, count in primaryCounts.items():
        if communityId == "unassigned" or count < 50:
            continue
        low = lowCounts.get(communityId, 0)
        if count and low / count >= 0.25:
            lowRatioRows.append([
                titleById.get(communityId, communityId),
                count,
                low,
                formatRate(low, count),
            ])
    lowRatioRows.sort(key=lambda row: (-row[2], row[0]))

    topicRows = []
    for item in topicCoverage.get("community_coverage") or []:
        topicRows.append([
            item.get("title") or titleById.get(item.get("community_id"), item.get("community_id")),
            item.get("topic_count", 0),
            item.get("updated_topic_count", 0),
            item.get("high_confidence_topic_count", 0),
            item.get("article_count", 0),
        ])
    topicRows.sort(key=lambda row: (row[1], -row[4], row[0]))

    clinicalCount = primaryCounts.get("clinicalSubtypesStratification", 0)
    clinicalRate = clinicalCount / total if total else 0
    competitiveCoverage = coverageById.get("competitiveLandscapeIndirectComparison") or {}
    competitiveTopicCount = int(competitiveCoverage.get("topic_count") or 0)
    competitiveCount = primaryCounts.get("competitiveLandscapeIndirectComparison", 0)
    issueLines = []
    if clinicalRate >= 0.25:
        issueLines.append(
            f"1. `clinicalSubtypesStratification` 仍超过 25% 阈值（{clinicalCount} 篇，{formatRate(clinicalCount, total)}）。"
            "建议继续把宽泛抗体词作为 population facet，primary community 只保留明确亚型分层、预测、诊断或差异治疗意图。"
        )
    else:
        issueLines.append(
            f"1. `clinicalSubtypesStratification` 已低于 25% 阈值（{clinicalCount} 篇，{formatRate(clinicalCount, total)}），"
            "但低置信度和冲突仍高，后续应继续把亚型/诊断/RWE 边界作为长期回归抽查对象。"
        )
    issueLines.append(
        f"2. FcRn 疑似漏归类样本：{len(fcrnLeakage)} 篇 assignment 具有 FcRn 产品/术语信号但 primary 不是 FcRn 社区。"
        "其中包含疗效终点、RWE、HEOR 和 competitive 作为合理 primary 的文献，不能直接等同于错误。"
    )
    issueLines.append(
        f"3. 补体/新靶点疑似漏归类样本：{len(complementLeakage)} 篇 assignment 具有补体产品/术语信号但 primary 不是补体社区。"
        "其中联合比较、RWE、HEOR 和宽泛综述需要保留 secondary/facet 解释，而不是一律提升补体 primary。"
    )
    if competitiveTopicCount < 3:
        issueLines.append(
            "4. `competitiveLandscapeIndirectComparison` 专题覆盖仍弱，说明 wiki 和 taxonomy 已有比较语义，但前台策展专题需要补齐。"
        )
    else:
        issueLines.append(
            f"4. `competitiveLandscapeIndirectComparison` 当前收敛到 {competitiveCount} 篇、{competitiveTopicCount} 个相关专题。"
            "v4d 已收窄为严格治疗策略、跨产品比较、NMA/ITC 或 evidence synthesis；普通 versus / controlled study 不再自动进入竞争格局。"
        )

    nextStepLines = [
        "1. v4d 已完成第二轮 LLM review 后的 P0.5 cleanup：competitive 收窄、safety override 增强、MG 背景文献更积极进入 unassigned / review queue。",
        "2. 由于 v4d 是质量优先版本，unassigned 占比升高是预期结果；后续重点抽查 recent high-evidence unassigned，而不是追求覆盖率最大化。",
        "3. P1：把 FcRn / complement 疑似漏归类样本拆成“合理 secondary”和“真实漏归类”两类，避免只看泄漏计数做误判。",
        "4. P1：为 `competitiveLandscapeIndirectComparison` 增加前端解释，说明该社区只代表药物、治疗策略、HEOR 或 evidence synthesis 的比较，不代表所有 versus 文献。",
        "5. 若下一次周更 recent unassigned 没有高等级 MG 核心文献，可进入 Phase 4 动态诊治格局。",
    ]

    lines = [
        "# MA-MG-HUB 社区语义层质量审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 总览",
        "",
        f"- 总文献：{total}",
        f"- 已归类：{total - unassignedCount}（{formatRate(total - unassignedCount, total)}）",
        f"- 未归类：{unassignedCount}（{formatRate(unassignedCount, total)}）",
        f"- 低置信度：{sum(lowCounts.values())}（{formatRate(sum(lowCounts.values()), total)}）",
        f"- 冲突归类：{len(conflictItems)}（{formatRate(len(conflictItems), total)}）",
        f"- wiki 专题覆盖：{topicCoverage.get('stats', {}).get('covered_community_count', 0)}/{topicCoverage.get('stats', {}).get('community_count', 0)} 个社区",
        "",
        "## 社区分布",
        "",
    ]
    lines.extend(markdownTable(["社区", "文献", "占比", "低置信度", "冲突", "专题", "近14天"], communityRows))
    lines.extend([
        "",
        "## 主要质量信号",
        "",
    ])
    if oversizedRows:
        lines.append("### 过大社区")
        lines.append("")
        lines.extend(markdownTable(["社区", "文献", "占比", "低置信度", "冲突", "专题", "近14天"], oversizedRows))
        lines.append("")
    if lowRatioRows:
        lines.append("### 低置信度占比较高")
        lines.append("")
        lines.extend(markdownTable(["社区", "文献", "低置信度", "比例"], lowRatioRows[:8]))
        lines.append("")
    lines.extend([
        "### 冲突归类 Top Pairs",
        "",
    ])
    lines.extend(markdownTable(["Primary", "Secondary", "冲突数", "样本 PMID"], conflictRows))
    lines.extend([
        "",
        "### 专题覆盖稀疏社区",
        "",
    ])
    lines.extend(markdownTable(["社区", "专题", "本周更新专题", "高置信专题", "社区文献"], topicRows[:8]))
    lines.extend([
        "",
        "## 疑似边界问题",
        "",
    ])
    lines.extend(issueLines)
    lines.extend(["", "## 抽样入口", "", "### FcRn 疑似漏归类样本", ""])
    lines.extend([
        f"- {articleLabel(str(item.get('pmid')), articleByPmid)}；primary={titleById.get(item.get('primary'), item.get('primary'))}；confidence={item.get('confidence')}"
        for item in fcrnLeakage[:12]
    ] or ["- 暂无"])
    lines.extend([
        "",
        "### 补体疑似漏归类样本",
        "",
    ])
    lines.extend([
        f"- {articleLabel(str(item.get('pmid')), articleByPmid)}；primary={titleById.get(item.get('primary'), item.get('primary'))}；confidence={item.get('confidence')}"
        for item in complementLeakage[:12]
    ] or ["- 暂无"])
    lines.extend([
        "",
        "## 建议下一步",
        "",
    ])
    lines.extend(nextStepLines)
    lines.extend([
        "",
        "## Phase 4 进入条件",
        "",
        "动态诊治格局可以在 v4d 规则稳定后进入，但生成洞察时必须展示 PMID、证据等级、社区 primary/secondary、图谱节点和 abstract-level 局限；unassigned 文献只能作为待审信号，不能直接生成格局结论。",
        "",
    ])

    outputPath.parent.mkdir(parents=True, exist_ok=True)
    outputPath.write_text("\n".join(lines), encoding="utf-8")
    return {
        "total": total,
        "unassigned": unassignedCount,
        "lowConfidence": sum(lowCounts.values()),
        "conflicts": len(conflictItems),
        "fcrnLeakage": len(fcrnLeakage),
        "complementLeakage": len(complementLeakage),
        "output": str(outputPath.relative_to(projectPath)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(reportDir / f"communitySemanticQualityAudit-{datetime.now().strftime('%Y-%m-%d')}.md"),
        help="输出 Markdown 报告路径",
    )
    args = parser.parse_args()
    outputPath = Path(args.out)
    if not outputPath.is_absolute():
        outputPath = projectPath / outputPath
    result = buildAuditReport(outputPath)
    print("✅ community quality audit written:", result["output"])
    print(
        "   total={total} unassigned={unassigned} low={lowConfidence} "
        "conflict={conflicts} fcrnLeakage={fcrnLeakage} complementLeakage={complementLeakage}".format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
