#!/usr/bin/env python3
"""周更 link：识别到新指南/共识时，联动刷新三个既有板块，不再另设展示面板。

三处落点：
  中外指南共识差异 → data/guideline-divergence.json → data/landscape-data.js
  诊疗现状         → build-landscape-knowledge.py → treatmentChapters.js / clinicalQuestions.js
  领域重大事件     → build-source-signals.py → source-signals.js（与缓存同源）

证据边界：只有拿到全文、且有经审阅的增量立场卡时才改写结论与引文，
每条引文按 NFKC 规范化逐字回验原文；仅有 PubMed 摘要时只登记待补全文，
不臆造诊疗结论。全文缺失时任何改写都 fail closed，保留 last-good。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.io import (  # noqa: E402
    atomic_write_js_global,
    atomic_write_json,
    atomic_write_text,
    load_js_global,
)

DATA = Path(os.environ.get("MG_DATA_DIR") or PROJECT / "data")
SCRATCH = Path(os.environ.get("MG_GUIDELINE_SCRATCH") or Path.home() / ".hermes" / "cache" / "scratch" / "guidelines")
CACHE_PATH = DATA / "guideline-consensus-cache.json"
DIVERGENCE_PATH = DATA / "guideline-divergence.json"
LANDSCAPE_PATH = DATA / "landscape-data.js"
STATE_PATH = DATA / "guideline-view-state.json"
DELTAS_PATH = DATA / "guideline-stance-deltas.json"


def loadJson(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def canon(value: str) -> str:
    """与 analyze-guideline-divergence.py 一致的引文规范化口径。"""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("\u00ad", "").replace("\u2010", "").replace("\u2011", "")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())


def verifyQuote(quote: str, textCanon: str) -> tuple[bool, str]:
    """返回 (是否通过, exact/partial/none)。"""
    q = canon(quote)
    if not q:
        return False, "none"
    if q in textCanon:
        return True, "exact"
    if q[: max(24, int(len(q) * 0.7))] in textCanon:
        return True, "partial"
    return False, "none"


def corpusCounts(payload: dict[str, Any]) -> dict[str, int]:
    """中外差异只区分中国 / 国际；中国台湾语料计入中国侧。"""
    corpus = payload.get("corpus") or []
    return {
        "total": len(corpus),
        "china": sum(1 for item in corpus if item.get("region") in ("china", "taiwan")),
        "international": sum(1 for item in corpus if item.get("region") == "international"),
    }


def normalizeRegions(payload: dict[str, Any]) -> bool:
    """把历史 taiwan 分区并入 china，语料清单不再单列第三组。"""
    changed = False
    for doc in payload.get("corpus") or []:
        if doc.get("region") == "taiwan":
            doc["region"] = "china"
            changed = True
    return changed


def normalizeRegionsOnly(args) -> int:
    """一次性把中国台湾语料并入中国侧，并联动刷新三个板块的派生产物。"""
    payload = loadJson(DIVERGENCE_PATH, None)
    if not isinstance(payload, dict) or not payload.get("divergences"):
        print("⚠️ guideline-divergence.json 不可读，保留 last-good。")
        return 0
    if not normalizeRegions(payload):
        print("语料地区已只有「中国 / 国际」两侧，无需变更。")
        return 0
    payload["corpus_count"] = corpusCounts(payload)
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recomputeQuoteCheck(payload)
    atomic_write_json(DIVERGENCE_PATH, payload)
    updateLandscape(payload)
    if not args.skip_knowledge:
        runBuilder("build-landscape-knowledge.py")
    if not args.skip_channels:
        runBuilder("build-source-signals.py")
    print(f"✅ 中国台湾语料并入中国侧：{payload['corpus_count']}")
    return 0


def recomputeQuoteCheck(payload: dict[str, Any]) -> None:
    evidence = [
        item
        for divergence in payload.get("divergences") or []
        for item in divergence.get("evidence") or []
    ]
    verified = sum(1 for item in evidence if item.get("quote_verified"))
    payload["quote_check"] = {
        "total": len(evidence),
        "verified": verified,
        "rate": round(verified / len(evidence) * 100, 1) if evidence else None,
    }


def applyDelta(
    payload: dict[str, Any],
    pmid: str,
    delta: dict[str, Any],
    fullText: str,
) -> int:
    """应用一份经审阅的增量立场卡；任何引文无法回验即整体失败。"""
    corpusEntry = delta.get("corpus") or {}
    key = str(corpusEntry.get("key") or "")
    if not key:
        raise ValueError(f"{pmid} 的增量卡缺少 corpus.key")
    if not fullText.strip():
        raise ValueError(f"{pmid} 缺少全文，禁止写入未经回验的引文")

    # 全文落到与既有 34 份语料相同的 scratch 目录，供后续 --reverify-only 复用。
    textDir = SCRATCH / "texts"
    atomic_write_text(textDir / f"{key}.txt", fullText)

    corpus = payload.setdefault("corpus", [])
    if not any(item.get("key") == key for item in corpus):
        corpus.append({
            "key": key,
            "short_name": corpusEntry.get("short_name", ""),
            "name": corpusEntry.get("name", ""),
            "year": corpusEntry.get("year", ""),
            "region": corpusEntry.get("region", "international"),
            "lang": corpusEntry.get("lang", "en"),
            "dims": corpusEntry.get("dims", 0),
        })
        corpus.sort(key=lambda item: str(item.get("key", "")))

    textCanon = canon(fullText)
    byId = {str(item.get("id")): item for item in payload.get("divergences") or []}
    addedQuotes = 0
    for divergenceId, patch in (delta.get("divergence_patches") or {}).items():
        target = byId.get(str(divergenceId))
        if target is None:
            raise ValueError(f"{pmid} 的增量卡指向不存在的差异条目 {divergenceId}")
        for field, value in patch.items():
            if field != "evidence_add":
                target[field] = value
        evidence = target.setdefault("evidence", [])
        for quote in patch.get("evidence_add") or []:
            ok, match = verifyQuote(str(quote), textCanon)
            if not ok:
                raise ValueError(f"{pmid}/{divergenceId} 引文无法回验全文：{quote[:60]}")
            evidence.append({
                "doc": key,
                "short_name": corpusEntry.get("short_name", ""),
                "name": corpusEntry.get("name", ""),
                "year": corpusEntry.get("year", ""),
                "region": corpusEntry.get("region", "international"),
                "quote": str(quote),
                "quote_verified": True,
                "quote_match": match,
            })
            addedQuotes += 1

    payload["corpus_count"] = corpusCounts(payload)
    pending = [item for item in payload.get("pending_full_text") or [] if str(item.get("pmid")) != pmid]
    payload["pending_full_text"] = pending
    updates = payload.setdefault("incremental_updates", [])
    updates.append({
        "pmid": pmid,
        "corpus_key": key,
        "refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reviewed_quotes": addedQuotes,
    })
    return addedQuotes


def updateLandscape(payload: dict[str, Any]) -> None:
    """把刷新后的差异数据写回公开派生层，保持其余字段不动。"""
    data = load_js_global(LANDSCAPE_PATH, "MG_LANDSCAPE_DATA")
    if not isinstance(data, dict):
        raise ValueError("landscape-data.js 解析失败，保留 last-good")
    counts = payload.get("corpus_count") or {}
    view = dict(payload)
    view["status"] = "ready"
    view["status_label"] = f"中国 {counts.get('china', 0)} 份 / 国际 {counts.get('international', 0)} 份"
    data.setdefault("china_landscape", {})["guideline_divergence"] = view
    data.setdefault("overview", {})["guideline_divergence_count"] = len(payload.get("divergences") or [])
    atomic_write_js_global(LANDSCAPE_PATH, "MG_LANDSCAPE_DATA", data)


def runBuilder(name: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / name)],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{name} 失败：{(result.stderr or result.stdout)[-400:]}")
    tail = (result.stdout or "").strip().splitlines()
    print(f"  ↳ {name}: {tail[-1] if tail else 'ok'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-text", default="", help="新指南全文文本文件（.md/.txt），写入 scratch/texts/gNN.txt")
    parser.add_argument("--deltas", default=str(DELTAS_PATH), help="经审阅的增量立场卡 JSON")
    parser.add_argument("--pmid", default="", help="只处理指定 PMID（本次全文入库用），其余记录并入基线")
    parser.add_argument("--force", action="store_true", help="忽略刷新状态，强制重扫")
    parser.add_argument("--skip-knowledge", action="store_true", help="跳过诊疗现状重建（测试用）")
    parser.add_argument("--skip-channels", action="store_true", help="跳过来源频道重建（测试用）")
    parser.add_argument("--normalize-only", action="store_true", help="只把中国台湾语料并入中国侧，不处理新指南")
    args = parser.parse_args()

    if args.normalize_only:
        return normalizeRegionsOnly(args)

    cache = loadJson(CACHE_PATH, {})
    records = [item for item in cache.get("records") or [] if item.get("pmid")]
    if not records:
        print("⚠️ 指南/共识缓存为空或不可读，保留 last-good，本次不刷新。")
        return 0

    state = loadJson(STATE_PATH, {})
    refreshed = {str(item) for item in state.get("refreshed_pmids") or []}
    if args.pmid:
        newRecords = [item for item in records if str(item["pmid"]) == args.pmid]
        if not newRecords:
            raise SystemExit(f"PMID {args.pmid} 不在指南/共识缓存中")
        # 指定处理时把其余历史记录一并纳入基线，避免下一轮重复登记。
        refreshed = {str(item["pmid"]) for item in records}
    elif not refreshed and not args.force:
        # 首次运行时缓存里都是历史记录，只建立基线，不把旧指南误当本周新增。
        atomic_write_json(STATE_PATH, {
            "schema_version": "1.0",
            "refreshed_pmids": sorted({str(item["pmid"]) for item in records}),
            "last_refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "首次基线：历史指南不触发三板块改写",
        })
        print("首次运行：指南/共识缓存已建立基线，三板块保持上一版。")
        return 0
    else:
        newRecords = [item for item in records if str(item["pmid"]) not in refreshed] if not args.force else records
    if not newRecords:
        print("无新增指南/共识：三板块保持上一版，不改写结论。")
        return 0

    payload = loadJson(DIVERGENCE_PATH, None)
    if not isinstance(payload, dict) or not payload.get("divergences"):
        print("⚠️ guideline-divergence.json 不可读，保留 last-good，本次不刷新。")
        return 0
    # 长期规则：无论本轮是否有新指南，都保证语料只分中国 / 国际两侧。
    if normalizeRegions(payload):
        payload["corpus_count"] = corpusCounts(payload)

    deltas = loadJson(Path(args.deltas), {}).get("deltas") or {}
    suppliedText = Path(args.full_text).read_text(encoding="utf-8") if args.full_text else ""
    pending = list(payload.get("pending_full_text") or [])
    applied = 0
    quotesAdded = 0

    for record in newRecords:
        pmid = str(record["pmid"])
        delta = deltas.get(pmid)
        fullText = suppliedText
        # 全文已入库时周更可直接复用，不必每轮重新提供文件。
        if delta and not fullText:
            key = str((delta.get("corpus") or {}).get("key") or "")
            cached = SCRATCH / "texts" / f"{key}.txt"
            if key and cached.is_file():
                fullText = cached.read_text(encoding="utf-8")
        if delta and fullText:
            added = applyDelta(payload, pmid, delta, fullText)
            quotesAdded += added
            applied += 1
            refreshed.add(pmid)
            print(f"  ✓ {pmid}：全文入库并应用审阅增量（新增回验引文 {added} 条）")
        else:
            reason = "缺全文" if not fullText else "缺经审阅的增量立场卡"
            if not any(str(item.get("pmid")) == pmid for item in pending):
                pending.append({
                    "pmid": pmid,
                    "title": record.get("title", ""),
                    "entry_date": record.get("entry_date") or record.get("pub_date") or "",
                    "reason": reason,
                })
            refreshed.add(pmid)
            print(f"  · {pmid}：仅登记待补语料（{reason}），结论不改写")

    payload["pending_full_text"] = pending
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if applied:
        payload["method"] = (
            str(payload.get("method") or "")
            + "；周更发现新指南时按全文与经审阅增量卡联动刷新，引文逐字回验，未做全量 16 维立场重提取"
        )
    recomputeQuoteCheck(payload)

    # 全部校验通过后才落盘，避免半刷新污染两个板块。
    atomic_write_json(DIVERGENCE_PATH, payload)
    updateLandscape(payload)
    if not args.skip_knowledge:
        runBuilder("build-landscape-knowledge.py")
    if not args.skip_channels:
        runBuilder("build-source-signals.py")

    atomic_write_json(STATE_PATH, {
        "schema_version": "1.0",
        "refreshed_pmids": sorted(refreshed),
        "last_refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_new_pmids": [str(item["pmid"]) for item in newRecords],
        "applied_deltas": applied,
        "reviewed_quotes": quotesAdded,
    })
    print(
        f"✅ 三板块联动刷新：新增 {len(newRecords)} 篇 · 应用全文增量 {applied} 篇 · "
        f"语料 {payload['corpus_count']['total']} 份 · 引文回验 "
        f"{payload['quote_check']['verified']}/{payload['quote_check']['total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
