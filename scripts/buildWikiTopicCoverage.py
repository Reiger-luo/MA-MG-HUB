#!/usr/bin/env python3
"""生成 wiki 专题与全 MG 社区语义层的覆盖关系。

该脚本不调用 LLM，也不读取 abstract 正文。它把 curated wiki topic 的
anchor_nodes 映射到知识图谱节点的 dominant community，并用 evidence_pmids
对应的社区 assignment 作为补充证据，生成前端轻量连接层。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"
topicPath = dataDir / "curated-topics.js"
graphPath = dataDir / "knowledge-graph.js"
taxonomyPath = dataDir / "communityTaxonomy.js"
cardsPath = dataDir / "communityCards.js"
assignmentJsonlPath = dataDir / "communityAssignments.jsonl"
recentAssignmentsPath = dataDir / "communityAssignmentsRecent.js"
outputPath = dataDir / "wikiTopicCoverage.js"


def loadJs(path: Path, globalName: str) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(globalName)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path.relative_to(projectPath)}")
    return json.loads(match.group(1))


def safeLoadJs(path: Path, globalName: str) -> dict:
    if not path.exists():
        return {}
    return loadJs(path, globalName)


def loadShardPayload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_COMMUNITY_ASSIGNMENT_SHARDS\[[^\]]+\]\s*=\s*(\{.*\});\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path.relative_to(projectPath)}")
    return json.loads(match.group(1))


def loadAssignmentsByPmid() -> dict[str, dict]:
    """优先使用 full 级 jsonl；缺失时回退公开分片，保证静态产物可重建。"""
    assignmentsByPmid: dict[str, dict] = {}
    if assignmentJsonlPath.exists():
        with assignmentJsonlPath.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                pmid = str(item.get("pmid") or "")
                if pmid:
                    assignmentsByPmid[pmid] = item
        return assignmentsByPmid

    shardPaths = sorted(
        path for path in dataDir.glob("communityAssignments-*.js")
        if path.name != "communityAssignmentsRecent.js"
    )
    for shardPath in shardPaths:
        try:
            payload = loadShardPayload(shardPath)
        except ValueError:
            continue
        for item in payload.get("items") or []:
            pmid = str(item.get("pmid") or "")
            if pmid:
                assignmentsByPmid[pmid] = item

    if not assignmentsByPmid and recentAssignmentsPath.exists():
        recentPayload = loadJs(recentAssignmentsPath, "MG_COMMUNITY_RECENT_ASSIGNMENTS")
        for item in recentPayload.get("items") or []:
            pmid = str(item.get("pmid") or "")
            if pmid:
                assignmentsByPmid[pmid] = item
    return assignmentsByPmid


def communityTitleMap(taxonomy: dict, cards: dict) -> dict[str, str]:
    titleById: dict[str, str] = {}
    for item in taxonomy.get("communities") or []:
        titleById[item["id"]] = item.get("title") or item["id"]
    for card in cards.get("cards") or []:
        titleById[card["id"]] = card.get("title") or titleById.get(card["id"], card["id"])
    return titleById


def communityArticleCountMap(cards: dict) -> dict[str, int]:
    return {
        card["id"]: int(card.get("article_count") or 0)
        for card in cards.get("cards") or []
    }


def addScore(counter: Counter, communityId: str | None, amount: float) -> None:
    if communityId and communityId != "unassigned":
        counter[communityId] += amount


def termsByCommunity(taxonomy: dict) -> dict[str, dict]:
    return {
        item["id"]: item.get("terms") or {}
        for item in taxonomy.get("communities") or []
    }


def topicSearchText(topic: dict) -> str:
    claims = " ".join((claim.get("text") or "") for claim in (topic.get("claims") or []))
    return " ".join([
        topic.get("title") or "",
        topic.get("summary") or "",
        claims,
        " ".join(topic.get("msl_use") or []),
    ]).lower()


def termInText(term: str, text: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9]{2,6}", term):
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def confidenceFor(score: float, anchorCount: int, pmidCount: int, termCount: int) -> str:
    sourceCount = int(anchorCount > 0) + int(pmidCount > 0) + int(termCount > 0)
    if score >= 8 and sourceCount >= 2:
        return "high"
    if score >= 5 or sourceCount >= 2:
        return "medium"
    if score > 0:
        return "low"
    return "unmapped"


def topicImpactStatus(topic: dict) -> str:
    return (topic.get("impact") or {}).get("status") or "quiet"


def buildTopicCoverage(topic: dict, nodesById: dict, assignmentsByPmid: dict, titleById: dict, termMap: dict) -> dict:
    scoreByCommunity: Counter = Counter()
    anchorCountByCommunity: Counter = Counter()
    pmidCountByCommunity: Counter = Counter()
    termCountByCommunity: Counter = Counter()

    for nodeId in topic.get("anchor_nodes") or []:
        node = nodesById.get(nodeId) or {}
        primaryId = node.get("dominant_community_id")
        if primaryId and primaryId != "unassigned":
            addScore(scoreByCommunity, primaryId, 3.0)
            anchorCountByCommunity[primaryId] += 1
        for profile in (node.get("community_profile") or [])[:3]:
            communityId = profile.get("community_id")
            if communityId and communityId != primaryId:
                addScore(scoreByCommunity, communityId, 0.75)
                anchorCountByCommunity[communityId] += 1

    for pmid in topic.get("evidence_pmids") or []:
        assignment = assignmentsByPmid.get(str(pmid)) or {}
        primaryId = assignment.get("primary")
        if primaryId and primaryId != "unassigned":
            addScore(scoreByCommunity, primaryId, 1.5)
            pmidCountByCommunity[primaryId] += 1
        for item in (assignment.get("secondary") or [])[:2]:
            communityId = item.get("community_id")
            if communityId and communityId != primaryId:
                addScore(scoreByCommunity, communityId, 0.5)
                pmidCountByCommunity[communityId] += 1

    text = topicSearchText(topic)
    for communityId, terms in termMap.items():
        for key, amount in (("strong", 4.0), ("normal", 1.8), ("weak", 0.75)):
            matched = [term for term in (terms.get(key) or []) if termInText(term, text)]
            if matched:
                addScore(scoreByCommunity, communityId, min(amount * len(matched), amount * 2))
                termCountByCommunity[communityId] += len(matched)

    ranked = []
    for communityId, score in scoreByCommunity.most_common():
        if score < 1.0:
            continue
        anchorCount = int(anchorCountByCommunity.get(communityId, 0))
        pmidCount = int(pmidCountByCommunity.get(communityId, 0))
        termCount = int(termCountByCommunity.get(communityId, 0))
        ranked.append({
            "community_id": communityId,
            "title": titleById.get(communityId, communityId),
            "score": round(score, 2),
            "anchor_node_count": anchorCount,
            "evidence_pmid_count": pmidCount,
            "keyword_hit_count": termCount,
            "confidence": confidenceFor(score, anchorCount, pmidCount, termCount),
        })

    top = ranked[0] if ranked else {}
    return {
        "topic_id": topic.get("id"),
        "title": topic.get("title") or topic.get("id"),
        "source_type": topic.get("source_type") or "topic",
        "status": topic.get("status") or "active",
        "impact_status": topicImpactStatus(topic),
        "updated": topic.get("updated") or "",
        "confidence": top.get("confidence") or "unmapped",
        "primary_community_id": top.get("community_id") or "",
        "primary_community_title": top.get("title") or "",
        "communities": ranked,
        "anchor_nodes": topic.get("anchor_nodes") or [],
        "evidence_pmid_count": len(topic.get("evidence_pmids") or []),
        "evidence_ref_count": len(topic.get("evidence_refs") or []),
    }


def buildCoveragePayload() -> dict:
    curated = loadJs(topicPath, "MG_CURATED_TOPICS")
    graph = loadJs(graphPath, "MG_KNOWLEDGE_GRAPH")
    taxonomy = loadJs(taxonomyPath, "MG_COMMUNITY_TAXONOMY")
    cards = safeLoadJs(cardsPath, "MG_COMMUNITY_CARDS")
    assignmentsByPmid = loadAssignmentsByPmid()

    titleById = communityTitleMap(taxonomy, cards)
    termMap = termsByCommunity(taxonomy)
    articleCountById = communityArticleCountMap(cards)
    nodesById = {node["id"]: node for node in graph.get("nodes") or []}
    topics = curated.get("topics") or []
    communities = taxonomy.get("communities") or []

    topicCoverage = [
        buildTopicCoverage(topic, nodesById, assignmentsByPmid, titleById, termMap)
        for topic in topics
    ]
    topicCoverage.sort(key=lambda item: (
        item["confidence"] == "unmapped",
        -(item["communities"][0]["score"] if item["communities"] else 0),
        item["title"],
    ))

    communityTopicIndex: dict[str, list[str]] = defaultdict(list)
    communityTopTopics: dict[str, list[dict]] = defaultdict(list)
    updatedCountByCommunity: Counter = Counter()
    highConfidenceByCommunity: Counter = Counter()

    for item in topicCoverage:
        for community in item.get("communities") or []:
            communityId = community["community_id"]
            communityTopicIndex[communityId].append(item["topic_id"])
            communityTopTopics[communityId].append({
                "topic_id": item["topic_id"],
                "title": item["title"],
                "score": community["score"],
                "confidence": community["confidence"],
                "impact_status": item["impact_status"],
            })
            if item["impact_status"] == "updatedEvidence":
                updatedCountByCommunity[communityId] += 1
            if community["confidence"] == "high":
                highConfidenceByCommunity[communityId] += 1

    communityCoverage = []
    for community in communities:
        communityId = community["id"]
        topTopics = sorted(
            communityTopTopics.get(communityId, []),
            key=lambda item: (item["impact_status"] != "updatedEvidence", -item["score"], item["title"]),
        )[:6]
        communityCoverage.append({
            "community_id": communityId,
            "title": titleById.get(communityId, communityId),
            "article_count": articleCountById.get(communityId, 0),
            "topic_count": len(set(communityTopicIndex.get(communityId, []))),
            "updated_topic_count": int(updatedCountByCommunity.get(communityId, 0)),
            "high_confidence_topic_count": int(highConfidenceByCommunity.get(communityId, 0)),
            "top_topics": topTopics,
        })
    communityCoverage.sort(key=lambda item: (-item["topic_count"], -item["updated_topic_count"], item["title"]))

    uncoveredTopics = [item for item in topicCoverage if not item.get("communities")]
    lowCoverageCommunities = [
        item for item in communityCoverage
        if item["topic_count"] == 0 or (item["article_count"] >= 500 and item["topic_count"] < 2)
    ]
    updatedTopics = [item for item in topicCoverage if item["impact_status"] == "updatedEvidence"]
    coveredCommunityCount = sum(1 for item in communityCoverage if item["topic_count"] > 0)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "2026.06-v4-phase3",
        "method": "anchorNodeDominantCommunityPlusEvidencePmidAssignments",
        "source_note": "efgar-wiki 专题层作为策展样板；社区归属来自 full MG 图谱节点和 full 级 PMID assignment，不做实时 LLM。",
        "stats": {
            "topic_count": len(topicCoverage),
            "community_count": len(communities),
            "covered_community_count": coveredCommunityCount,
            "uncovered_community_count": len(communities) - coveredCommunityCount,
            "uncovered_topic_count": len(uncoveredTopics),
            "updated_topic_count": len(updatedTopics),
            "assignment_source": "communityAssignments.jsonl" if assignmentJsonlPath.exists() else "publicAssignmentShards",
        },
        "topic_coverage": topicCoverage,
        "community_coverage": communityCoverage,
        "community_topic_index": {key: sorted(set(value)) for key, value in communityTopicIndex.items()},
        "gaps": {
            "uncovered_topics": [
                {
                    "topic_id": item["topic_id"],
                    "title": item["title"],
                    "evidence_pmid_count": item["evidence_pmid_count"],
                }
                for item in uncoveredTopics[:20]
            ],
            "low_coverage_communities": [
                {
                    "community_id": item["community_id"],
                    "title": item["title"],
                    "article_count": item["article_count"],
                    "topic_count": item["topic_count"],
                }
                for item in sorted(lowCoverageCommunities, key=lambda row: (-row["article_count"], row["title"]))[:10]
            ],
        },
    }


def writeJs(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* AUTO-GENERATED by scripts/buildWikiTopicCoverage.py\n"
        f" * 生成时间: {payload.get('generated_at', '')}\n"
        " * 说明: wiki 专题与全 MG 社区语义层连接关系，供知识库、首页和数据状态页展示。\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    path.write_text(header + f"window.MG_WIKI_TOPIC_COVERAGE = {js};\n", encoding="utf-8")
    print(f"✅ 已生成 {path.relative_to(projectPath)} ({path.stat().st_size // 1024} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(outputPath), help="输出 JS，默认 data/wikiTopicCoverage.js")
    args = parser.parse_args()
    outPath = Path(args.out)
    if not outPath.is_absolute():
        outPath = projectPath / outPath

    try:
        payload = buildCoveragePayload()
        writeJs(payload, outPath)
        stats = payload["stats"]
        print(
            "   专题覆盖: "
            f"{stats['topic_count']} 个专题 · "
            f"{stats['covered_community_count']}/{stats['community_count']} 个社区"
        )
        return 0
    except Exception as exc:
        print(f"❌ wiki topic coverage 生成失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
