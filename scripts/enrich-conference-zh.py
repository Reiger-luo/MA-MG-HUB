#!/usr/bin/env python3
"""Enrich conference abstracts with Chinese abstract translations and KOL key messages.

Reads data/conference-data.json or .js, calls the shared DeepSeek client, and writes
both JSON and JS artifacts. This is intentionally opt-in; the normal conference
builder remains deterministic and can run without LLM credentials.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA_JSON = PROJECT / "data" / "conference-data.json"
DATA_JS = PROJECT / "data" / "conference-data.js"
SCRIPTS = PROJECT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from llm_client import complete  # noqa: E402

SYSTEM = """你是医学会议摘要翻译与医学事务 key message 提炼助手。
要求：
1. 只输出 JSON，不要 Markdown。
2. abstractZh 必须忠实翻译英文 abstract，不删减、不扩写、不加入原文没有的信息。
3. 保留药物名、研究名、量表名、终点、时间点、P 值、百分比、剂量和随机比例。
4. kolKeyMessageZh 是给 KOL 交流用的 1 句中文 key message，必须优先包含明确数据、终点或设计信息；没有效应量时说明“仅提供设计/终点，疗效数据待核查”，不要编造。
"""


def load_payload() -> dict:
    if DATA_JSON.exists():
        return json.loads(DATA_JSON.read_text(encoding="utf-8"))
    text = DATA_JS.read_text(encoding="utf-8")
    prefix = "window.MG_CONFERENCE_DATA = "
    if not text.startswith(prefix):
        raise RuntimeError(f"Unexpected JS payload prefix in {DATA_JS}")
    body = text[len(prefix):].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def write_payload(payload: dict) -> None:
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DATA_JS.write_text(
        "window.MG_CONFERENCE_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def needs_enrichment(item: dict, force: bool = False) -> bool:
    if force:
        return bool(item.get("abstract"))
    insight = item.get("deepInsight") or {}
    return bool(item.get("abstract")) and (not item.get("abstractZh") or not insight.get("kolKeyMessageZh"))


def parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON array")
    return data


def enrich_batch(batch: list[dict]) -> list[dict]:
    payload = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "abstract": item.get("abstract"),
            "researchType": item.get("researchType"),
            "keyMetrics": (item.get("deepInsight") or {}).get("keyMetrics", [])[:3],
        }
        for item in batch
    ]
    prompt = "请为以下会议摘要生成字段。返回 JSON array，每项结构必须为：{id, abstractZh, kolKeyMessageZh}。\n\n" + json.dumps(payload, ensure_ascii=False)
    reply = complete(prompt, system=SYSTEM, temperature=0.1, max_tokens=8192, use_cache=True)
    rows = parse_json_array(reply)
    by_id = {row.get("id"): row for row in rows if isinstance(row, dict) and row.get("id")}
    missing = [item.get("id") for item in batch if item.get("id") not in by_id]
    if missing:
        raise ValueError(f"LLM response missing ids: {missing}")
    return rows


def apply_rows(items_by_id: dict[str, dict], rows: list[dict]) -> int:
    updated = 0
    for row in rows:
        item_id = str(row.get("id") or "")
        item = items_by_id.get(item_id)
        if not item:
            continue
        abstract_zh = str(row.get("abstractZh") or "").strip()
        key_message = str(row.get("kolKeyMessageZh") or "").strip()
        if abstract_zh:
            item["abstractZh"] = abstract_zh
        if key_message:
            insight = item.setdefault("deepInsight", {})
            insight["kolKeyMessageZh"] = key_message
        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 条缺失项；0 表示全部")
    parser.add_argument("--chunk-size", type=int, default=4)
    parser.add_argument("--force", action="store_true", help="重译所有有英文 abstract 的条目")
    args = parser.parse_args()

    payload = load_payload()
    abstracts = payload.get("abstracts", [])
    items = [item for item in abstracts if needs_enrichment(item, force=args.force)]
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("No conference abstracts need enrichment.")
        return

    items_by_id = {item.get("id"): item for item in abstracts if item.get("id")}
    total_updated = 0
    for index in range(0, len(items), args.chunk_size):
        batch = items[index : index + args.chunk_size]
        try:
            rows = enrich_batch(batch)
        except Exception as exc:
            if len(batch) == 1:
                raise
            print(f"⚠ batch failed ({index + 1}-{index + len(batch)}): {exc}; retrying one by one", file=sys.stderr)
            rows = []
            for item in batch:
                rows.extend(enrich_batch([item]))
        total_updated += apply_rows(items_by_id, rows)
        write_payload(payload)
        print(f"updated {min(index + len(batch), len(items))}/{len(items)}", flush=True)

    print(f"Enriched {total_updated} conference abstracts.")


if __name__ == "__main__":
    main()
