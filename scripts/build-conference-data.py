#!/usr/bin/env python3
"""
build-conference-data.py — 构建会议摘要情报前端数据。

数据仅来自公开会议页面、PDF abstract book / abstract guide。脚本输出：
  - data/conference-data.json
  - data/conference-data.js

注：原始 PDF 缓存在 data/.conference_cache/，不进入公开仓库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("需要 PyMuPDF: pip install pymupdf") from exc


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
CACHE_DIR = DATA_DIR / ".conference_cache"
JSON_PATH = DATA_DIR / "conference-data.json"
JS_PATH = DATA_DIR / "conference-data.js"

SECTION_RE = re.compile(
    r"^(INTRODUCTION|ABSTRACT|BACKGROUND(?: AND AIMS)?|OBJECTIVE|OBJECTIVES|AIM|AIMS|"
    r"METHODS|RESULTS|SUMMARY/CONCLUSION|CONCLUSION|DISCLOSURE|DISCLOSURES)[: ]",
    re.I,
)
EAN_CODE_RE = re.compile(r"^((?:OPR|EPO|EPV|FW)\s*-\s*\d{3,4}(?:_\d+)?)\s*\|\s*(.*)$", re.I)
MG_RELEVANCE_RE = re.compile(
    r"("
    r"myasthenia\s+gravis|generalized\s+myasthenia|generalised\s+myasthenia|"
    r"ocular\s+myasthenia|myasthenic\s+crisis|\bgMG\b|MG-ADL|\bQMG\b|"
    r"MuSK[-\s]*(?:MG|myasthenia)|AChR[-\s]*(?:MG|myasthenia|Ab\+?\s+gMG)|"
    r"LRP4[-\s]*(?:MG|myasthenia)"
    r")",
    re.I,
)
MG_TITLE_RE = re.compile(
    r"("
    r"myasthenia\s+gravis|generalized\s+myasthenia|generalised\s+myasthenia|"
    r"ocular\s+myasthenia|myasthenic\s+crisis|\bgMG\b|"
    r"MuSK[-\s]*(?:MG|myasthenia\s+gravis)|AChR[-\s]*(?:MG|myasthenia\s+gravis|Ab\+?\s+gMG)|"
    r"LRP4[-\s]*(?:MG|myasthenia\s+gravis)"
    r")",
    re.I,
)
MG_ABSTRACT_FOCUS_RE = re.compile(
    r"("
    r"(?:patients?|cohort|participants?|subjects?|registry|trial|study)\s+(?:with|of|in)\s+"
    r"(?:generalized\s+|generalised\s+|ocular\s+)?myasthenia\s+gravis|"
    r"(?:generalized\s+|generalised\s+|ocular\s+)?myasthenia\s+gravis\s+"
    r"(?:patients?|cohort|participants?|registry|trial|study|treatment|therapy|symptoms?|outcomes?)|"
    r"myasthenic\s+crisis|MG-ADL|\bQMG\b"
    r")",
    re.I,
)
NON_MG_RELATED_RE = re.compile(
    r"(Lambert[-\s]*Eaton|Eaton[-\s]*Lambert|\bLEMS\b|\bLES\b|congenital\s+myasthenic\s+syndromes?|"
    r"congenital\s+myasthenic\s+disorders?|\bCMS\b|myasthenic\s+syndrome)",
    re.I,
)
EAN_DRUG_RE = re.compile(
    r"(efgartigimod|nipocalimab|rozanolixizumab|ravulizumab|eculizumab|zilucoplan|"
    r"cemdisiran|claseprubart|telitacicept|gefurulimab|inebilizumab)",
    re.I,
)

SOURCES = [
    {
        "id": "mgfa-international-2025",
        "meetingId": "mgfa-ic-2025",
        "parser": "numbered-poster",
        "startPage": 8,
        "sourceLabel": "MGFA International Conference",
        "title": "15th International Conference on Myasthenia Gravis and Related Disorders",
        "shortTitle": "MGFA IC 2025",
        "year": 2025,
        "date": "2025-05-12 to 2025-05-15",
        "location": "The Hague, The Netherlands",
        "presentationType": "Poster",
        "url": "https://myasthenia.org/wp-content/uploads/2024/08/MGFAInternationalConferenceAbstractList_05.07.2025.pdf",
        "pageUrl": "https://myasthenia.org/mgfa-international-conference/",
    },
    {
        "id": "mgfa-scientific-session-2025",
        "meetingId": "mgfa-scientific-2025",
        "parser": "simple-numbered",
        "startPage": 0,
        "sourceLabel": "MGFA Scientific Session",
        "title": "2025 MGFA Scientific Session Poster List & Abstracts",
        "shortTitle": "MGFA SS 2025",
        "year": 2025,
        "date": "2025-10",
        "location": "AANEM Annual Meeting",
        "presentationType": "Poster",
        "url": "https://myasthenia.org/wp-content/uploads/2025/10/2025-MGFA-Scientific-Session-Posters-MGFA-Scientific-Session.pdf",
        "pageUrl": "https://myasthenia.org/events/2026-scientific-session/",
    },
    {
        "id": "ean-2026-abstract-book",
        "meetingId": "ean-2026",
        "parser": "ean-book",
        "sourceLabel": "European Academy of Neurology",
        "title": "12th Congress of the European Academy of Neurology - Abstract Book",
        "shortTitle": "EAN 2026",
        "year": 2026,
        "date": "2026-06-27 to 2026-06-30",
        "location": "Geneva, Switzerland",
        "presentationType": "ePoster / Oral",
        "url": "https://www.ean.org/fileadmin/user_upload/ean/Congress-2026/Abstracts/ENE_v33_iS1_Congress_Abstract_Book.pdf",
        "pageUrl": "https://www.ean.org/congress2026/abstracts/important-information/ean-2026-congress-abstract-book",
    },
    {
        "id": "aan-2026-mirasmart",
        "meetingId": "aan-2026",
        "parser": "aan-mirasmart",
        "sourceLabel": "American Academy of Neurology",
        "title": "2026 American Academy of Neurology Annual Meeting Abstracts",
        "shortTitle": "AAN 2026",
        "year": 2026,
        "date": "2026-04-18 to 2026-04-22",
        "location": "Chicago, Illinois / Online",
        "presentationType": "Abstract",
        "url": "https://index.mirasmart.com/AAN2026/SearchResults.php?q=myasthenia",
        "baseUrl": "https://index.mirasmart.com/AAN2026/",
        "pageUrl": "https://www.aan.com/events/annual-meeting",
    },
]

SOURCE_MONITOR = [
    {
        "id": "mgfa-ic",
        "organization": "MGFA International Conference",
        "status": "已抓取",
        "nextAction": "监控第 16 届会议日期地点，官网称年底前公布。",
        "url": "https://myasthenia.org/mgfa-international-conference/",
        "evidence": "2025 年会议页面公开 Program 与 Poster Abstract Guide；官网列示 73 presentations / 241 posters。",
    },
    {
        "id": "mgfa-scientific",
        "organization": "MGFA Scientific Session",
        "status": "已抓取历史摘要 / 监控 2026",
        "nextAction": "2026 摘要已截止，待会后 poster list / abstracts PDF 公开后自动补抓。",
        "url": "https://myasthenia.org/events/2026-scientific-session/",
        "evidence": "2026 session 为 2026-09-29，含 oral presentations 与 poster session；2025 poster abstracts PDF 已公开。",
    },
    {
        "id": "aanem",
        "organization": "AANEM Annual Meeting",
        "status": "2025 Abstract Guide 已定位",
        "nextAction": "AANEM 2025 guide 为 FlippingBook 签名阅读器；已定位 myasthenia 检索页段，待抽取稳定文本层或 Wiley supplement 后结构化补抓。",
        "url": "https://online.flippingbook.com/view/442003187/",
        "evidence": "AANEM abstract information 页面链接 2025 Abstracts Guide；阅读器内 myasthenia 搜索可定位 MG 页段。2026 年会继续作为未来会议监控。",
    },
    {
        "id": "aan",
        "organization": "AAN Annual Meeting",
        "status": "已抓取 Mirasmart",
        "nextAction": "持续重扫 myasthenia / MG 相关结果；重点抽取高优先级临床试验、机制转换和中国相关摘要。",
        "url": "https://index.mirasmart.com/AAN2026/",
        "evidence": "AAN 2026 online abstract website 已上线，myasthenia 搜索结果可直接进入 abstract HTML。",
    },
    {
        "id": "ean",
        "organization": "European Academy of Neurology",
        "status": "已抓取",
        "nextAction": "按 MG 关键词筛选 Wiley/EAN abstract book，并保留 ePoster Virtual 仅题名作者的条目。",
        "url": "https://www.ean.org/congress2026",
        "evidence": "EAN 2026 abstract book 在线公开，官网说明 accepted abstracts 作为 European Journal of Neurology online supplement 发布。",
    },
]

FUTURE_MEETINGS = [
    {
        "meeting": "MGFA Scientific Session 2026",
        "organization": "MGFA / AANEM",
        "date": "2026-09-29",
        "location": "Signia by Hilton Orlando Bonnet Creek, Orlando, Florida",
        "status": "摘要已截止，待会后公开",
        "url": "https://myasthenia.org/events/2026-scientific-session/",
    },
    {
        "meeting": "AANEM Annual Meeting 2026",
        "organization": "AANEM",
        "date": "2026-09-29 to 2026-10-02",
        "location": "Orlando, Florida",
        "status": "Registration open；摘要结果待会议/期刊公开",
        "url": "https://www.aanem.org/meetings/annual-meeting",
    },
    {
        "meeting": "AAN Annual Meeting 2027",
        "organization": "AAN",
        "date": "TBD",
        "location": "TBD",
        "status": "待官网更新",
        "url": "https://www.aan.com/events/annual-meeting",
    },
    {
        "meeting": "EAN Congress 2027",
        "organization": "EAN",
        "date": "TBD",
        "location": "TBD",
        "status": "待官网更新",
        "url": "https://www.ean.org/congress2026",
    },
    {
        "meeting": "16th International Conference on MG and Related Disorders",
        "organization": "MGFA",
        "date": "TBD",
        "location": "TBD",
        "status": "官网称日期地点将于年底前公布",
        "url": "https://myasthenia.org/mgfa-international-conference/",
    },
]

COUNTRY_RULES = [
    ("中国", ["china", "chinese", "beijing", "shanghai", "fudan", "huashan", "guangzhou", "hong kong", "taiwan"]),
    ("美国", ["usa", "u.s.a", "united states", "boston", "new york", "california", "mayo clinic", "duke", "yale", "harvard"]),
    ("日本", ["japan", "tokyo", "osaka", "nagoya", "kyoto", "hanamaki"]),
    ("德国", ["germany", "berlin", "munich", "charité", "hamburg", "essen", "münster"]),
    ("意大利", ["italy", "milan", "naples", "rome", "palermo", "pavia", "florence"]),
    ("英国", ["united kingdom", "uk", "london", "birmingham", "oxford", "cambridge"]),
    ("法国", ["france", "paris", "marseille", "lyon"]),
    ("西班牙", ["spain", "barcelona", "madrid", "valencia"]),
    ("荷兰", ["netherlands", "leiden", "maastricht", "amsterdam"]),
    ("比利时", ["belgium", "ghent", "brussels", "beerse"]),
    ("加拿大", ["canada", "toronto", "ottawa", "vancouver"]),
    ("澳大利亚", ["australia", "sydney", "melbourne"]),
    ("瑞士", ["switzerland", "zurich", "geneva", "basel", "bulle"]),
    ("丹麦", ["denmark", "copenhagen"]),
    ("瑞典", ["sweden", "stockholm", "uppsala"]),
    ("波兰", ["poland", "warsaw", "katowice"]),
    ("土耳其", ["turkey", "türkiye", "istanbul"]),
    ("以色列", ["israel", "jerusalem"]),
    ("葡萄牙", ["portugal", "lisbon"]),
    ("希腊", ["greece", "athens"]),
    ("印度", ["india", "delhi", "mumbai"]),
    ("巴西", ["brazil", "sao paulo"]),
]

TOPIC_RULES = [
    ("FcRn", ["fcrn", "efgartigimod", "nipocalimab", "rozanolixizumab", "batoclimab"]),
    ("补体", ["complement", "eculizumab", "ravulizumab", "zilucoplan", "c5", "c1s", "claseprubart", "gefurulimab", "cemdisiran"]),
    ("B细胞/免疫重置", ["b cell", "b-cell", "rituximab", "inebilizumab", "cd19", "car t", "telitacicept"]),
    ("抗体分型", ["achr", "musk", "lrp4", "seronegative", "titin", "autoantibody"]),
    ("真实世界/登记", ["real-world", "real world", "registry", "claims", "retrospective", "observational", "cohort"]),
    ("安全性", ["safety", "adverse", "infection", "tolerability", "vaccination"]),
    ("疗效/结局", ["efficacy", "response", "improvement", "outcome", "qmg", "mg-adl"]),
    ("PRO/生活质量", ["quality of life", "qol", "patient-reported", "fatigue", "preference", "burden", "cost"]),
    ("危象/急性加重", ["crisis", "exacerbation", "hospitalization", "acute"]),
    ("胸腺瘤", ["thymoma", "tamg", "thymectomy"]),
    ("数字监测", ["digital", "wearable", "mobile application", "biomarker", "speech", "app"]),
    ("妊娠/儿童", ["pregnancy", "postpartum", "juvenile", "pediatric", "maternal", "fetal"]),
]

DRUG_RULES = [
    ("efgartigimod", ["efgartigimod", "vyvgart"]),
    ("rozanolixizumab", ["rozanolixizumab"]),
    ("nipocalimab", ["nipocalimab"]),
    ("ravulizumab", ["ravulizumab"]),
    ("eculizumab", ["eculizumab"]),
    ("zilucoplan", ["zilucoplan"]),
    ("batoclimab", ["batoclimab"]),
    ("telitacicept", ["telitacicept"]),
    ("rituximab", ["rituximab"]),
    ("inebilizumab", ["inebilizumab"]),
    ("gefurulimab", ["gefurulimab"]),
    ("claseprubart", ["claseprubart"]),
    ("cemdisiran", ["cemdisiran"]),
    ("tacrolimus", ["tacrolimus"]),
]


def clean_line(value: str) -> str:
    """清洗 PDF 提取出来的单行文本。"""
    value = value.replace("\xad", "").replace("\u2003", " ").replace("\u2009", " ")
    return re.sub(r"\s+", " ", value.strip())


def collapse_lines(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(line.strip() for line in lines if line.strip())).strip()


def cache_path_for_url(url: str) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".pdf"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    stem = Path(parsed.path).stem or "source"
    return CACHE_DIR / f"{stem}-{digest}{suffix}"


def download(url: str, refresh: bool = False) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path_for_url(url)
    if path.exists() and not refresh:
        return path
    headers = {"User-Agent": "MA-MG-HUB/1.0 (+conference abstract monitor)"}
    resp = requests.get(url, headers=headers, timeout=90)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def download_text(url: str, refresh: bool = False) -> str:
    """下载 HTML 并缓存；AAN Mirasmart 摘要页为 UTF-8。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path_for_url(url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    headers = {"User-Agent": "MA-MG-HUB/1.0 (+conference abstract monitor)"}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=90)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            text = resp.text
            path.write_text(text, encoding="utf-8")
            return text
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError(f"HTML download failed after retries: {url}") from last_error


