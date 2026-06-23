#!/usr/bin/env python3
"""
build-knowledge-data.py — 从 efgartigimod-wiki Obsidian vault 提取核心知识节点，
编译为 MA-MG-HUB 知识库页面使用的 data/knowledge-graph.js。

只扫描 4 类核心知识节点（concepts/ entities/ data-points/ comparisons/），
studies/ 不进图谱，而是作为核心节点的关联研究列表呈现。

用法:
    python scripts/build-knowledge-data.py
    python scripts/build-knowledge-data.py --vault /path/to/efgartigimod-wiki
    MG_WIKI_VAULT=/path python scripts/build-knowledge-data.py

vault 路径解析优先级: --vault 参数 > $MG_WIKI_VAULT > 默认 iCloud 路径。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ── 核心节点类型 ───────────────────────────────────────────────
CORE_DIRS = {
    "concepts": "concept",
    "entities": "entity",
    "data-points": "data-point",
    "comparisons": "comparison",
}

VAULT_NAME = "efgartigimod-wiki"
DEFAULT_VAULT = Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / VAULT_NAME

PROJECT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT / "data" / "knowledge-graph.js"


# ── frontmatter 解析（轻量 YAML 子集，只处理 vault 用到的格式）──
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """返回 (frontmatter_dict, body)。无 frontmatter 时返回 ({}, text)。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 4:].lstrip("\n")
    return _parse_yaml_lite(fm_text), body


def _parse_yaml_lite(text: str) -> dict:
    """解析 vault 实际用到的 YAML 子集：标量、列表、行内数组。"""
    fm: dict = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # 列表项（- value）
        if line.startswith("- ") and current_key is not None:
            val = _strip_quotes(line[2:].strip())
            if isinstance(fm.get(current_key), list):
                fm[current_key].append(val)
            else:
                fm[current_key] = [val]
            continue
        # key: value
        m = re.match(r"^([\w-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            fm[key] = []
            current_key = key
        else:
            fm[key] = _parse_scalar(value)
            current_key = key
    return fm


def _parse_scalar(value: str):
    """标量或行内数组 [a, b, c]。"""
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1]
        return [_strip_quotes(x.strip()) for x in inner.split(",") if x.strip()]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return _strip_quotes(v)


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


# ── 正文提取 ───────────────────────────────────────────────────
def extract_summary(body: str, limit: int = 200) -> str:
    """跳过首个 H1，取第一段实质内容（引用块或正文段落），清理 obsidian 引用标记。"""
    lines = body.splitlines()
    # 跳过首个 H1
    skipped_h1 = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if not skipped_h1 and stripped.startswith("# "):
            skipped_h1 = True
            continue
        # 跳过纯表格分隔行 / Markdown 表格头
        if stripped.startswith("|") and set(stripped.replace("|", "").replace("-", "").replace(":", "")) == set():
            continue
        collected.append(stripped)
        if len(" ".join(collected)) >= limit * 3:
            break
    summary = " ".join(collected)
    summary = _clean_wiki_markup(summary)
    if len(summary) > limit:
        # 在字数边界截断
        cut = summary[:limit]
        # 尽量在句号/空格处断
        for sep in ("。", ". ", "；", "; "):
            idx = cut.rfind(sep)
            if idx > limit // 2:
                cut = summary[: idx + len(sep)]
                break
        summary = cut.rstrip() + "…"
    return summary or "（无摘要）"


def _clean_wiki_markup(text: str) -> str:
    """清理 obsidian/wikitext 标记，保留可读文本。"""
    # 行内脚注 ^[...]（含嵌套括号）→ 删除
    text = strip_inline_footnotes(text)
    # wikilink [[a|b]] → b；[[a]] → a
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # 普通 markdown 链接 [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 加粗/斜体标记
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    # 代码标记
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 折叠多余空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_inline_footnotes(text: str) -> str:
    """剥离 Obsidian 行内脚注 ^[...]（可能嵌套括号）。

    如 '^[[[adapt-study]]: Howard 2021, p15]' → ''。
    采用括号配平扫描，从 '^[开始匹配到对应的 ']'。
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "^" and i + 1 < n and text[i + 1] == "[":
            # 跳到匹配的 ']'
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if text[j] == "[":
                    depth += 1
                elif text[j] == "]":
                    depth -= 1
                j += 1
            i = j  # 跳过整个脚注
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def extract_wikilinks(body: str) -> list[str]:
    """提取所有 [[link]] 目标（不含 alias、不含 #anchor）。返回去重后的 slug 列表。"""
    body = strip_inline_footnotes(body)
    slugs: list[str] = []
    for m in re.finditer(r"\[\[([^\]|\n]+?)\]\]", body):
        target = m.group(1).split("|")[0].split("#")[0].strip()
        if target:
            slugs.append(target)
    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


