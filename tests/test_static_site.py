import posixpath
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


PROJECT = Path(__file__).resolve().parents[1]


ACTIVE_PAGES = [
    PROJECT / "index.html",
    PROJECT / "pages" / "literature.html",
    PROJECT / "pages" / "landscape.html",
    PROJECT / "pages" / "knowledge.html",
    PROJECT / "pages" / "msl.html",
    PROJECT / "pages" / "data-ops.html",
]


class LocalReferenceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"src", "href"}:
                self.references.append(value)


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


def test_all_local_html_references_match_tracked_paths_case_sensitively():
    tracked = set(
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=PROJECT,
            text=True,
        ).splitlines()
    )
    pages = [PROJECT / "index.html", *sorted((PROJECT / "pages").glob("*.html"))]

    for page in pages:
        parser = LocalReferenceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        pageName = page.relative_to(PROJECT).as_posix()
        base = posixpath.dirname(pageName)
        for value in parser.references:
            if not value or value.startswith(
                ("#", "data:", "mailto:", "tel:", "javascript:", "http://", "https://", "obsidian:")
            ):
                continue
            cleanPath = urlparse(value).path
            resolved = posixpath.normpath(posixpath.join(base, cleanPath))
            if cleanPath.endswith("/") or resolved == ".":
                resolved = "index.html"
            assert resolved in tracked, f"{pageName}: {value} 未精确匹配 Git 路径 {resolved}"


def test_common_js_blocks_dangerous_url_protocols():
    common = (PROJECT / "assets" / "common.js").read_text(encoding="utf-8")
    assert "javascript:" not in common
    assert "resolved.protocol === 'http:'" in common
    assert "resolved.protocol === 'https:'" in common


def test_dashboard_is_action_first_workbench():
    html = (PROJECT / "index.html").read_text(encoding="utf-8")
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    main_css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    assert 'href="#mainContent"' in html
    assert 'aria-current="page"' in html
    assert "MG医学事务工作台" in html
    assert "学术情报工作台" not in html
    assert 'id="dashboardReleaseStatus"' in html
    assert 'id="dashboardTrials"' not in html
    assert 'id="signalStrengthLegend"' in html
    assert 'id="trialSignalStrengthLegend"' in html
    assert 'id="trialSignalWindow"' in html
    assert "clinicalTrialsSummary.js" in html
    assert "trial-signals-weekly.js" in html
    assert 'id="dashboardCommunityDynamics"' not in html
    assert "本周升温社区" not in html
    assert "communityWeekly.js" not in html
    assert 'signal-filter-btn' not in html
    assert 'id="dashboardReviewQueue"' not in html
    assert 'id="dashboardSections"' not in html
    assert "待医学复核" not in html
    assert "工作区入口" not in html
    assert "communityAudit.js" not in html

    assert "renderReleaseStatus" in dashboard_js
    assert "release_consistency" in dashboard_js
    assert "发布产物已漂移" in dashboard_js
    assert "^\\d{4}-\\d{2}-\\d{2}$" in dashboard_js
    assert "changes.comparison_available !== false" in dashboard_js
    style_version = re.search(r'assets/main\.css\?v=([A-Za-z0-9._-]+)', html)
    script_version = re.search(r'assets/dashboard\.js\?v=([A-Za-z0-9._-]+)', html)
    assert style_version
    assert script_version
    assert style_version.group(1) == script_version.group(1)
    assert "grid-template-columns: minmax(0, 1fr);" in main_css
    assert ".trial-signal-card" in main_css
    assert "renderCommunityDynamics" not in dashboard_js
    assert "renderTrialSignals" in dashboard_js
    assert "renderSignalStrengthLegend" in dashboard_js
    assert "renderTrialSignalStrengthLegend" in dashboard_js
    assert "signal-stat-card" in dashboard_js
    assert "source_windows" in dashboard_js
    assert "注册/开发信号，不代表疗效证据" in dashboard_js
    assert "renderReviewQueue" not in dashboard_js
    assert "renderSections" not in dashboard_js
    assert "bindSignalFilters" not in dashboard_js
    assert "renderSignalKeywords" not in dashboard_js
    assert "signalDetailUrl" in dashboard_js


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
    assert "article.signal_strength" in literature_js
    assert "按近一年文献级信号标签筛选" in html
    assert "efgar 未命中强标准时以中信号兜底" in html
    assert "getFilteredSignalItems" in literature_js
    assert "buildCurrentBrief" in literature_js
    assert "activeIntelTab === 'signals'" in literature_js
    assert "activeIntelTab === 'china'" in literature_js
    assert "activeIntelTab === 'conference'" in literature_js
    assert "activeIntelTab === 'trials'" in literature_js
    assert "filteredResults.length > 0 ? filteredResults : allArticles" not in literature_js
    assert "window.MgConferenceBrief.getContext" in literature_js
    assert "window.MgConferenceBrief" in conference_js