def clean_html_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u200b", "")
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"\s+([,.;:!?%)\]])", r"\1", value)
    value = re.sub(r"([(\\[])\s+", r"\1", value)
    value = value.replace("Â®", "®")
    return value


def pdf_page_lines(path: Path, start_page: int = 0) -> list[tuple[int, list[str]]]:
    doc = fitz.open(str(path))
    pages: list[tuple[int, list[str]]] = []
    for page_index in range(start_page, len(doc)):
        lines = [clean_line(line) for line in doc[page_index].get_text("text").splitlines()]
        lines = [line for line in lines if line]
        pages.append((page_index + 1, lines))
    return pages


def parse_numbered_poster(path: Path, source: dict) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for page_number, lines in pdf_page_lines(path, source.get("startPage", 0)):
        start_idx = None
        poster_number = None
        raw_number = None
        for idx, line in enumerate(lines[:4]):
            if not re.fullmatch(r"\d{1,4}", line):
                continue
            lookahead = lines[idx + 1 : idx + 35]
            joined = " ".join(lookahead)
            has_abstract = any(SECTION_RE.search(item) for item in lookahead)
            if (("Authors:" in joined or "Author:" in joined or has_abstract) and not joined.startswith("Abstract Withdrawal")):
                raw_number = line
                numeric = int(line)
                if numeric <= 260:
                    poster_number = numeric
                elif int(line[-2:]) <= 260:
                    poster_number = int(line[-2:])
                elif int(line[-3:]) <= 260:
                    poster_number = int(line[-3:])
                start_idx = idx + 1
                break
        if start_idx is not None and poster_number is not None:
            if current:
                entries.append(current)
            current = {
                "number": poster_number,
                "rawNumber": raw_number,
                "startPage": page_number,
                "lines": lines[start_idx:],
            }
        elif current:
            current["lines"].extend(lines)
    if current:
        entries.append(current)
    return [parse_numbered_entry(item, source, labeled_authors=True) for item in entries]


