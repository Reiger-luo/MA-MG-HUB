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
MG_ABBREVIATION_TITLE_RE = re.compile(r"\bMG\b")
ICI_MYASTHENIA_RE = re.compile(r"(immune checkpoint|\bICI\b).{0,80}(myasthenia|myositis/myasthenia)|myositis/myasthenia", re.I)
SOURCE_COVERAGE_AUDITS: dict[str, dict] = {}
EAN_DRUG_RE = re.compile(
    r"(efgartigimod|nipocalimab|rozanolixizumab|ravulizumab|eculizumab|zilucoplan|"
    r"cemdisiran|claseprubart|telitacicept|gefurulimab|inebilizumab)",
    re.I,
)

SOURCES = [
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
]

SOURCE_MONITOR = [
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
    ("细胞治疗/免疫重置", ["car-t", "car t", "chimeric antigen receptor", "rese-cel", "resocabtagene", "kyv-101", "descartes-08", "kite-363", "bcma-directed", "cd19"]),
    ("B细胞/免疫重置", ["b cell", "b-cell", "rituximab", "inebilizumab", "cd19", "telitacicept", "april", "blys"]),
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
    ("telitacicept", ["telitacicept", "rc18", "reme-mg", "rememg"]),
    ("rituximab", ["rituximab"]),
    ("inebilizumab", ["inebilizumab"]),
    ("gefurulimab", ["gefurulimab"]),
    ("claseprubart", ["claseprubart", "dnth103"]),
    ("cemdisiran", ["cemdisiran"]),
    ("rese-cel", ["rese-cel", "resocabtagene autoleucel", "reset-mg"]),
    ("KYV-101", ["kyv-101", "kysa-6"]),
    ("Descartes-08", ["descartes-08"]),
    ("KITE-363", ["kite-363"]),
    ("MGAC-007", ["mgac-007"]),
    ("BHV-1300", ["bhv-1300"]),
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
    parsed = dedupe_items(parsed)
    SOURCE_COVERAGE_AUDITS[source["id"]] = {
        "sourceId": source["id"],
        "meeting": source["shortTitle"],
        "query": "myasthenia",
        "rawSearchResults": total or len(deduped_records),
        "recordsParsed": len(deduped_records),
        "curatedMgIncluded": len(parsed),
        "excludedByRule": max(len(deduped_records) - len(parsed), 0),
        "exclusionPrinciple": "保留 MG 全称、AAN 标题大写 MG 缩写、ICI myositis/myasthenia 安全性条目；剔除 CMS/LEMS、单纯神经肌接头 mimic、mg 剂量单位或非 MG 疾病误命中。",
        "externalBenchmark": {
            "label": "huashanmuscle AAN 2026 panorama",
            "reportedDirectMg": 106,
            "url": "https://mg-intelligence-hub.huashanmuscle.com/pages/conferences/aan-2026-mg-panorama.html",
            "note": "不同来源的摘要口径存在差异；会后复盘应优先回到站内摘要卡和原始来源核查具体证据。",
        },
    }
    return parsed


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
    """只保留 MG 核心内容；LEMS/CMS 等相关疾病不作为 MG 主库收录。"""
    title_text = title or ""
    abstract_text = abstract or ""
    early_abstract = abstract_text[:900]
    if NON_MG_RELATED_RE.search(title_text):
        return False
    if MG_TITLE_RE.search(title_text):
        return True
    # AAN 部分标题常用大写 MG 缩写；不能把全文里的小写 mg 剂量单位当作 MG。
    if MG_ABBREVIATION_TITLE_RE.search(title_text):
        return True
    # ICI 相关 myositis/myasthenia 是神经免疫安全性中的 MG 临床管理问题。
    if ICI_MYASTHENIA_RE.search(f"{title_text} {early_abstract}"):
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


def _first_sentence(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z])", text)
    sentence = parts[0] if parts else text
    return sentence[:max_len].rstrip() + ("…" if len(sentence) > max_len else "")


