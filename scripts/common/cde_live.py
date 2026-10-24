"""CDE 药物临床试验登记与信息公示平台的检索、详情与 RSS 订阅链路。

平台列表页默认每页 20 条，站点只允许通过表单 POST 检索，因此这里显式
翻页到「共 N 页」结束；详情页提供分期、申办者、首次公示日期等列表页
没有的字段。

RSS 带 ``keywords`` 参数时只返回该主题最近 20 条登记，可作为本主题的
新登记早报；但它不含状态与分期、也不反映既有试验的状态变化，因此缓存
更新仍以全量检索为准。
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.chinadrugtrials.org.cn"
LIST_URL = f"{BASE_URL}/clinicaltrials.searchlist.dhtml"
DETAIL_URL = f"{BASE_URL}/clinicaltrials.searchlistdetail.dhtml"
RSS_URL = f"{BASE_URL}/clinicaltrials.search.rss.dhtml"
DEFAULT_KEYWORD = "重症肌无力"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# 疾病检索会带出少量无关记录（平台为模糊匹配），统一按疾病名做二次门控
MG_TERMS = ("重症肌无力", "myasthenia gravis", "myasthenia")
MAX_PAGES = 40


class CdeLiveError(RuntimeError):
    """CDE 抓取链路不可用。"""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _page_count(html: str) -> int | None:
    match = re.search(r"共\s*<i>(\d+)</i>\s*页", html)
    return int(match.group(1)) if match else None


def _record_count(html: str) -> int | None:
    match = re.search(r"共\s*<i>(\d+)</i>\s*条记录", html)
    return int(match.group(1)) if match else None


def is_mg_trial(*values: Any) -> bool:
    """按疾病名判断是否为 MG 相关登记。"""
    text = " ".join(_clean(value) for value in values if value).lower()
    return any(term.lower() in text for term in MG_TERMS)


def parse_list_rows(html: str) -> list[dict[str, str]]:
    """解析检索结果列表，返回登记号、状态、药物、适应症与详情页定位信息。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for tr in soup.select("table.searchTable tr"):
        cells = tr.find_all("td")
        link = tr.find("a", onclick=True)
        if len(cells) < 6 or link is None or not link.get("id"):
            continue
        values = [_clean(cell.get_text(" ")) for cell in cells]
        rows.append(
            {
                "seq": values[0],
                "registry_id": values[1],
                "status_raw": values[2],
                "drug_name": values[3],
                "indication": values[4],
                "title": values[5],
                "detail_id": link["id"],
            }
        )
    return rows


def parse_detail(html: str) -> dict[str, str]:
    """把详情页的「标题-值」表格摊平为字典，取首次出现的值。"""
    soup = BeautifulSoup(html, "html.parser")
    values: dict[str, str] = {}
    for th in soup.find_all("th"):
        key = _clean(th.get_text(" "))
        cell = th.find_next_sibling("td")
        if key and cell is not None and key not in values:
            values[key] = _clean(cell.get_text(" "))
    return values


class CdeClient:
    """带会话 Cookie 的 CDE 客户端；平台要求先访问首页再检索。"""

    def __init__(self, *, delay_seconds: float = 0.3, timeout: int = 60) -> None:
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        self._bootstrapped = False

    def _bootstrap(self) -> None:
        if self._bootstrapped:
            return
        response = self.session.get(f"{BASE_URL}/", timeout=self.timeout)
        response.raise_for_status()
        self._bootstrapped = True

    def _sleep(self) -> None:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)

    def search_page(self, keyword: str, page: int) -> str:
        self._bootstrap()
        response = self.session.post(
            LIST_URL,
            data={"keywords": keyword, "currentpage": str(page), "rule": "CTR", "sort": "desc"},
            timeout=self.timeout,
            headers={"Referer": LIST_URL, "Origin": BASE_URL},
        )
        response.raise_for_status()
        text = response.text
        if "searchTable" not in text:
            raise CdeLiveError(f"CDE 检索页未返回结果表（第 {page} 页）")
        self._sleep()
        return text

    def detail(self, detail_id: str, seq: str) -> str:
        self._bootstrap()
        response = self.session.post(
            DETAIL_URL,
            data={"id": detail_id, "ckm_index": seq},
            timeout=self.timeout,
            headers={"Referer": LIST_URL},
        )
        response.raise_for_status()
        text = response.text
        if "searchDetailTable" not in text:
            raise CdeLiveError(f"CDE 详情页结构异常：{detail_id}")
        self._sleep()
        return text

    def rss(self, keyword: str | None = None) -> str:
        """抓取 RSS；带 ``keywords`` 参数时平台只返回该主题的最近登记。"""
        self._bootstrap()
        params = {"keywords": keyword} if keyword else None
        response = self.session.get(
            RSS_URL, params=params, timeout=self.timeout, headers={"Referer": f"{BASE_URL}/"}
        )
        response.raise_for_status()
        if "<rss" not in response.text:
            raise CdeLiveError("CDE RSS 未返回订阅文档")
        return response.text