def parse_simple_numbered(path: Path, source: dict) -> list[dict]:
    lines: list[tuple[int, str]] = []
    for page_number, page_lines in pdf_page_lines(path, source.get("startPage", 0)):
        for line in page_lines:
            if line in {"Poster Number", "Poster Title", "Authors", "Abstracts"}:
                continue
            lines.append((page_number, line))

    entries: list[dict] = []
    current: dict | None = None
    expected = 1
    for page_number, line in lines:
        if re.fullmatch(r"\d{1,3}", line) and int(line) == expected:
            if current:
                entries.append(current)
            current = {"number": expected, "rawNumber": line, "startPage": page_number, "lines": []}
            expected += 1
            continue
        if current:
            current["lines"].append(line)
    if current:
        entries.append(current)
    return [parse_numbered_entry(item, source, labeled_authors=False) for item in entries]


def parse_numbered_entry(entry: dict, source: dict, labeled_authors: bool) -> dict:
    lines = entry["lines"]
    section_idx = next((idx for idx, line in enumerate(lines) if SECTION_RE.search(line)), len(lines))
    preface = lines[:section_idx]
    abstract_lines = lines[section_idx:]

    title_lines: list[str]
    author_lines: list[str] = []
    affiliation_lines: list[str] = []

    author_label_idx = next((idx for idx, line in enumerate(preface) if line.startswith("Authors:") or line.startswith("Author:")), None)
    if labeled_authors and author_label_idx is not None:
        title_lines = preface[:author_label_idx]
        first_author_line = re.sub(r"^Authors?:\s*", "", preface[author_label_idx]).strip()
        if first_author_line:
            author_lines.append(first_author_line)
        for line in preface[author_label_idx + 1 :]:
            if re.match(r"^[0-9¹²³⁴⁵⁶⁷⁸⁹]", line) or re.search(r"\b(Department|University|Hospital|Institute|School|Faculty|Center|Centre|Clinic)\b", line, re.I):
                affiliation_lines.append(line)
            elif affiliation_lines:
                affiliation_lines.append(line)
            else:
                author_lines.append(line)
    else:
        author_start = next(
            (
                idx
                for idx, line in enumerate(preface)
                if idx > 0 and ("," in line or ";" in line) and re.search(r"[a-z]", line)
            ),
            None,
        )
        if author_start is None:
            title_lines = preface
        else:
            title_lines = preface[:author_start]
            for line in preface[author_start:]:
                if re.match(r"^[0-9¹²³⁴⁵⁶⁷⁸⁹]", line) or re.search(r"\b(Department|University|Hospital|Institute|School|Faculty|Center|Centre|Clinic)\b", line, re.I):
                    affiliation_lines.append(line)
                elif affiliation_lines:
                    affiliation_lines.append(line)
                else:
                    author_lines.append(line)

    text = collapse_lines(abstract_lines)
    text = re.split(r"\bDISCLOSURES?:", text, flags=re.I)[0].strip()
    title = collapse_lines(title_lines)
    authors = collapse_lines(author_lines)
    affiliations = collapse_lines(affiliation_lines)
    return make_abstract_item(
        source=source,
        local_id=f"poster-{entry['number']}",
        title=title,
        authors=authors,
        abstract=text,
        page=entry["startPage"],
        presentation_type=source["presentationType"],
        affiliations=affiliations,
    )


