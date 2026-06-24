#!/usr/bin/env python3
"""
build-curated-topic-data.py - 从本地 efgartigimod-wiki 生成医学事务专题策展层。

本脚本在每周网站管线中自动执行一次。wiki 是否维护由 Hermes/Obsidian 负责；
网站管线只读取当前本地版本，生成可上线的结构化专题数据。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DEFAULT_VAULT = Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / "efgartigimod-wiki"
FULL_PATH = DATA_DIR / "literature-full.json"
KNOWLEDGE_PATH = DATA_DIR / "knowledge-graph.js"
OUT_PATH = DATA_DIR / "curated-topics.js"

CURATED_DIRS = {
    "concepts": "concept",
    "entities": "entity",
    "data-points": "dataPoint",
    "comparisons": "comparison",
}

ANCHOR_RULES = [
    ("efgartigimod", ["efgartigimod", "vyvgart", "argx-113", "艾加莫德"]),
    ("fcrnInhibition", ["fcrn", "neonatal fc receptor", "igg recycling"]),
    ("generalizedMg", ["generalized mg", "generalised mg", "gmg", "全身型"]),
    ("achrPositive", ["achr", "acetylcholine receptor", "aChR".lower(), "乙酰胆碱受体"]),
    ("muskPositive", ["musk", "muscle-specific kinase"]),
    ("seronegativeMg", ["seronegative", "血清阴性"]),
    ("chinaEvidence", ["china", "chinese", "中国", "中文", "cmgcg", "北大", "唐都", "青岛"]),
    ("realWorldEvidence", ["real-world", "real world", "rwe", "真实世界", "回顾性", "前瞻性"]),
    ("safetyOutcome", ["safety", "adverse", "infection", "faers", "安全", "不良", "感染"]),
    ("steroidSparing", ["steroid-sparing", "steroid sparing", "glucocorticoid", "减激素", "gc 减量", "激素"]),
    ("rapidOnset", ["rapid", "early response", "fast-acting", "起效", "快速", "早期应答"]),
    ("longTermDurability", ["long-term", "maintenance", "multi-cycle", "多周期", "长期", "维持"]),
    ("mgAdl", ["mg-adl", "adl"]),
    ("qmg", ["qmg"]),
    ("mgQol", ["mg-qol", "qol", "quality of life"]),
    ("complementInhibition", ["complement", "c5", "eculizumab", "ravulizumab", "zilucoplan", "补体"]),
    ("eculizumab", ["eculizumab", "soliris"]),
    ("ravulizumab", ["ravulizumab", "ultomiris"]),
    ("zilucoplan", ["zilucoplan"]),
    ("rozanolixizumab", ["rozanolixizumab", "rystiggo"]),
    ("nipocalimab", ["nipocalimab"]),
    ("batoclimab", ["batoclimab"]),
    ("rituximab", ["rituximab", "cd20"]),
    ("bCellTargeting", ["b-cell", "b cell", "cd19", "cd20", "plasma cell"]),
    ("myasthenicCrisis", ["myasthenic crisis", "crisis", "危象"]),
    ("refractoryMg", ["refractory", "难治"]),
    ("thymomaAssociatedMg", ["thymoma", "thymic", "tamg", "胸腺"]),
    ("juvenileMg", ["juvenile", "pediatric", "paediatric", "青少年", "儿童"]),
    ("metaEvidence", ["meta-analysis", "systematic review", "nma", "itc", "间接比较", "meta"]),
    ("guidelineEvidence", ["guideline", "consensus", "recommendation", "指南", "共识"]),
]

MSL_USE_RULES = [
    ("拜访前准备", ["evidence", "summary", "landscape", "guideline", "consensus", "证据", "指南", "共识", "全景"]),
    ("机制沟通", ["mechanism", "fcrn", "igg", "pathogenesis", "机制"]),
    ("竞品比较", ["vs", "comparison", "competitive", "complement", "rozanolixizumab", "ravulizumab", "eculizumab", "对比", "竞争"]),
    ("安全性沟通", ["safety", "adverse", "infection", "pregnancy", "lactation", "安全", "妊娠", "感染"]),
    ("真实世界证据", ["real-world", "rwe", "china", "中国", "真实世界"]),
    ("内容工坊素材", ["positioning", "market", "access", "steroid", "endpoint", "定位", "准入", "减激素", "终点"]),
]

GENERIC_TOPIC_TERMS = {
    "efgartigimod", "evidence", "summary", "landscape", "myasthenia", "gravis",
    "fcrn", "alfa", "basic", "information", "effect", "drug", "profile",
    "profiles", "clinical", "trial", "trials", "registry", "mg", "gmg",
}

FOCUS_TERM_ALIASES = {
    "safety": ["safety", "adverse", "infection", "tolerability", "安全", "不良", "感染"],
    "pregnancy": ["pregnancy", "lactation", "妊娠", "哺乳"],
    "steroid": ["steroid", "glucocorticoid", "prednisone", "sparing", "激素", "减量"],
    "china": ["china", "chinese", "cmgcg", "中国", "中文"],
    "rwe": ["real-world", "real world", "rwe", "registry", "cohort", "真实世界"],
    "mse": ["mse", "minimal symptom", "minimal manifestation"],
    "endpoint": ["endpoint", "mg-adl", "qmg", "qol", "outcome", "终点"],
    "complement": ["complement", "eculizumab", "ravulizumab", "zilucoplan", "c5", "补体"],
    "competitive": ["competitive", "comparison", "versus", " vs ", "对比", "竞争"],
    "cidp": ["cidp", "chronic inflammatory demyelinating"],
    "gbs": ["gbs", "guillain"],
    "market": ["market", "access", "pricing", "nrdl", "准入"],
    "subtype": ["subtype", "achr", "musk", "lrp4", "seronegative", "亚型"],
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析轻量 YAML frontmatter。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 4:].lstrip("\n")
    return parse_yaml_lite(fm_text), body


def parse_yaml_lite(text: str) -> dict:
    """解析 wiki 当前使用的 YAML 子集：标量、列表、行内数组。"""
    result: dict = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            result.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if line.startswith("- ") and current_key:
            result.setdefault(current_key, []).append(strip_quotes(line[2:].strip()))
            continue
        match = re.match(r"^([\w-]+)\s*:\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        current_key = key
        if not value:
            result[key] = []
        else:
            result[key] = parse_scalar(value)
    return result


def parse_scalar(value: str):
    """解析标量或行内数组。"""
    if value.startswith("[") and value.endswith("]"):
        return [strip_quotes(item.strip()) for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return strip_quotes(value)


def strip_quotes(value: str) -> str:
    """去掉包裹引号。"""
    value = value.strip()
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        return value[1:-1]
    return value


def clean_markdown(text: str) -> str:
    """把 wiki Markdown 清理成前端可读摘要。"""
    text = strip_inline_footnotes(text)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s{0,3}[-*]\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_inline_footnotes(text: str) -> str:
    """剥离 Obsidian 行内脚注。"""
    output = []
    index = 0
    while index < len(text):
        if text[index:index + 2] == "^[":
            depth = 1
            index += 2
            while index < len(text) and depth:
                if text[index] == "[":
                    depth += 1
                elif text[index] == "]":
                    depth -= 1
                index += 1
        else:
            output.append(text[index])
            index += 1
    return "".join(output)


def extract_summary(body: str, limit: int = 220) -> str:
    """提取第一段有意义的专题摘要。"""
    chunks = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("# "):
            continue
        if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue
        if line.startswith("|") and "|" in line[1:]:
            continue
        chunks.append(line.lstrip("> ").strip())
        if len(" ".join(chunks)) > limit * 2:
            break
    summary = clean_markdown(" ".join(chunks))
    if len(summary) > limit:
        summary = summary[:limit].rstrip() + "..."
    return summary or "本专题来自本地 wiki，等待补充结构化摘要。"


def extract_claims(body: str, title: str) -> list[dict]:
    """从正文中抽取轻量 claim，用于前端专题卡片。"""
    claims: list[dict] = []
    current_heading = ""
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_heading = clean_markdown(line.lstrip("# "))
            continue
        if not line:
            continue
        is_claim_line = (
            line.startswith(">") or
            line.startswith("**核心") or
            line.startswith("**Bottom") or
            "核心结论" in line or
            "核心命题" in line or
            "⚠" in line
        )
        if not is_claim_line:
            continue
        text = clean_markdown(line.lstrip("> ").strip())
        if len(text) < 18:
            continue
        claims.append({
            "text": text[:260] + ("..." if len(text) > 260 else ""),
            "claim_type": infer_claim_type(text + " " + current_heading + " " + title),
            "section": current_heading,
        })
        if len(claims) >= 5:
            break
    if claims:
        return claims
    summary = extract_summary(body)
    return [{
        "text": summary,
        "claim_type": infer_claim_type(title + " " + summary),
        "section": "专题摘要",
    }]


def infer_claim_type(text: str) -> str:
    """根据内容推断 claim 类型。"""
    lower = text.lower()
    if any(term in lower for term in ["safety", "adverse", "infection", "安全", "不良"]):
        return "safety"
    if any(term in lower for term in ["vs", "comparison", "competitive", "对比", "竞争"]):
        return "comparison"
    if any(term in lower for term in ["mechanism", "fcrn", "igg", "机制"]):
        return "mechanism"
    if any(term in lower for term in ["mse", "mg-adl", "qmg", "efficacy", "疗效", "应答"]):
        return "efficacy"
    if any(term in lower for term in ["market", "access", "nrdl", "准入"]):
        return "access"
    return "positioning"


def extract_pmids(text: str, fm: dict) -> list[str]:
    """从 frontmatter 和正文中提取 PMID。"""
    values = []
    for key in ("pmid", "pmids", "evidence_pmids", "evidencePmids"):
        value = fm.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    values.extend(re.findall(r"\bPMID[:\s_]*(\d{6,9})\b", text, re.I))
    values.extend(re.findall(r"\bpmid[-_ ](\d{6,9})\b", text, re.I))
    values.extend(re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{6,9})", text, re.I))
    return unique([pmid for value in values for pmid in re.findall(r"\d{6,9}", value)])


def extract_wikilinks(body: str) -> list[str]:
    """提取 wiki 内链。"""
    links = []
    for match in re.finditer(r"\[\[([^\]|\n]+)(?:\|[^\]]+)?\]\]", strip_inline_footnotes(body)):
        target = match.group(1).split("#")[0].strip()
        if target:
            links.append(target)
    return unique(links)


def unique(items: list[str]) -> list[str]:
    """保序去重。"""
    seen = set()
    output = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def slug_to_title(slug: str) -> str:
    """从文件名生成兜底标题。"""
    return slug.replace("-", " ").replace("_", " ").strip().title()


def load_json(path: Path):
    """读取 JSON。"""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("articles") or data.get("items") or []


def load_knowledge_graph() -> dict:
    """读取 full abstract 知识图谱，用于校验 anchor_nodes。"""
    if not KNOWLEDGE_PATH.exists():
        return {"nodes": [], "stats": {}}
    text = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_KNOWLEDGE_GRAPH\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        return {"nodes": [], "stats": {}}
    return json.loads(match.group(1))


def compact_article(article: dict) -> dict:
    """压缩 PMID 引用字段。"""
    return {
        "pmid": article.get("pmid") or "",
        "title": article.get("title") or "",
        "journal": article.get("journal") or "",
        "pub_date": article.get("pub_date") or "",
        "entry_date": article.get("entry_date") or "",
        "url": article.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}/" if article.get("pmid") else ""),
        "evidence_level": article.get("evidence_level"),
        "study_types": article.get("study_types") or [],
        "china_related": bool(article.get("china_related")),
    }


def parse_date(value: str | None) -> datetime | None:
    """解析 entry_date/pub_date。"""
    if not value:
        return None
    value = value.strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    match = re.match(r"((?:19|20)\d{2})", value)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None


def article_text(article: dict) -> str:
    """拼接文献检索文本。"""
    return " ".join([
        article.get("title") or "",
        article.get("abstract") or "",
        " ".join(article.get("study_types") or []),
        " ".join(article.get("pub_types") or []),
    ]).lower()


def infer_anchor_nodes(text: str, valid_nodes: set[str], explicit: list[str] | None = None) -> list[str]:
    """从专题文本中推断 full graph 锚点。"""
    anchors = []
    for node_id in explicit or []:
        if node_id in valid_nodes:
            anchors.append(node_id)
    lower = text.lower()
    for node_id, terms in ANCHOR_RULES:
        if node_id in valid_nodes and any(term.lower() in lower for term in terms):
            anchors.append(node_id)
    return unique(anchors)[:8]


def infer_msl_use(text: str, fm: dict) -> list[str]:
    """推断 MSL 使用场景。"""
    explicit = fm.get("msl_use") or fm.get("mslUse") or []
    if isinstance(explicit, str):
        explicit = [explicit]
    lower = text.lower()
    uses = list(explicit)
    for label, terms in MSL_USE_RULES:
        if any(term.lower() in lower for term in terms):
            uses.append(label)
    return unique(uses)[:5] or ["拜访前准备", "内容工坊素材"]


def find_impact_articles(topic: dict, articles: list[dict], recent_cutoff: datetime | None) -> list[dict]:
    """找出每周新增且可能影响专题的文献。"""
    if not recent_cutoff:
        return []
    anchors = topic.get("anchor_nodes") or []
    anchor_terms = []
    for node_id, terms in ANCHOR_RULES:
        if node_id in anchors:
            anchor_terms.extend(terms)
    focus_terms = infer_focus_terms(topic)
    primary_terms = infer_primary_terms(topic)
    anchor_terms = unique([term.lower() for term in anchor_terms])
    known_pmids = set(topic.get("evidence_pmids") or [])
    hits = []
    for article in articles:
        pmid = str(article.get("pmid") or "")
        if not pmid or pmid in known_pmids:
            continue
        entry_date = parse_date(article.get("entry_date"))
        if not entry_date or entry_date < recent_cutoff:
            continue
        text = article_text(article)
        primary_match = sum(1 for term in primary_terms if term and term in text)
        anchor_match = sum(1 for term in anchor_terms if term and term in text)
        focus_match = sum(1 for term in focus_terms if term and term in text)
        if primary_terms and primary_match < 1:
            continue
        if anchor_match < 1:
            continue
        if focus_terms and focus_match < 1:
            continue
        if not focus_terms and anchor_match < 4:
            continue
        item = compact_article(article)
        item["match_count"] = anchor_match + focus_match * 2
        hits.append(item)
    hits.sort(key=lambda item: (item.get("evidence_level") not in {"I", "II"}, -item.get("match_count", 0), item.get("entry_date", "")))
    return hits[:6]


def infer_primary_terms(topic: dict) -> list[str]:
    """推断专题影响检测的必要主语，避免泛安全/RWE 误命中。"""
    seed = " ".join([topic.get("title", ""), topic.get("slug", "")]).lower()
    terms = []
    if any(term in seed for term in ["efgartigimod", "艾加莫德", "vyvgart"]):
        terms.extend(["efgartigimod", "vyvgart", "argx-113"])
    if "gbs" in seed or "guillain" in seed:
        terms.extend(["gbs", "guillain"])
    if "cidp" in seed:
        terms.extend(["cidp", "chronic inflammatory demyelinating"])
    if any(term in seed for term in ["eculizumab", "ravulizumab", "zilucoplan", "complement"]):
        terms.extend(["eculizumab", "ravulizumab", "zilucoplan", "complement", "c5"])
    if "rozanolixizumab" in seed:
        terms.extend(["rozanolixizumab", "rystiggo"])
    if "nipocalimab" in seed:
        terms.extend(["nipocalimab"])
    if "batoclimab" in seed:
        terms.extend(["batoclimab"])
    if not terms and "fcrn" in seed:
        terms.extend(["fcrn", "neonatal fc receptor", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"])
    return unique([term.lower() for term in terms])


def infer_focus_terms(topic: dict) -> list[str]:
    """从专题标题、slug、用途和 claim 中提取高精度影响检测词。"""
    seed = " ".join([
        topic.get("title", ""),
        topic.get("slug", ""),
    ]).lower()
    terms = []
    priority_keys = [
        "pregnancy", "steroid", "gbs", "cidp", "endpoint", "mse",
        "market", "subtype", "complement", "competitive", "china", "rwe",
    ]
    matched_priority = [
        key for key in priority_keys
        if key in seed or any(alias.lower() in seed for alias in FOCUS_TERM_ALIASES[key])
    ]
    keys = matched_priority or [
        key for key in FOCUS_TERM_ALIASES
        if key in seed or any(alias.lower() in seed for alias in FOCUS_TERM_ALIASES[key])
    ]
    for key in keys:
        aliases = FOCUS_TERM_ALIASES[key]
        if key in seed or any(alias.lower() in seed for alias in aliases):
            terms.extend(aliases)
    return unique([term.lower() for term in terms])[:18]


def scan_topics(vault: Path, valid_nodes: set[str], articles_by_pmid: dict[str, dict], articles: list[dict]) -> tuple[list[dict], list[str]]:
    """扫描 wiki 专题文件并生成结构化 topics。"""
    topics = []
    warnings = []
    latest_entry = max((parse_date(article.get("entry_date")) for article in articles if parse_date(article.get("entry_date"))), default=None)
    recent_cutoff = latest_entry - timedelta(days=14) if latest_entry else None

    for dir_name, source_type in CURATED_DIRS.items():
        dir_path = vault / dir_name
        if not dir_path.exists():
            warnings.append(f"missing_dir:{dir_name}")
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(text)
            status = str(fm.get("status") or "active")
            if status == "archived":
                continue
            slug = md_file.stem
            rel_path = f"{dir_name}/{md_file.name}"
            title = str(fm.get("title") or slug_to_title(slug))
            combined_text = f"{title}\n{body}\n{' '.join(str(item) for item in fm.values())}"
            pmids = extract_pmids(text, fm)
            anchor_nodes = infer_anchor_nodes(combined_text, valid_nodes, as_list(fm.get("anchor_nodes") or fm.get("anchorNodes")))
            evidence_refs = [compact_article(articles_by_pmid[pmid]) for pmid in pmids if pmid in articles_by_pmid]
            missing_pmids = [pmid for pmid in pmids if pmid not in articles_by_pmid]
            claims = extract_claims(body, title)
            for claim in claims:
                claim["evidence_pmids"] = pmids[:8]
            topic = {
                "id": camel_id(slug),
                "slug": slug,
                "title": title,
                "source_type": source_type,
                "status": status,
                "confidence": str(fm.get("confidence") or "unknown"),
                "updated": str(fm.get("updated") or fm.get("created") or ""),
                "summary": extract_summary(body),
                "anchor_nodes": anchor_nodes,
                "evidence_pmids": pmids,
                "evidence_refs": evidence_refs[:10],
                "missing_pmids": missing_pmids[:20],
                "claims": claims,
                "wikilinks": extract_wikilinks(body)[:20],
                "msl_use": infer_msl_use(combined_text, fm),
                "rel_path": rel_path,
                "obsidian_url": f"obsidian://open?vault=efgartigimod-wiki&file={rel_path}",
            }
            topic["impact"] = {
                "status": "updatedEvidence" if find_impact_articles(topic, articles, recent_cutoff) else "quiet",
                "recent_articles": find_impact_articles(topic, articles, recent_cutoff),
            }
            topics.append(topic)

    topics.sort(key=topic_sort_key)
    return topics, warnings


def as_list(value) -> list[str]:
    """统一转成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def camel_id(slug: str) -> str:
    """把 slug 转为前端 id。"""
    parts = re.split(r"[-_\s]+", slug)
    if not parts:
        return slug
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def topic_sort_key(topic: dict):
    """专题排序：证据多、锚点多、近期更新优先。"""
    confidence_score = {"high": 0, "medium": 1, "low": 2, "unknown": 3}.get(topic.get("confidence"), 3)
    return (
        confidence_score,
        -len(topic.get("evidence_refs") or []),
        -len(topic.get("anchor_nodes") or []),
        topic.get("source_type") != "comparison",
        topic.get("title", ""),
    )


