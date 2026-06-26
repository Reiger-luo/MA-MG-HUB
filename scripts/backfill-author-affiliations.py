#!/usr/bin/env python3
"""
backfill-author-affiliations.py — 为本地 full PubMed 库补齐作者级机构。

只改写每篇文献的：
- author_affiliations: 每位作者自己的 AffiliationInfo
- affiliations: 全作者机构去重

不会覆盖证据等级、IF、研究类型、摘要等下游富集字段。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import shutil
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
FULL_PATH = DATA_DIR / "literature-full.json"
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY", "")


def unique_list(values):
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def extract_author_name(author_elem):
    last = author_elem.findtext("LastName", "")
    fore = author_elem.findtext("ForeName", "")
    collective = author_elem.findtext("CollectiveName", "")
    if last:
        return f"{last} {fore}".strip() if fore else last.strip()
    return collective.strip()


def parse_article_authors(article_elem):
    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return None, [], []
    pmid = medline.findtext("PMID", "")
    if not pmid:
        return None, [], []

    author_affiliations = []
    all_affiliations = []
    for position, author in enumerate(medline.findall(".//Author"), 1):
        name = extract_author_name(author)
        if not name:
            continue
        author_affs = []
        for aff in author.findall("./AffiliationInfo/Affiliation"):
            if aff.text and aff.text.strip():
                author_affs.append(aff.text.strip())
        author_affs = unique_list(author_affs)
        all_affiliations.extend(author_affs)
        author_affiliations.append({
            "position": position,
            "name": name,
            "affiliations": author_affs,
        })
    return pmid, author_affiliations, unique_list(all_affiliations)


def efetch_author_affiliations(pmids, batch_size=100):
    by_pmid = {}
    failed_batches = 0
    for start in range(0, len(pmids), batch_size):
        batch = pmids[start:start + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
        }
        if API_KEY:
            params["api_key"] = API_KEY
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"{BASE_URL}/efetch.fcgi?{qs}"
        xml_data = None
        for attempt in range(1, 3):
            try:
                xml_data = curl_get(url)
                break
            except Exception as exc:
                try:
                    req = Request(url, headers={"User-Agent": "MG-HUB/2.0"})
                    with urlopen(req, timeout=60) as resp:
                        xml_data = resp.read().decode("utf-8")
                    break
                except Exception as urllib_exc:
                    exc = f"{exc}; urllib fallback: {urllib_exc}"
                if attempt == 2:
                    failed_batches += 1
                    print(f"    ⚠ 批次失败 {start // batch_size + 1}: {exc}", flush=True)
                else:
                    print(f"    ⚠ 批次重试 {start // batch_size + 1} ({attempt}/2): {exc}", flush=True)
                    time.sleep(2 * attempt)
        if not xml_data:
            continue
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            pmid, author_affiliations, affiliations = parse_article_authors(article)
            if pmid:
                by_pmid[pmid] = {
                    "author_affiliations": author_affiliations,
                    "affiliations": affiliations,
                }
        print(f"    efetch author affiliations: {min(start + batch_size, len(pmids))}/{len(pmids)}", flush=True)
        time.sleep(0.34)
    if failed_batches:
        print(f"    ⚠ 未完成批次数: {failed_batches}", flush=True)
    return by_pmid


def curl_get(url):
    result = subprocess.run(
        ["curl", "-L", "--retry", "1", "--connect-timeout", "15", "--max-time", "60", "-s", url],
        check=True,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        raise RuntimeError("curl returned empty body")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Backfill author-level PubMed affiliations into literature-full.json")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 篇，用于调试")
    parser.add_argument("--start", type=int, default=0, help="从第 N 条 PMID 开始处理，用于断点续跑")
    parser.add_argument("--batch-size", type=int, default=100, help="每批 efetch PMID 数")
    parser.add_argument("--no-backup", action="store_true", help="不写 archive 备份")
    args = parser.parse_args()

    if not FULL_PATH.exists():
        raise SystemExit(f"缺少 {FULL_PATH}")

    articles = json.loads(FULL_PATH.read_text(encoding="utf-8"))
    pmids = [article.get("pmid") for article in articles if article.get("pmid")]
    if args.start:
        pmids = pmids[args.start:]
    if args.limit:
        pmids = pmids[:args.limit]

    print("PubMed 作者级机构回填", flush=True)
    print(f"  full 文献数: {len(articles)}", flush=True)
    print(f"  本次处理 PMID: {len(pmids)}", flush=True)

    if not args.no_backup:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = ARCHIVE_DIR / f"literature-full_author-affiliation-backup_{stamp}.json"
        shutil.copy2(FULL_PATH, backup_path)
        print(f"  备份: {backup_path.relative_to(PROJECT)}", flush=True)

    target_pmids = set(pmids)
    fetched = efetch_author_affiliations(pmids, batch_size=args.batch_size)
    changed = 0
    missing = 0
    for article in articles:
        pmid = article.get("pmid")
        if pmid not in target_pmids:
            continue
        if pmid not in fetched:
            missing += 1
            continue
        patch = fetched[pmid]
        before = (article.get("author_affiliations"), article.get("affiliations"))
        article["author_affiliations"] = patch["author_affiliations"]
        article["affiliations"] = patch["affiliations"]
        after = (article.get("author_affiliations"), article.get("affiliations"))
        changed += int(before != after)

    FULL_PATH.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("完成", flush=True)
    print(f"  更新文献: {changed}", flush=True)
    print(f"  未取回 PMID: {missing}", flush=True)
    print(f"  输出: {FULL_PATH.relative_to(PROJECT)}", flush=True)


if __name__ == "__main__":
    main()
