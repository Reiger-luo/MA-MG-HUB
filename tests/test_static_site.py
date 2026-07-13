from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


ACTIVE_PAGES = [
    PROJECT / "index.html",
    PROJECT / "pages" / "literature.html",
    PROJECT / "pages" / "landscape.html",
    PROJECT / "pages" / "knowledge.html",
    PROJECT / "pages" / "msl.html",
    PROJECT / "pages" / "data-ops.html",
]


def test_active_pages_load_common_before_page_scripts():
    for path in ACTIVE_PAGES:
        html = path.read_text(encoding="utf-8")
        assert "/MA-MG-HUB/assets/main.css" not in html
        assert "/MA-MG-HUB/assets/" not in html
        assert "assets/common.js" in html


def test_active_pages_use_relative_navigation():
    for path in ACTIVE_PAGES:
        html = path.read_text(encoding="utf-8")
        assert 'href="/MA-MG-HUB/' not in html
        assert 'src="/MA-MG-HUB/' not in html


def test_common_js_blocks_dangerous_url_protocols():
    common = (PROJECT / "assets" / "common.js").read_text(encoding="utf-8")
    assert "javascript:" not in common
    assert "resolved.protocol === 'http:'" in common
    assert "resolved.protocol === 'https:'" in common


def test_dashboard_keeps_only_full_width_recent_signals_module():
    html = (PROJECT / "index.html").read_text(encoding="utf-8")
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    dashboard_data = (PROJECT / "data" / "dashboard-data.js").read_text(encoding="utf-8")

    assert 'class="dashboard-grid dashboard-grid-single"' in html
    assert 'id="dashboardWorkflows"' not in html
    assert 'id="dashboardHealth"' not in html
    assert "当前工作流" not in html
    assert "数据健康" not in html

    assert "renderWorkflows" not in dashboard_js
    assert "renderHealth" not in dashboard_js

    # 仅取消首页展示，不改动生成数据契约。
    assert '"workflows"' in dashboard_data
    assert '"data_health"' in dashboard_data
