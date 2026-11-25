"""知识库契约：同心圆概念地图 + 精读三镜。

用户 2026-11-25 修订：删掉顶部入口三栏；控制区改大白话；图谱改同心圆发散；
精读区必须显式表明来自图谱选中；连接镜删"进入"、关系全展开。
这里锁定结构、边界文案与显示层字典的一致性；运行时行为由 verifyFrontendRender.js 真实点击覆盖。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_JS = ROOT / "assets" / "knowledge.js"
KNOWLEDGE_HTML = ROOT / "pages" / "knowledge.html"
GRAPH_JS = ROOT / "data" / "knowledge-graph.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def object_keys(source: str, var_name: str) -> list:
    """取出 `var <name> = { ... };` 字面量的键（仅用于显示层字典这类扁平对象）。"""
    match = re.search(r"var " + re.escape(var_name) + r" = \{(.*?)\n  \};", source, re.S)
    assert match, f"未找到 {var_name}"
    return re.findall(r"^\s{4}([A-Za-z0-9_]+):", match.group(1), re.M)


def node_ids() -> set:
    ids = set(re.findall(r'"id":"([A-Za-z0-9_]+)"', read(GRAPH_JS)))
    assert len(ids) >= 50, "图谱产物缺少节点 id"
    return ids


def drug_node_ids() -> set:
    source = read(GRAPH_JS)
    return set(re.findall(r'"id":"([A-Za-z0-9_]+)","title":"[^"]*","type":"drug"', source))


def display_names() -> dict:
    source = read(KNOWLEDGE_JS)
    match = re.search(r"var zhLabel = \{(.*?)\n  \};", source, re.S)
    assert match, "未找到 zhLabel"
    return dict(re.findall(r"^\s{4}([A-Za-z0-9_]+): '([^']*)'", match.group(1), re.M))


def test_display_dictionaries_only_reference_real_nodes():
    """中文显示名与关键词别名是导航元数据：概念词典增删后不得留下悬空条目。"""
    source = read(KNOWLEDGE_JS)
    ids = node_ids()
    assert set(object_keys(source, "zhLabel")) <= ids
    assert set(object_keys(source, "nodeAlias")) <= ids
    assert "myastheniaGravis" not in object_keys(source, "nodeAlias")


def test_drug_chinese_names_come_from_site_dictionary_only():
    """药物中文显示名只允许沿用本站药物词典已有的名称，不自拟。"""
    dictionary = read(ROOT / "scripts" / "build-clinical-trials-data.py")
    names = display_names()
    drugs = drug_node_ids()
    assert {"efgartigimod", "eculizumab"} <= drugs, "未能从图谱产物识别药物节点"
    for node_id, name in names.items():
        if node_id not in drugs:
            continue
        for part in name.split("/"):
            assert "(" + part + ")" in dictionary, f"药物 {node_id} 的中文名「{part}」不在本站药物词典中"


def test_page_structure_is_radial_map_and_three_lenses():
    html = read(KNOWLEDGE_HTML)
    for element_id in (
        "kbBaseline", "knowledgeNodeSearch", "knowledgeTypeFilter", "knowledgeCommunityFilter",
        "kgResetFilters", "kgMapCount", "knowledgeGraphLegend",
        "knowledgeGraph", "kgSelectionRibbon", "kgRibbonText", "kgFromGraph",
        "knowledgeWorkbench", "kgIdentity",
        "kgLensKnowledge", "kgLensConnect", "kgLensThink",
        "kgRelationList", "kgCurationPanel", "kgEvidencePane", "kgEvidenceClose", "kgExportCard",
    ):
        assert f'id="{element_id}"' in html, f"缺少 #{element_id}"
    assert "kb-entry" not in html and "kbLedger" not in html, "顶部入口三栏应已删除"
    assert html.count("data-map-mode=") == 0
    assert "knowledgeGraphColorMode" not in html
    assert "data-relation-mode=" not in html
    assert html.count("data-kg-lens=") == 3
    assert "data-workbench-tab" not in html
    order = [html.index(f'data-kg-lens="{lens}"') for lens in ("knowledge", "connect", "think")]
    assert order == sorted(order)
    assert html.index('class="kb-map"') < html.index('id="kgSelectionRibbon"') < html.index('id="knowledgeWorkbench"')


def test_controls_use_plain_language():
    html = read(KNOWLEDGE_HTML)
    for label in ("找概念", "图上看什么", "只画最相关的关系", "圆点颜色只标药物机制家族", "这些说法是什么意思"):
        assert label in html, f"控制区缺少大白话标签：{label}"
    for old in ("决定图怎么画", "一起出现最多", "高共现关系", "不匹配的变淡", "按主题分类染色"):
        assert old not in html, f"控制区仍有看不懂的旧说法：{old}"


def test_page_loads_the_assets_the_reading_room_needs():
    html = read(KNOWLEDGE_HTML)
    for script in (
        "data/knowledge-graph.js", "data/curated-topics.js", "data/communityTaxonomy.js",
        "data/signals-weekly.js", "data/trial-signals-weekly.js", "data/clinicalQuestions.js",
    ):
        assert script in html, f"知识库未加载 {script}"
    assert "data/landscape-data.js" not in html
    source = read(KNOWLEDGE_JS)
    assert "hub.loadScript('data/landscape-data.js'" in source


def test_reading_area_stays_in_page_and_declares_boundaries():
    source = read(KNOWLEDGE_JS)
    assert "location.href" not in source
    for token in (
        "function selectNode", "function locateNode", "function selectEdge", "function renderCuration",
        "function renderCrossEvidence", "function hideEvidencePane", "function renderKnowledge",
        "function renderThink", "function buildConceptCard", "function focusQuestionCard",
    ):
        if token == "function focusQuestionCard":
            assert token in read(ROOT / "assets" / "landscape.js")
        else:
            assert token in source, f"缺少 {token}"
    for token in ("不代表疗效或因果", "落点由关键词关联推断", "静态策展快照", "引用前请核对 PMID 原文"):
        assert token in source, f"缺少边界说明：{token}"
    assert "本周新证据" not in source
    assert "hub.openBriefModal" in source and "hub.briefFooter" in source


def test_connect_lens_has_no_subject_switch_button():
    source = read(KNOWLEDGE_JS)
    html = read(KNOWLEDGE_HTML)
    assert "data-locate-node" in source and "function locateNode" in source
    assert "点圆点才会切换精读对象" in source
    assert "kg-relation-enter" not in html and "kg-relation-enter" not in source
    assert "data-relation-more" not in source
    assert "RELATION_PREVIEW" not in source


def test_map_draws_backbone_relations_on_concentric_rings():
    source = read(KNOWLEDGE_JS)
    assert "var HUB_ID = 'myastheniaGravis'" in source
    assert "function pickBackbone" in source
    assert "fill: 'none'" in source
    assert "var ringRadii" in source and "function computeLayout()" in source
    assert "kg-ring-guide" in source
    assert "columnX" not in source, "不应残留分列布局"
    assert "mapRelationMode" not in source and "graphColorMode" not in source, "不应残留关系画法/颜色切换"
    assert "var drugFamily" in source, "圆点颜色应按药物机制家族固定"
    assert "lift: expected > 0 ? (edge.article_count || 0) / expected : 0" in source


def test_landscape_accepts_question_deep_link():
    source = read(ROOT / "assets" / "landscape.js")
    assert "function focusQuestionCard" in source
    assert "getQueryParam('question')" in source
    assert 'data-question-id="' in source
    assert "question-card.is-focused" in read(ROOT / "assets" / "main.css")
