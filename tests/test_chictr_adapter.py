import csv
import json
from pathlib import Path

from scripts.common.clinical_registry import (
    build_clinical_pipeline_matrix,
    load_chictr_cache,
    normalize_chictr_record,
    refresh_chictr_cache,
)


ROOT = Path(__file__).resolve().parents[1]


def test_tracked_chictr_seed_contains_only_verified_public_fields():
    payload = load_chictr_cache(ROOT / "data" / "chictr-trials-cache.json")
    by_id = {item["registry_id"]: item for item in payload["records"]}

    assert payload["source"] == "ChiCTR official registry"
    assert payload["mode"] in {"cache", "manual"}
    assert set(by_id) == {
        "ChiCTR2500104662", "ChiCTR2600120351", "ChiCTR2600117375", "ChiCTR2500110600"
    }
    assert by_id["ChiCTR2500104662"]["status"] == "Not yet recruiting"
    assert by_id["ChiCTR2500104662"]["registered_date"] == "2025-06-20"
    assert by_id["ChiCTR2600120351"]["phase"] == "Unknown"
    assert by_id["ChiCTR2600117375"]["sponsor"] == ""
    assert all("contact" not in key.lower() for item in by_id.values() for key in item)
    assert all(item["official_url"].startswith("https://www.chictr.org.cn/") for item in by_id.values())


def test_manual_official_csv_refresh_is_deterministic_and_deduplicated(tmp_path):
    source = tmp_path / "official.csv"
    cache = tmp_path / "cache.json"
    rows = [
        {
            "registration_number": "ChiCTR9999999999",
            "title": "Myasthenia gravis registry study",
            "registered_date": "2026-07-01",
            "status": "Recruiting",
            "official_url": "https://www.chictr.org.cn/showprojEN.html?proj=1",
        },
        {
            "registration_number": "ChiCTR9999999999",
            "title": "Myasthenia gravis registry study updated",
            "registered_date": "2026-07-01",
            "status": "Recruiting",
            "official_url": "https://www.chictr.org.cn/showprojEN.html?proj=1",
        },
    ]
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    payload = refresh_chictr_cache(cache, input_path=source)
    saved = json.loads(cache.read_text(encoding="utf-8"))

    assert payload == saved
    assert saved["mode"] == "manual"
    assert saved["input_format"] == "csv"
    assert len(saved["records"]) == 1
    assert saved["records"][0]["title"].endswith("updated")


def test_failed_refresh_preserves_last_good_cache(tmp_path):
    cache = tmp_path / "cache.json"
    good = {
        "schema_version": "1.0",
        "source": "ChiCTR official registry",
        "mode": "cache",
        "records": [{"registry_id": "ChiCTR1", "title": "MG study"}],
    }
    cache.write_text(json.dumps(good), encoding="utf-8")
    before = cache.read_bytes()
    invalid = tmp_path / "bad.json"
    invalid.write_text("not json", encoding="utf-8")

    payload = refresh_chictr_cache(cache, input_path=invalid)

    assert cache.read_bytes() == before
    assert payload["records"] == good["records"]
    assert payload["mode"] == "cache"
    assert payload["warning"]


def test_chictr_unknown_fields_stay_unknown_or_blank():
    record = normalize_chictr_record({
        "registration_number": "ChiCTR1",
        "title": "Clinical study in myasthenia gravis",
        "status": "Recruiting",
    })
    assert record["phase"] == "Unknown"
    assert record["sponsor"] == ""
    assert record["institution"] == ""
    assert record["start_date"] == ""
    assert record["end_date"] == ""


def test_clinical_registry_matrix_normalization_is_importable_and_has_no_oxford_level():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT1", "briefTitle": "Batoclimab in generalized myasthenia gravis"},
            "statusModule": {"overallStatus": "RECRUITING", "lastUpdateSubmitDate": "2026-07-01"},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
            "conditionsModule": {"conditions": ["Myasthenia Gravis"]},
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Batoclimab"}]},
            "eligibilityModule": {},
        }
    }
    payload = build_clinical_pipeline_matrix({}, studies=[study], meta={"mode": "test"})
    assert payload["items"][0]["name"] == "Batoclimab"
    assert payload["items"][0]["key_trial"]["registry"] == "ClinicalTrials.gov"
    assert "evidence_level" not in payload["items"][0]["key_trial"]
