import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "filter-mg-core-literature.py"
    spec = importlib.util.spec_from_file_location("filter_mg_core_literature", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    return [
        {"pmid": "mg", "title": "Generalized myasthenia gravis trial", "evidence_level": "II"},
        {
            "pmid": "fp",
            "title": "Titin expression in gastrointestinal malignancy",
            "abstract": "Myasthenia gravis is mentioned as background.",
            "evidence_level": "III",
        },
    ]


def test_filter_default_dry_run_does_not_mutate_or_archive(tmp_path):
    module = load_module()
    full = tmp_path / "literature-full.json"
    archive = tmp_path / "archive"
    full.write_text(json.dumps(records()), encoding="utf-8")
    before = full.read_bytes()

    result = module.filter_file(full, archive, apply=False)

    assert result["status"] == "dry_run"
    assert result["excluded_count"] == 1
    assert full.read_bytes() == before
    assert not archive.exists()


def test_filter_apply_is_atomic_archives_full_excluded_records_and_is_idempotent(tmp_path):
    module = load_module()
    full = tmp_path / "literature-full.json"
    archive = tmp_path / "archive"
    full.write_text(json.dumps(records()), encoding="utf-8")

    first = module.filter_file(full, archive, apply=True)
    saved = json.loads(full.read_text(encoding="utf-8"))
    archive_payload = json.loads(Path(first["archive_path"]).read_text(encoding="utf-8"))
    second = module.filter_file(full, archive, apply=True)

    assert [item["pmid"] for item in saved] == ["mg"]
    assert archive_payload["source_sha256"]
    assert archive_payload["excluded_count"] == 1
    assert archive_payload["records"][0]["pmid"] == "fp"
    assert archive_payload["reason_counts"]
    assert second["excluded_count"] == 0
    assert second["archive_path"] is None


def test_filter_is_safe_when_full_is_absent(tmp_path):
    module = load_module()
    result = module.filter_file(tmp_path / "missing.json", tmp_path / "archive", apply=True)
    assert result == {"status": "absent", "input_count": 0, "excluded_count": 0, "archive_path": None}
    assert not (tmp_path / "archive").exists()
