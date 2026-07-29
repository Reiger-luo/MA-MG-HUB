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


def test_dashboard_is_action_first_workbench():
    html = (PROJECT / "index.html").read_text(encoding="utf-8")
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")

    assert 'href="#mainContent"' in html
    assert 'aria-current="page"' in html
    assert 'id="dashboardReleaseStatus"' in html
    assert 'id="dashboardTrials"' in html
    assert "clinicalTrialsSummary.js" in html
    assert html.index('id="dashboardSignals"') < html.index('id="dashboardCommunityDynamics"')
    assert 'id="dashboardReviewQueue"' not in html
    assert 'id="dashboardSections"' not in html
    assert "待医学复核" not in html
    assert "工作区入口" not in html
    assert "communityAudit.js" not in html

    assert "renderReleaseStatus" in dashboard_js
    assert "renderTrials" in dashboard_js
    assert "renderReviewQueue" not in dashboard_js
    assert "renderSections" not in dashboard_js
    assert "signalDetailUrl" in dashboard_js
    assert "level === 'active'" in dashboard_js
    assert "row.high_evidence_count != null" in dashboard_js
    assert "row.high_evidence_count ||" not in dashboard_js


def test_intelligence_brief_export_follows_active_tab_and_filters():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    conference_js = (PROJECT / "assets" / "conference.js").read_text(encoding="utf-8")

    assert 'id="filterSignalStrengthList"' in html
    assert 'value="强"' in html
    assert 'value="中"' in html
    assert 'value="弱"' in html

    assert "articleSignalStrengthByPmid" in literature_js
    assert "rebuildArticleSignalStrengthIndex" in literature_js
    assert "getFilteredSignalItems" in literature_js
    assert "buildCurrentBrief" in literature_js
    assert "activeIntelTab === 'signals'" in literature_js
    assert "activeIntelTab === 'china'" in literature_js
    assert "activeIntelTab === 'conference'" in literature_js
    assert "activeIntelTab === 'trials'" in literature_js
    assert "filteredResults.length > 0 ? filteredResults : allArticles" not in literature_js
    assert "window.MgConferenceBrief.getContext" in literature_js
    assert "window.MgConferenceBrief" in conference_js
