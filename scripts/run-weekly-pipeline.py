#!/usr/bin/env python3
"""MA-MG-HUB 可审计、可恢复周更管线。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.pipeline_runner import (
    PipelineFailure,
    PipelineRunner,
    PipelineStep,
    generate_release_manifest,
)


PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
AUDIT_DIR = PROJECT / ".hermes-audit" / "pipeline-runs"


def py(script: str) -> list[str]:
    return [sys.executable, f"scripts/{script}"]


def pipeline_steps(args, full_available: bool | None = None) -> list[PipelineStep]:
    if full_available is None:
        full_available = (DATA / "literature-full.json").exists()
    steps = []
    if not args.skip_fetch:
        steps.extend([
            PipelineStep("fetch-pubmed", py("fetch-pubmed-weekly.py"), outputs=[DATA / "literature-weekly.json"]),
            PipelineStep("enrich-weekly", py("enrich-weekly-literature.py"), outputs=[DATA / "literature-weekly.json", DATA / "guideline-consensus-cache.json"]),
            PipelineStep("merge-weekly", py("merge-weekly-literature.py"), outputs=[DATA / "literature-recent.js"]),
        ])
    if args.local_full and full_available:
        steps.extend([
            PipelineStep(
                "filter-mg-core-full",
                py("filter-mg-core-literature.py") + ["--apply"],
                outputs=[DATA / "literature-full.json"],
            ),
            PipelineStep(
                "reclassify-recent-full",
                py("reclassify-existing-iii.py") + ["--modes", "ALL", "--recent-days", "365"],
                outputs=[DATA / "literature-full.json", DATA / "literature-recent.js"],
            ),
        ])
    if args.skip_downstream:
        return steps
    buildFrontendCommand = py("build-frontend-data.py")
    if full_available:
        buildFrontendCommand.append("--rebuild-experts-from-full")
    steps.append(PipelineStep(
        "build-frontend", buildFrontendCommand,
        outputs=[
            DATA / "signals-weekly.js", DATA / "china-intelligence.js", DATA / "dashboard-data.js",
            DATA / "expert-profiles.js", DATA / "expert-profiles-china.js",
            DATA / "expert-profiles-international.js", DATA / "landscape-data.js", DATA / "content-modules.js",
        ],
    ))
    if not args.skip_llm:
        steps.append(PipelineStep(
            "enrich-literature-narrative", py("enrich-literature-narrative.py"),
            outputs=[DATA / "signals-weekly.js"], optional=True,
        ))
    if full_available:
        steps.extend([
            PipelineStep("build-full-index", py("buildFullLiteratureIndex.py"), outputs=[DATA / "literature-full-index.js"]),
            PipelineStep("build-community", py("buildCommunityData.py"), outputs=[DATA / "communityAssignmentIndex.js", DATA / "communityCards.js", DATA / "communityWeekly.js"]),
            PipelineStep("build-knowledge", py("build-knowledge-data.py"), outputs=[DATA / "knowledge-graph.js", DATA / "graphHealth.js"]),
            PipelineStep("build-china-author-network", py("buildChinaAuthorNetwork.py"), outputs=[DATA / "china-author-network.js"]),
        ])
    steps.extend([
        PipelineStep("build-curated-topics", py("build-curated-topic-data.py"), outputs=[DATA / "curated-topics.js"]),
        PipelineStep("build-wiki-coverage", py("buildWikiTopicCoverage.py"), outputs=[DATA / "wikiTopicCoverage.js"]),
        PipelineStep("build-landscape-insights", py("buildLandscapeInsights.py"), outputs=[DATA / "landscapeInsights.js"]),
        PipelineStep("build-backend-options", py("buildBackendOptions.py"), outputs=[DATA / "backendOptions.js"]),
        PipelineStep("refresh-chictr-cache", py("refresh-chictr-cache.py"), outputs=[DATA / "chictr-trials-cache.json"], optional=True),
        PipelineStep(
            "build-clinical-trials",
            py("build-clinical-trials-data.py"),
            outputs=[DATA / "clinical-trials-data.js", DATA / "clinicalTrialsSummary.js"],
        ),
        PipelineStep("build-source-signals", py("build-source-signals.py"), outputs=[DATA / "source-signals.js"]),
        PipelineStep("generate-weekly-summary", py("generate-weekly-summary.py"), outputs=[DATA / "weekly-summary.md"]),
    ])
    if not args.skip_status:
        steps.append(PipelineStep("generate-pipeline-status", py("generate-pipeline-status.py"), outputs=[DATA / "pipeline-status.js"]))
    return steps


def public_artifacts() -> list[Path]:
    return sorted(path for path in DATA.glob("*.js") if path.name != "release-manifest.js")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MA-MG-HUB weekly data pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过 PubMed 增量抓取")
    parser.add_argument("--skip-llm", action="store_true", help="跳过文献语义增强")
    parser.add_argument("--skip-status", action="store_true", help="跳过管线状态生成")
    parser.add_argument("--skip-downstream", action="store_true", help="只执行抓取/富集/存储同步")
    parser.add_argument("--local-full", action="store_true", help="本地 full 模式：合并后执行 MG-core --apply 与近一年重分类")
    parser.add_argument("--run-id", help="审计运行 ID；默认使用 UTC 时间戳")
    parser.add_argument("--resume", action="store_true", help="恢复同 run-id，仅跳过输出哈希仍匹配的成功步骤")
    parser.add_argument("--from-step", help="从指定 step id 开始；建议与 --resume 配合")
    parser.add_argument("--step-timeout", type=float, default=900, help="单步骤默认超时秒数")
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        parser.error("--run-id 仅允许字母、数字、点、下划线和连字符")
    if args.resume and not args.run_id:
        parser.error("--resume 必须显式提供 --run-id")
    if args.step_timeout <= 0:
        parser.error("--step-timeout 必须大于 0")

    full_available = (DATA / "literature-full.json").exists()
    if args.local_full and not full_available:
        parser.error("--local-full 需要 data/literature-full.json")
    steps = pipeline_steps(args, full_available=full_available)
    if not full_available:
        print("ℹ️ cloud-safe mode: 保留 full index/community/knowledge/china-author-network last-good 产物")
    print(f"MA-MG-HUB weekly pipeline · run-id={run_id}")
    runner = PipelineRunner(PROJECT, AUDIT_DIR, default_timeout=args.step_timeout)
    try:
        result = runner.run(steps, run_id=run_id, resume=args.resume, from_step=args.from_step)
    except PipelineFailure as exc:
        print(f"❌ required step {exc.step_id}: {exc}", file=sys.stderr)
        return exc.return_code
    if not args.skip_downstream and result["status"] in {"success", "success_with_warnings"}:
        generate_release_manifest(result, public_artifacts(), DATA / "release-manifest.js", project=PROJECT)
        print(f"✅ coherent release manifest: data/release-manifest.js · run-id={run_id}")
    else:
        print("ℹ️ partial/ingest-only run: release manifest not updated")
    print(f"✅ Pipeline finished with status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
