#!/usr/bin/env python3
"""
fetch-pubmed-weekly.py — MG-HUB PubMed 数据管线

每周抓取过去 14 天新上线的 MG 相关文献，输出 data/literature-weekly.json。

检索策略：
  ("Myasthenia Gravis"[MeSH] OR myasthenia gravis[Title/Abstract])
  AND [Date - Entry] 14天窗口

字段说明：
  - study_types / evidence_level 留空，待后处理管线回填
  - china_related 暂不在管线层判定，保留 affiliations 原始数据供 UI 筛选
"""

import argparse, json, os, sys, time, ssl, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import quote
from pathlib import Path

# macOS SSL 证书兼容（pubmed-search skill 已验证方案）
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# ── 配置 ──────────────────────────────────────────────
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
WINDOW_DAYS = 14      # 时间窗天数
RETMAX = 10000         # 最大返回数（safe upper bound）

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

# ── NCBI API key ──
API_KEY = os.environ.get("NCBI_API_KEY", "")


# ── 工具函数 ───────────────────────────────────────────

def eutils_get(path, params):
    """调 E-utilities API，返回 response body"""
    params["retmode"] = "json"
    if API_KEY:
        params["api_key"] = API_KEY
    qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"{BASE_URL}/{path}?{qs}"
    req = Request(url, headers={"User-Agent": "MG-HUB/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


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

    # 标题
    title_elem = medline.find(".//ArticleTitle")
    title = "".join(title_elem.itertext()) if title_elem is not None else ""

    # 摘要
    abstract_parts = []
    for at in medline.findall(".//AbstractText"):
        label = at.get("Label", "")
        text = "".join(at.itertext())
        if label:
            abstract_parts.append(f"{label}: {text}")
        else:
            abstract_parts.append(text)
    abstract = "\n".join(abstract_parts)

    # 作者
    authors = []
    for author in medline.findall(".//Author"):
        last = author.findtext("LastName", "")
        fore = author.findtext("ForeName", "")
        if last:
            full = f"{last} {fore}" if fore else last
            authors.append(full.strip())

    # 期刊：优先全称（Title），次选 ISO 缩写
    journal_title = medline.findtext(".//Journal/Title", "")
    journal_iso = medline.findtext(".//Journal/ISOAbbreviation", "")
    journal = journal_title if journal_title else journal_iso

    # PubDate
    pub_date_elem = medline.find(".//Journal/JournalIssue/PubDate")
    if pub_date_elem is not None:
        year = pub_date_elem.findtext("Year", "")
        month = pub_date_elem.findtext("Month", "")
        day = pub_date_elem.findtext("Day", "")
        pub_date = f"{year}" if year else ""
        if month:
            pub_date += f"-{month}"
        if day:
            pub_date += f"-{day}"
    else:
        pub_date = ""

    # DOI
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

    # URL
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    # Affiliation（只取第一作者的）
    affiliations = []
    first_aff = medline.find(".//Author[1]/AffiliationInfo/Affiliation")
    if first_aff is not None and first_aff.text:
        affiliations.append(first_aff.text.strip())

    # Entry date (EDAT)
    entry_date = edat_map.get(pmid, "")

    return {
        "pmid": pmid,
        "title": title.strip(),
        "abstract": abstract.strip(),
        "authors": authors,
        "journal": journal,
        "entry_date": entry_date,
        "pub_date": pub_date,
        "doi": doi,
        "url": url,
        "affiliations": affiliations,
        "pub_types": pub_types,
        "china_related": None,      # 暂空
        "study_types": [],           # 后处理回填
        "evidence_level": None,      # 后处理回填
    }


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
    batch_size = 200
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i+batch_size]
        try:
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            }
            if API_KEY:
                params["api_key"] = API_KEY
            qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url = f"{BASE_URL}/efetch.fcgi?{qs}"
            req = Request(url, headers={"User-Agent": "MG-HUB/1.0"})
            with urlopen(req, timeout=60) as resp:
                xml_data = resp.read().decode("utf-8")
            root = ET.fromstring(xml_data)
            for article in root.findall(".//PubmedArticle"):
                parsed = parse_article_xml(article, edat_map)
                if parsed:
                    all_articles.append(parsed)
        except Exception as e:
            print(f"  ⚠ efetch batch {i//batch_size + 1} failed: {e}", file=sys.stderr)
        time.sleep(0.3)

    print(f"   解析完成: {len(all_articles)} 篇")
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
    print(f"   覆盖期刊数: {len(set(a['journal'] for a in all_articles if a['journal']))}")


def _write_output(articles, archive=False):
    """写入 data/literature-weekly.json；归档需显式开启。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 主文件
    main_path = DATA_DIR / "literature-weekly.json"
    with open(main_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📝 输出: {main_path} ({len(articles)} 篇)")

    if archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        date_str = TODAY.strftime("%Y-%m-%d")
        archive_path = ARCHIVE_DIR / f"literature_{date_str}.json"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"📦 归档: {archive_path}")
    else:
        print("📦 归档: 跳过（需要时使用 --archive）")


if __name__ == "__main__":
    main()
