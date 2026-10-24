import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.common import cde_live
from scripts.common.cde_live import (
    CdeLiveError,
    collect_mg_trials,
    is_mg_trial,
    parse_detail,
    parse_list_rows,
    parse_rss,
)

LIST_HTML = """
<table class="searchTable">
 <tr class="Tab_title"><th>序号</th><th>登记号</th><th>试验状态</th><th>药物名称</th><th>适应症</th><th>试验通俗题目</th></tr>
 <tr style=" color:#535353">
  <td height="40">&nbsp;1</td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-mg" name="1"> CTR20263476 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-mg" name="1"> 进行中&nbsp;尚未招募 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-mg" name="1"> CG001注射液 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-mg" name="1">全身型重症肌无力（gMG）</a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-mg" name="1">CG001 注射液在 gMG 患者中的安全性研究</a></td>
 </tr>
 <tr style=" color:#535353">
  <td height="40">&nbsp;2</td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-lung" name="2"> CTR20263746 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-lung" name="2"> 进行中&nbsp;尚未招募 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-lung" name="2"> EIK1001注射液 </a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-lung" name="2">IV期非小细胞肺癌的治疗</a></td>
  <td><a href="javascript:void(0)" onclick="getDetail(this.id)" id="hash-lung" name="2">一项在 IV 期非小细胞肺癌受试者中开展的研究</a></td>
 </tr>
</table>
<div class="pull-right pageInfo">当前第 <i>1</i> 页，共 <i>3</i> 页，共 <i>52</i> 条记录</div>
"""

DETAIL_HTML = """
<div class="searchDetailPartTit">三、临床试验信息</div>
<table class="searchDetailTable">
 <tr><th width="15%">试验分类</th><td>安全性和有效性</td><th width="15%">试验分期</th><td>其它 其他说明:II/III期</td><th>设计类型</th><td>平行分组</td></tr>
</table>
<table>
 <tr><th>首次公示信息日期</th><td> 2026-09-14 </td><th>申请人名称</th><td> 示例药业 </td></tr>
</table>
"""

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
 <item>
  <title><![CDATA[一项评价 XX 注射液治疗重症肌无力的 II 期研究]]></title>
  <link><![CDATA[/clinicaltrials.searchlistdetail.dhtml?id=abc]]></link>
  <guid><![CDATA[CTR20269999]]></guid>
  <pubDate><![CDATA[2026-10-23]]></pubDate>
 </item>
 <item>
  <title><![CDATA[苯磺酸美洛加巴林片生物等效性试验]]></title>
  <link><![CDATA[/clinicaltrials.searchlistdetail.dhtml?id=def]]></link>
  <guid><![CDATA[CTR20264035]]></guid>
  <pubDate><![CDATA[2026-10-23]]></pubDate>
 </item>
