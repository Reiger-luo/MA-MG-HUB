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
    attribution = (ROOT / "assets" / "china-provinces-map-ATTRIBUTION.md").read_text(encoding="utf-8")
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")
    html = (ROOT / "pages" / "knowledge.html").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")

    assert map_asset.exists()
    assert 'id="shanghai"' in map_asset.read_text(encoding="utf-8")
    assert "china-standard-map-gs-2016-2923.jpg" not in frontend
    assert "standardMapAssetUrl" not in frontend
    assert "china-standard-map-overlay" not in frontend
    assert "china-standard-map-image" not in frontend
    assert "china-editable-map-shell" in frontend
    assert "china-province-map" in frontend
    assert "china-map-audit-label" in frontend
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
    assert 'Number(el.edgeWeight.value || 1) : 1' in frontend
    assert '<option value="1" selected>全部边 ≥1</option>' in html
    assert "globalFilterInputs" in frontend
    assert "graphFilterInputs" in frontend
    assert "rerenderActiveDetail" in frontend
    assert "clearActiveDetail" not in frontend[frontend.index("function attachFilters"):frontend.index("function renderLoadingShell")]
    graph_filter_block = frontend[frontend.index("graphFilterInputs.forEach"):frontend.index("function renderLoadingShell")]
    assert "renderGraph();" in graph_filter_block
    assert "rerenderActiveDetail();" not in graph_filter_block
    assert "rerenderActiveDetail" in frontend
    assert "activeDetail = { type: 'province'" in frontend
    assert "activeDetail = { type: 'mapHospital'" in frontend
    assert "china-network-main-column" in html
    assert "china-network-detail" in html
    assert "全局筛选（地域/药物）" in html
    assert "合作图筛选（医院搜索/合作强度）" in html
    assert "医院联络视图" in frontend
    assert "医院合作" in frontend
    assert "省级全作者分布" in frontend
    assert "医院全作者文献" in frontend
    assert "currentGlobalContext" in frontend
    assert "node.drug_paper_ids" in frontend
    assert "node.all_author_drug_paper_ids" in frontend
    assert "当前全局筛选下暂无匹配数据" in frontend
    assert "drug.article_count || 0) + '篇</option>'" not in frontend
    assert "drug.id === selected" in frontend
    assert "syncDetailHeight" not in frontend
    assert "ResizeObserver" not in frontend
    assert "overflow-y: auto" not in css[css.index(".china-network-detail"):css.index(".china-network-map-head")]
    assert "pmids = latestFirst(pmids);" in frontend
    assert "renderPaperList(nodePaperIds, 8)" not in frontend
    assert "renderPaperList(paperIds, 20)" not in frontend
    assert "renderPaperList(pmids, 30" not in frontend
    assert "repeat(5, minmax(0, 1fr))" in css
    assert "GS（2016）2923号" in attribution
    assert "单层可编辑省级 SVG · 审图号 GS（2016）2923号" in frontend
    assert "透明交互几何层" not in attribution
