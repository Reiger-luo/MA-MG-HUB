"""三项新增能力的契约测试。

1. 情报中心临床试验矩阵把戈鲁利单抗独立成行（ALXN1720 不再误并 Ravulizumab）。
2. 重点药物 II/III 期文献进入「领域重大事件」信息流，且排除综述/评论/机制研究。
3. 指南/共识周更 link：识别 German-Austrian 专家共识，并同步到两个页面。
"""
import json
import re
from pathlib import Path

from scripts.common.guideline_consensus import (
    isGuidelineConsensus,
    syncGuidelineCacheFromLiterature,
)
from scripts.common.key_drugs import (
    buildWatchlist,
    classifyTrialPhase,
    selectKeyDrugTrialPublications,
)
from scripts.common.source_channels import build_source_signals

PROJECT = Path(__file__).resolve().parents[1]

GERMAN_TITLE = (
    "Practical Guidance on Initiating and Switching Targeted Immunotherapies in "
    "Generalised Myasthenia Gravis: A German-Austrian Expert Opinion Paper."
)
PREVAIL_TITLE = (
    "Efficacy and Safety of Gefurulimab in Generalized Myasthenia Gravis: "
    "The PREVAIL Phase 3 Randomized Clinical Trial."
)


def test_drug_alias_corrections_and_geforulimab_pipeline_row():
    source = (PROJECT / "scripts" / "build-clinical-trials-data.py").read_text(encoding="utf-8")
    assert '"alxn1720": "Gefurulimab (戈鲁利单抗)"' in source
    assert '"m281": "Nipocalimab (尼卡利单抗)"' in source

    text = (PROJECT / "data" / "clinical-trials-data.js").read_text(encoding="utf-8")
    payload = json.loads(text[re.search(r"window\.MG_CLINICAL_TRIALS_DATA\s*=\s*", text).end():].strip().rstrip(";"))
    rows = {row["name"]: row for row in payload["pipeline_matrix"]}
    gefurulimab = next(row for name, row in rows.items() if "Gefurulimab" in name)
    ids = {trial["registry_id"] for trial in gefurulimab["trials"]}
    assert {"NCT05556096", "NCT06607627", "CTR20232711"}.issubset(ids)
    assert gefurulimab["highest_phase_label"] == "Phase 3"
    ravulizumab = rows["Ravulizumab (瑞利珠单抗)"]
    assert "NCT05556096" not in {trial["registry_id"] for trial in ravulizumab["trials"]}


def test_key_drug_phase_rules_accept_trials_and_reject_non_trials():
    watchlist = buildWatchlist({
        "all_competitive_matrix": [{"name": "Gefurulimab"}],
        "clinical_pipeline_matrix": [{"name": "IMVT-1402"}, {"name": "Pozelimab/Cemdisiran"}],
    })
    assert "Gefurulimab" in watchlist and "IMVT-1402" in watchlist

    assert classifyTrialPhase({"title": PREVAIL_TITLE, "pub_types": ["Journal Article"]}) == "III期"
    assert classifyTrialPhase({
        "title": "Efficacy and safety of cemdisiran siRNA in myasthenia gravis (NIMBLE): "
                 "a double-blind, randomised, placebo-controlled, phase 3 trial.",
        "pub_types": ["Journal Article"],
    }) == "III期"
    # 摘要里提到既往 phase 3 试验的综述与机制研究不得混入。
    for title in (
        "Efgartigimod for generalized myasthenia gravis: a comprehensive review of clinical evidence",
        "Pathogenic properties of myasthenia gravis AChR autoantibodies associate with clinical response",
        "Comparative Efficacy of Zilucoplan Versus Intravenous Immunoglobulin in generalized myasthenia gravis",
        "Clinical effectiveness of efgartigimod in routine care: a retrospective cohort study",
    ):
        assert classifyTrialPhase({
            "title": title,
            "pub_types": ["Journal Article"],
            "abstract": "We reviewed the phase 3 ADAPT trial of efgartigimod in myasthenia gravis.",
        }) == ""

    selected = selectKeyDrugTrialPublications([
        {"pmid": "42507440", "title": PREVAIL_TITLE, "entry_date": "2026/07/27 11:35"},
        {"pmid": "90000001", "title": "A comprehensive review of phase 3 efgartigimod evidence",
         "pub_types": ["Journal Article"], "entry_date": "2026/08/01"},
        {"pmid": "90000002", "title": "Unrelated phase 3 trial in another disease",
         "pub_types": ["Journal Article"], "entry_date": "2026/09/01"},
    ], watchlist)
    assert [item["pmid"] for item in selected] == ["42507440"]
    assert selected[0]["phase_label"] == "III期"
    assert "Gefurulimab" in selected[0]["drugs"]