def parse_ean_book(path: Path, source: dict) -> list[dict]:
    doc = fitz.open(str(path))
    raw_entries: list[dict] = []
    current: dict | None = None
    for page_index, page in enumerate(doc):
        for raw in page.get_text("text").splitlines():
            line = clean_line(raw)
            if not line:
                continue
            if re.match(r"^\d+ of \d+$", line) or line == "European Journal of Neurology, 2026":
                continue
            match = EAN_CODE_RE.match(line)
            if match:
                if current:
                    raw_entries.append(current)
                code = match.group(1).replace(" ", "")
                first_line = match.group(2).strip()
                current = {"code": code, "page": page_index + 1, "lines": [first_line] if first_line else []}
            elif current:
                current["lines"].append(line)
    if current:
        raw_entries.append(current)

    parsed = []
    for entry in raw_entries:
        item = parse_ean_entry(entry, source)
        if not item:
            continue
        parsed.append(item)
    return dedupe_items(parsed)


def parse_ean_entry(entry: dict, source: dict) -> dict | None:
    lines = entry["lines"]
    section_idx = next((idx for idx, line in enumerate(lines) if SECTION_RE.search(line)), len(lines))
    preface = lines[:section_idx]
    abstract_lines = lines[section_idx:]
    author_start = next((idx for idx, line in enumerate(preface) if re.match(r"^[A-ZÀ-ÖØ-Þ]\.", line)), None)
    if author_start is None:
        title_lines = preface
        author_lines: list[str] = []
        affiliation_lines: list[str] = []
    else:
        title_lines = preface[:author_start]
        author_lines = []
        affiliation_lines = []
        for line in preface[author_start:]:
            if re.match(r"^[0-9]", line) or affiliation_lines:
                affiliation_lines.append(line)
            else:
                author_lines.append(line)

    title = collapse_lines(title_lines)
    authors = collapse_lines(author_lines)
    affiliations = collapse_lines(affiliation_lines)
    abstract = collapse_lines(abstract_lines)
    abstract = re.split(r"\bDisclosure:", abstract, flags=re.I)[0].strip()
    if not is_mg_text(title, abstract):
        return None

    presentation_type = "Oral" if entry["code"].startswith("OPR") else "ePoster"
    if entry["code"].startswith("EPV"):
        presentation_type = "ePoster Virtual"
    return make_abstract_item(
        source=source,
        local_id=entry["code"],
        title=title,
        authors=authors,
        abstract=abstract,
        page=entry["page"],
        presentation_type=presentation_type,
        affiliations=affiliations,
    )


