import importlib.util
import sys
from pathlib import Path

from scripts.common.io import load_js_global


PROJECT = Path(__file__).resolve().parents[1]


def loadPipelineModule():
    path = PROJECT / "scripts" / "generate-pipeline-status.py"
    scriptsDir = str(PROJECT / "scripts")
    if scriptsDir not in sys.path:
        sys.path.insert(0, scriptsDir)
    spec = importlib.util.spec_from_file_location("generate_pipeline_status", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_status_separates_public_rolling_and_semantic_full_counts():
    module = loadPipelineModule()
    status = module.buildStatus()
    storage = status["storage"]

    recent = load_js_global(PROJECT / "data" / "literature-recent.js", "MG_LITERATURE_DATA")
    fullIndex = load_js_global(PROJECT / "data" / "literature-full-index.js", "MG_LITERATURE_FULL_INDEX")
    communityIndex = load_js_global(PROJECT / "data" / "communityAssignmentIndex.js", "MG_COMMUNITY_ASSIGNMENT_INDEX")

    assert storage["public_rolling_count"] == len(recent)
    assert storage["recent_count"] == len(recent)
    assert storage["semantic_full_count"] == fullIndex["item_count"]
    assert storage["semantic_full_count"] == communityIndex["item_count"]
    assert storage["full_count"] == storage["semantic_full_count"]
    assert storage["active_recent_source"] in {"literature-recent.js", "communityAssignmentsRecent.js"}
    activeRecent = next(item for item in storage["recent_sources"] if item["id"] == storage["active_recent_source"])
    assert storage["active_recent_count"] == activeRecent["count"]

    checkById = {item["id"]: item for item in storage["count_checks"]}
    assert checkById["semanticFullConsistency"]["status"] == "ok"
    assert checkById["activeRecentSource"]["status"] == "ok"


def test_pipeline_status_counts_expert_and_community_shards():
    module = loadPipelineModule()
    status = module.buildStatus()
    artifacts = {item["id"]: item for item in status["artifacts"]}

    expertManifest = load_js_global(PROJECT / "data" / "expert-profiles.js", "MG_EXPERT_PROFILES")
    expertShardTotal = sum(item["count"] for item in expertManifest["shards"])
    expertArtifact = artifacts["expert-profiles.js"]
    assert expertArtifact["count"] == expertShardTotal
    assert expertArtifact["shard_count"] == len(expertManifest["shards"])
    assert expertArtifact["updated_at"] == expertManifest["generated_at"]

    communityIndex = load_js_global(PROJECT / "data" / "communityAssignmentIndex.js", "MG_COMMUNITY_ASSIGNMENT_INDEX")
    communityShardTotal = sum(item["item_count"] for item in communityIndex["shards"])
    communityArtifact = artifacts["communityAssignmentIndex.js"]
    assert communityArtifact["count"] == communityIndex["item_count"]
    communityArtifactShardTotal = communityArtifact["shard_total_count"]
    assert communityArtifactShardTotal == communityShardTotal
    assert communityArtifact["updated_at"] == communityIndex["generated_at"]


def test_release_consistency_detects_hash_drift_and_unlisted_artifacts(tmp_path):
    module = loadPipelineModule()
    artifact = tmp_path / "artifact.js"
    artifact.write_text("window.TEST = {};\n", encoding="utf-8")
    manifest = {
        "run_id": "test-run",
        "released_at": "2026-08-01T00:00:00+00:00",
        "pipeline_status": "success",
        "artifacts": [{"path": "data/artifact.js", "sha256": module.sha256_file(artifact)}],
    }

    consistent = module.releaseConsistency(manifest, dataDir=tmp_path)
    assert consistent["status"] == "ok"
    assert consistent["mismatched"] == []

    artifact.write_text("window.TEST = {changed: true};\n", encoding="utf-8")
    (tmp_path / "new.js").write_text("window.NEW = {};\n", encoding="utf-8")
    drifted = module.releaseConsistency(manifest, dataDir=tmp_path)
    assert drifted["status"] == "warning"
    assert drifted["mismatched"] == ["artifact.js"]
    assert drifted["unlisted"] == ["new.js"]