def _metric_snippets(text: str, limit: int = 4) -> list[str]:
    """提取摘要中可进入医学事务讨论的关键数字。按句子/短句评分，避免小数点被截断。"""
    text = re.sub(r"\s+", " ", text or "").replace("efgartigi- mod", "efgartigimod").replace("pla- cebo", "placebo")
    if not text:
        return []
    sentences = re.split(r"(?<=[.;])\s+(?=[A-Z][a-z])", text)
    anchors = re.compile(
        r"(MG-ADL|QMG|MG-QOL15r|Neuro-QoL|MSE|minimum symptom expression|"
        r"least squares mean|mean change|response|responder|reduction|improvement|"
        r"steroid|corticosteroid|prednisone|p\s*[<=>]|OR\s*=|CI\)|%|mg/day|week|month)",
        re.I,
    )
    has_number = re.compile(r"\d+(?:\.\d+)?\s*(?:%|mg/day|mg|weeks?|months?|years?|patients?|participants?)?|p\s*[<=>]\s*0?\.\d+|OR\s*=\s*\d+(?:\.\d+)?", re.I)
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        sentence = sentence.strip(" ;")
        if len(sentence) < 24:
            continue
        score = 0
        if anchors.search(sentence):
            score += 2
        if has_number.search(sentence):
            score += 2
        if re.search(r"(primary endpoint|baseline|week 4|week 24|cycle|placebo|well tolerated|adverse)", sentence, re.I):
            score += 1
        if score >= 3:
            cleaned = sentence[:220].rstrip() + ("…" if len(sentence) > 220 else "")
            scored.append((score, cleaned))
    scored.sort(key=lambda row: (-row[0], len(row[1])))
    hits: list[str] = []
    seen: set[str] = set()
    for _, snippet in scored:
        key = re.sub(r"\W+", " ", snippet.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        hits.append(snippet)
        if len(hits) >= limit:
            break
    return hits


def infer_patient_lens(text: str) -> list[str]:
    lower = text.lower()
    rules = [
        ("血清阴性/MuSK/LRP4", ["seronegative", "musk", "lrp4", "anti-muscle-specific kinase"]),
        ("青少年/妊娠", ["juvenile", "pediatric", "paediatric", "adolescent", "pregnancy", "postpartum"]),
        ("早期病程", ["early disease", "disease duration", "newly diagnosed", "≤5", "<=5"]),
        ("胸腺瘤相关", ["thymoma", "tamg"]),
        ("真实世界长期管理", ["real-world", "real world", "registry", "retrospective", "extension", "long-term"]),
        ("患者负担/生活质量", ["quality of life", "burden", "fatigue", "preference", "cost", "qol"]),
    ]
    out = [label for label, terms in rules if any(term in lower for term in terms)]
    return out[:4] or ["总体 gMG 人群"]


def infer_action_tags(text: str, research_type: str, drugs: list[str], countries: list[str]) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    if research_type == "随机/对照试验" or any(term in lower for term in ["phase 3", "primary endpoint", "placebo"]):
        tags.append("Congress debrief核心证据")
    if any(term in lower for term in ["steroid", "corticosteroid", "prednisone", "taper"]):
        tags.append("激素减量叙事")
    if any(term in lower for term in ["quality of life", "burden", "preference", "fatigue", "cost"]):
        tags.append("患者价值沟通")
    if any(term in lower for term in ["infection", "adverse", "safety", "tolerability"]):
        tags.append("安全性追问")
    if any(term in lower for term in ["juvenile", "pediatric", "pregnancy", "seronegative", "musk", "lrp4", "thymoma"]):
        tags.append("特殊人群KOL问题")
    if "中国" in countries:
        tags.append("中国专家/机构跟进")
    if drugs:
        tags.append("竞品机制比较")
    return tags[:5] or ["摘要监控"]


def make_deep_conference_insight(title: str, abstract: str, topics: list[str], research_type: str, drugs: list[str], countries: list[str]) -> dict:
    """生成网站使用的医学事务深度解读字段。规则化、可复现，不替代人工医学判断。"""
    text = f"{title} {abstract}"
    lower = text.lower()
    metrics = _metric_snippets(abstract)
    focus = "、".join(topics[:3])
    drug_text = "、".join(drugs[:3]) if drugs else "相关机制"
    patient_lens = infer_patient_lens(text)
    action_tags = infer_action_tags(text, research_type, drugs, countries)

    if not abstract:
        return {
            "clinicalReadoutZh": f"当前仅有题名/作者信息。题名提示该摘要属于{research_type}，主题聚焦 {focus}，需等待完整摘要或会后资料确认。",
            "maImplicationZh": "适合作为会议源监控线索，不应直接进入对外材料；可先列入会后核查清单。",
            "evidenceBoundaryZh": "证据边界：摘要正文缺失，无法判断样本量、终点、效应量、随访长度和安全性口径。",
            "keyMetrics": [],
            "patientLens": patient_lens,
            "actionTags": action_tags,
            "kolQuestions": ["该题名对应的研究设计、入组人群和核心终点是什么？", "是否有可核查的摘要全文、poster 或 oral slide？"],
            "evidenceNeed": "补全文摘/海报后再判定医学事务优先级。",
        }

    if "steroid" in lower or "corticosteroid" in lower or "prednisone" in lower:
        implication = "这条摘要的工作价值不止是疗效，而是把靶向治疗转成临床更关心的“激素负担下降、长期控制和治疗目标重构”。适合进入激素减量、患者旅程和长期管理讨论。"
    elif any(term in lower for term in ["juvenile", "pediatric", "pregnancy", "seronegative", "musk", "lrp4", "thymoma"]):
        implication = "这条摘要适合用于定义治疗边界：哪些特殊人群已有数据、哪些只是探索信号、哪些问题需要 KOL 访谈确认。它比单纯疗效新闻更适合作为精准管理议题入口。"
    elif any(term in lower for term in ["quality of life", "burden", "preference", "fatigue", "cost"]):
        implication = "这条摘要能把会议报道从“药物有效”推进到“患者感知获益和实践价值”。适合用于 MSL 拜访前准备患者价值、PRO 和资源负担相关问题。"
    elif research_type == "随机/对照试验" or any(term in lower for term in ["phase 3", "placebo", "primary endpoint"]):
        implication = "这是会后复盘应优先核查的核心证据。医学事务使用时应同时看机制定位、人群、终点、随访和安全性，而不是只摘录一个阳性结果。"
    elif research_type == "真实世界/队列":
        implication = "这条摘要适合补足 RCT 外部有效性和临床路径问题：真实世界患者如何选择、维持、减量、停药或转换治疗。它应作为实践场景证据，而非直接替代随机证据。"
    else:
        implication = "这条摘要适合作为主题雷达信号：用于生成专家追问、后续文献监控关键词，或补充会议全景叙事中的证据空白。"

    boundary_parts = []
    if research_type not in {"随机/对照试验", "试验设计/进行中"}:
        boundary_parts.append("非随机证据需注意选择偏倚和因果外推")
    if "post hoc" in lower or "subgroup" in lower:
        boundary_parts.append("亚组/事后分析不能直接等同于预设结论")
    if "retrospective" in lower or "chart review" in lower:
        boundary_parts.append("回顾性资料适合提出实践假设，不宜包装成疗效定论")
    if "trial in progress" in lower or "study design" in lower:
        boundary_parts.append("进行中研究只能说明证据布局，不能用于疗效结论")
    if not metrics:
        boundary_parts.append("需回到原文核查具体样本量、效应量和安全性数据")
    boundary = "；".join(boundary_parts) or "需核查入组标准、主要终点、效应量、随访长度和 AE 采集口径后再用于材料。"

    kol_questions = []
    if drugs:
        kol_questions.append(f"在同类患者路径中，{drug_text}最适合解决什么未满足需求？")
    if any(term in lower for term in ["steroid", "corticosteroid", "prednisone"]):
        kol_questions.append("您在真实诊疗中会用哪些指标判断“可以减激素”，MG-ADL/MSE 是否足够？")
    if any(term in lower for term in ["seronegative", "musk", "lrp4"]):
        kol_questions.append("抗体分型会如何影响您对靶向治疗证据的信任和患者选择？")
    if any(term in lower for term in ["quality of life", "burden", "preference", "fatigue"]):
        kol_questions.append("患者价值数据中，哪些 PRO 最能改变您与患者的治疗目标沟通？")
    if "中国" in countries:
        kol_questions.append("中国参与机构的数据是全球多中心贡献，还是能形成独立的本土证据叙事？")
    if not kol_questions:
        kol_questions.append("这条摘要是否足以改变您的治疗讨论，还是只应作为趋势观察？")
    kol_questions.append("如果要转化为中国医学事务行动，下一步最缺的是全文、专家反馈还是本土数据？")

    clinical = f"{research_type}；聚焦 {focus}。"
    if metrics:
        clinical += "关键数据点：" + "；".join(metrics[:3]) + "。"
    else:
        clinical += _first_sentence(abstract, 180) or "需展开原文确认关键结果。"

    return {
        "clinicalReadoutZh": clinical,
        "maImplicationZh": implication,
        "evidenceBoundaryZh": "证据边界：" + boundary + "。",
        "keyMetrics": metrics,
        "patientLens": patient_lens,
        "actionTags": action_tags,
        "kolQuestions": kol_questions[:4],
        "evidenceNeed": "核查研究设计、患者分型、主要终点、随访长度、安全性口径，并判断是否能进入内部 briefing / KOL 访谈 / 本土证据规划。",
    }


def make_zh_summary(title: str, abstract: str, topics: list[str], research_type: str, drugs: list[str], countries: list[str]) -> str:
    insight = make_deep_conference_insight(title, abstract, topics, research_type, drugs, countries)
    return " ".join([insight["clinicalReadoutZh"], insight["maImplicationZh"]])


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
    item["deepInsight"] = make_deep_conference_insight(title, abstract, topics, research_type, drugs, countries)
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


def _top_items(items: list[dict], predicate, limit: int = 3) -> list[dict]:
    return sorted([item for item in items if predicate(item)], key=lambda item: (-item.get("priorityScore", 0), item.get("title", "")))[:limit]


def _mini_ref(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "presentationType": item.get("presentationType"),
        "researchType": item.get("researchType"),
        "drugs": item.get("drugs", []),
        "topics": item.get("topics", []),
        "countries": item.get("countries", []),
        "sourceUrl": item.get("sourceUrl") or item.get("pageUrl"),
        "keyMetrics": (item.get("deepInsight") or {}).get("keyMetrics", [])[:3],
    }


def build_meeting_narratives(abstracts: list[dict]) -> dict:
    """按会议生成可直接在前端展示的医学事务全景叙事。"""
    by_meeting: dict[str, list[dict]] = {}
    for item in abstracts:
        by_meeting.setdefault(item["conference"], []).append(item)

    narratives: dict[str, dict] = {}
    for conference, items in by_meeting.items():
        topics = Counter(topic for item in items for topic in item.get("topics", []))
        drugs = Counter(drug for item in items for drug in item.get("drugs", []))
        types = Counter(item.get("researchType", "其他临床研究") for item in items)
        china_count = sum(1 for item in items if item.get("isChinaRelated"))
        high_count = sum(1 for item in items if item.get("priorityScore", 0) >= 6)
        top_topics = [name for name, _ in topics.most_common(4)]
        top_drugs = [name for name, _ in drugs.most_common(5)]
        top_types = [name for name, _ in types.most_common(3)]

        treatment_refs = _top_items(
            items,
            lambda item: item.get("researchType") == "随机/对照试验" or bool(item.get("drugs")) or item.get("priorityScore", 0) >= 8,
            4,
        )
        practice_refs = _top_items(
            items,
            lambda item: item.get("researchType") in {"真实世界/队列", "PRO/HEOR", "安全性"}
            or any(topic in item.get("topics", []) for topic in ["真实世界/登记", "PRO/生活质量", "安全性", "危象/急性加重"]),
            4,
        )
        subgroup_refs = _top_items(
            items,
            lambda item: any(
                term in f"{item.get('title','')} {item.get('abstract','')}".lower()
                for term in ["seronegative", "musk", "lrp4", "juvenile", "pediatric", "pregnancy", "thymoma", "early disease"]
            ),
            4,
        )
        china_refs = _top_items(items, lambda item: item.get("isChinaRelated"), 4)

        if conference == "EAN 2026":
            headline = "EAN 2026 的 MG 线索集中在 FcRn/补体新药、血清阴性与青少年人群、真实世界长期管理和欧洲—中国协作网络。"
            strategic_read = "会后复盘应按治疗机制、人群边界、实践价值和本土转化拆解，区分可直接交流的数据、仍需全文核查的探索信号和适合追问的证据空白。"
        elif conference == "AAN 2026":
            headline = "AAN 2026 的 MG 线索集中在靶向治疗 RCT、补体/FcRn/B 细胞与细胞治疗布局、特殊人群证据和真实世界负担。"
            strategic_read = "会后复盘应围绕哪些数据能改变治疗讨论、哪些仍属于设计或探索性证据、哪些适合转成 KOL 追问展开。"
        elif conference.startswith("MGFA"):
            headline = "MGFA 摘要更接近 MG 专病生态，适合连接患者旅程、基础机制、临床实践和专家网络。"
            strategic_read = "医学事务使用时应优先识别能进入疾病教育、ad board 议题和本地研究假设的摘要。"
        else:
            headline = f"{conference} 已结构化为 MG 摘要情报模块。"
            strategic_read = "当前以摘要监控和来源核查为主，待字段完整后再升级为会后复盘材料。"

        narratives[conference] = {
            "headline": headline,
            "strategicRead": strategic_read,
            "contentDepth": {
                "abstracts": len(items),
                "highPriority": high_count,
                "chinaRelated": china_count,
                "topTopics": top_topics,
                "topDrugs": top_drugs,
                "topResearchTypes": top_types,
            },
            "competitiveComparison": None,
            "chapters": [
                {
                    "title": "治疗格局：从阳性结果走向机制定位",
                    "takeaway": f"核心药物/机制集中在{'、'.join(top_drugs[:4]) if top_drugs else '待识别机制'}；真正需要回答的是不同机制在患者路径中的位置，而不是谁有一条阳性摘要。",
                    "maUse": "用于 congress debrief、竞品比较、KOL 访谈前问题树。",
                    "refs": [_mini_ref(item) for item in treatment_refs],
                },
                {
                    "title": "临床落地：真实世界、PRO 与安全性决定材料可用性",
                    "takeaway": "激素减量、长期控制、生活质量、感染/安全性和给药负担，是会议摘要最容易转化为 MSL 日常对话的部分。",
                    "maUse": "用于患者价值沟通、长期管理 slide、临床实践追问清单。",
                    "refs": [_mini_ref(item) for item in practice_refs],
                },
                {
                    "title": "人群边界：特殊亚群是下一轮差异化入口",
                    "takeaway": "血清阴性、MuSK/LRP4、青少年、妊娠、早期病程和胸腺瘤相关 MG 等摘要，不应被压缩成“也有效”，而应转成患者画像和证据缺口。",
                    "maUse": "用于精准管理议题、专家访谈和本土研究 gap。",
                    "refs": [_mini_ref(item) for item in subgroup_refs],
                },
                {
                    "title": "中国转化：中国相关不是计数，而是专家网络和证据机会",
                    "takeaway": f"本会议中国相关 {china_count} 条；需要区分中国只是参与全球多中心，还是能形成独立的本土证据或 KOL 合作机会。",
                    "maUse": "用于 KOL mapping、区域 follow-up、研究合作假设和本地化叙事。",
                    "refs": [_mini_ref(item) for item in china_refs],
                },
            ],
            "briefingQuestions": [
                "哪些靶向治疗结果已经有明确终点和效应量，哪些仍只是设计或探索性信号？",
                "细胞治疗、补体、FcRn 与 B 细胞/免疫重置分别对应哪类患者路径和证据边界？",
                "特殊人群数据能否支持患者分层讨论，还是仅适合形成 KOL 追问？",
                "真实世界、PRO 和安全性摘要能否转化为长期管理或患者价值议题？",
            ] if conference == "AAN 2026" else [
                "哪些摘要可以进入内部 briefing，哪些只能作为趋势观察？",
                "核心结果对应的是疗效、激素减量、长期控制、患者价值还是安全性管理？",
                "是否存在中国机构/作者线索，能否转化为 KOL follow-up？",
                "关键证据是否足以支持医学判断，还是需要等待全文/poster/后续研究？",
            ],
        }
    return narratives


def load_existing_zh_enrichment() -> dict[str, dict]:
    """Preserve optional LLM-generated Chinese fields across deterministic rebuilds."""
    payload = None
    if JSON_PATH.exists():
        try:
            payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    elif JS_PATH.exists():
        try:
            text = JS_PATH.read_text(encoding="utf-8")
            prefix = "window.MG_CONFERENCE_DATA = "
            body = text[len(prefix):].strip() if text.startswith(prefix) else ""
            if body.endswith(";"):
                body = body[:-1]
            payload = json.loads(body) if body else None
        except Exception:
            payload = None
    if not payload:
        return {}
    enrichments: dict[str, dict] = {}
    for item in payload.get("abstracts", []):
        item_id = item.get("id")
        if not item_id:
            continue
        insight = item.get("deepInsight") or {}
        entry: dict = {}
        if item.get("abstractZh"):
            entry["abstractZh"] = item["abstractZh"]
        if insight.get("kolKeyMessageZh"):
            entry["kolKeyMessageZh"] = insight["kolKeyMessageZh"]
        if entry:
            enrichments[item_id] = entry
    return enrichments


def load_existing_meeting_narrative_enrichment() -> dict[str, dict]:
    """Preserve optional LLM-curated meeting narratives across deterministic rebuilds."""
    payload = None
    if JSON_PATH.exists():
        try:
            payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    elif JS_PATH.exists():
        try:
            text = JS_PATH.read_text(encoding="utf-8")
            prefix = "window.MG_CONFERENCE_DATA = "
            body = text[len(prefix):].strip() if text.startswith(prefix) else ""
            if body.endswith(";"):
                body = body[:-1]
            payload = json.loads(body) if body else None
        except Exception:
            payload = None
    if not payload:
        return {}
    enrichments: dict[str, dict] = {}
    for conference, narrative in (payload.get("meetingNarratives") or {}).items():
        if isinstance(narrative, dict) and narrative.get("llmCurated"):
            enrichments[str(conference)] = narrative
    return enrichments


def apply_existing_zh_enrichment(abstracts: list[dict], enrichments: dict[str, dict]) -> None:
    for item in abstracts:
        entry = enrichments.get(str(item.get("id") or ""))
        if not entry:
            continue
        if entry.get("abstractZh"):
            item["abstractZh"] = entry["abstractZh"]
        if entry.get("kolKeyMessageZh"):
            item.setdefault("deepInsight", {})["kolKeyMessageZh"] = entry["kolKeyMessageZh"]


def apply_existing_meeting_narrative_enrichment(narratives: dict[str, dict], enrichments: dict[str, dict]) -> None:
    for conference, enriched in enrichments.items():
        if not enriched:
            continue
        base = dict(narratives.get(conference, {}))
        base.update(enriched)
        narratives[conference] = base


def build_payload(refresh: bool = False) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zh_enrichments = load_existing_zh_enrichment()
    narrative_enrichments = load_existing_meeting_narrative_enrichment()
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
    apply_existing_zh_enrichment(abstracts, zh_enrichments)
    meeting_narratives = build_meeting_narratives(abstracts)
    apply_existing_meeting_narrative_enrichment(meeting_narratives, narrative_enrichments)
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
        "meetingNarratives": meeting_narratives,
        "coverageAudits": SOURCE_COVERAGE_AUDITS,
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
