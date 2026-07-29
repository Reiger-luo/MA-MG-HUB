import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.common.chictr_live import (
    extract_project_ids,
    extract_xml_url,
    is_refresh_due,
    parse_xml_record,
    refresh_chictr_live,
)
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
    assert payload.get("mode", "cache") in {"cache", "manual", "live"}
    # Full scrape: 97 MG-related trials (was 4 seed records)
    assert len(by_id) >= 90, f"Expected >=90 ChiCTR records, got {len(by_id)}"
    # Original seed records must still be present
    seed_ids = {"ChiCTR2500104662", "ChiCTR2600120351", "ChiCTR2600117375", "ChiCTR2500110600"}
    assert seed_ids.issubset(set(by_id)), f"Missing seed IDs: {seed_ids - set(by_id)}"
    # Every record must have registry_id and a chictr.org.cn URL
    assert all(item["registry_id"].startswith("ChiCTR") for item in by_id.values())
    assert all(
        item.get("url", "").startswith("https://www.chictr.org.cn/")
        or item.get("official_url", "").startswith("https://www.chictr.org.cn/")
        for item in by_id.values()
    )


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


def test_chictr_monthly_due_gate_uses_last_successful_verification():
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)

    assert is_refresh_due(
        {"last_verified": "2026-07-27T08:57:44+08:00"},
        interval_days=28,
        now=now,
    ) is False
    assert is_refresh_due(
        {"last_verified": "2026-06-20T08:57:44+08:00"},
        interval_days=28,
        now=now,
    ) is True
    assert is_refresh_due({}, interval_days=28, now=now) is True


def test_chictr_official_result_and_xml_links_are_extracted():
    page = """
    <table>
      <tr><td><a href="/showproj.html?proj=101">ChiCTR1</a></td></tr>
      <tr><td><a href="showprojEN.html?proj=202">ChiCTR2</a></td></tr>
      <tr><td><a href="/showproj.html?proj=101">duplicate</a></td></tr>
    </table>
    """
    detail = '<a href="/bin/chictr/DownloadXml?path=encrypted%2Bvalue">下载XML文档</a>'

    assert extract_project_ids(page) == ["101", "202"]
    assert extract_xml_url(detail) == (
        "https://www.chictr.org.cn/bin/chictr/DownloadXml?path=encrypted%2Bvalue"
    )


def test_chictr_xml_parser_builds_public_cache_record():
    xml = """
    <trial>
      <trial_id>ChiCTR2600129999</trial_id>
      <date_registration>2026-07-28</date_registration>
      <public_title>Myasthenia gravis study</public_title>
      <scientific_title>Scientific MG study</scientific_title>
      <primary_sponsor>Example Hospital</primary_sponsor>
      <recruitment_status>Recruiting</recruitment_status>
      <phase>3</phase>
      <i_freetext>Experimental group:Efgartigimod;</i_freetext>
    </trial>
    """

    record = parse_xml_record(xml, proj_id="999")

    assert record["registry_id"] == "ChiCTR2600129999"
    assert record["title"] == "Scientific MG study"
    assert record["registered_date"] == "2026-07-28"
    assert record["url"].endswith("showproj.html?proj=999")


def test_failed_chictr_live_refresh_preserves_last_good_cache(tmp_path):
    class BlockedClient:
        def get_text(self, _url, *, params=None):
            raise RuntimeError("WAF blocked")

    cache = tmp_path / "cache.json"
    cached = {
        "schema_version": "1.0",
        "source": "ChiCTR official registry",
        "last_verified": "2026-06-01T00:00:00+00:00",
        "records": [{"registry_id": "ChiCTR1", "title": "MG study"}],
    }
    cache.write_text(json.dumps(cached), encoding="utf-8")
    before = cache.read_bytes()

    payload = refresh_chictr_live(
        cache,
        force=True,
        client=BlockedClient(),
        now=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert cache.read_bytes() == before
    assert payload["refresh_status"] == "failed"
    assert payload["records"] == cached["records"]


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