def collect_mg_trials(
    client: CdeClient | None = None,
    *,
    keyword: str = DEFAULT_KEYWORD,
    max_pages: int = MAX_PAGES,
    with_detail: bool = True,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """翻页抓取检索结果，并对 MG 记录抓取详情页字段。"""
    active = client or CdeClient()
    rows: list[dict[str, str]] = []
    total_pages: int | None = None
    declared_total: int | None = None
    page = 1
    while page <= max_pages:
        html = active.search_page(keyword, page)
        total_pages = total_pages or _page_count(html)
        declared_total = declared_total or _record_count(html)
        page_rows = parse_list_rows(html)
        if not page_rows:
            break
        rows.extend(page_rows)
        if total_pages and page >= total_pages:
            break
        page += 1

    mg_rows = [row for row in rows if is_mg_trial(row["title"], row["indication"], row["drug_name"])]
    failures: list[str] = []
    records: list[dict[str, str]] = []
    for row in mg_rows:
        record = {
            "registry_id": row["registry_id"],
            "title": row["title"],
            "drug_name": row["drug_name"],
            "indication": row["indication"],
            "status": _clean(row["status_raw"]),
            "status_raw": _clean(row["status_raw"]),
            "official_url": f"https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistpage.dhtml?searchtype=keyword&keyword={row['registry_id']}",
        }
        if with_detail:
            try:
                detail = parse_detail(active.detail(row["detail_id"], row["seq"]))
            except Exception:
                failures.append(row["registry_id"])
                detail = {}
            record.update(
                {
                    "phase": detail.get("试验分期", ""),
                    "sponsor": detail.get("申请人名称", ""),
                    "registered_date": detail.get("首次公示信息日期", ""),
                    "professional_title": detail.get("试验专业题目", ""),
                    "drug_type": detail.get("药物类型", ""),
                    "design": detail.get("设计类型", ""),
                    "enrollment_target": detail.get("目标入组人数", ""),
                    "enrollment_actual": detail.get("已入组人数", ""),
                }
            )
        records.append(record)

    meta = {
        "keyword": keyword,
        "scanned_rows": len(rows),
        "declared_total": declared_total,
        "total_pages": total_pages,
        "mg_rows": len(mg_rows),
        "detail_failures": failures,
    }
    if not records:
        raise CdeLiveError("CDE 检索没有返回任何 MG 记录")
    return records, meta


def parse_rss(xml_text: str) -> list[dict[str, str]]:
    """解析 CDE RSS 条目：guid 为登记号，link 为详情页相对地址。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise CdeLiveError(f"CDE RSS 解析失败: {exc}") from exc
    items: list[dict[str, str]] = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        guid = _clean(item.findtext("guid"))
        link = _clean(item.findtext("link"))
        pub_date = _clean(item.findtext("pubDate"))
        if not guid:
            continue
        items.append(
            {
                "registry_id": guid,
                "title": title,
                "url": link if link.startswith("http") else f"{BASE_URL}{link}",
                "published_date": pub_date,
            }
        )
    return items


def rss_watch(client: CdeClient | None = None, *, keyword: str = DEFAULT_KEYWORD) -> dict[str, Any]:
    """抓取按主题过滤的 RSS，返回最近登记与其中尚未进入缓存的条目。

    带 ``keywords`` 时平台只返回该主题最近 20 条登记，是本主题的「新登记
    早报」。它不含状态与分期，也不反映既有试验的状态变化，因此只用于
    提示新增登记与核对缓存覆盖，不替代全量检索。
    """
    active = client or CdeClient()
    items = parse_rss(active.rss(keyword))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "keyword": keyword,
        "items": items,
    }