def test_guideline_detection_covers_expert_guidance_without_overmatching():
    assert isGuidelineConsensus({
        "title": GERMAN_TITLE,
        "study_types": ["Single Arm"],
        "pub_types": ["Journal Article"],
    }) is True
    assert isGuidelineConsensus({
        "title": PREVAIL_TITLE,
        "study_types": ["RCT"],
        "pub_types": ["Journal Article"],
    }) is False
    assert isGuidelineConsensus({
        "title": "Refinement of a rat myasthenia gravis model: an update to the guidelines",
        "study_types": ["Guideline/Consensus"],
        "pub_types": ["Journal Article"],
    }) is False


def test_guideline_cache_sync_is_idempotent(tmp_path):
    cache = tmp_path / "guideline-consensus-cache.json"
    record = {
        "pmid": "42717567",
        "title": GERMAN_TITLE,
        "abstract": "Consensus recommendations for myasthenia gravis targeted immunotherapy.",
        "entry_date": "2026/09/10 05:04",
        "study_types": ["Single Arm"],
    }
    first, counters = syncGuidelineCacheFromLiterature(cache, [record])
    assert counters == {"scanned": 1, "matched": 1, "cache_total": 1}
    assert first["records"][0]["pmid"] == "42717567"
    second, _ = syncGuidelineCacheFromLiterature(cache, [record])
    assert second == first
    # 空输入只保留 last-good，不清空缓存。
    third, _ = syncGuidelineCacheFromLiterature(cache, [])
    assert third == first


def test_source_signals_exposes_both_new_channels(tmp_path):
    recent = tmp_path / "literature-recent.js"
    recent.write_text(
        "window.MG_LITERATURE_DATA = " + json.dumps([
            {"pmid": "42507440", "title": PREVAIL_TITLE, "entry_date": "2026/07/27 11:35",
             "pub_types": ["Journal Article"]},
        ], ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    landscape = tmp_path / "landscape-data.js"
    landscape.write_text(
        'window.MG_LANDSCAPE_DATA = {"all_competitive_matrix":[{"name":"Gefurulimab"}]};\n',
        encoding="utf-8",
    )
    guideline = tmp_path / "guideline-consensus-cache.json"
    guideline.write_text(json.dumps({
        "records": [{"pmid": "42717567", "title": GERMAN_TITLE,
                     "entry_date": "2026/09/10 05:04", "journal": "Eur J Neurol"}],
    }, ensure_ascii=False), encoding="utf-8")

    payload = build_source_signals(
        literature_signals_path=tmp_path / "missing-signals.js",
        guideline_cache_path=guideline,
        regulatory_path=tmp_path / "missing.json",
        clinicaltrials_path=tmp_path / "missing.json",
        chictr_path=tmp_path / "missing.json",
        china_drug_trials_path=tmp_path / "missing.json",
        conference_path=tmp_path / "missing.json",
        literature_recent_path=recent,
        landscape_data_path=landscape,
    )
    by_id = {channel["id"]: channel for channel in payload["channels"]}
    assert [item["id"] for item in by_id["keyDrugTrialPublications"]["items"]] == ["42507440"]
    assert by_id["keyDrugTrialPublications"]["watchlist_count"] > 0
    sync = by_id["guidelineConsensus"]["sync"]
    assert sync["hub"] == "data/guideline-consensus-cache.json"
    assert {view["path"] for view in sync["linked_views"]} == {
        "pages/literature.html", "pages/landscape.html",
    }
    assert by_id["guidelineConsensus"]["recent_items"][0]["id"] == "42717567"


def test_weekly_pipeline_wires_guideline_sync_before_channel_builders():
    source = (PROJECT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    assert source.count('"sync-guideline-consensus"') == 2
    assert source.index('"sync-guideline-consensus"') < source.index('"build-frontend"')
    assert source.index('"sync-guideline-consensus"') < source.index('"build-source-signals"')
    builder = (PROJECT / "scripts" / "build-source-signals.py").read_text(encoding="utf-8")
    assert "literature_recent_path" in builder and "landscape_data_path" in builder


def test_both_pages_consume_the_shared_channel():
    literature_html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    assert "II/III期重点药物文献" in literature_html
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert "keyDrugTrialPublications: 'II/III期文献'" in literature_js

    landscape_html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    assert 'id="guidelineSyncList"' in landscape_html
    assert "领域重大事件" not in landscape_html
    assert re.search(r'<script src="[^"]*source-signals\.js', landscape_html) is None
    landscape_js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    assert "renderGuidelineSync" in landscape_js
    assert "loadGuidelineSyncModule" in landscape_js
    assert "guidelineConsensus" in landscape_js