# ── vault 扫描 ────────────────────────────────────────────────
def scan_vault(vault: Path) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """
    扫描核心节点目录。
    返回:
        nodes_by_slug: { slug: node_dict }
        studies_by_slug: { slug: [study_title, ...] }  关联的非核心笔记（含路径）
    """
    nodes_by_slug: dict[str, dict] = {}
    all_core_slugs: set[str] = set()

    # 第一遍：收集所有核心 slug（用于区分边和关联列表）
    for dir_name in CORE_DIRS:
        dir_path = vault / dir_name
        if not dir_path.exists():
            print(f"⚠️  目录不存在: {dir_path}", file=sys.stderr)
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            all_core_slugs.add(md_file.stem)

    # 第二遍：解析节点
    for dir_name, node_type in CORE_DIRS.items():
        dir_path = vault / dir_name
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            slug = md_file.stem
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(text)

            tags = fm.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            wikilinks = extract_wikilinks(body)
            summary = extract_summary(body)

            node = {
                "id": slug,
                "title": fm.get("title") or slug.replace("-", " ").replace("_", " "),
                "type": node_type,
                "tags": tags,
                "confidence": fm.get("confidence", "unknown"),
                "status": fm.get("status", "unknown"),
                "contested": bool(fm.get("contested", False)),
                "contradictions": _as_list(fm.get("contradictions", [])),
                "summary": summary,
                "pmid": fm.get("pmid"),
                "updated": fm.get("updated") or fm.get("created"),
                "rel_path": f"{dir_name}/{md_file.name}",
                "wikilinks": wikilinks,
            }
            nodes_by_slug[slug] = node

    # 第三遍：区分核心关联（边）vs 非核心关联（study list）
    studies_by_slug: dict[str, list[str]] = {}
    for slug, node in nodes_by_slug.items():
        core_links = []
        non_core_links = []
        for link in node["wikilinks"]:
            # wikilink 可能是 slug 或 path；取末段作为 slug
            link_slug = link.split("/")[-1]
            if link_slug in all_core_slugs and link_slug != slug:
                core_links.append(link_slug)
            elif link_slug != slug:
                non_core_links.append(link)
        node["core_links"] = core_links
        studies_by_slug[slug] = non_core_links[:30]  # 限制数量

    return nodes_by_slug, studies_by_slug


def _as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ── 布局计算：按 type 分簇径向扇形布局 ──────────────────────
def compute_layout(nodes_by_slug: dict[str, dict]) -> None:
    """
    entity 置于中心；concept / data-point / comparison 三簇围绕成扇形。
    同簇内节点沿一段弧线均匀分布，关联度高的靠近簇心方向。
    坐标写入 node.x / node.y（SVG viewBox 1100x720）。
    """
    CENTER_X, CENTER_Y = 550, 360
    CLUSTER_RADIUS = 240
    # 三簇方向角（从正东逆时针，数学坐标）
    CLUSTER_ANGLES = {
        "entity": None,                 # 中心
        "concept": math.pi / 2,         # 正上
        "data-point": 7 * math.pi / 4,  # 右下（315°，屏幕右下）
        "comparison": 3 * math.pi / 4,  # 左下（135°，屏幕左下）
    }
    SPAN = 0.85  # 每簇弧长（弧度），节点沿此弧分布

    # 按 type 分组
    by_type: dict[str, list[str]] = defaultdict(list)
    for slug, node in nodes_by_slug.items():
        by_type[node["type"]].append(slug)

    # entity 放中心（多个实体则小圆环）
    entities = by_type.get("entity", [])
    if len(entities) == 1:
        nodes_by_slug[entities[0]]["x"], nodes_by_slug[entities[0]]["y"] = CENTER_X, CENTER_Y
    elif len(entities) > 1:
        ring_r = 48
        for i, slug in enumerate(entities):
            a = 2 * math.pi * i / len(entities) + math.pi / 2
            nodes_by_slug[slug]["x"] = round(CENTER_X + ring_r * math.cos(a), 1)
            nodes_by_slug[slug]["y"] = round(CENTER_Y - ring_r * math.sin(a), 1)

    # 三簇：节点沿弧线分布
    for type_name, angle in CLUSTER_ANGLES.items():
        if angle is None:
            continue
        slugs = by_type.get(type_name, [])
        if not slugs:
            continue
        # 关联度高的排在簇心方向（弧线中点）
        slugs_sorted = sorted(slugs, key=lambda s: -len(nodes_by_slug[s].get("core_links", [])))
        n = len(slugs_sorted)
        for i, slug in enumerate(slugs_sorted):
            if n == 1:
                t = 0.0
            else:
                t = (i / (n - 1)) - 0.5  # -0.5..+0.5
            node_angle = angle + t * SPAN  # 该节点在弧上的角度
            # 屏幕坐标：y 向下为正，故 y = CENTER_Y - r*sin
            x = CENTER_X + CLUSTER_RADIUS * math.cos(node_angle)
            y = CENTER_Y - CLUSTER_RADIUS * math.sin(node_angle)
            nodes_by_slug[slug]["x"] = round(x, 1)
            nodes_by_slug[slug]["y"] = round(y, 1)


