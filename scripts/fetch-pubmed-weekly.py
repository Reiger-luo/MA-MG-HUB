#!/usr/bin/env python3
"""
fetch-pubmed-weekly.py — MG-HUB PubMed 数据管线

每周抓取当前 1 周新上线的 MG 相关文献，输出 data/literature-weekly.json。

检索策略：
  ("Myasthenia Gravis"[MeSH] OR myasthenia gravis[Title/Abstract])
  AND [Date - Entry] 7 天窗口

字段说明：
  - study_types / evidence_level 留空，待后处理管线回填
  - china_related 暂不在管线层判定，保留 affiliations 原始数据供 UI 筛选
  - author_affiliations 为作者级机构，供专家画像和机构文献计量使用
"""

import argparse, json, os, re, socket, sys, time, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from pathlib import Path

from common.io import atomic_write_json

# ── 配置 ──────────────────────────────────────────────
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
WINDOW_DAYS = 7       # 时间窗天数
RETMAX = 10000         # 最大返回数（safe upper bound）
BATCH_SIZE = 200

# 项目根目录（脚本在 project/scripts/ 下）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"

# ── 检索参数 ─────────────────────────────────────────

# 日期窗口：今天 → 往前 WINDOW_DAYS 天
TODAY = datetime.now()
SINCE = TODAY - timedelta(days=WINDOW_DAYS)
DATE_STR_SINCE = SINCE.strftime("%Y/%m/%d")
DATE_STR_UNTIL = TODAY.strftime("%Y/%m/%d")

# 检索词
QUERY = (
    '("Myasthenia Gravis"[MeSH] OR myasthenia gravis[Title/Abstract]) '
    f'AND {DATE_STR_SINCE}:{DATE_STR_UNTIL}[Date - Entry]'
)

# ── NCBI 公共参数：参考 Entrez skill 的稳定接口规范 ──
API_KEY = os.environ.get("NCBI_API_KEY") or os.environ.get("NCBI_EUTILS_API_KEY", "")
NCBI_TOOL = os.environ.get("NCBI_TOOL", "MA-MG-HUB")
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
API_KEY_ENABLED = bool(API_KEY)
MAX_RETRIES = 3
MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


# ── 工具函数 ───────────────────────────────────────────

def ncbi_params(params):
    """合并 NCBI E-utilities 公共参数。"""
    merged = dict(params)
    if API_KEY and API_KEY_ENABLED and "api_key" not in merged:
        merged["api_key"] = API_KEY
    if NCBI_TOOL and "tool" not in merged:
        merged["tool"] = NCBI_TOOL
    if NCBI_EMAIL and "email" not in merged:
        merged["email"] = NCBI_EMAIL
    return merged


def request_delay():
    return 0.12 if API_KEY_ENABLED else 0.34


