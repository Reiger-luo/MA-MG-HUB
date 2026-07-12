#!/usr/bin/env python3
"""Build the China hospital collaboration graph for MA-MG-HUB.

The public output is aggregate-only: hospital nodes, hospital-hospital edges,
minimal PMID metadata, heatmap counts, and audit signals. It does not include
private visit notes or internal team labels.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
import argparse
import re
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.common.io import atomic_write_js_global, load_js_global, load_json


DATA_DIR = PROJECT / "data"
FULL_PATH = DATA_DIR / "literature-full.json"
RECENT_JS_PATH = DATA_DIR / "literature-recent.js"
OUTPUT_PATH = DATA_DIR / "china-author-network.js"
OUTPUT_GLOBAL = "MG_CHINA_AUTHOR_NETWORK"

DATA_EDGE_THRESHOLD = 1
DEFAULT_DISPLAY_EDGE_WEIGHT = 5

CHINA_TERMS = (
    "china", "chinese", "hong kong", "hongkong", "macau", "macao", "taiwan",
    "beijing", "shanghai", "guangzhou", "nanjing", "tianjin", "wuhan", "changsha",
    "chengdu", "hangzhou", "xian", "xi'an", "jinan", "shenyang", "harbin", "fuzhou",
    "xiamen", "qingdao", "zhengzhou", "chongqing", "suzhou", "nanchang", "hefei",
    "kunming", "nanning", "urumqi", "lanzhou", "shijiazhuang", "taipei", "kaohsiung",
)

GEO_SCOPE_LABELS = {
    "mainland": "Mainland China",
    "hong_kong": "Hong Kong",
    "macau": "Macau",
    "taiwan": "Taiwan",
}

LOCATION_RULES = [
    ("hong_kong", "Hong Kong", "Hong Kong", ["hong kong", "hongkong"]),
    ("macau", "Macau", "Macau", ["macau", "macao"]),
    ("taiwan", "Taiwan", "Taiwan", ["taiwan", "taipei", "kaohsiung", "taichung", "tainan"]),
    ("mainland", "Beijing", "Beijing", ["beijing", "peking"]),
    ("mainland", "Shanghai", "Shanghai", ["shanghai"]),
    ("mainland", "Guangdong", "Guangzhou", ["guangzhou"]),
    ("mainland", "Guangdong", "Shenzhen", ["shenzhen"]),
    ("mainland", "Guangdong", "Shantou", ["shantou"]),
    ("mainland", "Guangdong", "Dongguan", ["dongguan"]),
    ("mainland", "Jiangsu", "Nanjing", ["nanjing"]),
    ("mainland", "Jiangsu", "Suzhou", ["suzhou"]),
    ("mainland", "Jiangsu", "Xuzhou", ["xuzhou"]),
    ("mainland", "Jiangsu", "Wuxi", ["wuxi"]),
    ("mainland", "Jiangsu", "Nantong", ["nantong"]),
    ("mainland", "Jiangsu", "Yancheng", ["yancheng"]),
    ("mainland", "Jiangsu", "Huai'an", ["huai'an", "huaian"]),
    ("mainland", "Jiangsu", "Yangzhou", ["yangzhou"]),
    ("mainland", "Tianjin", "Tianjin", ["tianjin"]),
    ("mainland", "Hubei", "Wuhan", ["wuhan"]),
    ("mainland", "Hubei", "Xiangyang", ["xiangyang"]),
    ("mainland", "Hubei", "Suizhou", ["suizhou"]),
    ("mainland", "Hunan", "Changsha", ["changsha"]),
    ("mainland", "Sichuan", "Chengdu", ["chengdu"]),
    ("mainland", "Sichuan", "Mianyang", ["mianyang"]),
    ("mainland", "Sichuan", "Dazhou", ["dazhou"]),
    ("mainland", "Zhejiang", "Hangzhou", ["hangzhou"]),
    ("mainland", "Zhejiang", "Wenzhou", ["wenzhou"]),
    ("mainland", "Zhejiang", "Shaoxing", ["shaoxing"]),
    ("mainland", "Shaanxi", "Xi'an", ["xian", "xi'an"]),
    ("mainland", "Shaanxi", "Xianyang", ["xianyang"]),
    ("mainland", "Shaanxi", "Baoji", ["baoji"]),
    ("mainland", "Shaanxi", "Shangluo", ["shangluo"]),
    ("mainland", "Shandong", "Jinan", ["jinan"]),
    ("mainland", "Shandong", "Qingdao", ["qingdao"]),
    ("mainland", "Shandong", "Tai'an", ["tai'an", "taian"]),
    ("mainland", "Shandong", "Zibo", ["zibo"]),
    ("mainland", "Henan", "Zhengzhou", ["zhengzhou"]),
    ("mainland", "Henan", "Luoyang", ["luoyang"]),
    ("mainland", "Henan", "Nanyang", ["nanyang"]),
    ("mainland", "Henan", "Kaifeng", ["kaifeng"]),
    ("mainland", "Chongqing", "Chongqing", ["chongqing"]),
    ("mainland", "Anhui", "Hefei", ["hefei"]),
    ("mainland", "Anhui", "Bengbu", ["bengbu"]),
    ("mainland", "Fujian", "Fuzhou", ["fuzhou"]),
    ("mainland", "Fujian", "Xiamen", ["xiamen"]),
    ("mainland", "Fujian", "Quanzhou", ["quanzhou"]),
    ("mainland", "Yunnan", "Kunming", ["kunming"]),
    ("mainland", "Yunnan", "Qujing", ["qujing"]),
    ("mainland", "Yunnan", "Lincang", ["lincang"]),
    ("mainland", "Guangxi", "Nanning", ["nanning"]),
    ("mainland", "Guangxi", "Guilin", ["guilin"]),
    ("mainland", "Xinjiang", "Urumqi", ["urumqi"]),
    ("mainland", "Gansu", "Lanzhou", ["lanzhou"]),
    ("mainland", "Hebei", "Shijiazhuang", ["shijiazhuang"]),
    ("mainland", "Hebei", "Cangzhou", ["cangzhou"]),
    ("mainland", "Liaoning", "Shenyang", ["shenyang"]),
    ("mainland", "Liaoning", "Dalian", ["dalian"]),
    ("mainland", "Liaoning", "Panjin", ["panjin"]),
    ("mainland", "Liaoning", "Anshan", ["anshan"]),
    ("mainland", "Heilongjiang", "Harbin", ["harbin"]),
]


GENERIC_ORG_PREFIX_RE = re.compile(
    r"^(department|dept\.?|division|unit|laboratory|lab|center|centre|institute|school|college|faculty|"
    r"clinic|program|programme|office|ward|key laboratory)\b",
    re.I,
)
HOSPITAL_RE = re.compile(r"\b(hospital|medical\s+center|medical\s+centre)\b", re.I)
ACADEMIC_RE = re.compile(r"\b(university|medical\s+university|school\s+of\s+medicine|college|academy|faculty)\b", re.I)
ADDRESS_RE = re.compile(r"\b(road|street|avenue|district|province|postal|zipcode|zip\s*code|p\.r\.\s*china|people's\s+republic)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

TOPIC_RULES = [
    ("FcRn", ["fcrn", "efgartigimod", "rozanolixizumab", "nipocalimab", "batoclimab"]),
    ("Complement", ["complement", "eculizumab", "ravulizumab", "zilucoplan"]),
    ("RWE", ["real-world", "real world", "registry", "cohort", "retrospective", "observational"]),
    ("Safety", ["safety", "adverse", "infection", "toxicity", "crisis"]),
    ("Diagnosis", ["diagnosis", "diagnostic", "antibody", "seronegative", "biomarker"]),
    ("Guideline", ["guideline", "consensus", "recommendation"]),
]


def slugify(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_") or "unknown"


def compact_space(value: str) -> str:
    value = EMAIL_RE.sub("", value or "")
    value = re.sub(r"Electronic address:.*$", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .;,\t\n")


def split_affiliation_parts(affiliation: str) -> list[str]:
    cleaned = compact_space(affiliation)
    raw_parts = re.split(r"[,;]", cleaned)
    parts: list[str] = []
    for part in raw_parts:
        item = compact_space(part)
        if not item:
            continue
        if re.fullmatch(r"\d{4,}#?", item):
            continue
        parts.append(item)
    return parts


def normalize_org_label(value: str) -> str:
    value = compact_space(value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\bCentre\b", "Center", value)
    value = re.sub(r"\bcentre\b", "center", value)
    value = re.sub(r"\s*&\s*", " and ", value)
    # Preserve official English names such as "The University of Hong Kong";
    # the module deliberately avoids manual translation/alias rewriting.
    value = re.sub(r"\s+#?\d{3,}.*$", "", value)
    value = re.sub(r"\s+\d{5,6}$", "", value)
    return compact_space(value)


def has_china_signal(text: str) -> bool:
    lower = (text or "").lower()
    return any(term in lower for term in CHINA_TERMS)


def article_is_china_related(article: dict[str, Any]) -> bool:
    if article.get("china_related"):
        return True
    texts: list[str] = []
    for key in ("title", "abstract"):
        if article.get(key):
            texts.append(str(article[key]))
    for aff in article.get("affiliations") or []:
        texts.append(str(aff))
    for detail in article.get("author_affiliations") or []:
        texts.extend(str(aff) for aff in detail.get("affiliations") or [])
    return has_china_signal(" ".join(texts))


def infer_geo_scope(text: str) -> str:
    lower = (text or "").lower()
    if "hong kong" in lower or "hongkong" in lower:
        return "hong_kong"
    if "macau" in lower or "macao" in lower:
        return "macau"
    if "taiwan" in lower or "taipei" in lower or "kaohsiung" in lower:
        return "taiwan"
    return "mainland"


def infer_location(text: str) -> dict[str, str]:
    lower = (text or "").lower()
    matches: list[tuple[int, int, int, str, str, str]] = []
    for rule_index, (scope, province, city, terms) in enumerate(LOCATION_RULES):
        for term in terms:
            position = lower.rfind(term)
            if position >= 0:
                matches.append((position, len(term), rule_index, scope, province, city))
    if matches:
        _, _, _, scope, province, city = max(matches)
        return {
            "geo_scope": scope,
            "region": GEO_SCOPE_LABELS.get(scope, scope),
            "province": province,
            "city": city,
        }
    scope = infer_geo_scope(text)
    return {
        "geo_scope": scope,
        "region": GEO_SCOPE_LABELS.get(scope, scope),
        "province": GEO_SCOPE_LABELS.get(scope, scope),
        "city": "",
    }


def looks_like_address(part: str) -> bool:
    if ADDRESS_RE.search(part):
        return True
    if re.search(r"\b\d{4,}\b", part):
        return True
    return False


def parent_org_after(parts: list[str], start_index: int) -> str:
    for part in parts[start_index + 1:start_index + 5]:
        candidate = normalize_org_label(part)
        candidate = re.sub(r"^(?:of|at|to|with)\s+", "", candidate, flags=re.I)
        if not candidate:
            continue
        if HOSPITAL_RE.search(candidate):
            continue
        if looks_like_address(candidate) and not ACADEMIC_RE.search(candidate):
            continue
        if ACADEMIC_RE.search(candidate):
            return candidate
    return ""


def non_hospital_label(parts: list[str]) -> str:
    for index, part in enumerate(parts):
        candidate = normalize_org_label(part)
        if not candidate:
            continue
        if HOSPITAL_RE.search(candidate):
            continue
        if ACADEMIC_RE.search(candidate):
            parent = parent_org_after(parts, index)
            if parent and parent.lower() not in candidate.lower():
                return f"{candidate}, {parent}"
            return candidate
    for part in parts:
        candidate = normalize_org_label(part)
        if candidate and not looks_like_address(candidate) and not GENERIC_ORG_PREFIX_RE.search(candidate):
            return candidate
    return ""


GENERIC_HOSPITAL_MARKERS = (
    "first ", "second ", "third ", "fourth ", "fifth ", "affiliated",
    "provincial", "people", "general", "central", "union", "medical center",
    "cancer", "children", "women", "maternal", "army", "military",
    "traditional chinese", "rehabilitation", "hospital of",
)


def canonical_hospital_label(candidate: str, parts: list[str], index: int) -> str:
    """Collapse department, punctuation, and academic-suffix variants."""
    value = normalize_org_label(candidate)
    match = HOSPITAL_RE.search(value)
    if not match:
        return value

    label = value[:match.end()].strip(" .;,\t\n")
    label = re.sub(
        r"^(?:department|dept\.?|division|unit|laboratory|lab)\b.*?\b(?:and|&)\s+",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(r"^the\s+", "", label, flags=re.I)
    label = normalize_org_label(label)
    if not label:
        return ""

    location = infer_location("; ".join(parts))
    if location["geo_scope"] == "mainland":
        reversed_match = re.match(r"^.+\b(?:university|college)\s+(.+\bhospital)$", label, flags=re.I)
        if reversed_match:
            reversed_label = normalize_org_label(reversed_match.group(1))
            if not any(marker in reversed_label.lower() for marker in GENERIC_HOSPITAL_MARKERS):
                label = reversed_label
    needs_parent = (
        location["geo_scope"] in {"hong_kong", "macau", "taiwan"}
        or any(marker in label.lower() for marker in GENERIC_HOSPITAL_MARKERS)
    )
    suffix = normalize_org_label(value[match.end():].strip(" .;,\t\n"))
    suffix = re.sub(r"^(?:of|at|to|with)\s+", "", suffix, flags=re.I)
    parent = ""
    if suffix and re.search(r"\b(university|college|academy|medical school|school of medicine)\b", suffix, re.I):
        parent = suffix
    if not parent:
        parent = parent_org_after(parts, index)
    if needs_parent and parent and parent.lower() not in label.lower():
        label = f"{label}, {parent}"
    return normalize_org_label(label)


def hospital_from_affiliation(affiliation: str) -> dict[str, Any] | None:
    parts = split_affiliation_parts(affiliation)
    if not parts:
        return None
    lower = " ".join(parts).lower()
    if not has_china_signal(lower):
        return None

    for index, part in enumerate(parts):
        candidate = normalize_org_label(part)
        if not HOSPITAL_RE.search(candidate):
            continue
        label = canonical_hospital_label(candidate, parts, index)
        if not label:
            continue
        location = infer_location("; ".join(parts))
        return {
            "id": slugify(label),
            "label": label,
            "geo_scope": location["geo_scope"],
            "region": location["region"],
            "province": location["province"],
            "city": location["city"],
            "source_label": compact_space(affiliation),
        }
    return None


def extract_non_hospital_institution(affiliation: str) -> dict[str, Any] | None:
    parts = split_affiliation_parts(affiliation)
    if not parts or not has_china_signal(" ".join(parts)):
        return None
    label = non_hospital_label(parts)
    if not label:
        return None
    location = infer_location("; ".join(parts))
    return {
        "id": slugify(label),
        "label": label,
        "geo_scope": location["geo_scope"],
        "province": location["province"],
        "city": location["city"],
    }


def article_topics(article: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(article.get(key) or "") for key in ("title", "abstract")
    ).lower()
    topics = [label for label, terms in TOPIC_RULES if any(term in text for term in terms)]
    for topic in article.get("topics") or article.get("keywords") or []:
        if topic and topic not in topics:
            topics.append(str(topic))
    return topics[:8]


def author_name_set(values: Any) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    return {str(v).strip().lower() for v in values if str(v).strip()}


def author_position(detail: dict[str, Any]) -> int:
    try:
        return int(detail.get("position") or 0)
    except (TypeError, ValueError):
        return 0


def author_affiliation_emails(detail: dict[str, Any]) -> list[str]:
    emails = detail.get("emails") or []
    if isinstance(emails, str):
        emails = [emails]
    found = [str(email).strip() for email in emails if str(email).strip()]
    if found:
        return sorted(set(found))
    return sorted({
        email
        for affiliation in detail.get("affiliations") or []
        for email in EMAIL_RE.findall(str(affiliation))
    })


def graph_author_details(article: dict[str, Any]) -> list[dict[str, Any]]:
    details = [d for d in article.get("author_affiliations") or [] if isinstance(d, dict)]
    if not details:
        return []

    first_names = author_name_set(article.get("first_authors"))
    corr_names = author_name_set(article.get("corresponding_authors"))
    explicit_corr = [
        d for d in details
        if (
            d.get("is_corresponding")
            or author_affiliation_emails(d)
            or str(d.get("name") or "").strip().lower() in corr_names
        )
    ]
    max_pos = max((author_position(d) for d in details), default=0)

    selected: dict[str, dict[str, Any]] = {}
    for detail in details:
        name = str(detail.get("name") or "").strip()
        if not name:
            continue
        name_key = name.lower()
        roles: list[tuple[str, str]] = []
        if detail.get("is_first") or author_position(detail) == 1 or name_key in first_names:
            roles.append(("first", "first_author_metadata"))
        is_explicit_corr = detail in explicit_corr
        is_last_fallback = not explicit_corr and (detail.get("is_last") or author_position(detail) == max_pos)
        if is_explicit_corr:
            if detail.get("is_corresponding") or name_key in corr_names:
                role_source = "corresponding_author_metadata"
            else:
                role_source = "email_in_affiliation"
            roles.append(("corresponding", role_source))
        elif is_last_fallback:
            roles.append(("corresponding", "last_author_fallback"))
        for role, role_source in roles:
            key = f"{name_key}:{role}"
            selected[key] = {
                "name": name,
                "role": role,
                "role_source": role_source,
                "affiliations": detail.get("affiliations") or [],
                "position": author_position(detail),
            }
    return sorted(selected.values(), key=lambda item: (item["position"], item["role"]))


def all_author_affiliations(article: dict[str, Any]) -> list[str]:
    affs: list[str] = []
    for detail in article.get("author_affiliations") or []:
        affs.extend(str(aff) for aff in detail.get("affiliations") or [] if aff)
    if not affs:
        affs.extend(str(aff) for aff in article.get("affiliations") or [] if aff)
    return affs


def unique_hospitals_from_affiliations(affiliations: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hospitals: dict[str, dict[str, Any]] = {}
    excluded: dict[str, dict[str, Any]] = {}
    for aff in affiliations:
        hospital = hospital_from_affiliation(aff)
        if hospital:
            hospitals[hospital["id"]] = hospital
            continue
        non_hospital = extract_non_hospital_institution(aff)
        if non_hospital:
            excluded[non_hospital["id"]] = non_hospital
    return list(hospitals.values()), list(excluded.values())


def compact_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "pmid": article.get("pmid", ""),
        "title": article.get("title", ""),
        "journal": article.get("journal", ""),
        "pub_date": article.get("pub_date", ""),
        "entry_date": article.get("entry_date", ""),
        "evidence_level": article.get("evidence_level", ""),
        "study_types": article.get("study_types") or [],
        "china_related": bool(article.get("china_related")),
    }


def counter_top(counter: Counter, limit: int = 8) -> list[dict[str, Any]]:
    return [{"label": key, "count": count} for key, count in counter.most_common(limit)]


def sort_pmids_latest(pmids: set[str] | list[str], papers: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        {str(pmid) for pmid in pmids},
        key=lambda pmid: (
            str(papers.get(pmid, {}).get("entry_date") or papers.get(pmid, {}).get("pub_date") or ""),
            pmid,
        ),
        reverse=True,
    )


def ensure_node(nodes: dict[str, dict[str, Any]], hospital: dict[str, Any]) -> dict[str, Any]:
    node = nodes.get(hospital["id"])
    if not node:
        node = {
            "id": hospital["id"],
            "label": hospital["label"],
            "geo_scope": hospital["geo_scope"],
            "region": hospital["region"],
            "province": hospital["province"],
            "city": hospital["city"],
            "paper_ids": set(),
            "all_author_paper_ids": set(),
            "source_labels": set(),
            "authors": Counter(),
            "topics": Counter(),
            "first_author_paper_ids": set(),
            "corresponding_author_paper_ids": set(),
            "collaborators": set(),
        }
        nodes[hospital["id"]] = node
    node["source_labels"].add(hospital.get("source_label") or hospital["label"])
    return node


def build_network(articles: list[dict[str, Any]], source_scope: str = "full") -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    papers: dict[str, dict[str, Any]] = {}
    heatmap_tracker: dict[tuple[str, str, str], dict[str, Any]] = {}
    audit_unresolved = Counter()
    audit_excluded: dict[str, dict[str, Any]] = {}
    corresponding_last_author_count = 0
    china_papers = 0
    graph_author_rows = 0
    graph_author_with_hospital = 0
    role_source_counts = Counter()

    for article in articles:
        if not article_is_china_related(article):
            continue
        pmid = str(article.get("pmid") or "").strip()
        if not pmid:
            continue
        china_papers += 1
        topics = article_topics(article)

        all_hospitals, all_excluded = unique_hospitals_from_affiliations(all_author_affiliations(article))
        for item in all_excluded:
            audit_excluded[item["id"]] = item
        for hospital in all_hospitals:
            node = ensure_node(nodes, hospital)
            node["all_author_paper_ids"].add(pmid)
            key = (hospital["geo_scope"], hospital.get("province") or "", hospital.get("city") or "")
            row = heatmap_tracker.setdefault(key, {
                "geo_scope": hospital["geo_scope"],
                "region": hospital["region"],
                "province": hospital.get("province") or "",
                "city": hospital.get("city") or "",
                "hospital_ids": set(),
                "paper_ids": set(),
                "all_author_occurrences": 0,
                "hospital_paper_ids": defaultdict(set),
            })
            row["hospital_ids"].add(hospital["id"])
            row["paper_ids"].add(pmid)
            row["all_author_occurrences"] += 1
            row["hospital_paper_ids"][hospital["id"]].add(pmid)

        authors_graph = []
        edge_hospital_ids: set[str] = set()
        for author in graph_author_details(article):
            graph_author_rows += 1
            role_source_counts[author["role_source"]] += 1
            author_hospitals, author_excluded = unique_hospitals_from_affiliations(author["affiliations"])
            for item in author_excluded:
                audit_excluded[item["id"]] = item
            if not author_hospitals:
                for aff in author["affiliations"]:
                    audit_unresolved[compact_space(aff)] += 1
                continue
            graph_author_with_hospital += 1
            if author["role_source"] == "last_author_fallback":
                corresponding_last_author_count += 1
            hospital_refs = []
            for hospital in author_hospitals:
                node = ensure_node(nodes, hospital)
                node["paper_ids"].add(pmid)
                node["authors"][author["name"]] += 1
                for topic in topics:
                    node["topics"][topic] += 1
                if author["role"] == "first":
                    node["first_author_paper_ids"].add(pmid)
                if author["role"] == "corresponding":
                    node["corresponding_author_paper_ids"].add(pmid)
                edge_hospital_ids.add(hospital["id"])
                hospital_refs.append(hospital["id"])
            authors_graph.append({
                "name": author["name"],
                "role": author["role"],
                "role_source": author["role_source"],
                "hospitals": hospital_refs,
            })

        if authors_graph or all_hospitals:
            papers[pmid] = {
                **compact_article(article),
                "topics": topics,
                "authors_graph": authors_graph,
                "all_author_hospital_count": len(all_hospitals),
            }

        for a, b in combinations(sorted(edge_hospital_ids), 2):
            edge = edges.setdefault((a, b), {
                "id": f"{a}__{b}",
                "source": a,
                "target": b,
                "paper_ids": set(),
                "authors": Counter(),
                "topics": Counter(),
                "latest_date": "",
            })
            edge["paper_ids"].add(pmid)
            edge["latest_date"] = max(edge["latest_date"], str(article.get("entry_date") or article.get("pub_date") or ""))
            for author in authors_graph:
                edge["authors"][author["name"]] += 1
            for topic in topics:
                edge["topics"][topic] += 1
            nodes[a]["collaborators"].add(b)
            nodes[b]["collaborators"].add(a)

    edge_list = []
    for (_, _), edge in edges.items():
        weight = len(edge["paper_ids"])
        if weight < DATA_EDGE_THRESHOLD:
            continue
        source = nodes[edge["source"]]
        target = nodes[edge["target"]]
        edge_list.append({
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            "source_label": source["label"],
            "target_label": target["label"],
            "weight": weight,
            "edge_weight": weight,
            "paper_ids": sorted(edge["paper_ids"]),
            "latest_date": edge["latest_date"],
            "geo_scopes": sorted({source["geo_scope"], target["geo_scope"]}),
            "top_authors": counter_top(edge["authors"], 8),
            "top_topics": counter_top(edge["topics"], 8),
        })
    edge_list.sort(key=lambda item: (-item["edge_weight"], item["source_label"], item["target_label"]))

    node_list = []
    for node in nodes.values():
        paper_ids = sort_pmids_latest(node["paper_ids"], papers)
        all_author_ids = sort_pmids_latest(node["all_author_paper_ids"], papers)
        node_list.append({
            "id": node["id"],
            "label": node["label"],
            "geo_scope": node["geo_scope"],
            "region": node["region"],
            "province": node["province"],
            "city": node["city"],
            "paper_count": len(paper_ids),
            "all_author_paper_count": len(all_author_ids),
            "first_author_paper_count": len(node["first_author_paper_ids"]),
            "corresponding_author_paper_count": len(node["corresponding_author_paper_ids"]),
            "collaborator_count": len(node["collaborators"]),
            "degree": len(node["collaborators"]),
            "top_authors": counter_top(node["authors"], 10),
            "top_topics": counter_top(node["topics"], 8),
            "paper_ids": paper_ids[:200],
            "all_author_paper_ids": all_author_ids[:200],
        })
    node_list.sort(key=lambda item: (-item["paper_count"], -item["degree"], item["label"]))

    heatmap = []
    for row in heatmap_tracker.values():
        heatmap.append({
            "geo_scope": row["geo_scope"],
            "region": row["region"],
            "province": row["province"],
            "city": row["city"],
            "hospital_count": len(row["hospital_ids"]),
            "paper_count": len(row["paper_ids"]),
            "all_author_occurrences": row["all_author_occurrences"],
            "top_hospitals": [
                {"id": hospital_id, "label": nodes[hospital_id]["label"], "count": len(paper_ids)}
                for hospital_id, paper_ids in sorted(
                    row["hospital_paper_ids"].items(),
                    key=lambda item: (-len(item[1]), nodes[item[0]]["label"]),
                )[:8]
            ],
        })
    heatmap.sort(key=lambda item: (-item["paper_count"], item["geo_scope"], item["province"], item["city"]))

    mainland_default_edges = [e for e in edge_list if e["edge_weight"] >= DEFAULT_DISPLAY_EDGE_WEIGHT and e["geo_scopes"] == ["mainland"]]
    graph_author_parse_rate = (graph_author_with_hospital / graph_author_rows) if graph_author_rows else 0

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_scope": source_scope,
        "inclusion_policy": {
            "geography": "china_only_mainland_default_hmt_filter_layers",
            "heatmap_authors": "all_authors",
            "graph_authors": "first_and_corresponding_authors",
            "graph_edges": "first_and_corresponding_hospital_cooccurrence",
            "corresponding_fallback": "last_author_as_corresponding",
            "corresponding_source_order": [
                "corresponding_authors_or_is_corresponding",
                "email_in_affiliation",
                "last_author_fallback",
            ],
            "data_edge_threshold": DATA_EDGE_THRESHOLD,
            "institution_level": "hospital_canonical",
            "node_label_policy": "english_or_pinyin_canonical_no_zh_dictionary",
        },
        "display_policy": {
            "default_geo_scope": "mainland",
            "default_edge_weight_min": DEFAULT_DISPLAY_EDGE_WEIGHT,
            "available_edge_weight_min": [5, 3, 1],
            "node_search_expands_all_edges": True,
            "edge_weight_basis": "deduplicated PMID count across first/corresponding author hospitals",
        },
        "summary": {
            "input_articles": len(articles),
            "china_related_papers": china_papers,
            "papers": len(papers),
            "papers_with_graph_authors": sum(1 for p in papers.values() if p.get("authors_graph")),
            "hospitals": len(node_list),
            "mainland_hospitals": sum(1 for n in node_list if n["geo_scope"] == "mainland"),
            "edges": len(edge_list),
            "mainland_default_edges": len(mainland_default_edges),
            "graph_author_rows": graph_author_rows,
            "graph_author_with_hospital": graph_author_with_hospital,
            "graph_author_hospital_parse_rate": round(graph_author_parse_rate, 4),
        },
        "nodes": node_list,
        "edges": edge_list,
        "default_edge_ids": [edge["id"] for edge in mainland_default_edges],
        "papers": papers,
        "heatmap": heatmap,
        "audit": {
            "unresolved_affiliations": [
                {"label": label, "count": count}
                for label, count in audit_unresolved.most_common(50)
            ],
            "non_hospital_institutions_excluded": sorted(
                audit_excluded.values(), key=lambda item: (item.get("geo_scope", ""), item.get("label", ""))
            )[:80],
            "corresponding_last_author_count": corresponding_last_author_count,
            "graph_author_role_sources": dict(role_source_counts),
            "notes": [
                "Default graph shows mainland edges with edge_weight >= 5.",
                "Heatmap uses all-author hospitals; collaboration edges use first/corresponding-author hospitals.",
                "PubMed XML has no normalized corresponding-author tag; email-in-affiliation candidates are used before last-author fallback.",
                "Hong Kong, Macau, and Taiwan are retained as filter layers.",
                "Hospital labels are English/pinyin canonical values parsed from PubMed affiliations; no Chinese dictionary is maintained.",
            ],
        },
    }


def load_articles() -> tuple[list[dict[str, Any]], str]:
    if FULL_PATH.exists():
        return load_json(FULL_PATH), "full"
    if RECENT_JS_PATH.exists():
        return load_js_global(RECENT_JS_PATH, "MG_LITERATURE_DATA"), "recent_fallback"
    raise FileNotFoundError("Need data/literature-full.json or data/literature-recent.js")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build China hospital author collaboration network")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output JS path")
    args = parser.parse_args()

    articles, source_scope = load_articles()
    payload = build_network(articles, source_scope=source_scope)
    output = Path(args.output)
    atomic_write_js_global(output, OUTPUT_GLOBAL, payload)
    summary = payload["summary"]
    print(
        "✅ china author network written: "
        f"{output.relative_to(PROJECT)} · {summary['hospitals']} hospitals · "
        f"{summary['edges']} edges · default {summary['mainland_default_edges']} edges"
    )


if __name__ == "__main__":
    main()
