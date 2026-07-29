"""ChiCTR 官方检索页与 XML 下载链路。

站点由阿里云 WAF 保护。自动刷新时从 ``CHICTR_COOKIE`` 读取运营人员
提供的短期 Cookie；Cookie 只存在于运行环境，不写入缓存、日志或仓库。
"""

from __future__ import annotations

import html
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .io import atomic_write_json


BASE_URL = "https://www.chictr.org.cn/"
SEARCH_URL = urljoin(BASE_URL, "searchproj.html")
DEFAULT_QUERIES = ("重症肌无力", "Myasthenia Gravis")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BLOCK_MARKERS = (
    "your request has been blocked",
    "访问被阻断",
    "errors.aliyun.com",
    "<title>405</title>",
)

XML_ALIASES = {
    "registry_id": ("trial_id", "registration_number", "regno"),
    "reg_name": ("reg_name", "registry_name"),
    "date_registration": ("date_registration", "registration_date"),
    "primary_sponsor": ("primary_sponsor",),
    "public_title": ("public_title",),
    "scientific_title": ("scientific_title",),
    "date_enrolment": ("date_enrolment", "enrolment_date"),
    "target_size": ("target_size",),
    "recruitment_status": ("recruitment_status",),
    "study_type": ("study_type",),
    "study_design": ("study_design",),
    "phase": ("phase", "study_phase"),
    "hc_freetext": ("hc_freetext", "health_condition"),
    "i_freetext": ("i_freetext", "intervention"),
    "results_date_completed": ("results_date_completed",),
    "results_date_posted": ("results_date_posted",),
    "results_date_first_publication": ("results_date_first_publication",),
    "results_IPD_plan": ("results_ipd_plan",),
    "contact_scientific_name": ("contact_scientific_name",),
    "contact_scientific_affiliation": ("contact_scientific_affiliation",),
    "contact_public_name": ("contact_public_name",),
    "contact_public_affiliation": ("contact_public_affiliation",),
    "countries": ("countries", "country"),
    "inclusion_criteria": ("inclusion_criteria",),
    "exclusion_criteria": ("exclusion_criteria",),
    "agemin": ("agemin", "min_age"),
    "agemax": ("agemax", "max_age"),
    "gender": ("gender",),
}


class ChiCTRLiveError(RuntimeError):
    """ChiCTR 实时刷新不可用。"""


def parse_timestamp(value: Any) -> datetime | None:
    """宽容解析缓存中的 ISO 时间。"""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_refresh_due(payload: dict[str, Any], *, interval_days: int = 28, now: datetime | None = None) -> bool:
    """最近一次成功核对超过指定天数时才触发实时刷新。"""
    if interval_days <= 0:
        return True
    reference = parse_timestamp(payload.get("last_verified") or payload.get("scraped_at"))
    if reference is None:
        return True
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return current - reference >= timedelta(days=interval_days)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].strip().lower()


def _flatten_xml(root: ET.Element) -> dict[str, list[str]]:
    values: dict[str, list[str]] = defaultdict(list)
    for element in root.iter():
        text = _clean_text(element.text)
        if text:
            values[_local_tag(element.tag)].append(text)
    return values


def _first(values: dict[str, list[str]], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        candidates = values.get(alias.lower()) or []
        if candidates:
            return candidates[0]
    return ""


def parse_xml_record(xml_text: str, *, proj_id: str = "") -> dict[str, Any]:
    """把 ChiCTR 官方 XML 转成缓存使用的公开字段。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ChiCTRLiveError(f"ChiCTR XML 解析失败: {exc}") from exc
    values = _flatten_xml(root)
    record = {key: _first(values, aliases) for key, aliases in XML_ALIASES.items()}
    registry_id = record.pop("registry_id")
    if not registry_id:
        raise ChiCTRLiveError("ChiCTR XML 缺少注册号")
    record["results_IPD_plan"] = record.pop("results_IPD_plan")
    title = record.get("scientific_title") or record.get("public_title")
    return {
        "registry_id": registry_id,
        "proj_id": str(proj_id),
        "title": title,
        "study_type": record.get("study_type") or "Unknown",
        "registered_date": record.get("date_registration"),
        **record,
        "url": urljoin(BASE_URL, f"showproj.html?proj={proj_id}") if proj_id else BASE_URL,
    }


def extract_project_ids(page_html: str) -> list[str]:
    """从官方检索结果页提取项目编号，保留页面顺序并去重。"""
    soup = BeautifulSoup(page_html, "html.parser")
    result: list[str] = []
    for link in soup.select('a[href*="showproj"]'):
        match = re.search(r"[?&]proj=(\d+)", str(link.get("href") or ""))
        if match and match.group(1) not in result:
            result.append(match.group(1))
    return result


def extract_xml_url(detail_html: str) -> str:
    """从详情页提取官方加密 DownloadXml 链接。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for link in soup.select('a[href*="DownloadXml"]'):
        href = str(link.get("href") or "").strip()
        if href:
            return urljoin(BASE_URL, href)
    match = re.search(
        r"""(?:href=["'])?([^"'<>]*?/bin/chictr/DownloadXml\?path=[^"'<> ]+)""",
        detail_html,
        re.I,
    )
    return urljoin(BASE_URL, html.unescape(match.group(1))) if match else ""


class ChiCTRClient:
    """带 WAF Cookie 的节流官方客户端。"""

    def __init__(
        self,
        *,
        requests_module=None,
        cookie: str | None = None,
        timeout: float = 45,
        delay_seconds: float = 0.25,
    ):
        if requests_module is None:
            import requests as requests_module
        self.session = requests_module.Session()
        self.timeout = timeout
        self.delay_seconds = max(0, delay_seconds)
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": BASE_URL,
        })
        active_cookie = cookie if cookie is not None else os.environ.get("CHICTR_COOKIE", "")
        if active_cookie:
            self.session.headers.update({"Cookie": active_cookie})

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        text = response.text
        low = text.lower()
        if any(marker in low for marker in BLOCK_MARKERS):
            raise ChiCTRLiveError("ChiCTR WAF 阻断了本次请求")
        if not text.strip():
            raise ChiCTRLiveError("ChiCTR 返回空响应")
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return text


