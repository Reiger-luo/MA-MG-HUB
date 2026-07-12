#!/usr/bin/env python3
"""
fetch-pubmed-full.py — MG-HUB PubMed 全量初始化

一次性拉取 PubMed 上所有 MG 相关文献（MeSH 为主，TiAb 补漏），
输出 data/literature-full.json。

策略：先按年分批（MeSH），再用 TiAb 补漏。
"""

import json, os, re, sys, time, xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import quote
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"

API_KEY = os.environ.get("NCBI_API_KEY", "")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def eutils_get(path, params):
    params["retmode"] = "json"
    if API_KEY:
        params["api_key"] = API_KEY
    qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{path}?{qs}"
    req = Request(url, headers={"User-Agent": "MG-HUB/2.0"})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def esearch_yearly(query, retmax=100000):
    """按年分批搜索，返回全部 PMID 列表（去重）"""
    all_pmids = set()
    years = list(range(2026, 2009, -1))  # 2026 → 2010
    for year in years:
        start = f"{year}/01/01"
        end = f"{year}/12/31" if year < 2026 else f"{year}/12/31"
        date_query = f'{query} AND {start}:{end}[Date - Entry]'
        try:
            data = json.loads(eutils_get("esearch.fcgi", {
                "db": "pubmed",
                "term": date_query,
                "retmax": retmax,
            }))
            pmids = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            all_pmids.update(pmids)
            print(f"  {year}: {count} hits, {len(pmids)} fetched (total dedup: {len(all_pmids)})")
        except Exception as e:
            print(f"  ⚠ {year} failed: {e}", file=sys.stderr)
        time.sleep(0.3)
    return list(all_pmids)