def extract_aan_value(result_node, label_name: str) -> str:
    for item in result_node.select("p.item"):
        label = item.select_one(".label")
        value = item.select_one(".value")
        if not label or not value:
            continue
        label_text = label.get_text(" ", strip=True).rstrip(":")
        if label_text != label_name:
            continue
        links = [clean_html_text(link.get_text(" ", strip=True)) for link in value.select("a")]
        links = [link for link in links if link]
        if links:
            return "; ".join(links)
        return clean_html_text(value.get_text(" ", strip=True))
    return ""


def parse_aan_search_page(html: str, source: dict) -> tuple[list[dict], int]:
    soup = BeautifulSoup(html, "html.parser")
    total = 0
    title_node = soup.select_one(".pagination .title")
    if title_node:
        match = re.search(r"of\s+(\d+)", title_node.get_text(" ", strip=True), re.I)
        if match:
            total = int(match.group(1))

    results = []
    for result in soup.select(".search-result"):
        title_node = result.find("h2")
        title = clean_html_text(title_node.get_text(" ", strip=True)) if title_node else ""
        abstract_link = ""
        for link in result.select("ul.downloads a[href]"):
            href = link.get("href") or ""
            text = link.get_text(" ", strip=True)
            if "PDFfiles/AAN2026-" in href and "Disclosure" not in href and "Abstract" in text:
                abstract_link = urljoin(source["baseUrl"], href)
                break
        if not title or not abstract_link:
            continue
        results.append({
            "title": title,
            "authors": extract_aan_value(result, "Author"),
            "session": extract_aan_value(result, "Session Name"),
            "topic": extract_aan_value(result, "Topic"),
            "program": extract_aan_value(result, "Program Number"),
            "affiliations": extract_aan_value(result, "Author Institution"),
            "abstractUrl": abstract_link,
        })
    return results, total


