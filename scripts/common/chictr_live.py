"""ChiCTR 官方检索页与 XML 下载链路。

站点由阿里云 WAF 保护。优先使用 ``CHICTR_COOKIE`` 提供的短期 Cookie；
未提供时用 curl_cffi 的浏览器指纹发起请求，遇到 ``acw_sc__v2`` 挑战则用
本机无头浏览器求解一次后复用会话。Cookie 只存在于运行环境，不写入缓存、
日志或仓库。
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
CHALLENGE_MARKER = "acw_sc__v2"
CHALLENGE_COOKIE = "acw_sc__v2"


class ChiCTRLiveError(RuntimeError):
    """ChiCTR 实时刷新不可用。"""


def solve_waf_challenge(challenge_html: str, url: str, *, acw_tc: str = "") -> str:
    """用无头浏览器执行阿里云 WAF 挑战，返回 ``acw_sc__v2`` 值。

    挑战脚本依赖真实 DOM 与 history 行为，纯 Python 复刻其混淆逻辑极易失效；
    这里让浏览器执行官网脚本，只把挑战响应注入首次请求，第二次请求被拦截，
    因此不会真正打到站点，只用于取出浏览器算出的 Cookie。
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # Playwright 未安装时不阻断整个周更
        raise ChiCTRLiveError(f"未安装 Playwright，无法自动求解 ChiCTR WAF 挑战: {exc}") from exc

    last_error = ""
    for engine in ("chrome", "chromium"):
        try:
            with sync_playwright() as playwright:
                launcher = getattr(playwright, "chromium")
                browser = (
                    launcher.launch(channel=engine, headless=True)
                    if engine == "chrome"
                    else launcher.launch(headless=True)
                )
                try:
                    context = browser.new_context(locale="zh-CN")
                    if acw_tc:
                        context.add_cookies(
                            [{"name": "acw_tc", "value": acw_tc, "domain": ".chictr.org.cn", "path": "/"}]
                        )
                    page = context.new_page()
                    state = {"count": 0}

                    def _handler(route, _request):
                        state["count"] += 1
                        if state["count"] == 1:
                            route.fulfill(
                                status=200,
                                content_type="text/html; charset=UTF-8",
                                body=challenge_html,
                            )
                        else:
                            route.abort()

                    page.route("**/searchproj.html*", _handler)
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)
                    for cookie in context.cookies():
                        if cookie.get("name") == CHALLENGE_COOKIE and cookie.get("value"):
                            return str(cookie["value"])
                    last_error = "浏览器未生成 acw_sc__v2"
                finally:
                    browser.close()
        except Exception as exc:
            last_error = str(exc)
    raise ChiCTRLiveError(f"ChiCTR WAF 挑战求解失败: {last_error}")


def _build_session(requests_module=None):
    """优先用 curl_cffi 的浏览器指纹，回退到 requests。"""
    if requests_module is not None:
        return requests_module.Session(), False
    try:
        from curl_cffi import requests as curl_requests

        return curl_requests.Session(impersonate="chrome"), True
    except Exception:
        import requests as plain_requests

        return plain_requests.Session(), False

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
        solve_challenge: bool = True,
    ):
        self.session, self.impersonated = _build_session(requests_module)
        self.timeout = timeout
        self.delay_seconds = max(0, delay_seconds)
        self.solve_challenge = solve_challenge
        self._challenge_solved = False
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": BASE_URL,
        })
        active_cookie = cookie if cookie is not None else os.environ.get("CHICTR_COOKIE", "")
        if active_cookie:
            self.session.headers.update({"Cookie": active_cookie})

    def _session_cookies(self) -> dict[str, str]:
        cookies = getattr(self.session, "cookies", None)
        if cookies is None:
            return {}
        try:
            return {str(key): str(value) for key, value in cookies.get_dict().items()}
        except Exception:
            return {}

    def _set_cookie(self, name: str, value: str) -> None:
        cookies = getattr(self.session, "cookies", None)
        if cookies is None:
            return
        try:
            cookies.set(name, value, domain="www.chictr.org.cn")
        except Exception:
            self.session.cookies.set(name, value)

    def _warm_up(self, url: str) -> None:
        """先访问首页获取 acw_tc，检索页才不会直接落到拦截页。"""
        try:
            self.session.get(BASE_URL, timeout=self.timeout)
        except Exception:
            pass

    def _try_solve_challenge(self, url: str, challenge_html: str) -> bool:
        if self._challenge_solved or not self.solve_challenge:
            return False
        try:
            token = solve_waf_challenge(
                challenge_html,
                url,
                acw_tc=self._session_cookies().get("acw_tc", ""),
            )
        except ChiCTRLiveError:
            return False
        self._set_cookie(CHALLENGE_COOKIE, token)
        self._challenge_solved = True
        return True

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        if not self._challenge_solved and not self._session_cookies().get("acw_tc"):
            self._warm_up(url)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        text = response.text
        low = text.lower()
        challenged = CHALLENGE_MARKER in text and "arg1" in text
        blocked = any(marker in low for marker in BLOCK_MARKERS)
        if challenged or blocked:
            # 挑战页需要用同一 URL 求解后重试；拦截页则重试一次即可
            if not challenged and any(marker in low for marker in BLOCK_MARKERS):
                self._warm_up(url)
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                text, low = response.text, response.text.lower()
                challenged = CHALLENGE_MARKER in text and "arg1" in text
                blocked = any(marker in low for marker in BLOCK_MARKERS)
            if challenged:
                target = response.url if hasattr(response, "url") else url
                if self._try_solve_challenge(str(target), text):
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    response.raise_for_status()
                    text, low = response.text, response.text.lower()
                    blocked = any(marker in low for marker in BLOCK_MARKERS)
                else:
                    raise ChiCTRLiveError("ChiCTR WAF 挑战无法自动求解，请提供 CHICTR_COOKIE")
            if blocked:
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
