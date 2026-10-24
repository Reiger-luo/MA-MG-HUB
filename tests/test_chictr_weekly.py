"""ChiCTR 周更的三条 fail-closed 契约：站点拦截、回退过量、条数下限。"""
import json
from datetime import datetime, timezone

import pytest

from scripts.common.chictr_live import (
    ChiCTRLiveError,
    refresh_chictr_live,
    scrape_chictr_records,
)

XML_TEMPLATE = """<?xml version="1.0"?>
<Trial>
  <trial_id>{reg}</trial_id>
  <public_title>{title}</public_title>
  <date_registration>2026-01-05</date_registration>
  <recruitment_status>{status}</recruitment_status>
  <phase>2</phase>
</Trial>
"""


def make_xml(reg, status="Recruiting", title="MG study"):
    return XML_TEMPLATE.format(reg=reg, status=status, title=title)


SEARCH_HTML = "<html><body>" + "".join(
    f'<a href="showproj.html?proj={i}">x</a>' for i in range(1, 11)
) + "</body></html>"

DETAIL_HTML = '<a href="/bin/chictr/DownloadXml?path=ABC{}">xml</a>'


class FakeClient:
    """可控的 ChiCTR 替身：按 URL 返回检索页 / 详情页 / XML。"""

    def __init__(self, *, block_after=None, fail_xml_ids=(), projects=10, missing_xml_ids=()):
        self.block_after = block_after
        self.fail_xml_ids = set(fail_xml_ids)
        self.missing_xml_ids = set(missing_xml_ids)
        self.projects = projects
        self.calls = 0

    def get_text(self, url, *, params=None):
        self.calls += 1
        if self.block_after is not None and self.calls > self.block_after:
            raise ChiCTRLiveError("ChiCTR WAF 阻断了本次请求")
        if "searchproj" in url:
            ids = "".join(f'<a href="showproj.html?proj={i}">x</a>' for i in range(1, self.projects + 1))
            return f"<html><body>{ids}</body></html>"
        if "showproj" in url:
            proj = url.split("proj=")[-1]
            if proj in self.missing_xml_ids:
                return "<html><body>no link</body></html>"
            return DETAIL_HTML.format(proj)
        if "DownloadXml" in url:
            proj = url.split("path=ABC")[-1].split("&")[0]
            if proj in self.fail_xml_ids:
                raise RuntimeError(f"XML 损坏 {proj}")
            return make_xml(f"ChiCTR{int(proj):06d}")
        raise AssertionError(f"未预期的 URL {url}")


def test_site_block_aborts_run_instead_of_falling_back_to_stale():
    """站点 405/WAF 必须中止整轮，不能靠旧记录凑数后宣称成功。"""
    client = FakeClient(block_after=12)

    with pytest.raises(ChiCTRLiveError, match="拦截|阻断"):
        scrape_chictr_records(client, old_records=[], detail_budget=None)


def test_heavy_stale_fallback_is_rejected():
    """超过 10% 的记录只能沿用旧数据时，本轮视为未完成核对。"""
    old = [
        {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "xml_url": f"https://x/{i}"}
        for i in range(1, 11)
    ]
    # 所有 XML 链接都失效 → 全部回退旧数据
    client = FakeClient(fail_xml_ids=[str(i) for i in range(1, 11)])

    with pytest.raises(ChiCTRLiveError, match="沿用旧数据|安全阈值"):
        scrape_chictr_records(client, old_records=old, detail_budget=None)


def test_result_count_floor_uses_previous_cache_size():
    """发现数量骤降时，按上一版缓存条数兜底，防止把 120 条写成 20 条。"""
    old = [
        {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "xml_url": f"https://x/{i}"}
        for i in range(1, 41)
    ]
    client = FakeClient(projects=10)  # 站点只回 10 个项目

    with pytest.raises(ChiCTRLiveError, match="未达到安全阈值"):
        scrape_chictr_records(client, old_records=old, detail_budget=None)


def test_xml_url_reuse_skips_detail_page():
    """有缓存 xml_url 时应直接取 XML，节省一次详情页请求。"""
    old = [
        {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "xml_url": f"https://www.chictr.org.cn/bin/chictr/DownloadXml?path=ABC{i}"}
        for i in range(1, 11)
    ]
    client = FakeClient()

    records, meta = scrape_chictr_records(client, old_records=old, detail_budget=None)

    assert len(records) == 10
    assert meta["records_xml_reused"] == 10
    assert meta["records_detail_fetched"] == 0
    assert all(record["xml_url"] for record in records)


def test_detail_budget_defers_remaining_projects_without_claiming_freshness():
    """分批迁移：预算用尽后保留旧记录并计入 deferred，不能让它们算作已核对。"""
    old = [
        {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "title": "旧标题"}
        for i in range(1, 11)
    ]
    client = FakeClient()

    records, meta = scrape_chictr_records(client, old_records=old, detail_budget=4)

    assert meta["records_detail_fetched"] == 4
    assert meta["records_deferred"] == 6
    assert meta["records_with_xml"] == 4
    assert len(records) == 10


def test_partial_refresh_keeps_last_verified_and_marks_mode(tmp_path):
    """分批迁移期间 last_verified 不前移，mode 标记 live_partial。"""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "last_verified": "2026-10-01T00:00:00+00:00",
        "records": [
            {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "title": "旧"}
            for i in range(1, 11)
        ],
    }), encoding="utf-8")

    payload = refresh_chictr_live(
        cache,
        force=True,
        client=FakeClient(),
        detail_budget=4,
        now=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )

    assert payload["refresh_status"] == "updated"
    assert payload["mode"] == "live_partial"
    assert payload["last_verified"] == "2026-10-01T00:00:00+00:00"
    assert payload["records_deferred"] == 6


def test_full_refresh_advances_last_verified(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "last_verified": "2026-10-01T00:00:00+00:00",
        "records": [
            {"registry_id": f"ChiCTR{i:06d}", "proj_id": str(i), "title": "旧"}
            for i in range(1, 11)
        ],
    }), encoding="utf-8")

    payload = refresh_chictr_live(
        cache,
        force=True,
        client=FakeClient(),
        now=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )

    assert payload["mode"] == "live"
    assert payload["last_verified"].startswith("2026-10-24")
    assert payload["records_deferred"] == 0


def test_failed_refresh_leaves_cache_untouched(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "last_verified": "2026-10-01T00:00:00+00:00",
        "records": [{"registry_id": "ChiCTR000001", "proj_id": "1"}],
    }), encoding="utf-8")
    before = cache.read_bytes()

    payload = refresh_chictr_live(
        cache,
        force=True,
        client=FakeClient(block_after=1),
        now=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )

    assert payload["refresh_status"] == "failed"
    assert cache.read_bytes() == before