def infer_aan_presentation_type(session: str, program: str) -> str:
    text = f"{session} {program}"
    if re.search(r"plenary|\bPL\d", text, re.I):
        return "Plenary"
    if re.search(r"\bLS\d", text, re.I):
        return "Scientific Session"
    if re.match(r"^P\d+", program or "", re.I):
        return "Poster"
    if re.match(r"^S\d+", program or "", re.I):
        return "Scientific Session"
    return "Abstract"


def parse_aan_abstract_record(record: dict, source: dict, refresh: bool) -> dict | None:
    html = download_text(record["abstractUrl"], refresh=refresh)
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(".SubmissionTitle")
    body_node = soup.select_one(".SubmissionBody")
    title = clean_html_text(title_node.get_text(" ", strip=True)) if title_node else record["title"]
    abstract = clean_html_text(body_node.get_text(" ", strip=True)) if body_node else ""
    if not is_mg_text(title, abstract):
        return None

    code_match = re.search(r"AAN2026-(\d+)\.html", record["abstractUrl"])
    local_id = record["program"] or f"abstract-{code_match.group(1) if code_match else hashlib.sha1(record['abstractUrl'].encode('utf-8')).hexdigest()[:8]}"
    presentation_type = infer_aan_presentation_type(record.get("session", ""), record.get("program", ""))
    item = make_abstract_item(
        source=source,
        local_id=local_id,
        title=title,
        authors=record.get("authors", ""),
        abstract=abstract,
        page=0,
        presentation_type=presentation_type,
        affiliations=record.get("affiliations", ""),
    )
    item["sourceUrl"] = record["abstractUrl"]
    item["searchUrl"] = source["url"]
    item["sessionName"] = record.get("session", "")
    item["programNumber"] = record.get("program", "")
    item["aanTopic"] = record.get("topic", "")
    if presentation_type == "Plenary":
        item["priorityScore"] += 2
    if re.search(r"abstracts? of distinction", record.get("session", ""), re.I):
        item["priorityScore"] += 1
    item["analysisZh"] = make_zh_summary(item["title"], item["abstract"], item["topics"], item["researchType"], item["drugs"], item["countries"])
    return item


def parse_aan_mirasmart(source: dict, refresh: bool = False) -> list[dict]:
    first_html = download_text(source["url"], refresh=refresh)
    first_results, total = parse_aan_search_page(first_html, source)
    all_records = first_results[:]
    page_size = max(len(first_results), 1)
    total_pages = (total + page_size - 1) // page_size if total else 1
    for page in range(2, total_pages + 1):
        separator = "&" if "?" in source["url"] else "?"
        page_url = f"{source['url']}{separator}pg={page}"
        try:
            html = download_text(page_url, refresh=refresh)
            page_results, _ = parse_aan_search_page(html, source)
            all_records.extend(page_results)
        except Exception as exc:
            print(f"⚠ {source['id']} page {page} skipped: {exc}", file=sys.stderr)

    deduped_records = []
    seen_urls = set()
    for record in all_records:
        if record["abstractUrl"] in seen_urls:
            continue
        seen_urls.add(record["abstractUrl"])
        deduped_records.append(record)

    parsed: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(parse_aan_abstract_record, record, source, refresh) for record in deduped_records]
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception as exc:
                print(f"⚠ {source['id']} abstract skipped: {exc}", file=sys.stderr)
                continue
            if item:
                parsed.append(item)
    return dedupe_items(parsed)


def dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    output = []
    for item in items:
        key = (item["meetingId"], item.get("code") or item["title"][:90], item["title"][:120])
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def is_mg_text(title: str, abstract: str = "") -> bool:
    """只保留 MG 内容；LEMS/CMS 等相关疾病不作为 MG 收录。"""
    title_text = title or ""
    abstract_text = abstract or ""
    early_abstract = abstract_text[:900]
    if NON_MG_RELATED_RE.search(title_text):
        return False
    if MG_TITLE_RE.search(title_text):
        return True
    if NON_MG_RELATED_RE.search(early_abstract):
        return False
    return bool(MG_ABSTRACT_FOCUS_RE.search(early_abstract) and MG_RELEVANCE_RE.search(f"{title_text} {abstract_text}"))


def infer_countries(text: str) -> list[str]:
    lower = text.lower()
    countries = []
    for country, terms in COUNTRY_RULES:
        if any(term in lower for term in terms):
            countries.append(country)
    return countries or ["未识别"]


def infer_topics(text: str) -> list[str]:
    lower = text.lower()
    topics = []
    for topic, terms in TOPIC_RULES:
        if any(term in lower for term in terms):
            topics.append(topic)
    return topics[:5] or ["其他"]


def infer_drugs(text: str) -> list[str]:
    lower = text.lower()
    drugs = []
    for drug, terms in DRUG_RULES:
        if any(term in lower for term in terms):
            drugs.append(drug)
    return drugs


def infer_research_type(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["randomized", "randomised", "placebo", "double-blind", "phase 3", "phase iii"]):
        return "随机/对照试验"
    if any(term in lower for term in ["trial in progress", "study design", "protocol"]):
        return "试验设计/进行中"
    if any(term in lower for term in ["real-world", "real world", "claims", "registry", "retrospective", "observational", "cohort"]):
        return "真实世界/队列"
    if any(term in lower for term in ["case report", "case series", "single center experience", "single-centre experience"]):
        return "病例/病例系列"
    if any(term in lower for term in ["quality of life", "patient-reported", "preference", "burden", "cost", "survey", "discrete choice"]):
        return "PRO/HEOR"
    if any(term in lower for term in ["biomarker", "proteomic", "cytokine", "b cell", "t cell", "mechanism", "pathogenesis", "in vitro", "mice", "mouse"]):
        return "机制/转化"
    if any(term in lower for term in ["safety", "adverse", "tolerability", "vaccination"]):
        return "安全性"
    if any(term in lower for term in ["digital", "wearable", "mobile", "app", "algorithm", "machine learning"]):
        return "数字/方法学"
    return "其他临床研究"


def make_zh_summary(title: str, abstract: str, topics: list[str], research_type: str, drugs: list[str], countries: list[str]) -> str:
    focus = "、".join(topics[:3])
    drug_text = "；涉及药物：" + "、".join(drugs[:4]) if drugs else ""
    country_text = "；国家/地区线索：" + "、".join([c for c in countries if c != "未识别"][:4]) if countries and countries != ["未识别"] else ""
    clue = "摘要原文待公开，当前仅保留题名/作者用于监控。" if not abstract else "可展开英文摘要核查方法与结果。"
    return f"中文分析：{research_type}，主题聚焦 {focus}{drug_text}{country_text}。{clue}"


def priority_score(item: dict) -> int:
    score = 0
    text = f"{item['title']} {item.get('abstract', '')}".lower()
    if item["researchType"] == "随机/对照试验":
        score += 4
    if item["researchType"] in {"真实世界/队列", "PRO/HEOR"}:
        score += 2
    if item["drugs"]:
        score += 2
    if "中国" in item["countries"]:
        score += 2
    if any(term in text for term in ["phase 3", "pivotal", "final results", "primary results"]):
        score += 2
    if item["presentationType"] == "Oral":
        score += 1
    return score


def make_abstract_item(
    source: dict,
    local_id: str,
    title: str,
    authors: str,
    abstract: str,
    page: int,
    presentation_type: str,
    affiliations: str,
) -> dict:
    title = title.strip() or "(Untitled)"
    text = f"{title} {authors} {affiliations} {abstract}"
    countries = infer_countries(text)
    topics = infer_topics(text)
    drugs = infer_drugs(text)
    research_type = infer_research_type(text)
    item = {
        "id": f"{source['id']}::{local_id}",
        "sourceId": source["id"],
        "meetingId": source["meetingId"],
        "conference": source["shortTitle"],
        "conferenceFullName": source["title"],
        "organization": source["sourceLabel"],
        "year": source["year"],
        "date": source["date"],
        "location": source["location"],
        "presentationType": presentation_type,
        "title": title,
        "authors": authors,
        "affiliations": affiliations,
        "abstract": abstract,
        "topics": topics,
        "drugs": drugs,
        "countries": countries,
        "researchType": research_type,
        "isChinaRelated": "中国" in countries,
        "sourceUrl": source["url"],
        "pageUrl": source["pageUrl"],
        "page": page,
    }
    item["priorityScore"] = priority_score(item)
    item["analysisZh"] = make_zh_summary(title, abstract, topics, research_type, drugs, countries)
    return item


