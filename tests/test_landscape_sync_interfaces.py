"""三项新增能力的契约测试。

1. 情报中心临床试验矩阵把戈鲁利单抗独立成行（ALXN1720 不再误并 Ravulizumab）。
2. 重点药物 II/III 期文献进入「领域重大事件」信息流，且排除综述/评论/机制研究。
3. 指南/共识周更 link：识别 German-Austrian 专家共识，并联动刷新三个既有板块。
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
    assert sync["refresh_step"] == "scripts/refresh-guideline-views.py"
    assert {view["view"] for view in sync["linked_views"]} == {
        "中外指南共识差异", "诊疗现状", "领域重大事件",
    }
    # 独立展示面板已删除，不再输出面板专用字段
    assert "recent_items" not in by_id["guidelineConsensus"]


def test_weekly_pipeline_wires_guideline_sync_before_channel_builders():
    source = (PROJECT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    assert source.count('"sync-guideline-consensus"') == 2
    assert source.count('"refresh-guideline-views"') == 2
    assert source.index('"sync-guideline-consensus"') < source.index('"refresh-guideline-views"')
    assert source.index('"refresh-guideline-views"') < source.index('"build-frontend"')
    builder = (PROJECT / "scripts" / "build-source-signals.py").read_text(encoding="utf-8")
    assert "literature_recent_path" in builder and "landscape_data_path" in builder


def test_guideline_link_targets_three_existing_views():
    literature_html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    assert "II/III期重点药物文献" in literature_html
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert "keyDrugTrialPublications: 'II/III期文献'" in literature_js

    landscape_html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    # 独立「周更指南/共识同步」面板已删除，差异面板改为周更联动口径
    assert "guidelineSyncList" not in landscape_html
    assert "周更指南 / 共识同步" not in landscape_html
    assert "新指南周更联动" in landscape_html
    assert "领域重大事件" not in landscape_html
    assert re.search(r'<script src="[^"]*source-signals\.js', landscape_html) is None
    landscape_js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    assert "renderGuidelineSync" not in landscape_js
    assert "loadGuidelineSyncModule" not in landscape_js
    assert "周更发现新指南后联动刷新" in landscape_js


def parseJsGlobal(name):
    text = (PROJECT / "data" / name).read_text(encoding="utf-8")
    return json.loads(text[text.index("=") + 1:].strip().rstrip(";").strip())


def test_german_consensus_refreshes_all_three_artifacts():
    """本次德国共识全文应同时进入差异语料、诊疗现状与领域重大事件。"""
    divergence = json.loads(
        (PROJECT / "data" / "guideline-divergence.json").read_text(encoding="utf-8")
    )
    assert divergence["corpus_count"]["total"] >= 35
    assert any(item["key"] == "g35" for item in divergence["corpus"])
    check = divergence["quote_check"]
    assert check["total"] == check["verified"]
    gd01 = next(item for item in divergence["divergences"] if item["id"] == "gd01")
    assert "德奥" in gd01["international"]
    assert all(e["quote_verified"] for e in gd01["evidence"] if e["doc"] == "g35")

    landscape = parseJsGlobal("landscape-data.js")
    view = landscape["china_landscape"]["guideline_divergence"]
    assert view["status"] == "ready" and len(view["corpus"]) >= 35
    assert "德奥" in json.dumps(view, ensure_ascii=False)

    chapters = parseJsGlobal("treatmentChapters.js")
    targeted = next(item for item in chapters["chapters"] if item["id"] == "targeted")
    assert "g35" in targeted["ref_map"]
    assert len(targeted["statements"]) >= 7

    signals = parseJsGlobal("source-signals.js")
    channel = next(item for item in signals["channels"] if item["id"] == "guidelineConsensus")
    assert any(item["id"] == "42717567" for item in channel["items"])


def test_targeted_chapter_is_layered_and_regions_have_only_two_sides():
    """诊疗现状按总论→分类→重点药物分层；中外差异语料只分中国 / 国际。"""
    divergence = json.loads(
        (PROJECT / "data" / "guideline-divergence.json").read_text(encoding="utf-8")
    )
    assert sorted({item["region"] for item in divergence["corpus"]}) == ["china", "international"]
    counts = divergence["corpus_count"]
    assert "taiwan" not in counts
    assert counts["china"] + counts["international"] == counts["total"]

    landscape = parseJsGlobal("landscape-data.js")
    label = landscape["china_landscape"]["guideline_divergence"]["status_label"]
    assert "台湾" not in label and "中国" in label and "国际" in label

    chapters = parseJsGlobal("treatmentChapters.js")
    targeted = next(item for item in chapters["chapters"] if item["id"] == "targeted")
    groups = [item.get("group", "") for item in targeted["statements"]]
    assert sum(1 for g in groups if g.startswith("一、")) == 3
    assert sum(1 for g in groups if g.startswith("二、")) == 4
    efg = [item for item in targeted["statements"] if item.get("group", "").startswith("三、")]
    assert len(efg) >= 11
    assert all(item["refs"] for item in efg), "每份指南定位都必须带语料角标"
    # 中国 2025 MG 指南首次纳入艾加莫德，必须带 g23 语料角标与推荐等级
    assert any(
        "中国 2025 MG 指南" in item["text"] and any(r.get("key") == "g23" for r in item["refs"])
        for item in efg
    )
    assert any("Ⅰa 级证据" in item["text"] and "A 级推荐" in item["text"] for item in efg)
    texts = " ".join(item["text"] for item in targeted["statements"])
    for name in ("telitacicept", "inebilizumab", "rituximab", "gefurulimab", "efgartigimod"):
        assert name in texts

    js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    assert "renderGroupedStatements" in js
    assert "['china', 'international']" in js

    # 中国 2025 MG 指南：按 wiki 全文逐字回验后落地的分层定位与差异引文
    assert sum(1 for item in efg if "中国 2025 MG 指南" in item["text"]) == 3
    assert any("升级为艾加莫德" in item["text"] and "Ⅰa 级证据" in item["text"] for item in efg)
    assert "贝利尤单抗" in texts and "IL-6R" in texts
    # 2026 药学共识按 wiki 全文核对：JBI 2014 分级与 4 类适用情形，不能写成 2025 指南的 Ⅰa/A 级
    assert any(
        "药学共识" in item["text"] and "JBI 2014" in item["text"] and "1a，强推荐" in item["text"]
        for item in efg
    )
    gd01 = next(x for x in divergence["divergences"] if x["id"] == "gd01")
    g23_quotes = [e for e in gd01["evidence"] if e.get("doc") == "g23"]
    assert len(g23_quotes) >= 3 and all(e["quote_verified"] for e in g23_quotes)
    assert "中国 2025 MG 指南" in gd01["china"]
