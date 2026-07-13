import re
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
    map_js_asset = ROOT / "assets" / "china-provinces-map.js"
    attribution = (ROOT / "assets" / "china-provinces-map-ATTRIBUTION.md").read_text(encoding="utf-8")
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")
    html = (ROOT / "pages" / "knowledge.html").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")

    assert map_asset.exists()
    assert 'id="shanghai"' in map_asset.read_text(encoding="utf-8")
    assert map_js_asset.exists()
    map_js = map_js_asset.read_text(encoding="utf-8")
    assert "window.MG_CHINA_PROVINCES_SVG" in map_js
    assert "<svg" in map_js
    assert 'viewBox="0 0 774 569"' in map_js
    assert 'id="beijing"' in map_js
    assert 'id="shanghai"' in map_js
    map_script = '<script src="../assets/china-provinces-map.js"></script>'
    network_script = '<script src="../assets/chinaAuthorNetwork.js"></script>'
    assert map_script in html
    assert html.index(map_script) < html.index(network_script)
    assert "window.MG_CHINA_PROVINCES_SVG" in frontend
    assert "DOMParser" in frontend
    assert "cloneNode(true)" in frontend
    assert "function mapAssetUrl" not in frontend
    assert "fetch(mapAssetUrl()" not in frontend
    assert "loadChinaMap(" not in frontend
    assert "chinaMapLoading" not in frontend
    assert "chinaMapCallbacks" not in frontend
    assert "正在加载中国省级底图" not in frontend
    assert "中国省级底图加载失败" not in frontend
    assert "已保留地区排行数据" in frontend
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
    assert "mapFilterInputs" in frontend
    assert "rerenderActiveDetail" in frontend
    assert "clearActiveDetail" not in frontend[frontend.index("function attachFilters"):frontend.index("function renderLoadingShell")]
    graph_filter_block = frontend[frontend.index("graphFilterInputs.forEach"):frontend.index("mapFilterInputs.forEach")]
    assert "renderGraph();" in graph_filter_block
    assert "renderHeatmap();" not in graph_filter_block
    assert "rerenderActiveDetail();" not in graph_filter_block
    map_filter_block = frontend[frontend.index("mapFilterInputs.forEach"):frontend.index("function renderLoadingShell")]
    assert "renderHeatmap();" in map_filter_block
    assert "renderGraph();" not in map_filter_block
    assert "rerenderActiveDetail();" not in map_filter_block
    global_filter_block = frontend[frontend.index("globalFilterInputs.forEach"):frontend.index("graphFilterInputs.forEach")]
    assert "renderStats();" in global_filter_block
    assert "renderGraph();" in global_filter_block
    assert "renderHeatmap();" in global_filter_block
    assert "rerenderActiveDetail();" in global_filter_block
    assert "rerenderActiveDetail" in frontend
    assert "activeDetail = { type: 'province'" in frontend
    assert "activeDetail = { type: 'mapHospital'" in frontend
    assert "china-network-main-column" not in html
    assert 'class="kg-layout china-network-layout"' not in html
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


def test_china_network_approved_information_architecture():
    html = (ROOT / "pages" / "knowledge.html").read_text(encoding="utf-8")

    global_group = html.index('id="chinaGlobalFilterLabel"')
    stats = html.index('id="chinaNetworkStats"')
    visual_grid = html.index('class="china-network-visual-grid"')
    graph_card = html.index('id="chinaNetworkGraphCard"')
    map_card = html.index('id="chinaNetworkMapCard"')
    shared_module = html.index('class="china-network-results"')
    shared_heading = html.index('id="chinaNetworkSharedTitle"')
    detail = html.index('id="chinaNetworkDetail"')

    assert stats < global_group < visual_grid < shared_module < detail
    assert visual_grid < graph_card < map_card < shared_module < shared_heading < detail
    assert '<aside class="kg-detail china-network-detail"' not in html
    assert 'id="chinaNetworkProvinceFilter"' in html
    assert '<option value="">全部省份</option>' in html
    assert 'id="chinaNetworkMapHospitalSearch"' in html
    assert 'id="chinaNetworkMapSearch"' not in html
    assert 'aria-labelledby="chinaNetworkSharedTitle"' in html
    assert "统一分析结果" in html
    assert html.index('id="chinaNetworkSearch"') > graph_card
    assert html.index('id="chinaNetworkEdgeWeight"') > graph_card
    assert html.index('id="chinaAuthorNetworkGraph"') > graph_card
    assert html.index('id="chinaNetworkLegend"') > graph_card
    assert html.index('id="chinaNetworkProvinceFilter"') > map_card
    assert html.index('id="chinaNetworkMapHospitalSearch"') > map_card
    assert html.index('id="chinaNetworkHeatmap"') > map_card