def eutils_request(path, params, retmode="json", method="GET", timeout=60):
    """带重试和限速的 E-utilities 请求。"""
    global API_KEY_ENABLED
    headers = {
        "User-Agent": "MA-MG-HUB/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        merged = ncbi_params({**params, "retmode": retmode})
        encoded = urlencode(merged, doseq=True)
        url = f"{BASE_URL}/{path}"
        data = None
        if method.upper() == "GET":
            url = f"{url}?{encoded}"
        else:
            data = encoded.encode("utf-8")
        try:
            req = Request(url, data=data, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
            time.sleep(request_delay())
            return body
        except HTTPError as exc:
            last_error = exc
            if exc.code in (403, 429) and API_KEY_ENABLED:
                print(f"  ⚠ API key rejected/rate-limited (HTTP {exc.code})，切换 keyless 后重试。", file=sys.stderr)
                API_KEY_ENABLED = False
                continue
            if attempt == MAX_RETRIES:
                break
            wait = min(8, 2 ** attempt)
            print(f"  ⚠ {path} 第 {attempt} 次请求失败，{wait}s 后重试: {exc}", file=sys.stderr)
            time.sleep(wait)
        except (URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait = min(8, 2 ** attempt)
            print(f"  ⚠ {path} 第 {attempt} 次请求失败，{wait}s 后重试: {exc}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"{path} failed after {MAX_RETRIES} attempts: {last_error}")


def eutils_get(path, params):
    """调 E-utilities API，返回 response body"""
    return eutils_request(path, params, retmode="json", method="GET", timeout=60)


def eutils_post(path, params, retmode="xml", timeout=120):
    """POST 调 E-utilities，适合 efetch 大批量 PMID。"""
    return eutils_request(path, params, retmode=retmode, method="POST", timeout=timeout)


def text_content(elem):
    return "".join(elem.itertext()).strip() if elem is not None else ""


def parse_pub_date(pub_date_elem):
    if pub_date_elem is None:
        return ""
    year = pub_date_elem.findtext("Year", "")
    month = pub_date_elem.findtext("Month", "")
    day = pub_date_elem.findtext("Day", "")
    medline_date = pub_date_elem.findtext("MedlineDate", "")
    if not year and medline_date:
        match = re.search(r"\d{4}", medline_date)
        year = match.group(0) if match else ""
    if month in MONTH_MAP:
        month = MONTH_MAP[month]
    elif month.isdigit():
        month = month.zfill(2)
    else:
        month = month[:3] if month else ""
    parts = [year]
    if month:
        parts.append(month)
    if day:
        parts.append(day.zfill(2) if day.isdigit() else day)
    return "-".join(part for part in parts if part)


def parse_date_node(parent, path):
    elem = parent.find(path)
    if elem is None:
        return ""
    year = elem.findtext("Year", "")
    month = elem.findtext("Month", "")
    day = elem.findtext("Day", "")
    if month and month.isdigit():
        month = month.zfill(2)
    if day and day.isdigit():
        day = day.zfill(2)
    return "-".join(part for part in [year, month, day] if part)


def collect_article_ids(article_elem):
    article_ids = {}
    for eid in article_elem.findall(".//ArticleIdList/ArticleId"):
        id_type = eid.get("IdType")
        value = (eid.text or "").strip()
        if id_type and value:
            article_ids[id_type] = value
    return article_ids


def parse_pubmed_history_date(date_elem):
    year = date_elem.findtext("Year", "")
    month = date_elem.findtext("Month", "")
    day = date_elem.findtext("Day", "")
    hour = date_elem.findtext("Hour", "")
    minute = date_elem.findtext("Minute", "")
    if month and month.isdigit():
        month = month.zfill(2)
    if day and day.isdigit():
        day = day.zfill(2)
    date_value = "/".join(part for part in [year, month, day] if part)
    if hour or minute:
        date_value += f" {hour.zfill(2) if hour else '00'}:{minute.zfill(2) if minute else '00'}"
    return date_value


def collect_abstract(parent):
    abstract_parts = []
    for at in parent.findall(".//AbstractText"):
        label = at.get("Label", "")
        text = text_content(at)
        if not text:
            continue
        abstract_parts.append(f"{label}: {text}" if label else text)
    return "\n".join(abstract_parts)


def collect_pub_types(parent):
    values = []
    for pt in parent.findall(".//PublicationTypeList/PublicationType"):
        if pt.text:
            values.append(pt.text.strip())
    return unique_list(values)


def collect_mesh_terms(medline):
    terms = []
    for heading in medline.findall(".//MeshHeadingList/MeshHeading"):
        descriptor = heading.find("DescriptorName")
        if descriptor is None or not descriptor.text:
            continue
        item = {
            "descriptor": descriptor.text.strip(),
            "major": descriptor.get("MajorTopicYN") == "Y",
            "qualifiers": [],
        }
        for qualifier in heading.findall("QualifierName"):
            if qualifier.text:
                item["qualifiers"].append({
                    "name": qualifier.text.strip(),
                    "major": qualifier.get("MajorTopicYN") == "Y",
                })
        terms.append(item)
    return terms


def collect_keywords(medline):
    keywords = []
    for keyword in medline.findall(".//KeywordList/Keyword"):
        text = text_content(keyword)
        if text:
            keywords.append(text)
    return unique_list(keywords)


def collect_chemicals(medline):
    chemicals = []
    for chemical in medline.findall(".//ChemicalList/Chemical"):
        name = chemical.findtext("NameOfSubstance", "")
        registry = chemical.findtext("RegistryNumber", "")
        if name:
            chemicals.append({
                "name": name.strip(),
                "registry_number": registry.strip(),
            })
    return chemicals


def collect_grants(medline):
    grants = []
    for grant in medline.findall(".//GrantList/Grant"):
        grant_id = grant.findtext("GrantID", "")
        agency = grant.findtext("Agency", "")
        country = grant.findtext("Country", "")
        if grant_id or agency or country:
            grants.append({
                "grant_id": grant_id,
                "agency": agency,
                "country": country,
            })
    return grants


def collect_languages(medline):
    return unique_list(
        lang.text.strip()
        for lang in medline.findall(".//Article/Language")
        if lang.text and lang.text.strip()
    )


def parse_authors(author_list):
    authors = []
    author_affiliations = []
    affiliations = []
    email_corresponding = []
    first_authors = []
    author_count = len(author_list)
    for position, author in enumerate(author_list, 1):
        name = extract_author_name(author)
        if not name:
            continue
        authors.append(name)
        is_equal = author.get("EqualContrib") == "Y"
        if position == 1 or is_equal:
            first_authors.append(name)
        author_affs = []
        for aff in author.findall("./AffiliationInfo/Affiliation"):
            aff_text = text_content(aff)
            if aff_text:
                author_affs.append(aff_text)
        author_affs = unique_list(author_affs)
        emails = unique_list(
            email
            for aff_text in author_affs
            for email in EMAIL_RE.findall(aff_text)
        )
        if emails:
            email_corresponding.append(name)
        affiliations.extend(author_affs)
        author_affiliations.append({
            "position": position,
            "name": name,
            "affiliations": author_affs,
            "emails": emails,
            "is_first": position == 1,
            "is_last": position == author_count,
            "equal_contrib": is_equal,
            "is_corresponding": bool(emails),
        })
    corresponding_authors = unique_list(email_corresponding)
    corresponding_source = "email" if corresponding_authors else ""
    if not corresponding_authors and len(authors) > 1:
        corresponding_authors = [authors[-1]]
        corresponding_source = "last_author_fallback"
    return {
        "authors": authors,
        "first_authors": unique_list(first_authors),
        "corresponding_authors": corresponding_authors,
        "corresponding_authors_source": corresponding_source,
        "author_affiliations": author_affiliations,
        "affiliations": unique_list(affiliations),
    }


def fetch_edates(pmids):
    """批量查询 PMID → EDAT 映射（esummary JSON）"""
    edat_map = {}
    # 分批，每批 200 个
    batch_size = 200
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i+batch_size]
        try:
            data = json.loads(eutils_get("esummary.fcgi", {
                "db": "pubmed",
                "id": ",".join(batch),
            }))
            for uid_str, record in data.get("result", {}).items():
                if uid_str == "uids":
                    continue
                edat = None
                history = record.get("history", [])
                for h in history:
                    if h.get("pubstatus") == "entrez":
                        edat = h.get("date")
                        break
                if edat:
                    edat_map[uid_str] = edat
        except Exception as e:
            print(f"  ⚠ esummary batch failed ({len(batch)} PMIDs): {e}", file=sys.stderr)
        time.sleep(0.2)  # 限速
    return edat_map


def parse_article_xml(article_elem, edat_map):
    """解析一条 PubmedArticle XML → 字典"""
    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return None

    pmid = medline.findtext("PMID", "")
    if not pmid:
        return None

    title = text_content(medline.find(".//Article/ArticleTitle"))
    abstract = collect_abstract(medline)
    author_data = parse_authors(medline.findall(".//Article/AuthorList/Author"))

    # 期刊：优先全称（Title），次选 ISO 缩写
    journal_title = medline.findtext(".//Journal/Title", "")
    journal_iso = medline.findtext(".//Journal/ISOAbbreviation", "")
    journal = journal_title if journal_title else journal_iso

    # PubDate
    pub_date = parse_pub_date(medline.find(".//Journal/JournalIssue/PubDate"))
    article_ids = collect_article_ids(article_elem)
    doi = article_ids.get("doi", "")
    pmcid = article_ids.get("pmc", "")
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    full_text_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else (f"https://doi.org/{doi}" if doi else "")
    entry_date = edat_map.get(pmid, "")
    if not entry_date:
        for date_elem in article_elem.findall(".//PubmedData/History/PubMedPubDate"):
            if date_elem.get("PubStatus") == "entrez":
                entry_date = parse_pubmed_history_date(date_elem)
                break
    pub_types = collect_pub_types(medline)

    return {
        "source_type": "pubmed_article",
        "pmid": pmid,
        "title": title.strip(),
        "abstract": abstract.strip(),
        "authors": author_data["authors"],
        "first_authors": author_data["first_authors"],
        "corresponding_authors": author_data["corresponding_authors"],
        "corresponding_authors_source": author_data["corresponding_authors_source"],
        "author_affiliations": author_data["author_affiliations"],
        "journal": journal,
        "journal_iso": journal_iso,
        "issn": medline.findtext(".//Journal/ISSN", ""),
        "volume": medline.findtext(".//Journal/JournalIssue/Volume", ""),
        "issue": medline.findtext(".//Journal/JournalIssue/Issue", ""),
        "pages": medline.findtext(".//Pagination/MedlinePgn", ""),
        "entry_date": entry_date,
        "pub_date": pub_date,
        "date_completed": parse_date_node(medline, "DateCompleted"),
        "date_revised": parse_date_node(medline, "DateRevised"),
        "doi": doi,
        "pmcid": pmcid,
        "article_ids": article_ids,
        "url": url,
        "full_text_url": full_text_url,
        "affiliations": author_data["affiliations"],
        "pub_types": pub_types,
        "publication_types": pub_types,
        "mesh_terms": collect_mesh_terms(medline),
        "keywords": collect_keywords(medline),
        "chemicals": collect_chemicals(medline),
        "grants": collect_grants(medline),
        "languages": collect_languages(medline),
        "publication_status": article_elem.findtext(".//PubmedData/PublicationStatus", ""),
        "china_related": None,      # 暂空
        "study_types": [],           # 后处理回填
        "evidence_level": None,      # 后处理回填
    }


def parse_book_article_xml(article_elem, edat_map):
    """解析 PubmedBookArticle，避免周更命中但被静默跳过。"""
    book_doc = article_elem.find(".//BookDocument")
    if book_doc is None:
        return None
    pmid = book_doc.findtext("PMID", "")
    if not pmid:
        return None
    title = text_content(book_doc.find("ArticleTitle")) or text_content(book_doc.find(".//Book/BookTitle"))
    abstract = collect_abstract(book_doc)
    author_data = parse_authors(book_doc.findall(".//AuthorList/Author"))
    article_ids = collect_article_ids(article_elem)
    doi = article_ids.get("doi", "")
    pmcid = article_ids.get("pmc", "")
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    full_text_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else (f"https://doi.org/{doi}" if doi else "")
    entry_date = edat_map.get(pmid, "")
    if not entry_date:
        for date_elem in article_elem.findall(".//PubmedBookData/History/PubMedPubDate"):
            if date_elem.get("PubStatus") == "entrez":
                entry_date = parse_pubmed_history_date(date_elem)
                break
    source_title = text_content(book_doc.find(".//Book/BookTitle")) or text_content(book_doc.find(".//CollectionTitle"))
    return {
        "source_type": "pubmed_book_article",
        "pmid": pmid,
        "title": title.strip(),
        "abstract": abstract.strip(),
        "authors": author_data["authors"],
        "first_authors": author_data["first_authors"],
        "corresponding_authors": author_data["corresponding_authors"],
        "corresponding_authors_source": author_data["corresponding_authors_source"],
        "author_affiliations": author_data["author_affiliations"],
        "journal": source_title,
        "journal_iso": "",
        "issn": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "entry_date": entry_date,
        "pub_date": parse_pub_date(book_doc.find(".//Book/PubDate")),
        "date_completed": "",
        "date_revised": "",
        "doi": doi,
        "pmcid": pmcid,
        "article_ids": article_ids,
        "url": url,
        "full_text_url": full_text_url,
        "affiliations": author_data["affiliations"],
        "pub_types": ["Book Article"],
        "publication_types": ["Book Article"],
        "mesh_terms": [],
        "keywords": collect_keywords(book_doc),
        "chemicals": [],
        "grants": [],
        "languages": [],
        "publication_status": "book",
        "china_related": None,
        "study_types": [],
        "evidence_level": None,
    }


def extract_author_name(author_elem):
    last = author_elem.findtext("LastName", "")
    fore = author_elem.findtext("ForeName", "")
    collective = author_elem.findtext("CollectiveName", "")
    if last:
        return f"{last} {fore}".strip() if fore else last.strip()
    return collective.strip()


def unique_list(values):
    seen = set()
    result = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


# ── 主流程 ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch recent MG articles from PubMed")
    parser.add_argument("--archive", action="store_true", help="额外写入 data/archive 日期归档")
    args = parser.parse_args()

    print(f"📡 MG-HUB PubMed 抓取")
    print(f"   窗口: {DATE_STR_SINCE} → {DATE_STR_UNTIL}（{WINDOW_DAYS}天）")
    print(f"   检索: {QUERY}")
    print()

    # Step 1: esearch
    print("🔍 esearch...")
    search_result = eutils_get("esearch.fcgi", {
        "db": "pubmed",
        "term": QUERY,
        "retmax": RETMAX,
        "usehistory": "y",
    })
    search_data = json.loads(search_result)
    pmids = search_data.get("esearchresult", {}).get("idlist", [])
    total_count = search_data.get("esearchresult", {}).get("count", "0")
    print(f"   命中: {total_count} 篇（本次拉取: {len(pmids)}）")

    try:
        declared_count = int(total_count)
    except (TypeError, ValueError):
        raise SystemExit("PubMed esearch count 无法解析；保留上一份 weekly 输入并停止发布")
    if declared_count != len(pmids):
        raise SystemExit(
            f"PubMed esearch 返回不完整：声明 {declared_count}，idlist {len(pmids)}；"
            "保留上一份 weekly 输入并停止发布"
        )

    if not pmids:
        print("   无新文献，输出空文件。")
        _write_output([], archive=args.archive)
        return

    # Step 2: 批量获取 EDAT
    print("📅 获取 EDAT...")
    edat_map = fetch_edates(pmids)
    print(f"   查到 EDAT: {len(edat_map)}/{len(pmids)}")

    # Step 3: efetch XML
    print("📄 efetch XML...")
    all_articles = []
    parsed_pmids = set()
    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i:i+BATCH_SIZE]
        try:
            xml_data = eutils_post("efetch.fcgi", {
                "db": "pubmed",
                "id": ",".join(batch),
            }, retmode="xml", timeout=120)
            root = ET.fromstring(xml_data)
            for article in root.findall(".//PubmedArticle"):
                parsed = parse_article_xml(article, edat_map)
                if parsed and parsed["pmid"] not in parsed_pmids:
                    all_articles.append(parsed)
                    parsed_pmids.add(parsed["pmid"])
            for article in root.findall(".//PubmedBookArticle"):
                parsed = parse_book_article_xml(article, edat_map)
                if parsed and parsed["pmid"] not in parsed_pmids:
                    all_articles.append(parsed)
                    parsed_pmids.add(parsed["pmid"])
        except Exception as e:
            print(f"  ⚠ efetch batch {i//BATCH_SIZE + 1} failed: {e}", file=sys.stderr)

    print(f"   解析完成: {len(all_articles)} 篇")
    missing_pmids = [pmid for pmid in pmids if pmid not in parsed_pmids]
    if missing_pmids:
        print(f"   ⚠ 未解析 PMID: {len(missing_pmids)} 个（示例: {', '.join(missing_pmids[:8])}）")
        raise SystemExit("PubMed 返回集未完整解析；保留上一份 weekly 输入并停止发布")
    undated_pmids = [article["pmid"] for article in all_articles if not article.get("entry_date")]
    if undated_pmids:
        raise SystemExit(
            f"PubMed 有 {len(undated_pmids)} 篇缺少 entry date（示例: {', '.join(undated_pmids[:8])}）；"
            "保留上一份 weekly 输入并停止发布"
        )
    print()

    # Step 4: 输出
    _write_output(all_articles, archive=args.archive)

    # 摘要
    china_count = sum(
        1 for a in all_articles
        if any("China" in aff or "Chinese" in aff for aff in a["affiliations"])
    )
    print(f"📊 统计")
    print(f"   总文献: {len(all_articles)}")
    print(f"   中国相关(Affiliation): {china_count}")
    print(f"   总作者数: {sum(len(a['authors']) for a in all_articles)}")
    print(f"   作者-机构行: {sum(len(a.get('author_affiliations') or []) for a in all_articles)}")
    print(f"   覆盖期刊数: {len(set(a['journal'] for a in all_articles if a['journal']))}")


def _write_output(articles, archive=False):
    """写入 data/literature-weekly.json；归档需显式开启。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 主文件
    main_path = DATA_DIR / "literature-weekly.json"
    atomic_write_json(main_path, articles)
    print(f"📝 输出: {main_path} ({len(articles)} 篇)")

    if archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        date_str = TODAY.strftime("%Y-%m-%d")
        archive_path = ARCHIVE_DIR / f"literature_{date_str}.json"
        atomic_write_json(archive_path, articles)
        print(f"📦 归档: {archive_path}")
    else:
        print("📦 归档: 跳过（需要时使用 --archive）")


if __name__ == "__main__":
    main()