</channel></rss>
"""


EMPTY_LIST_HTML = '<table class="searchTable"><tr><th>序号</th></tr></table>'


class FakeClient:
    """按页码返回固定检索页的替身客户端；越界页返回空表。"""

    def __init__(self, pages: dict[int, str], details: dict[str, str] | None = None):
        self.pages = pages
        self.details = details or {}
        self.detail_calls: list[tuple[str, str]] = []
        self.requested_pages: list[int] = []

    def search_page(self, keyword, page):
        self.requested_pages.append(page)
        return self.pages.get(page, EMPTY_LIST_HTML)

    def detail(self, detail_id, seq):
        self.detail_calls.append((detail_id, seq))
        if detail_id not in self.details:
            raise CdeLiveError("no detail")
        return self.details[detail_id]


def test_parse_list_rows_reads_registry_and_detail_handle():
    rows = parse_list_rows(LIST_HTML)

    assert [row["registry_id"] for row in rows] == ["CTR20263476", "CTR20263746"]
    assert rows[0]["status_raw"] == "进行中 尚未招募"
    assert rows[0]["detail_id"] == "hash-mg"
    assert rows[0]["seq"] == "1"


def test_parse_detail_flattens_header_value_tables():
    values = parse_detail(DETAIL_HTML)

    assert values["试验分期"] == "其它 其他说明:II/III期"
    assert values["首次公示信息日期"] == "2026-09-14"
    assert values["申请人名称"] == "示例药业"


def test_is_mg_trial_rejects_unrelated_indication():
    assert is_mg_trial("CG001 注射液研究", "全身型重症肌无力（gMG）")
    assert is_mg_trial("Batoclimab study", "Myasthenia Gravis")
    assert not is_mg_trial("EIK1001", "IV期非小细胞肺癌的治疗")


def test_collect_mg_trials_paginates_and_filters_non_mg_rows():
    client = FakeClient({1: LIST_HTML}, {"hash-mg": DETAIL_HTML})

    records, meta = collect_mg_trials(client, keyword="重症肌无力")

    assert meta["declared_total"] == 52
    assert meta["total_pages"] == 3
    assert meta["scanned_rows"] == 2
    assert meta["mg_rows"] == 1
    assert [record["registry_id"] for record in records] == ["CTR20263476"]
    assert records[0]["phase"] == "其它 其他说明:II/III期"
    assert records[0]["registered_date"] == "2026-09-14"
    assert client.detail_calls == [("hash-mg", "1")]


def test_collect_mg_trials_keeps_records_when_detail_fails():
    client = FakeClient({1: LIST_HTML}, {})

    records, meta = collect_mg_trials(client, keyword="重症肌无力")

    assert meta["detail_failures"] == ["CTR20263476"]
    assert records[0]["registry_id"] == "CTR20263476"
    assert records[0]["phase"] == ""


def test_collect_mg_trials_steps_through_all_pages():
    pages = {1: LIST_HTML, 2: LIST_HTML}
    client = FakeClient(pages, {"hash-mg": DETAIL_HTML})

    records, meta = collect_mg_trials(client, keyword="重症肌无力")

    assert meta["scanned_rows"] == 4
    assert len(records) == 2  # 同登记号去重由导入器负责，这里只验证翻页
    assert client.requested_pages == [1, 2, 3]
    assert len(client.detail_calls) == 2


def test_parse_rss_extracts_items_and_absolute_links():
    items = parse_rss(RSS_XML)

    assert [item["registry_id"] for item in items] == ["CTR20269999", "CTR20264035"]
    assert items[0]["url"].startswith("https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml")
    assert items[0]["published_date"] == "2026-10-23"
    assert is_mg_trial(items[0]["title"])
    assert not is_mg_trial(items[1]["title"])


def test_rss_watch_requests_keyword_scoped_feed():
    """RSS 的铁律：必须带 keywords 参数，否则返回全站最近 20 条无关登记。"""
    class RssClient:
        def __init__(self):
            self.keywords = []

        def rss(self, keyword=None):
            self.keywords.append(keyword)
            return RSS_XML

    client = RssClient()
    result = cde_live.rss_watch(client, keyword="重症肌无力")

    assert client.keywords == ["重症肌无力"]
    assert result["keyword"] == "重症肌无力"
    assert len(result["items"]) == 2
    assert result["checked_at"]


def test_parse_rss_filters_nothing_when_platform_already_scoped():
    """平台已按主题过滤，解析层不再二次裁剪，避免漏掉登记。"""
    items = parse_rss(RSS_XML)

    assert len(items) == 2


def test_refresh_script_due_gate_uses_generated_at(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import importlib.util

    script = Path(__file__).resolve().parent.parent / "scripts" / "refresh-cde-live-cache.py"
    spec = importlib.util.spec_from_file_location("refresh_cde_live_cache", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "generated_at": (datetime(2026, 10, 20, tzinfo=timezone.utc)).isoformat(),
        "records": [{"registry_id": "CTR1"}],
    }), encoding="utf-8")

    due, last = module.is_due(cache, 7, now=datetime(2026, 10, 24, tzinfo=timezone.utc))
    assert due is False
    assert last.startswith("2026-10-20")

    due, _ = module.is_due(cache, 7, now=datetime(2026, 10, 20, tzinfo=timezone.utc) + timedelta(days=8))
    assert due is True

    missing = tmp_path / "missing.json"
    assert module.is_due(missing, 7)[0] is True
    assert module.is_due(cache, 0)[0] is True