def test_china_network_shared_detail_state_and_map_controls():
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")

    assert "provinceFilter: document.getElementById('chinaNetworkProvinceFilter')" in frontend
    assert "hospitalSearch: document.getElementById('chinaNetworkMapHospitalSearch')" in frontend
    assert "mapSearch" not in frontend
    assert "chinaNetworkMapSearch" not in frontend
    assert "populateProvinceFilter" in frontend
    assert "全部省份" in frontend
    assert "data-china-province-rank" in frontend
    assert "data-china-hospital" in frontend
    assert "china-province selected" in frontend
    assert "activeDetail = { type: 'node'" in frontend
    assert "activeDetail = { type: 'edge'" in frontend
    assert "activeDetail = { type: 'province'" in frontend
    assert "activeDetail = { type: 'mapHospital'" in frontend
    assert "currentGlobalContext" in frontend
    assert "keepActiveGraphSelectionVisible" in frontend

    clear_selection = frontend[
        frontend.index("function clearMapSelection"):
        frontend.index("function selectMapProvince")
    ]
    assert "selectedMapProvince = '';" in clear_selection
    assert "selectedMapHospitalId = '';" in clear_selection
    assert "el.provinceFilter.value = '';" in clear_selection
    assert "renderHeatmap();" in clear_selection
    assert "activeDetail.type === 'province'" in clear_selection
    assert "activeDetail.type === 'mapHospital'" in clear_selection
    assert "clearActiveDetail();" in clear_selection

    province_map = frontend[
        frontend.index("function renderProvinceMap()"):
        frontend.index("function renderProvinceMapFallback()")
    ]
    assert "mapCanvas.addEventListener('click', clearMapSelection);" in province_map
    assert "event.stopPropagation();" in province_map
    assert "event.key === 'Enter' || event.key === ' '" in province_map


def test_china_network_province_map_content_order_and_fallback_stack():
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")

    province_map = frontend[
        frontend.index("function renderProvinceMap()"):
        frontend.index("function renderProvinceMapFallback()")
    ]
    map_heading = province_map.index("全作者医院热力线索 · 中国省级图")
    map_canvas = province_map.index('class="china-network-map-canvas"')
    map_legend = province_map.index('class="china-network-map-legend"')
    map_divider = province_map.index('class="china-network-map-divider"')
    map_ranking = province_map.index("renderMapRanking(stats, sorted)")
    assert map_heading < map_canvas < map_legend < map_divider < map_ranking

    fallback = frontend[
        frontend.index("function renderProvinceMapFallback()"):
        frontend.index("function renderRegionalHeatmapCards()")
    ]
    fallback_hint = fallback.index("无法显示省级地图")
    fallback_divider = fallback.index('class="china-network-map-divider"')
    fallback_ranking = fallback.index("renderMapRanking(stats, sorted)")
    assert fallback_hint < fallback_divider < fallback_ranking
    assert "右侧排行" not in fallback


def test_china_network_result_height_and_responsive_stack():
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")
    detail_css = css[css.index(".china-network-detail {"):css.index(".china-network-detail-context")]

    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css[css.index(".china-network-visual-grid"):]
    visual_grid_css = css[css.index(".china-network-visual-grid {"):css.index(".china-network-visual-card")]
    assert "align-items: start" in visual_grid_css
    assert "align-items: stretch" not in visual_grid_css
    shared_module_css = css[css.index(".china-network-results {"):css.index(".china-network-detail {")]
    assert "\n  height:" not in shared_module_css
    assert "min-height:" not in shared_module_css
    assert "max-height:" not in shared_module_css
    assert "overflow:" not in shared_module_css
    assert "gradient" not in shared_module_css
    assert "overflow: visible" in detail_css
    assert "max-height: none" in detail_css
    assert "overflow-y: auto" not in detail_css
    responsive = css[css.index("@media (max-width: 900px)"):]
    assert ".china-network-visual-grid" in responsive
    assert "grid-template-columns: 1fr" in responsive
    assert "min-width: 0" in css[css.index(".china-network-visual-card"):]
    map_layout_css = css[css.index(".china-network-map-layout {"):css.index(".china-network-map-canvas")]
    assert "grid-template-columns:" not in map_layout_css
    assert ".china-network-map-divider" in css
    rank_list_css = css[css.index(".china-network-map-rank ol {"):css.index(".china-network-map-rank li")]
    assert "display: grid" in rank_list_css
    assert "repeat(auto-fit, minmax(" in rank_list_css


def test_china_network_node_detail_lists_expand_only_in_semantic_scope():
    frontend = (ROOT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")

    assert frontend.count("china-network-node-detail-section") == 2
    assert "renderPaperList(nodePaperIds, null, true, 'china-network-node-detail-list')" in frontend
    assert 'class="kg-study-list china-network-node-detail-list"' in frontend

    scoped_rule = re.search(
        r"\.china-network-detail\s+\.china-network-node-detail-section\s+"
        r"\.china-network-node-detail-list\s*\{([^}]*)\}",
        css,
        re.S,
    )
    assert scoped_rule is not None
    assert "max-height: none" in scoped_rule.group(1)
    assert "overflow: visible" in scoped_rule.group(1)

    # 通用知识库文献列表继续保留内部滚动，避免影响诊治格局等模块。
    assert re.search(
        r"\.kg-study-list\s*\{[^}]*max-height:\s*200px;[^}]*overflow-y:\s*auto",
        css,
        re.S,
    )
