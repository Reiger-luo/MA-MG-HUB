"""可恢复、可审计并带步骤超时的通用管线执行器。"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import atomic_write_json, atomic_write_js_global, load_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class PipelineStep:
    id: str
    command: list[str]
    outputs: list[Path] = field(default_factory=list)
    optional: bool = False
    timeout: float | None = None


class PipelineFailure(RuntimeError):
    def __init__(self, step_id: str, return_code: int, message: str):
        super().__init__(message)
        self.step_id = step_id
        self.return_code = return_code


class PipelineRunner:
    def __init__(self, project: Path, audit_dir: Path, *, default_timeout: float = 900):
        self.project = Path(project).resolve()
        self.audit_dir = Path(audit_dir)
        self.default_timeout = default_timeout

    def _display_path(self, path: Path) -> str:
        resolved = path if path.is_absolute() else self.project / path
        try:
            return str(resolved.resolve().relative_to(self.project))
        except ValueError:
            return str(resolved.resolve())

    def _hash_outputs(self, step: PipelineStep) -> dict[str, str | None]:
        hashes = {}
        for raw in step.outputs:
            path = raw if raw.is_absolute() else self.project / raw
            hashes[self._display_path(raw)] = sha256_file(path) if path.is_file() else None
        return hashes

    def _resume_valid(self, step: PipelineStep, prior: dict[str, Any] | None) -> bool:
        if not prior or prior.get("status") not in {"success", "skipped_resume"} or not step.outputs:
            return False
        expected = prior.get("output_hashes") or {}
        if set(expected) != {self._display_path(path) for path in step.outputs}:
            return False
        return all(value and self._hash_outputs(step).get(key) == value for key, value in expected.items())

    def run(self, steps: list[PipelineStep], *, run_id: str, resume: bool = False, from_step: str | None = None):
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = self.audit_dir / f"{run_id}.json"
        previous = load_json(audit_path) if resume and audit_path.exists() else {}
        previous_by_id = {item.get("id"): item for item in previous.get("steps") or []}
        if from_step and from_step not in {step.id for step in steps}:
            raise ValueError(f"Unknown --from-step: {from_step}")
        started = previous.get("started_at") if resume else None
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "started_at": started or _now(),
            "completed_at": None,
            "status": "running",
            "default_timeout_seconds": self.default_timeout,
            "steps": [],
        }
        atomic_write_json(audit_path, payload)
        warnings = 0
        partial = False
        reached_from = from_step is None
        for step in steps:
            if not reached_from:
                if step.id != from_step:
                    prior = previous_by_id.get(step.id)
                    if resume and self._resume_valid(step, prior):
                        record = dict(prior)
                        record.update({"status": "skipped_resume", "error": None})
                    else:
                        partial = True
                        record = {
                            "id": step.id,
                            "command": step.command,
                            "started_at": None,
                            "completed_at": None,
                            "duration_seconds": 0,
                            "status": "skipped_from_step",
                            "optional": step.optional,
                            "error": None,
                            "return_code": None,
                            "declared_outputs": [self._display_path(path) for path in step.outputs],
                            "output_hashes": {},
                        }
                    payload["steps"].append(record)
                    atomic_write_json(audit_path, payload)
                    continue
                reached_from = True
            prior = previous_by_id.get(step.id)
            declared_outputs = [self._display_path(path) for path in step.outputs]
            if resume and self._resume_valid(step, prior):
                record = dict(prior)
                record.update({
                    "id": step.id,
                    "command": step.command,
                    "optional": step.optional,
                    "declared_outputs": declared_outputs,
                    "status": "skipped_resume",
                    "error": None,
                })
                payload["steps"].append(record)
                atomic_write_json(audit_path, payload)
                continue

            started_at = _now()
            monotonic_start = time.monotonic()
            timeout = step.timeout if step.timeout is not None else self.default_timeout
            record = {
                "id": step.id,
                "command": step.command,
                "started_at": started_at,
                "completed_at": None,
                "duration_seconds": None,
                "status": "running",
                "optional": step.optional,
                "error": None,
                "return_code": None,
                "declared_outputs": declared_outputs,
                "output_hashes": {},
            }
            payload["steps"].append(record)
            atomic_write_json(audit_path, payload)
            try:
                result = subprocess.run(step.command, cwd=self.project, timeout=timeout)
                record["return_code"] = result.returncode
                if result.returncode != 0:
                    record["status"] = "warning" if step.optional else "failed"
                    record["error"] = f"command exited with code {result.returncode}"
                else:
                    record["status"] = "success"
                    record["output_hashes"] = self._hash_outputs(step)
            except subprocess.TimeoutExpired:
                record["return_code"] = 124
                record["status"] = "warning" if step.optional else "timeout"
                record["error"] = f"step exceeded timeout of {timeout} seconds"
            finally:
                record["completed_at"] = _now()
                record["duration_seconds"] = round(time.monotonic() - monotonic_start, 3)
                atomic_write_json(audit_path, payload)

            if record["status"] == "warning":
                warnings += 1
                continue
            if record["status"] in {"failed", "timeout"}:
                payload["status"] = "failed"
                payload["completed_at"] = _now()
                atomic_write_json(audit_path, payload)
                raise PipelineFailure(step.id, record["return_code"], record["error"])

        payload["completed_at"] = _now()
        payload["status"] = "partial" if partial else "success_with_warnings" if warnings else "success"
        atomic_write_json(audit_path, payload)
        return payload


def generate_release_manifest(audit_payload, artifacts, target, *, project: Path):
    if audit_payload.get("status") not in {"success", "success_with_warnings"}:
        raise ValueError("all required pipeline steps must succeed before release manifest generation")
    entries = []
    for raw in artifacts:
        path = raw if Path(raw).is_absolute() else project / raw
        if not path.is_file():
            continue
        entries.append({
            "path": str(path.resolve().relative_to(project.resolve())),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        })
    payload = {
        "schema_version": "1.0",
        "run_id": audit_payload.get("run_id"),
        "released_at": audit_payload.get("completed_at") or _now(),
        "pipeline_status": audit_payload.get("status"),
        "artifacts": entries,
    }
    atomic_write_js_global(target, "MG_RELEASE_MANIFEST", payload)
    return payload
