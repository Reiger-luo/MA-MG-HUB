from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_literature_inactive_modules_are_not_synchronous():
    html = (ROOT / "pages" / "literature.html").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "literature.js").read_text(encoding="utf-8")

    assert "data/conference-data.js" not in html
    assert "assets/conference.js" not in html
    assert "loadConferenceModule" in js
    assert "ensureChinaInsights" in js

    init_block = js[js.index("function init()"):js.index("el.btnExport.addEventListener")]
    assert "renderChinaInsights();" not in init_block


def test_knowledge_graph_omits_unused_edge_references():
    graph = (ROOT / "data" / "knowledge-graph.js").read_text(encoding="utf-8")
    frontend = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")

    assert '"edge_references"' not in graph
    assert "graphData.edge_references" not in frontend
    assert "ensureTabInitialized" in frontend


def test_china_network_map_asset_and_render_hook_exist():
    map_asset = ROOT / "assets" / "china-provinces.svg"
    standard_map = ROOT / "assets" / "china-standard-map-gs-2016-2923.jpg"
    attribution = (ROOT / "assets" / "china-provinces-map-ATTRIBUTION.md").read_text(encoding="utf-8")
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")

    assert map_asset.exists()
    assert standard_map.exists()
    assert standard_map.stat().st_size > 1_000_000
    assert 'id="shanghai"' in map_asset.read_text(encoding="utf-8")
    assert "assets/china-standard-map-gs-2016-2923.jpg" in frontend
    assert "china-standard-map-overlay" in frontend
    assert "data-china-hospital" in frontend
    assert "china-network-edge-hit" in frontend
    assert "all_author_paper_ids" in frontend
    assert "paper.entry_date || paper.pub_date" in frontend
    assert "latestFirst" in frontend
    assert "provinceHeatmapStats" in frontend
    assert "chinaNetworkDrugFilter" in frontend
    assert "renderDrugCounts" in frontend
    assert "all_author_drug_paper_ids" in frontend
    assert "drug_paper_ids" in frontend
    assert "GS（2016）2923号" in attribution
