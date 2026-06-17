#!/usr/bin/env python3
"""
build-frontend-data.py — 生成 MA-MG-HUB 前端数据产物。

本脚本只读取公开 PubMed 文献数据，输出 GitHub Pages 可加载的 .js 文件。
敏感的专家内部标签、拜访记录不在这里生成，也不进入公开仓库。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
FULL_PATH = DATA_DIR / "literature-full.json"
RECENT_PATH = DATA_DIR / "literature-recent.json"
RECENT_JS_PATH = DATA_DIR / "literature-recent.js"

STOPWORDS = {
    "with", "from", "into", "using", "study", "case", "report", "review",
    "myasthenia", "gravis", "patients", "patient", "clinical", "disease",
    "treatment", "therapy", "analysis", "associated", "among", "after",
    "before", "during", "based", "results", "outcome", "outcomes",
    "china", "chinese", "generalized", "generalised", "mg",
}

TOPIC_DEFS = [
    ("FcRn", ["fcrn", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"]),
    ("补体", ["complement", "zilucoplan", "ravulizumab", "eculizumab", "c5 inhibitor"]),
    ("B细胞", ["b cell", "b-cell", "rituximab", "inebilizumab", "cd20", "cd19"]),
    ("抗体分型", ["seronegative", "musk", "achr", "lrp4", "autoantibody"]),
    ("真实世界", ["real-world", "registry", "observational", "retrospective"]),
    ("安全性", ["safety", "adverse", "infection", "tolerability"]),
    ("疗效", ["efficacy", "outcome", "improvement", "response"]),
    ("机制", ["pathogenesis", "mechanism", "biomarker", "cytokine", "receptor"]),
    ("诊疗策略", ["guideline", "consensus", "recommendation", "treatment strategy"]),
]

DRUG_KEYWORDS = {
    "Efgartigimod": ["efgartigimod", "vyvgart"],
    "Rozanolixizumab": ["rozanolixizumab"],
    "Ravulizumab": ["ravulizumab"],
    "Eculizumab": ["eculizumab"],
    "Zilucoplan": ["zilucoplan"],
    "Nipocalimab": ["nipocalimab"],
    "Batoclimab": ["batoclimab"],
    "Rituximab": ["rituximab"],
}

PIPELINE = [
    {"name": "Efgartigimod", "target": "FcRn", "route": "IV/SC", "status": "已上市", "owner": "argenx"},
    {"name": "Rozanolixizumab", "target": "FcRn", "route": "SC", "status": "已上市", "owner": "UCB"},
    {"name": "Nipocalimab", "target": "FcRn", "route": "IV", "status": "临床后期", "owner": "Johnson & Johnson"},
    {"name": "Batoclimab", "target": "FcRn", "route": "SC", "status": "临床开发", "owner": "Immunovant / Harbour"},
    {"name": "Zilucoplan", "target": "C5", "route": "SC", "status": "已上市", "owner": "UCB"},
    {"name": "Ravulizumab", "target": "C5", "route": "IV", "status": "已上市", "owner": "Alexion"},
    {"name": "Eculizumab", "target": "C5", "route": "IV", "status": "已上市", "owner": "Alexion"},
    {"name": "Rituximab", "target": "CD20", "route": "IV", "status": "超说明书/研究", "owner": "Multiple"},
    {"name": "Inebilizumab", "target": "CD19", "route": "IV", "status": "研究线索", "owner": "Amgen"},
]


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_public_js(path: Path, global_name: str):
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(global_name)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def load_articles_for_frontend():
    if RECENT_PATH.exists():
        recent = load_json(RECENT_PATH)
    elif RECENT_JS_PATH.exists():
        recent = load_public_js(RECENT_JS_PATH, "MG_LITERATURE_DATA")
    else:
        raise FileNotFoundError("需要 data/literature-recent.json 或 data/literature-recent.js")

    if FULL_PATH.exists():
        full = load_json(FULL_PATH)
    else:
        print("⚠️  literature-full.json 不存在，专家画像将使用近一年公开数据降级生成。")
        full = recent
    return recent, full


def parse_date(value: str | None):
    if not value:
        return None
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value[: len(pattern)], pattern)
        except ValueError:
            pass
    match = re.match(r"(\d{4})", value)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None


def text_of(article):
    parts = [
        article.get("title", ""),
        article.get("abstract", ""),
        " ".join(article.get("pub_types") or []),
        " ".join(article.get("study_types") or []),
    ]
    return " ".join(parts).lower()


def has_any(text, words):
    return any(word in text for word in words)


def infer_topics(article):
    text = text_of(article)
    topics = [label for label, words in TOPIC_DEFS if has_any(text, words)]
    if not topics and article.get("study_types"):
        topics.append(article["study_types"][0])
    return topics[:5]


def evidence_score(level):
    return {"I": 7, "II": 5, "III": 4, "IV": 3, "V": 2, "VI": 1}.get(level or "", 0)


def compact_article(article):
    return {
        "pmid": article.get("pmid", ""),
        "title": article.get("title", ""),
        "journal": article.get("journal", ""),
        "entry_date": article.get("entry_date", ""),
        "pub_date": article.get("pub_date", ""),
        "url": article.get("url", ""),
        "evidence_level": article.get("evidence_level"),
        "journal_if": article.get("journal_if"),
        "journal_quartile": article.get("journal_quartile"),
        "china_related": bool(article.get("china_related")),
        "study_types": article.get("study_types") or [],
    }


def write_js(name, global_name, payload):
    path = DATA_DIR / name
    text = "window.%s = %s;\n" % (
        global_name,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    path.write_text(text, encoding="utf-8")
    print(f"✅ {path.relative_to(PROJECT)}")


def build_signals(recent):
    latest = max((parse_date(a.get("entry_date")) for a in recent if parse_date(a.get("entry_date"))), default=datetime.now())
    cutoff = latest - timedelta(days=14)
    signals = []
    topic_counter = Counter()
    for article in recent:
        dt = parse_date(article.get("entry_date"))
        if not dt or dt < cutoff:
            continue
        text = text_of(article)
        topics = infer_topics(article)
        for topic in topics:
            topic_counter[topic] += 1
        level = article.get("evidence_level")
        if_val = float(article.get("journal_if") or 0)
        signal_type = "新证据"
        if has_any(text, ["guideline", "consensus", "recommendation", "review", "meta-analysis"]):
            signal_type = "新观点"
        if has_any(text, ["pathogenesis", "mechanism", "biomarker", "cytokine", "receptor", "autoantibody"]):
            signal_type = "新机制"
        subtype = "其他"
        if has_any(text, ["efgartigimod", "vyvgart"]):
            subtype = "本品"
        elif any(has_any(text, words) for drug, words in DRUG_KEYWORDS.items() if drug != "Efgartigimod"):
            subtype = "竞品"
        reasons = []
        if level in {"I", "II"}:
            reasons.append("高等级证据")
        if if_val >= 10:
            reasons.append("高影响期刊")
        elif if_val >= 5:
            reasons.append("中高影响期刊")
        if article.get("china_related"):
            reasons.append("中国相关")
        if (latest - dt).days <= 7:
            reasons.append("最新入库")
        if not reasons and not topics:
            continue
        strength = "弱"
        if if_val >= 10 or (level in {"I", "II"} and if_val >= 5):
            strength = "强"
        elif if_val >= 4 or level in {"I", "II"} or article.get("china_related"):
            strength = "中"
        score = if_val + evidence_score(level) + (14 - (latest - dt).days) / 3
        if article.get("china_related"):
            score += 1.5
        if strength == "强":
            score += 10
        elif strength == "中":
            score += 4
        signals.append({
            "date": dt.strftime("%Y-%m-%d"),
            "type": signal_type,
            "subtype": subtype,
            "strength": strength,
            "summary": article.get("title", ""),
            "reason": " · ".join(reasons) or "基于近期入库与主题关键词",
            "related_pmids": [article.get("pmid", "")],
            "keywords": topics,
            "score": round(score, 2),
            "article": compact_article(article),
        })
    signals.sort(key=lambda item: (-item["score"], item["date"]))
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": 14,
        "topic_hotspots": [{"topic": k, "count": v} for k, v in topic_counter.most_common(12)],
        "signals": signals[:80],
    }


def normalize_institution(affiliation):
    if not affiliation:
        return ""
    parts = [p.strip() for p in affiliation.split(",") if p.strip()]
    for part in parts:
        low = part.lower()
        if "@" in part or "road" in low or "street" in low or "china" == low:
            continue
        if any(key in low for key in ["hospital", "university", "institute", "college", "center", "centre"]):
            return re.sub(r"^the\s+", "", part, flags=re.I)[:90]
    return re.sub(r"^the\s+", "", parts[0], flags=re.I)[:90] if parts else ""


def build_china(recent):
    articles = [a for a in recent if a.get("china_related")]
    monthly = Counter()
    evidence = Counter()
    journals = Counter()
    institutions = Counter()
    for article in articles:
        dt = parse_date(article.get("entry_date"))
        if dt:
            monthly[dt.strftime("%Y-%m")] += 1
        evidence[article.get("evidence_level") or "未分类"] += 1
        journals[article.get("journal") or "Unknown"] += 1
        for affiliation in article.get("affiliations") or []:
            inst = normalize_institution(affiliation)
            if inst:
                institutions[inst] += 1
    articles.sort(key=lambda a: parse_date(a.get("entry_date")) or datetime.min, reverse=True)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "recent_year_articles": len(articles),
            "high_evidence": sum(1 for a in articles if a.get("evidence_level") in {"I", "II"}),
            "top_journal": journals.most_common(1)[0][0] if journals else "",
        },
        "monthly": [{"month": k, "count": monthly[k]} for k in sorted(monthly)],
        "evidence": [{"level": k, "count": evidence[k]} for k in ["I", "II", "III", "IV", "V", "VI", "未分类"] if evidence[k]],
        "top_journals": [{"name": k, "count": v} for k, v in journals.most_common(12)],
        "top_institutions": [{"name": k, "count": v} for k, v in institutions.most_common(12)],
        "pubmed_articles": [compact_article(a) for a in articles[:120]],
        "manual_updates": load_manual_china_updates(),
    }


def load_manual_china_updates():
    path = DATA_DIR / "china-manual.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("manual_updates", [])
    except Exception:
        return []


def tokenize(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
    return [w for w in words if w not in STOPWORDS and not w.isdigit()]


def build_experts(full):
    author_articles = defaultdict(list)
    for article in full:
        for author in article.get("authors") or []:
            if author:
                author_articles[author].append(article)
    candidates = sorted(author_articles.items(), key=lambda item: len(item[1]), reverse=True)[:160]
    profiles = []
    for idx, (author, articles) in enumerate(candidates, 1):
        articles_sorted = sorted(articles, key=lambda a: parse_date(a.get("entry_date")) or datetime.min, reverse=True)
        now = datetime.now()
        recent_3y = [a for a in articles if (parse_date(a.get("entry_date")) or datetime.min) >= now - timedelta(days=365 * 3)]
        journals = Counter(a.get("journal") or "Unknown" for a in articles)
        highest_if = max(float(a.get("journal_if") or 0) for a in articles)
        coauthors = Counter()
        words = Counter()
        for article in articles:
            for co in article.get("authors") or []:
                if co and co != author:
                    coauthors[co] += 1
            words.update(tokenize((article.get("title") or "") + " " + (article.get("abstract") or "")))
        topic_hits = Counter()
        for article in articles:
            for topic in infer_topics(article):
                topic_hits[topic] += 1
        interests = [{"term": k, "count": v} for k, v in (topic_hits or words).most_common(10)]
        affiliations = Counter()
        for article in articles_sorted[:20]:
            for aff in article.get("affiliations") or []:
                inst = normalize_institution(aff)
                if inst:
                    affiliations[inst] += 1
        profiles.append({
            "id": f"expert_{idx:03d}",
            "name_en": author,
            "name_zh": "",
            "affiliation": affiliations.most_common(1)[0][0] if affiliations else "",
            "metrics": {
                "total_publications": len(articles),
                "recent_3y_publications": len(recent_3y),
                "highest_if": round(highest_if, 1),
                "journal_count": len(journals),
                "china_related": sum(1 for a in articles if a.get("china_related")),
            },
            "interests": interests,
            "top_journals": [{"name": k, "count": v} for k, v in journals.most_common(6)],
            "collaborators": [{"name": k, "count": v} for k, v in coauthors.most_common(8)],
            "timeline": [compact_article(a) for a in articles_sorted[:8]],
            "public_tags": [item["term"] for item in interests[:4]],
        })
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_authors": len(author_articles),
            "profiled_authors": len(profiles),
            "authors_ge_10": sum(1 for v in author_articles.values() if len(v) >= 10),
            "authors_ge_20": sum(1 for v in author_articles.values() if len(v) >= 20),
        },
        "experts": profiles,
    }


def match_articles(articles, keywords, limit=12):
    scored = []
    for article in articles:
        text = text_of(article)
        hits = sum(1 for word in keywords if word in text)
        if not hits:
            continue
        if_val = float(article.get("journal_if") or 0)
        score = hits * 5 + evidence_score(article.get("evidence_level")) + if_val / 2
        scored.append((score, parse_date(article.get("entry_date")) or datetime.min, article))
    scored.sort(key=lambda item: (-item[0], item[1]), reverse=False)
    scored = sorted(scored, key=lambda item: (-item[0], -item[1].timestamp()))
    return [compact_article(item[2]) for item in scored[:limit]]


def build_landscape(recent):
    questions = [
        ("Efgartigimod 在 gMG 的长期疗效", ["efgartigimod", "long-term", "efficacy", "adapt"]),
        ("FcRn 拮抗剂安全性谱", ["fcrn", "safety", "infection", "adverse"]),
        ("Rozanolixizumab 疗效与患者报告结局", ["rozanolixizumab", "efficacy", "patient-reported", "mycaring"]),
        ("补体抑制剂在 MG 的定位", ["complement", "zilucoplan", "ravulizumab", "eculizumab", "efficacy"]),
        ("血清阴性 MG 的诊断与疾病特征", ["seronegative", "diagnosis", "characteristics"]),
        ("真实世界治疗策略", ["real-world", "registry", "retrospective", "treatment"]),
    ]
    matrices = []
    for question, keywords in questions:
        refs = match_articles(recent, keywords, limit=8)
        matrices.append({
            "question": question,
            "verified": False,
            "summary": "基于近一年 PubMed 文献的自动证据聚合，需医学复核。",
            "evidence_matrix": [
                {
                    "type": "支持",
                    "level": ref.get("evidence_level") or "未分类",
                    "source": ref.get("journal", ""),
                    "pmid": ref.get("pmid", ""),
                    "key_finding": ref.get("title", ""),
                    "limitations": "自动提取，未完成人工核验",
                }
                for ref in refs[:5]
            ],
            "references": refs,
        })
    tracks = []
    for name, keywords in {
        "FcRn 通路": ["fcrn", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"],
        "补体通路": ["complement", "zilucoplan", "ravulizumab", "eculizumab"],
        "B细胞通路": ["b cell", "rituximab", "inebilizumab", "cd20", "cd19"],
        "传统免疫": ["azathioprine", "mycophenolate", "steroid", "prednisone", "tacrolimus"],
    }.items():
        refs = match_articles(recent, keywords, limit=10)
        tracks.append({"name": name, "article_count": len(refs), "references": refs})
    for item in PIPELINE:
        refs = match_articles(recent, DRUG_KEYWORDS.get(item["name"], [item["name"].lower()]), limit=5)
        item["references"] = refs
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "evidence_questions": matrices,
        "treatment_tracks": tracks,
        "china_difference": [
            {"dimension": "获批状态", "china": "手动维护为主", "global": "多产品已上市/后期开发", "gap": "时间差与适应症范围差"},
            {"dimension": "指南推荐", "china": "需结合中国指南与共识更新", "global": "指南/共识持续纳入新机制治疗", "gap": "证据积累与支付环境不同"},
            {"dimension": "医保覆盖", "china": "需手动维护医保与准入状态", "global": "按市场差异显著", "gap": "支付路径差异"},
        ],
        "competitive_pipeline": PIPELINE,
    }


def build_modules(recent, landscape):
    modules = []
    specs = [
        ("module_pharmacology_fcrn", "药理机制", "FcRn 通路机制", ["fcrn", "efgartigimod", "rozanolixizumab", "mechanism"]),
        ("module_clinical_efgartigimod", "临床数据", "Efgartigimod 临床证据", ["efgartigimod", "efficacy", "adapt"]),
        ("module_safety_fcrn", "安全性", "FcRn 拮抗剂安全性", ["fcrn", "safety", "infection", "adverse"]),
        ("module_competitive_fcrn", "竞品对比", "FcRn 产品对比", ["efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"]),
        ("module_real_world", "真实世界", "MG 真实世界证据", ["real-world", "registry", "observational", "retrospective"]),
        ("module_guideline", "指南比较", "MG 指南与共识", ["guideline", "consensus", "recommendation"]),
    ]
    for mid, mtype, title, keywords in specs:
        refs = match_articles(recent, keywords, limit=8)
        modules.append({
            "id": mid,
            "type": mtype,
            "title": title,
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "verified": False,
            "placeholder": len(refs) == 0,
            "summary": "自动从近一年文献提取的模块草稿，需医学/合规复核后使用。",
            "claims": [
                {"text": ref.get("title", ""), "pmid": ref.get("pmid", ""), "evidence_level": ref.get("evidence_level") or "未分类"}
                for ref in refs[:4]
            ],
            "references": refs,
        })
    templates = [
        {"id": "weekly_brief", "name": "文献速递简报", "modules": ["module_clinical_efgartigod", "module_safety_fcrn", "module_real_world"]},
        {"id": "visit_material", "name": "拜访材料", "modules": ["module_pharmacology_fcrn", "module_clinical_efgartigimod", "module_competitive_fcrn"]},
        {"id": "competitive_response", "name": "竞品应对", "modules": ["module_competitive_fcrn", "module_safety_fcrn"]},
        {"id": "internal_strategy", "name": "医学部内部", "modules": ["module_guideline", "module_real_world", "module_competitive_fcrn"]},
    ]
    # 修正模板中的拼写，避免前端找不到模块。
    templates[0]["modules"][0] = "module_clinical_efgartigimod"
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "modules": modules,
        "templates": templates,
        "compliance_rules": [
            {"id": "pmid_required", "label": "每条声明必须绑定 PMID", "type": "rule"},
            {"id": "verified_required", "label": "正式使用前必须医学/合规复核", "type": "workflow"},
            {"id": "placeholder_block", "label": "placeholder 模块不得进入最终材料", "type": "rule"},
            {"id": "off_label_review", "label": "超说明书暗示需人工判定", "type": "llm_assist"},
        ],
    }


def build_dashboard(recent, signals, experts, china, landscape, modules):
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "recent_articles": len(recent),
            "china_articles": china["summary"]["recent_year_articles"],
            "signals": len(signals["signals"]),
            "experts": len(experts["experts"]),
            "modules": len(modules["modules"]),
        },
        "top_signals": signals["signals"][:5],
        "work_items": [
            {"type": "文献", "label": "近 14 天候选信号", "count": len(signals["signals"]), "href": "/MA-MG-HUB/pages/literature.html"},
            {"type": "专家", "label": "已构建专家画像", "count": len(experts["experts"]), "href": "/MA-MG-HUB/pages/msl.html"},
            {"type": "模块", "label": "待核实内容模块", "count": sum(1 for m in modules["modules"] if not m["verified"]), "href": "/MA-MG-HUB/pages/materials.html"},
            {"type": "证据", "label": "待核实证据矩阵", "count": len(landscape["evidence_questions"]), "href": "/MA-MG-HUB/pages/landscape.html"},
        ],
    }


def main():
    recent, full = load_articles_for_frontend()
    signals = build_signals(recent)
    china = build_china(recent)
    experts = build_experts(full)
    landscape = build_landscape(recent)
    modules = build_modules(recent, landscape)
    dashboard = build_dashboard(recent, signals, experts, china, landscape, modules)

    write_js("signals-weekly.js", "MG_SIGNALS_DATA", signals)
    write_js("china-intelligence.js", "MG_CHINA_DATA", china)
    write_js("expert-profiles.js", "MG_EXPERT_PROFILES", experts)
    write_js("landscape-data.js", "MG_LANDSCAPE_DATA", landscape)
    write_js("content-modules.js", "MG_CONTENT_MODULES", modules)
    write_js("dashboard-data.js", "MG_DASHBOARD_DATA", dashboard)


if __name__ == "__main__":
    main()
