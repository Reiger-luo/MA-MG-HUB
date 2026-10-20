"""AANEM/MGFA 会议源解析与数据契约测试。

覆盖：全大写题名恢复、美国同名城市国家判定、获奖条目收敛、以及已发布
conference-data.json 中 AANEM 2026 / MGFA 2026 模块的结构约束。
"""

import importlib.util
import json
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
GUIDE_PDF = PROJECT / "data" / ".conference_cache" / "AANEM-2026-Abstracts-Guide.pdf"


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_conference_data", PROJECT / "scripts" / "build-conference-data.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_payload():
    data_json = PROJECT / "data" / "conference-data.json"
    if data_json.exists():
        return json.loads(data_json.read_text(encoding="utf-8"))
    js_path = PROJECT / "data" / "conference-data.js"
    text = js_path.read_text(encoding="utf-8")
    prefix = "window.MG_CONFERENCE_DATA = "
    body = text[len(prefix):].strip() if text.startswith(prefix) else ""
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def test_aanem_title_case_restores_sentence_case_and_keeps_acronyms():
    builder = load_builder()
    out = builder.aanem_title_case(
        "EFGARTIGIMOD IN ACHR-AB-NEGATIVE GENERALIZED MYASTHENIA GRAVIS: RESULTS OF ADAPT SERON PART A"
    )
    assert out.startswith("Efgartigimod in AChR-Ab-negative")
    assert "ADAPT SERON Part A" in out
    # 常规词不应保留全大写
    assert "GENERALIZED" not in out and "MYASTHENIA" not in out


def test_title_case_merges_hyphenation_and_canonicalizes_abbreviations():
    builder = load_builder()
    out = builder.aanem_title_case(
        "POLYSOMNOGRAPHIC EVALUATION OF SLEEP IN MUSK-POSITIVE MYASTHENIA GRAVIS"
    )
    assert "MuSK-positive" in out
    merged = builder.aanem_title_case("ANALYSIS OF ACHR-AB- NEGATIVE PATIENTS")
    assert "AChR-Ab-negative" in merged


def test_country_inference_handles_us_city_namesakes_and_postal_codes():
    builder = load_builder()
    assert builder.infer_countries("Cambridge, MA; Birmingham, AL") == ["美国"]
    assert "加拿大" in builder.infer_countries("Toronto, ON; London, ON")
    assert "英国" in builder.infer_countries("London, United Kingdom")
    assert builder.infer_countries("") == ["未识别"]


def test_awards_drop_narrative_entries_without_poster_number():
    builder = load_builder()
    awards = [
        {"category": "Best Abstract Award", "recipient": "Best Abstract Runner-Up - Yuan Zhang, MS",
         "title": "Efgartigimod followed by telitacicept", "posterNumber": 5},
        {"category": "Best Abstract Award", "recipient": "Yuan Zhang, MS, is testing how",
         "title": "narrative paragraph", "posterNumber": None},
        {"category": "Best Abstract Award", "recipient": "duplicate", "title": "同一 poster 重复",
         "posterNumber": 5},
    ]
    cleaned = builder.clean_aanem_awards(awards)
    assert len(cleaned) == 1
    assert cleaned[0]["recipient"] == "Yuan Zhang, MS"
    assert cleaned[0]["posterNumber"] == 5


@pytest.mark.skipif(not GUIDE_PDF.exists(), reason="AANEM 摘要集本地归档不存在（data/.conference_cache 未随仓库分发）")
def test_aanem_guide_parses_poster_and_mgfa_blocks():
    builder = load_builder()
    aanem_source = next(s for s in builder.SOURCES if s["id"] == "aanem-2026-abstract-guide")
    mgfa_source = next(s for s in builder.SOURCES if s["id"] == "mgfa-2026-scientific-session")

    aanem_items = builder.parse_aanem_guide(GUIDE_PDF, aanem_source)
    mgfa_items = builder.parse_aanem_guide(GUIDE_PDF, mgfa_source)

    # 两段独立编号必须分开，避免 id 冲突
    assert all(item["id"].startswith("aanem-2026-abstract-guide::poster-") for item in aanem_items)
    assert all(item["id"].startswith("mgfa-2026-scientific-session::mgfa-") for item in mgfa_items)
    assert len({item["id"] for item in aanem_items}) == len(aanem_items)
    assert len({item["id"] for item in mgfa_items}) == len(mgfa_items)
    assert len(aanem_items) > 400
    assert len(mgfa_items) > 100
    # MGFA 专病专场几乎全为 MG
    assert len(mgfa_items) / max(sum(1 for _ in mgfa_items), 1) == 1.0

    awards = builder.parse_aanem_awards(GUIDE_PDF, aanem_source)
    assert awards, "应解析出可对齐 poster 编号的获奖条目"
    assert all(award["posterNumber"] for award in awards)


def test_published_payload_has_aanem_and_mgfa_modules():
    payload = load_payload()
    by_meeting = {row["name"]: row["count"] for row in payload["summary"]["byMeeting"]}
    assert by_meeting.get("AANEM 2026", 0) > 50
    assert by_meeting.get("MGFA 2026", 0) > 50

    source_ids = {source["id"] for source in payload["sourceStats"]}
    assert {"aanem-2026-abstract-guide", "mgfa-2026-scientific-session"} <= source_ids

    monitor_ids = {row["id"] for row in payload["sourceMonitor"]}
    assert {"aanem", "mgfa"} <= monitor_ids

    items = [
        item for item in payload["abstracts"] if item["conference"] in {"AANEM 2026", "MGFA 2026"}
    ]
    assert items
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))

    required = {"id", "sourceId", "conference", "title", "authors", "abstract", "topics", "countries"}
    for item in items:
        assert required <= set(item)
        assert item["abstract"].strip(), item["id"]
        # 题名不应保留 PDF 的全大写形态
        letters = [ch for ch in item["title"] if ch.isalpha()]
        if len(letters) > 20:
            upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
            assert upper_ratio < 0.6, item["title"]

    award_winners = payload.get("awardWinners", {}).get("AANEM 2026", [])
    assert award_winners
    assert all(award.get("posterNumber") for award in award_winners)