#!/usr/bin/env python3
"""校验 MA-MG-HUB 公开数据契约；本脚本只读，不改写产物。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.io import load_js_global, load_json
from common.publicDataContract import (
    communityShardNames,
    publicArtifactNames,
    publicDataGlobals,
)


projectPath = Path(__file__).resolve().parent.parent
dataDir = projectPath / "data"


def sha256File(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def loadCommunityShard(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_COMMUNITY_ASSIGNMENT_SHARDS\[[^\]]+\]\s*=\s*", text)
    if not match:
        raise ValueError("缺少 MG_COMMUNITY_ASSIGNMENT_SHARDS 赋值")
    payload, _ = json.JSONDecoder().raw_decode(text[match.end():].lstrip())
    return payload


def pmidSet(items) -> set[str]:
    return {
        str(item.get("pmid") or "").strip()
        for item in (items or [])
        if str(item.get("pmid") or "").strip()
    }


def isPredominantlyChinese(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    chineseCount = len(re.findall(r"[\u3400-\u9fff]", text))
    latinCount = len(re.findall(r"[A-Za-z]", text))
    return chineseCount >= 4 and chineseCount >= latinCount * 0.35


def validateArtifacts() -> list[str]:
    errors = []
    expectedNames = set(publicArtifactNames())
    actualNames = {
        path.name for path in dataDir.glob("*.js")
        if path.name != "release-manifest.js"
    }
    missing = sorted(expectedNames - actualNames)
    unexpected = sorted(actualNames - expectedNames)
    if missing:
        errors.append("缺少公开 JS：" + "、".join(missing))
    if unexpected:
        errors.append("未登记公开 JS：" + "、".join(unexpected))

    for name, globalName in publicDataGlobals.items():
        path = dataDir / name
        if not path.exists():
            continue
        try:
            load_js_global(path, globalName)
        except Exception as exc:
            errors.append(f"{name} 无法按 window.{globalName} 解析：{exc}")

    shardTotal = 0
    for name in communityShardNames:
        path = dataDir / name
        if not path.exists():
            continue
        try:
            payload = loadCommunityShard(path)
            items = payload.get("items") or []
            if payload.get("item_count") != len(items):
                errors.append(f"{name} item_count 与 items 长度不一致")
            shardTotal += len(items)
        except Exception as exc:
            errors.append(f"{name} 无法解析：{exc}")

    indexPath = dataDir / "communityAssignmentIndex.js"
    if indexPath.exists():
        indexPayload = load_js_global(indexPath, "MG_COMMUNITY_ASSIGNMENT_INDEX")
        declaredNames = {
            Path(str(item.get("path") or item.get("file") or "")).name
            for item in (indexPayload.get("shards") or [])
        }
        if declaredNames != set(communityShardNames):
            errors.append("communityAssignmentIndex.js 的分片列表与公开契约不一致")
        if indexPayload.get("item_count") != shardTotal:
            errors.append(
                f"社区主计数 {indexPayload.get('item_count')} 与分片合计 {shardTotal} 不一致"
            )
    return errors


def validateRecentContracts() -> list[str]:
    errors = []
    literature = load_js_global(dataDir / "literature-recent.js", "MG_LITERATURE_DATA")
    literatureMeta = load_js_global(dataDir / "literature-recent.js", "MG_LITERATURE_META")
    assignments = load_js_global(
        dataDir / "communityAssignmentsRecent.js",
        "MG_COMMUNITY_RECENT_ASSIGNMENTS",
    )
    signals = load_js_global(dataDir / "signals-weekly.js", "MG_SIGNALS_DATA")
    dashboard = load_js_global(dataDir / "dashboard-data.js", "MG_DASHBOARD_DATA")

    literaturePmids = pmidSet(literature)
    assignmentPmids = pmidSet(assignments.get("items") or [])
    if literaturePmids != assignmentPmids:
        errors.append(
            "公开 recent 与社区 recent PMID 不一致："
            f"缺归类 {len(literaturePmids - assignmentPmids)}，多余 {len(assignmentPmids - literaturePmids)}"
        )
    if literatureMeta.get("item_count") != len(literature):
        errors.append("MG_LITERATURE_META.item_count 与公开数组长度不一致")
    if assignments.get("item_count") != len(assignments.get("items") or []):
        errors.append("communityAssignmentsRecent.js item_count 与 items 长度不一致")

    stats = dashboard.get("stats") or {}
    if stats.get("recent_articles") != len(literature):
        errors.append("dashboard recent_articles 与 literature recent 长度不一致")
    if stats.get("signals") != len(signals.get("signals") or []):
        errors.append("dashboard signals 与 signals-weekly.js 不一致")
    if signals.get("window_basis") != "trueIngestAddedPmids":
        errors.append("signals-weekly.js 未声明 trueIngestAddedPmids 窗口口径")
    sourcePolicy = signals.get("source_policy") or {}
    if sourcePolicy.get("llm_enrichment") is not True:
        errors.append("signals-weekly.js 未完成 LLM 中文叙事 enrich，禁止发布占位 finding")
    for signal in signals.get("signals") or []:
        signalId = signal.get("id") or "未编号"
        relatedPmids = {str(item) for item in signal.get("related_pmids") or [] if item}
        evidenceItems = signal.get("evidenceItems") or []
        evidencePmids = {str(item.get("pmid") or "") for item in evidenceItems if item.get("pmid")}
        if evidencePmids != relatedPmids:
            errors.append(f"信号 {signalId} 的逐篇证据与 related_pmids 不一致")
        for evidence in evidenceItems:
            finding = str(evidence.get("finding") or "").strip()
            if not isPredominantlyChinese(finding):
                errors.append(f"信号 {signalId} 含非中文或空 finding")
            if finding.endswith(("…", "...")):
                errors.append(f"信号 {signalId} 含截断 finding")
    return errors


def validateWeeklyIngest() -> list[str]:
    """本地完整发布额外核对真实 ingest；该文件不进入公开仓库。"""
    errors = []
    signals = load_js_global(dataDir / "signals-weekly.js", "MG_SIGNALS_DATA")
    sourcePolicy = signals.get("source_policy") or {}
    if sourcePolicy.get("weekly_selection") == "replay_current_published_window":
        # 受控重放保留已发布窗口，不应被后来生成的空 ingest 清空；但冻结队列必须可完整审计。
        cohort = [str(item) for item in signals.get("analysis_cohort_pmids") or [] if item]
        decisions = signals.get("selection_decisions") or []
        decisionPmids = [str(item.get("pmid") or "") for item in decisions if item.get("pmid")]
        signalPmids = {
            str(item)
            for signal in signals.get("signals") or []
            for item in signal.get("related_pmids") or []
            if item
        }
        if sourcePolicy.get("replay_window_preserved") is not True:
            errors.append("signals-weekly.js 重放模式未声明 replay_window_preserved")
        if not signals.get("window_start") or not signals.get("window_end"):
            errors.append("signals-weekly.js 重放模式缺少冻结窗口")
        if not cohort or len(cohort) != len(set(cohort)):
            errors.append("signals-weekly.js 重放队列为空或含重复 PMID")
        if set(decisionPmids) != set(cohort) or len(decisionPmids) != len(cohort):
            errors.append("signals-weekly.js 重放逐篇裁决未完整覆盖冻结队列")
        if sourcePolicy.get("replay_source_count") != len(cohort):
            errors.append("signals-weekly.js replay_source_count 与冻结队列不一致")
        if not signalPmids.issubset(set(cohort)):
            errors.append("signals-weekly.js 重放信号含冻结队列以外 PMID")
        return errors

    ingestPath = dataDir / "literature-ingest-latest.json"
    if not ingestPath.exists():
        return ["缺少本轮 literature-ingest-latest.json"]
    ingest = load_json(ingestPath)
    addedPmids = {str(item) for item in ingest.get("added_pmids") or []}
    signalPmids = set()
    for signal in signals.get("signals") or []:
        signalPmids.update(str(item) for item in signal.get("related_pmids") or [] if item)
    if not signalPmids.issubset(addedPmids):
        errors.append(f"本周信号含 {len(signalPmids - addedPmids)} 个非本轮真实新增 PMID")
    if signals.get("window_start") != ingest.get("window_start"):
        errors.append("signals-weekly.js window_start 与 ingest manifest 不一致")
    if signals.get("window_end") != ingest.get("window_end"):
        errors.append("signals-weekly.js window_end 与 ingest manifest 不一致")
    return errors


def validateReleaseManifest() -> list[str]:
    errors = []
    manifestPath = dataDir / "release-manifest.js"
    if not manifestPath.exists():
        return ["缺少 release-manifest.js"]
    manifest = load_js_global(manifestPath, "MG_RELEASE_MANIFEST")
    manifestByName = {
        Path(str(item.get("path") or "")).name: item
        for item in manifest.get("artifacts") or []
        if item.get("path")
    }
    expectedNames = set(publicArtifactNames())
    if set(manifestByName) != expectedNames:
        missing = sorted(expectedNames - set(manifestByName))
        unlisted = sorted(set(manifestByName) - expectedNames)
        if missing:
            errors.append("release manifest 缺少：" + "、".join(missing))
        if unlisted:
            errors.append("release manifest 含未登记项：" + "、".join(unlisted))
    for name in sorted(expectedNames & set(manifestByName)):
        path = dataDir / name
        if path.exists() and sha256File(path) != manifestByName[name].get("sha256"):
            errors.append(f"release manifest 哈希不符：{name}")
    if manifest.get("pipeline_status") not in {"success", "success_with_warnings"}:
        errors.append("release manifest pipeline_status 不是可发布状态")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-release", action="store_true", help="同时核对最终 release manifest")
    parser.add_argument("--source-only", action="store_true", help="只核对当前仓库已发布产物，不要求本地 ingest")
    args = parser.parse_args()

    errors = validateArtifacts()
    errors.extend(validateRecentContracts())
    if not args.source_only:
        errors.extend(validateWeeklyIngest())
    if args.require_release:
        errors.extend(validateReleaseManifest())
    if errors:
        for error in errors:
            print(f"❌ {error}", file=sys.stderr)
        return 1
    scope = "公开文件与发布清单" if args.require_release else "公开文件契约"
    print(f"✅ {scope}校验通过：{len(publicArtifactNames())} 个 JS 产物")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
