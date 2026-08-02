import re
import subprocess
import sys
from pathlib import Path

from scripts.common.io import load_js_global
from scripts.common.publicDataContract import publicArtifactNames


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
ACTIVE_PAGES = (
    PROJECT / "index.html",
    PROJECT / "pages" / "literature.html",
    PROJECT / "pages" / "landscape.html",
    PROJECT / "pages" / "knowledge.html",
    PROJECT / "pages" / "msl.html",
    PROJECT / "pages" / "data-ops.html",
)


def pmidSet(items):
    return {str(item.get("pmid")) for item in items if item.get("pmid")}


def test_public_js_files_match_the_explicit_release_contract():
    actual = {
        path.name
        for path in DATA.glob("*.js")
        if path.name != "release-manifest.js"
    }
    assert actual == set(publicArtifactNames())


def test_recent_community_and_dashboard_use_one_public_window():
    literature = load_js_global(DATA / "literature-recent.js", "MG_LITERATURE_DATA")
    metadata = load_js_global(DATA / "literature-recent.js", "MG_LITERATURE_META")
    community = load_js_global(
        DATA / "communityAssignmentsRecent.js",
        "MG_COMMUNITY_RECENT_ASSIGNMENTS",
    )
    signals = load_js_global(DATA / "signals-weekly.js", "MG_SIGNALS_DATA")
    dashboard = load_js_global(DATA / "dashboard-data.js", "MG_DASHBOARD_DATA")

    assert metadata["item_count"] == len(literature)
    assert community["basis"] == "literatureRecentPmidSet"
    assert pmidSet(literature) == pmidSet(community["items"])
    assert signals["window_basis"] == "trueIngestAddedPmids"
    assert dashboard["stats"]["recent_articles"] == len(literature)
    assert dashboard["stats"]["signals"] == len(signals["signals"])


def test_active_pages_load_release_manifest_first_and_share_one_token():
    releaseIds = set()
    for page in ACTIVE_PAGES:
        html = page.read_text(encoding="utf-8")
        releasePosition = html.index("data/release-manifest.js")
        commonPosition = html.index("assets/common.js")
        assert releasePosition < commonPosition

        localUrls = re.findall(
            r'(?:src|href)="((?:\.\./)?(?:assets|data)/[^"?#]+)\?v=([A-Za-z0-9._-]+)"',
            html,
        )
        assert localUrls
        pageIds = {releaseId for _, releaseId in localUrls}
        assert len(pageIds) == 1
        releaseIds.update(pageIds)
    assert len(releaseIds) == 1


def test_all_local_lazy_loaders_inherit_the_release_token():
    common = (PROJECT / "assets" / "common.js").read_text(encoding="utf-8")
    knowledge = (PROJECT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    literature = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    chinaNetwork = (PROJECT / "assets" / "chinaAuthorNetwork.js").read_text(encoding="utf-8")

    assert "withReleaseVersion(assetUrl(src))" in common
    assert "hub.withReleaseVersion(src)" in knowledge
    assert "hub.loadScript(src, callback)" in literature
    assert "var loader = hub.loadScript" in chinaNetwork


def test_committed_release_passes_read_only_validation():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validatePublicRelease.py",
            "--source-only",
            "--require-release",
        ],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