def rank_counter(counter: Counter, limit: int = 15) -> list[dict]:
    return [{"name": key, "count": value} for key, value in counter.most_common(limit)]


def build_summary(abstracts: list[dict]) -> dict:
    country_counter: Counter = Counter()
    topic_counter: Counter = Counter()
    type_counter: Counter = Counter()
    meeting_counter: Counter = Counter()
    for item in abstracts:
        meeting_counter[item["conference"]] += 1
        type_counter[item["researchType"]] += 1
        for topic in item["topics"]:
            topic_counter[topic] += 1
        for country in item["countries"]:
            country_counter[country] += 1
    country_count = len([country for country in country_counter if country != "未识别"])
    return {
        "totalAbstracts": len(abstracts),
        "meetingCount": len(meeting_counter),
        "countryCount": country_count,
        "chinaRelated": sum(1 for item in abstracts if item["isChinaRelated"]),
        "highPriorityCount": sum(1 for item in abstracts if item["priorityScore"] >= 6),
        "byMeeting": rank_counter(meeting_counter, 10),
        "byCountry": rank_counter(country_counter, 20),
        "byTopic": rank_counter(topic_counter, 20),
        "byResearchType": rank_counter(type_counter, 20),
    }


def build_payload(refresh: bool = False) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    abstracts: list[dict] = []
    source_stats = []
    for source in SOURCES:
        try:
            cache_name = cache_path_for_url(source["url"]).name
            if source["parser"] == "aan-mirasmart":
                items = parse_aan_mirasmart(source, refresh=refresh)
            else:
                path = download(source["url"], refresh=refresh)
                cache_name = path.name
            if source["parser"] == "numbered-poster":
                items = parse_numbered_poster(path, source)
            elif source["parser"] == "simple-numbered":
                items = parse_simple_numbered(path, source)
            elif source["parser"] == "ean-book":
                items = parse_ean_book(path, source)
            else:
                items = items if source["parser"] == "aan-mirasmart" else []
            raw_count = len(items)
            items = [item for item in items if is_mg_text(item.get("title", ""), item.get("abstract", ""))]
            abstracts.extend(items)
            source_stats.append({
                "id": source["id"],
                "title": source["shortTitle"],
                "status": "ok",
                "items": len(items),
                "rawItems": raw_count,
                "cacheFile": cache_name,
            })
        except Exception as exc:  # pragma: no cover - 网络状态不稳定时保留其他源
            print(f"⚠ {source['id']} failed: {exc}", file=sys.stderr)
            source_stats.append({"id": source["id"], "title": source["shortTitle"], "status": "failed", "error": str(exc)})

    abstracts = dedupe_items(abstracts)
    abstracts.sort(key=lambda item: (-item["year"], -item["priorityScore"], item["conference"], item["title"]))
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": build_summary(abstracts),
        "meetings": [
            {
                "id": source["meetingId"],
                "title": source["title"],
                "shortTitle": source["shortTitle"],
                "organization": source["sourceLabel"],
                "year": source["year"],
                "date": source["date"],
                "location": source["location"],
                "url": source["pageUrl"],
            }
            for source in SOURCES
        ],
        "abstracts": abstracts,
        "sourceStats": source_stats,
        "sourceMonitor": SOURCE_MONITOR,
        "futureMeetings": FUTURE_MEETINGS,
        "analysisSpec": {
            "dimensions": [
                "会议/组织",
                "国家/地区投稿排名",
                "摘要类型/研究设计",
                "主题/治疗机制",
                "药物/靶点",
                "重大突破/转化价值",
                "中国相关",
            ],
            "notes": "研究类型、国家和主题为规则自动判定，适合快速浏览；用于医学判断前需回到原始摘要核查。",
        },
    }
    return payload


def write_payload(payload: dict) -> None:
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    JS_PATH.write_text(
        "window.MG_CONFERENCE_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="重新下载 PDF 源文件")
    args = parser.parse_args()
    payload = build_payload(refresh=args.refresh)
    write_payload(payload)
    print(
        f"Generated {JS_PATH.relative_to(PROJECT)}: "
        f"{payload['summary']['totalAbstracts']} abstracts / {payload['summary']['meetingCount']} meetings"
    )


if __name__ == "__main__":
    main()