# ── 边构建（仅核心节点间去重）─────────────────────────────────
def build_edges(nodes_by_slug: dict[str, dict]) -> list[dict]:
    edges: list[dict] = []
    seen: set[tuple] = set()
    for slug, node in nodes_by_slug.items():
        for target in node.get("core_links", []):
            if target not in nodes_by_slug:
                continue
            key = tuple(sorted([slug, target]))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"from": key[0], "to": key[1]})
    return edges


# ── 输出 ───────────────────────────────────────────────────────
def build_output(nodes_by_slug: dict[str, dict], studies_by_slug: dict[str, dict], vault: Path) -> dict:
    edges = build_edges(nodes_by_slug)

    # 统计
    type_counts: dict[str, int] = defaultdict(int)
    high_conf = 0
    contested = 0
    draft = 0
    for node in nodes_by_slug.values():
        type_counts[node["type"]] += 1
        if node["confidence"] == "high":
            high_conf += 1
        if node["contested"]:
            contested += 1
        if node["status"] == "draft":
            draft += 1

    nodes_out = []
    study_links_out = {}
    for slug, node in nodes_by_slug.items():
        study_links_out[slug] = [
            {"title": s.split("/")[-1].replace("-", " "), "slug": s}
            for s in studies_by_slug.get(slug, [])
        ]
        nodes_out.append({
            "id": node["id"],
            "title": node["title"],
            "type": node["type"],
            "tags": node["tags"],
            "confidence": node["confidence"],
            "status": node["status"],
            "contested": node["contested"],
            "contradictions": node["contradictions"],
            "summary": node["summary"],
            "pmid": node["pmid"],
            "updated": node["updated"],
            "rel_path": node["rel_path"],
            "x": node.get("x", 0),
            "y": node.get("y", 0),
            "study_count": len(study_links_out[slug]),
            "obsidian_url": f"obsidian://open?vault={VAULT_NAME}&file={node['rel_path']}",
        })

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "vault_path": str(vault),
        "stats": {
            "total_nodes": len(nodes_out),
            "concepts": type_counts.get("concept", 0),
            "entities": type_counts.get("entity", 0),
            "data_points": type_counts.get("data-point", 0),
            "comparisons": type_counts.get("comparison", 0),
            "high_confidence": high_conf,
            "contested": contested,
            "draft": draft,
            "edges": len(edges),
        },
        "nodes": nodes_out,
        "edges": edges,
        "study_links": study_links_out,
    }


def write_js(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* AUTO-GENERATED by scripts/build-knowledge-data.py\n"
        f" * 来源: efgartigimod-wiki Obsidian vault\n"
        f" * 生成时间: {data['generated_at']}\n"
        " * 请勿手动编辑；运行脚本重新生成。\n"
        " */\n"
    )
    path.write_text(header + f"window.MG_KNOWLEDGE_GRAPH = {payload};\n", encoding="utf-8")
    print(f"✅ 已生成 {path} ({path.stat().st_size // 1024} KB)")


def resolve_vault(arg_vault: str | None) -> Path:
    if arg_vault:
        return Path(arg_vault).expanduser()
    env = os.environ.get("MG_WIKI_VAULT")
    if env:
        return Path(env).expanduser()
    return DEFAULT_VAULT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="efgartigimod-wiki vault 路径（默认 iCloud Obsidian 目录）")
    ap.add_argument("--out", default=str(OUT_PATH), help="输出 .js 路径")
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    if not vault.exists():
        print(f"❌ vault 不存在: {vault}", file=sys.stderr)
        print("   请用 --vault 指定路径，或设置 MG_WIKI_VAULT 环境变量", file=sys.stderr)
        return 1

    print(f"📦 扫描 vault: {vault}")
    nodes_by_slug, studies_by_slug = scan_vault(vault)
    if not nodes_by_slug:
        print("❌ 未找到任何核心节点，终止。", file=sys.stderr)
        return 1

    compute_layout(nodes_by_slug)
    data = build_output(nodes_by_slug, studies_by_slug, vault)
    write_js(data, Path(args.out))

    s = data["stats"]
    print(f"   节点: {s['total_nodes']}（实体 {s['entities']} · 概念 {s['concepts']} · 数据点 {s['data_points']} · 对比 {s['comparisons']}）")
    print(f"   边: {s['edges']} · 高置信 {s['high_confidence']} · 争议 {s['contested']} · 草稿 {s['draft']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