def build_bridge(topics: list[dict]) -> dict[str, list[str]]:
    """建立 full graph 节点到专题的桥接索引。"""
    bridge = defaultdict(list)
    for topic in topics:
        for node_id in topic.get("anchor_nodes") or []:
            bridge[node_id].append(topic["id"])
    return dict(bridge)


def build_output(vault: Path) -> dict:
    """生成 curated topics 数据。"""
    articles = load_json(FULL_PATH)
    articles_by_pmid = {str(article.get("pmid")): article for article in articles if article.get("pmid")}
    knowledge_graph = load_knowledge_graph()
    valid_nodes = {node["id"] for node in knowledge_graph.get("nodes", [])}
    topics, warnings = scan_topics(vault, valid_nodes, articles_by_pmid, articles)
    bridge = build_bridge(topics)
    impact_count = sum(1 for topic in topics if topic.get("impact", {}).get("status") == "updatedEvidence")
    anchor_counter = Counter(node_id for topic in topics for node_id in topic.get("anchor_nodes") or [])

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "efgartigimod-wiki curated layer",
        "vault_label": "efgartigimod-wiki",
        "stats": {
            "topics": len(topics),
            "active_topics": sum(1 for topic in topics if topic.get("status") == "active"),
            "with_anchor_nodes": sum(1 for topic in topics if topic.get("anchor_nodes")),
            "with_evidence_refs": sum(1 for topic in topics if topic.get("evidence_refs")),
            "impact_topics": impact_count,
            "top_anchor_nodes": anchor_counter.most_common(8),
        },
        "topics": topics,
        "bridge_by_node": bridge,
        "warnings": warnings,
    }


