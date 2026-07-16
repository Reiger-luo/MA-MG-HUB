import json
import sys
from pathlib import Path

import pytest

from scripts.common.io import load_js_global
from scripts.common.pipeline_runner import (
    PipelineFailure,
    PipelineRunner,
    PipelineStep,
    generate_release_manifest,
)


def command(code):
    return [sys.executable, "-c", code]


def audit(tmp_path, run_id):
    return json.loads((tmp_path / "audit" / f"{run_id}.json").read_text(encoding="utf-8"))


def test_runner_records_success_and_output_hash(tmp_path):
    output = tmp_path / "out.txt"
    runner = PipelineRunner(tmp_path, tmp_path / "audit", default_timeout=2)
    steps = [PipelineStep("write", command(f"from pathlib import Path; Path({str(output)!r}).write_text('ok')"), outputs=[output])]

    result = runner.run(steps, run_id="success")

    assert result["status"] == "success"
    step = audit(tmp_path, "success")["steps"][0]
    assert step["status"] == "success"
    assert step["return_code"] == 0
    assert step["duration_seconds"] >= 0
    assert step["output_hashes"][str(output.relative_to(tmp_path))]


def test_required_failure_stops_and_preserves_return_code(tmp_path):
    runner = PipelineRunner(tmp_path, tmp_path / "audit", default_timeout=2)
    with pytest.raises(PipelineFailure) as exc:
        runner.run([
            PipelineStep("fail", command("raise SystemExit(7)")),
            PipelineStep("later", command("raise SystemExit(0)")),
        ], run_id="failure")
    assert exc.value.return_code == 7
    payload = audit(tmp_path, "failure")
    assert payload["status"] == "failed"
    assert [item["id"] for item in payload["steps"]] == ["fail"]


def test_timeout_is_hard_failure_for_required_step(tmp_path):
    runner = PipelineRunner(tmp_path, tmp_path / "audit", default_timeout=0.05)
    with pytest.raises(PipelineFailure) as exc:
        runner.run([PipelineStep("slow", command("import time; time.sleep(1)"))], run_id="timeout")
    assert exc.value.return_code == 124
    assert audit(tmp_path, "timeout")["steps"][0]["status"] == "timeout"


def test_optional_failure_and_timeout_are_warnings_and_pipeline_continues(tmp_path):
    output = tmp_path / "done.txt"
    runner = PipelineRunner(tmp_path, tmp_path / "audit", default_timeout=0.05)
    result = runner.run([
        PipelineStep("optional-fail", command("raise SystemExit(9)"), optional=True),
        PipelineStep("optional-timeout", command("import time; time.sleep(1)"), optional=True),
        PipelineStep("required", command(f"from pathlib import Path; Path({str(output)!r}).write_text('done')"), outputs=[output], timeout=2),
    ], run_id="warnings")
    assert result["status"] == "success_with_warnings"
    assert [item["status"] for item in audit(tmp_path, "warnings")["steps"]] == ["warning", "warning", "success"]


def test_resume_skips_valid_success_but_reruns_stale_hash(tmp_path):
    output = tmp_path / "counter.txt"
    code = (
        "from pathlib import Path; "
        f"p=Path({str(output)!r}); v=p.read_text() if p.exists() else ''; n=int(v) if v.isdigit() else 0; p.write_text(str(n+1))"
    )
    runner = PipelineRunner(tmp_path, tmp_path / "audit", default_timeout=2)
    steps = [PipelineStep("counter", command(code), outputs=[output])]
    runner.run(steps, run_id="resume")
    runner.run(steps, run_id="resume", resume=True)
    assert output.read_text() == "1"
    assert audit(tmp_path, "resume")["steps"][0]["status"] == "skipped_resume"

    output.write_text("stale", encoding="utf-8")
    runner.run(steps, run_id="resume", resume=True)
    assert output.read_text() == "1"
    assert audit(tmp_path, "resume")["steps"][0]["status"] == "success"


def test_release_manifest_written_only_for_successful_required_run(tmp_path):
    artifact = tmp_path / "data" / "artifact.js"
    artifact.parent.mkdir()
    artifact.write_text("window.X = {};", encoding="utf-8")
    audit_payload = {"run_id": "coherent", "status": "success", "steps": []}
    target = tmp_path / "data" / "release-manifest.js"

    payload = generate_release_manifest(audit_payload, [artifact], target, project=tmp_path)
    loaded = load_js_global(target, "MG_RELEASE_MANIFEST")
    assert loaded == payload
    assert loaded["run_id"] == "coherent"
    assert loaded["artifacts"][0]["sha256"]

    with pytest.raises(ValueError, match="required"):
        generate_release_manifest({"run_id": "bad", "status": "failed", "steps": []}, [artifact], target, project=tmp_path)