def discover_project_ids(
    client: ChiCTRClient,
    *,
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    max_pages: int = 30,
) -> list[str]:
    """按中英文疾病名检索全部结果页。"""
    all_ids: list[str] = []
    for query in queries:
        empty_pages = 0
        for page in range(1, max_pages + 1):
            params = {
                "page": page,
                "studyailment": query,
                "btngo": "btn",
            }
            found = extract_project_ids(client.get_text(SEARCH_URL, params=params))
            new_ids = [proj_id for proj_id in found if proj_id not in all_ids]
            all_ids.extend(new_ids)
            if not found or not new_ids:
                empty_pages += 1
            else:
                empty_pages = 0
            if empty_pages >= 2:
                break
    if not all_ids:
        raise ChiCTRLiveError("ChiCTR 检索未返回任何项目")
    return all_ids


def scrape_chictr_records(
    client: ChiCTRClient,
    *,
    old_records: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """检索详情并下载 XML；少量失败时保留对应的最后良好记录。"""
    project_ids = discover_project_ids(client)
    previous_by_project = {
        str(record.get("proj_id") or ""): record
        for record in old_records or []
        if record.get("proj_id")
    }
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    with_xml = 0
    for proj_id in project_ids:
        try:
            detail_url = urljoin(BASE_URL, f"showproj.html?proj={proj_id}")
            detail_html = client.get_text(detail_url)
            xml_url = extract_xml_url(detail_html)
            if not xml_url:
                raise ChiCTRLiveError("详情页没有 XML 链接")
            record = parse_xml_record(client.get_text(xml_url), proj_id=proj_id)
            records.append(record)
            with_xml += 1
        except Exception:
            fallback = previous_by_project.get(proj_id)
            if fallback:
                records.append(fallback)
            else:
                failures.append(proj_id)

    by_id = {
        str(record.get("registry_id") or ""): record
        for record in records
        if record.get("registry_id")
    }
    minimum = max(1, int(len(project_ids) * 0.75))
    if len(by_id) < minimum:
        raise ChiCTRLiveError(
            f"ChiCTR 仅获得 {len(by_id)}/{len(project_ids)} 条有效记录，未达到安全阈值"
        )
    return sorted(by_id.values(), key=lambda item: item["registry_id"], reverse=True), {
        "total_found": len(project_ids),
        "records_scraped": len(by_id),
        "records_with_xml": with_xml,
        "failed_project_ids": failures,
    }


def refresh_chictr_live(
    cache_path: Path,
    *,
    interval_days: int = 28,
    force: bool = False,
    now: datetime | None = None,
    client: ChiCTRClient | None = None,
) -> dict[str, Any]:
    """到期时运行官方检索；失败不改写最后良好缓存。"""
    cached = {}
    if cache_path.exists():
        import json

        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    if not force and not is_refresh_due(cached, interval_days=interval_days, now=now):
        return {**cached, "refresh_status": "not_due"}

    try:
        active_client = client or ChiCTRClient()
        records, meta = scrape_chictr_records(
            active_client,
            old_records=cached.get("records") or [],
        )
        refreshed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        payload = {
            "schema_version": "1.0",
            "source": "ChiCTR official registry",
            "source_url": BASE_URL,
            "mode": "live",
            "query": "重症肌无力 (Myasthenia Gravis)",
            **meta,
            "scraped_at": refreshed_at,
            "last_verified": refreshed_at,
            "records": records,
        }
        atomic_write_json(cache_path, payload)
        return {**payload, "refresh_status": "updated"}
    except Exception as exc:
        return {
            **cached,
            "mode": "cache",
            "refresh_status": "failed",
            "warning": str(exc),
        }