def write_js(payload: dict, out_path: Path) -> None:
    """写出前端 JS 数据。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* AUTO-GENERATED by scripts/build-curated-topic-data.py\n"
        " * 来源: efgartigimod-wiki 本地专题策展层\n"
        f" * 生成时间: {payload['generated_at']}\n"
        " * 请勿手动编辑；运行每周管线重新生成。\n"
        " */\n"
    )
    out_path.write_text(header + f"window.MG_CURATED_TOPICS = {text};\n", encoding="utf-8")
    print(f"✅ 已生成 {out_path.relative_to(PROJECT)} ({out_path.stat().st_size // 1024} KB)")


def resolve_vault(arg_vault: str | None) -> Path:
    """解析 vault 路径。"""
    if arg_vault:
        return Path(arg_vault).expanduser()
    env = os.environ.get("MG_WIKI_VAULT")
    if env:
        return Path(env).expanduser()
    return DEFAULT_VAULT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", help="efgartigimod-wiki 本地路径")
    parser.add_argument("--out", default=str(OUT_PATH), help="输出 .js 路径")
    args = parser.parse_args()

    vault = resolve_vault(args.vault)
    out_path = Path(args.out)
    if not vault.exists():
        print(f"⚠️  wiki vault 不存在: {vault}", file=sys.stderr)
        if out_path.exists():
            print(f"   保留现有专题层产物，不覆盖: {out_path}", file=sys.stderr)
            return 0
        payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "efgartigimod-wiki curated layer",
            "vault_label": "efgartigimod-wiki",
            "stats": {"topics": 0, "active_topics": 0, "with_anchor_nodes": 0, "with_evidence_refs": 0, "impact_topics": 0, "top_anchor_nodes": []},
            "topics": [],
            "bridge_by_node": {},
            "warnings": ["vault_missing"],
        }
        write_js(payload, out_path)
        return 0

    payload = build_output(vault)
    write_js(payload, out_path)
    stats = payload["stats"]
    print(
        "   专题: {topics} · 锚点覆盖: {anchors} · 有 PMID 证据: {refs} · 本周影响: {impact}".format(
            topics=stats["topics"],
            anchors=stats["with_anchor_nodes"],
            refs=stats["with_evidence_refs"],
            impact=stats["impact_topics"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
