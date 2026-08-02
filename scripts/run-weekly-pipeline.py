#!/usr/bin/env python3
"""MA-MG-HUB 可审计、可恢复周更管线。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.pipeline_runner import (
    PipelineFailure,
    PipelineRunner,
    PipelineStep,
    generate_release_manifest,
)
from common.publicDataContract import communityArtifactPaths, publicArtifactPaths


PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
AUDIT_DIR = PROJECT / ".hermes-audit" / "pipeline-runs"
ACTIVE_HTML = [
    PROJECT / "index.html",
    PROJECT / "pages" / "literature.html",
    PROJECT / "pages" / "landscape.html",
    PROJECT / "pages" / "knowledge.html",
    PROJECT / "pages" / "msl.html",
    PROJECT / "pages" / "data-ops.html",
]


def py(script: str) -> list[str]:
    return [sys.executable, f"scripts/{script}"]


def pipelineMode(args, fullAvailable: bool) -> str:
    """解析运行模式；--local-full 仅保留为向后兼容别名。"""
    explicitMode = getattr(args, "mode", None)
    if explicitMode:
        return explicitMode
    if getattr(args, "local_full", False):
        return "authoritative-full"
    return "validate-only"


def pipeline_steps(args, full_available: bool | None = None) -> list[PipelineStep]:
    if full_available is None:
        full_available = (DATA / "literature-full.json").exists()
    mode = pipelineMode(args, full_available)
    if mode == "validate-only":
        return [PipelineStep(
            "validate-current-release",
            py("validatePublicRelease.py") + ["--source-only", "--require-release"],
        )]

    steps = []
    if mode == "authoritative-full" and not args.skip_fetch:
        steps.extend([
            PipelineStep("fetch-pubmed", py("fetch-pubmed-weekly.py"), outputs=[DATA / "literature-weekly.json"]),
            PipelineStep("enrich-weekly", py("enrich-weekly-literature.py"), outputs=[DATA / "literature-weekly.json", DATA / "guideline-consensus-cache.json"]),
            PipelineStep("merge-weekly", py("merge-weekly-literature.py"), outputs=[DATA / "literature-recent.js", DATA / "literature-ingest-latest.json"]),
        ])
    if full_available:
        steps.extend([
            PipelineStep(
                "filter-mg-core-full",
                py("filter-mg-core-literature.py") + ["--apply"],
                outputs=[DATA / "literature-full.json"],
            ),
            PipelineStep(
                "reclassify-recent-full",
                py("reclassify-existing-iii.py") + [
                    "--modes", "ALL", "--recent-days", "365", "--skip-frontend-build",
                ],
                outputs=[DATA / "literature-full.json", DATA / "literature-recent.js"],
            ),
        ])
    if args.skip_downstream:
        return steps
    steps.append(PipelineStep(
        "refresh-chictr-cache",
        py("refresh-chictr-cache.py"),
        outputs=[DATA / "chictr-trials-cache.json"],
        optional=True,
    ))
    buildFrontendCommand = py("build-frontend-data.py")
    if full_available:
        buildFrontendCommand.append("--rebuild-experts-from-full")
    steps.append(PipelineStep(
        "build-frontend", buildFrontendCommand,
        outputs=[
            DATA / "signals-weekly.js", DATA / "china-intelligence.js", DATA / "dashboard-data.js",
            DATA / "expert-profiles.js", DATA / "expert-profiles-china.js",
            DATA / "expert-profiles-international.js", DATA / "landscape-data.js", DATA / "content-modules.js",
            DATA / "clinicaltrials-pipeline-cache.json",
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
            PipelineStep("build-community", py("buildCommunityData.py"), outputs=communityArtifactPaths(DATA)),
            PipelineStep("build-knowledge", py("build-knowledge-data.py"), outputs=[DATA / "knowledge-graph.js", DATA / "graphHealth.js"]),
            PipelineStep("build-china-author-network", py("buildChinaAuthorNetwork.py"), outputs=[DATA / "china-author-network.js"]),
            PipelineStep("build-curated-topics", py("build-curated-topic-data.py"), outputs=[DATA / "curated-topics.js"]),
            PipelineStep("build-wiki-coverage", py("buildWikiTopicCoverage.py"), outputs=[DATA / "wikiTopicCoverage.js"]),
        ])
    steps.extend([
        PipelineStep("build-landscape-insights", py("buildLandscapeInsights.py"), outputs=[DATA / "landscapeInsights.js"]),
        PipelineStep("build-backend-options", py("buildBackendOptions.py"), outputs=[DATA / "backendOptions.js"]),
        PipelineStep(
            "build-clinical-trials",
            py("build-clinical-trials-data.py"),
            outputs=[DATA / "clinical-trials-data.js", DATA / "clinicalTrialsSummary.js", DATA / "clinicaltrials-weekly-changes-snapshot.json"],
        ),
        PipelineStep("build-source-signals", py("build-source-signals.py"), outputs=[DATA / "source-signals.js"]),
        PipelineStep("generate-weekly-summary", py("generate-weekly-summary.py"), outputs=[DATA / "weekly-summary.md"]),
        PipelineStep("update-release-token", py("updateFrontendReleaseToken.py"), outputs=ACTIVE_HTML),
        PipelineStep("validate-public-contracts", py("validatePublicRelease.py")),
    ])
    if not args.skip_status:
        steps.append(PipelineStep("generate-pipeline-status", py("generate-pipeline-status.py"), outputs=[DATA / "pipeline-status.js"]))
    return steps


def public_artifacts() -> list[Path]:
    return publicArtifactPaths(DATA)


def validateReusedIngest(parser, mode: str, args) -> None:
    """禁止跳过抓取时静默复用未知或跨周 ingest。"""
    if mode not in {"authoritative-full", "rebuild-full"}:
        return
    reusesIngest = mode == "rebuild-full" or args.skip_fetch
    if not reusesIngest:
        return
    if not args.reuse_ingest:
        parser.error("重建或 --skip-fetch 必须显式提供 --reuse-ingest")
    ingestPath = DATA / "literature-ingest-latest.json"
    if not ingestPath.exists():
        parser.error("--reuse-ingest 需要 data/literature-ingest-latest.json")
    try:
        ingest = json.loads(ingestPath.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        parser.error("data/literature-ingest-latest.json 无法解析")
    today = datetime.now().date()
    weekStart = today - timedelta(days=today.weekday())
    if ingest.get("window_start") != weekStart.isoformat():
        parser.error(
            f"ingest window_start={ingest.get('window_start') or '-'} 不属于当前周 {weekStart.isoformat()}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MA-MG-HUB weekly data pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过 PubMed 增量抓取")
    parser.add_argument("--skip-llm", action="store_true", help="跳过文献语义增强")
    parser.add_argument("--skip-status", action="store_true", help="跳过管线状态生成")
    parser.add_argument("--skip-downstream", action="store_true", help="只执行抓取/富集/存储同步")
    parser.add_argument(
        "--mode",
        choices=("authoritative-full", "rebuild-full", "validate-only"),
        help="运行模式：完整周更、复用本周 ingest 的 full 重建或只读发布校验",
    )
    parser.add_argument("--local-full", action="store_true", help="兼容别名：等同 --mode authoritative-full")
    parser.add_argument("--reuse-ingest", action="store_true", help="显式允许复用当前自然周 ingest manifest")
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
    if args.local_full and args.mode and args.mode != "authoritative-full":
        parser.error("--local-full 不能与其他 --mode 组合")
    mode = pipelineMode(args, full_available)
    if mode in {"authoritative-full", "rebuild-full"} and not full_available:
        parser.error(f"--mode {mode} 需要 data/literature-full.json")
    validateReusedIngest(parser, mode, args)
    os.environ["MG_PIPELINE_RUN_ID"] = run_id
    steps = pipeline_steps(args, full_available=full_available)
    print(f"MA-MG-HUB weekly pipeline · mode={mode} · run-id={run_id}")
    runner = PipelineRunner(PROJECT, AUDIT_DIR, default_timeout=args.step_timeout)
    try:
        result = runner.run(steps, run_id=run_id, resume=args.resume, from_step=args.from_step)
    except PipelineFailure as exc:
        print(f"❌ required step {exc.step_id}: {exc}", file=sys.stderr)
        return exc.return_code
    publishEligible = mode in {"authoritative-full", "rebuild-full"} and not args.skip_downstream
    if publishEligible and result["status"] in {"success", "success_with_warnings"}:
        # 第一次清单供状态生成器核对；状态刷新后再生成最终清单，避免状态文件自引用哈希漂移。
        generate_release_manifest(result, public_artifacts(), DATA / "release-manifest.js", project=PROJECT)
        if not args.skip_status:
            statusResult = subprocess.run(py("generate-pipeline-status.py"), cwd=PROJECT, check=False)
            if statusResult.returncode != 0:
                print("❌ release consistency status refresh failed", file=sys.stderr)
                return statusResult.returncode
            generate_release_manifest(result, public_artifacts(), DATA / "release-manifest.js", project=PROJECT)
        finalCheck = subprocess.run(
            py("validatePublicRelease.py") + ["--require-release"],
            cwd=PROJECT,
            check=False,
        )
        if finalCheck.returncode != 0:
            print("❌ final public release validation failed", file=sys.stderr)
            return finalCheck.returncode
        print(f"✅ coherent release manifest: data/release-manifest.js · run-id={run_id}")
    else:
        print("ℹ️ partial/ingest-only run: release manifest not updated")
    print(f"✅ Pipeline finished with status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