def fetch_edates(pmids):
    edat_map = {}
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i+200]
        try:
            data = json.loads(eutils_get("esummary.fcgi", {
                "db": "pubmed",
                "id": ",".join(batch),
            }))
            for uid_str, record in data.get("result", {}).items():
                if uid_str == "uids":
                    continue
                for h in record.get("history", []):
                    if h.get("pubstatus") == "entrez":
                        edat_map[uid_str] = h.get("date")
                        break
        except Exception as e:
            print(f"  ⚠ esummary batch failed: {e}", file=sys.stderr)
        time.sleep(0.2)
        if (i // 200) % 10 == 0:
            print(f"    EDAT progress: {len(edat_map)}/{len(pmids)}")
    return edat_map


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
        author_affs = unique_list(
            "".join(aff.itertext()).strip()
            for aff in author.findall("./AffiliationInfo/Affiliation")
            if "".join(aff.itertext()).strip()
        )
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


def parse_article_xml(article_elem, edat_map):
    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return None
    pmid = medline.findtext("PMID", "")
    if not pmid:
        return None

    title = "".join(medline.findtext(".//ArticleTitle", ""))
    # 标题补全——findtext 可能丢子标签文本
    title_elem = medline.find(".//ArticleTitle")
    if title_elem is not None:
        title = "".join(title_elem.itertext())

    abstract_parts = []
    for at in medline.findall(".//AbstractText"):
        label = at.get("Label", "")
        text = "".join(at.itertext())
        abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = "\n".join(abstract_parts)

    author_data = parse_authors(medline.findall(".//Article/AuthorList/Author"))
    # 期刊：优先全称（Title），次选 ISO 缩写
    journal_title = medline.findtext(".//Journal/Title", "")
    journal_iso = medline.findtext(".//Journal/ISOAbbreviation", "")
    journal = journal_title if journal_title else journal_iso

    pub_date_elem = medline.find(".//Journal/JournalIssue/PubDate")
    if pub_date_elem is not None:
        year = pub_date_elem.findtext("Year", "")
        month = pub_date_elem.findtext("Month", "")
        day = pub_date_elem.findtext("Day", "")
        pub_date = year
        if month:
            month_map = {
                "Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12",
            }
            if month in month_map:
                pub_date += f"-{month_map[month]}"
            elif month.isdigit():
                pub_date += f"-{month.zfill(2)}"
        if day and day.isdigit():
            pub_date += f"-{day.zfill(2)}"
    else:
        pub_date = ""

    doi = ""
    for eid in medline.findall(".//ArticleIdList/ArticleId"):
        if eid.get("IdType") == "doi":
            doi = eid.text or ""
            break

    # Publication Types
    pub_types = []
    for pt in medline.findall(".//PublicationTypeList/PublicationType"):
        if pt.text:
            pub_types.append(pt.text)

    entry_date = edat_map.get(pmid, "")

    return {
        "pmid": pmid,
        "title": title.strip(),
        "abstract": abstract.strip(),
        "authors": author_data["authors"],
        "first_authors": author_data["first_authors"],
        "corresponding_authors": author_data["corresponding_authors"],
        "corresponding_authors_source": author_data["corresponding_authors_source"],
        "author_affiliations": author_data["author_affiliations"],
        "journal": journal,
        "entry_date": entry_date,
        "pub_date": pub_date,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "pub_types": pub_types,
        "affiliations": author_data["affiliations"],
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
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def efetch_pmids(pmids, edat_map):
    articles = []
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i+200]
        try:
            params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
            if API_KEY:
                params["api_key"] = API_KEY
            qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{qs}"
            req = Request(url, headers={"User-Agent": "MG-HUB/2.0"})
            with urlopen(req, timeout=120) as resp:
                xml_data = resp.read().decode("utf-8")
            root = ET.fromstring(xml_data)
            for article in root.findall(".//PubmedArticle"):
                parsed = parse_article_xml(article, edat_map)
                if parsed:
                    articles.append(parsed)
        except Exception as e:
            print(f"  ⚠ efetch batch {i//200 + 1} failed: {e}", file=sys.stderr)
        time.sleep(0.3)
        if (i // 200) % 5 == 0:
            print(f"    efetch progress: {len(articles)}/{len(pmids)}")
    return articles


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("📡 MG-HUB PubMed 全量初始化")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # ── Step 1: MeSH 按年分批 ──
    print("🔍 Pass 1: MeSH 按年搜索")
    mesh_query = '"Myasthenia Gravis"[MeSH]'
    mesh_pmids = esearch_yearly(mesh_query)
    print(f"\n  MeSH 总去重: {len(mesh_pmids)}")
    print()

    # ── Step 2: TiAb 补漏 ──
    print("🔍 Pass 2: TiAb 补漏")
    tiab_query = 'myasthenia gravis[Title/Abstract]'
    tiab_data = json.loads(eutils_get("esearch.fcgi", {
        "db": "pubmed",
        "term": tiab_query,
        "retmax": 100000,
    }))
    tiab_pmids = set(tiab_data.get("esearchresult", {}).get("idlist", []))
    new_pmids = list(tiab_pmids - set(mesh_pmids))
    print(f"  TiAb: {len(tiab_pmids)} | 补漏: {len(new_pmids)} 篇")
    print()

    # ── 合并 ──
    all_pmids = mesh_pmids + new_pmids
    print(f"📊 总去重 PMID: {len(all_pmids)}")

    if not all_pmids:
        print("  无数据，退出。")
        return

    # ── Step 3: EDAT ──
    print("\n📅 获取 EDAT...")
    edat_map = fetch_edates(all_pmids)

    # ── Step 4: efetch XML ──
    print("\n📄 efetch XML 元数据...")
    articles = efetch_pmids(all_pmids, edat_map)
    print(f"\n   解析完成: {len(articles)} 篇")

    # ── 输出 ──
    date_str = datetime.now().strftime("%Y-%m-%d")
    main_path = DATA_DIR / "literature-full.json"
    with open(main_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n📝 输出: {main_path}")

    archive_path = ARCHIVE_DIR / f"literature-full_{date_str}.json"
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📦 归档: {archive_path}")

    # ── 统计 ──
    china_count = sum(
        1 for a in articles
        if any("China" in aff or "Chinese" in aff for aff in a["affiliations"])
    )
    print(f"\n📊 统计")
    print(f"   总文献: {len(articles)}")
    print(f"   中国相关: {china_count}")
    print(f"   总作者数: {sum(len(a['authors']) for a in articles)}")
    print(f"   期刊数: {len(set(a['journal'] for a in articles if a['journal']))}")
    print(f"   数据文件大小: {os.path.getsize(main_path) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
