"""视图架构契约：模块是同一条判断簇的切面，不按数据源切目录。

三条硬约束：
1. 主导航只暴露四个视图（三工作视图 + 工具箱），社区不再是并列视图；
2. 每个视图都要能落到具体标签，且带 ?view=&tab= 可分享；
3. 可导出的两块判断（竞争定位、指南差异）必须有导出入口，且导出内容不得含语料代号。
"""
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PAGES = [
    PROJECT / "index.html",
    PROJECT / "pages" / "literature.html",
    PROJECT / "pages" / "landscape.html",
    PROJECT / "pages" / "knowledge.html",
    PROJECT / "pages" / "msl.html",
]

VIEW_KEYS = ("evidence", "experts", "answers", "toolbox")


def test_every_page_carries_the_same_view_bar():
    for path in PAGES:
        html = path.read_text(encoding="utf-8")
        assert 'id="viewBar"' in html, f"{path.name} 缺少视图切换条"
        assert "assets/view.js" in html, f"{path.name} 未加载 view.js"


def test_view_bar_declares_exactly_the_four_views():
    js = (PROJECT / "assets" / "view.js").read_text(encoding="utf-8")
    declared = re.findall(r"key: '([a-z]+)', label:", js)
    assert tuple(declared) == VIEW_KEYS, f"视图集合变化: {declared}"
    for key in VIEW_KEYS:
        assert f"key: '{key}'" in js


def test_view_routes_resolve_to_a_page_and_tab():
    js = (PROJECT / "assets" / "view.js").read_text(encoding="utf-8")
    # 每个视图都要声明 file 和至少一个标签
    for key in VIEW_KEYS:
        block = js[js.index(f"key: '{key}'"):]
        block = block[:block.index("}") + 1]
        assert "file:" in block, f"{key} 未声明落地页面"
        assert "tabs: [" in block and "]" in block, f"{key} 未声明标签"


def test_community_is_no_longer_a_parallel_view():
    html = (PROJECT / "pages" / "knowledge.html").read_text(encoding="utf-8")
    tabs = re.findall(r'data-knowledge-tab="([a-z-]+)"', html)
    assert "communities" not in tabs, f"社区仍作为并列标签存在: {tabs}"
    assert "graph" in tabs and "matrix" in tabs and "china-network" in tabs
    # 面板保留但必须隐藏，且旧链接仍能被 JS 兜住
    assert 'id="knowledge-communities-panel" hidden' in html


def test_knowledge_matrix_tab_is_renamed_to_claim_evidence():
    html = (PROJECT / "pages" / "knowledge.html").read_text(encoding="utf-8")
    assert "Claim–Evidence" in html
    assert "<h2>证据矩阵</h2>" not in html


def test_landscape_exposes_matrix_and_guide_as_own_tabs():
    html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    tabs = re.findall(r'data-landscape-tab="([a-z]+)"', html)
    assert tabs == ["overview", "matrix", "guide", "answers"], tabs
    for panel in ("landscape-matrix", "landscape-guide"):
        assert f'id="{panel}"' in html


def test_both_judgement_blocks_can_be_exported():
    html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")

    assert 'id="btnExportMatrix"' in html
    assert 'id="btnExportGuideline"' in html
    assert "buildMatrixBrief" in js and "buildGuidelineBrief" in js
    # 导出内容必须是 Markdown，且能下载
    assert "text/markdown" in js
    # 导出模板不得回填语料代号
    assert "gcode" not in js.lower()


def test_homepage_offers_the_three_working_views():
    html = (PROJECT / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'class="dashboard-view-card[^"]*" href="([^"]+)"', html)
    assert len(cards) == 4, cards
    assert all("view=" in href for href in cards), cards
    for key in VIEW_KEYS:
        assert f"view={key}" in " ".join(cards), f"首页缺少 {key} 入口"