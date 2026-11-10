"""重点药物 II/III 期文献判定（确定性规则，不引入 LLM）。

情报中心「领域重大事件」需要把重点药物发表的 II/III 期文章纳入信息流。
重点药物 = 诊治格局主清单 + 临床试验情报里的格局药物，两者都从
``landscape-data.js`` 动态并入，避免维护第二份会漂移的名单。

期别只认 PubMed PubType 或标题/摘要里明确写出的 Phase 2/3 标记；
综述、荟萃分析与评论不进入该信息流，避免把综述误报成试验结果。
"""

from __future__ import annotations

import re
from typing import Any

# 规范药名 → 可复核的别名（开发代号、商品名、中文名）。
# ALXN1720 只能指向 gefurulimab，M281 只能指向 nipocalimab。
KEY_DRUG_ALIASES: dict[str, tuple[str, ...]] = {
    "Efgartigimod": ("efgartigimod", "argx-113", "vyvgart", "艾加莫德"),
    "Rozanolixizumab": ("rozanolixizumab", "ucb7665", "罗泽利昔珠单抗"),
    "Nipocalimab": ("nipocalimab", "m281", "jnj-80202135", "尼卡利单抗"),
    "Batoclimab": ("batoclimab", "hbm9161", "hl161", "imvt-1401", "巴托利单抗"),
    "IMVT-1402": ("imvt-1402",),
    "Zilucoplan": ("zilucoplan", "ra101495", "zilbrysq", "泽卢克布仑钠"),
    "Ravulizumab": ("ravulizumab", "alxn1210", "瑞利珠单抗"),
    "Eculizumab": ("eculizumab", "依库珠单抗"),
    "Gefurulimab": ("gefurulimab", "alxn1720", "klygefa", "戈鲁利单抗"),
    "Telitacicept": ("telitacicept", "rc18", "rc-18", "泰它西普"),
    "Rituximab": ("rituximab", "利妥昔单抗"),
    "Inebilizumab": ("inebilizumab",),
    "Claseprubart": ("claseprubart", "dnth103"),
    "Iptacopan": ("iptacopan",),
    "Empasiprubart": ("empasiprubart",),
    "Pozelimab/Cemdisiran": ("pozelimab", "cemdisiran"),
    "Remibrutinib": ("remibrutinib", "lou064"),
    "Povetacicept": ("povetacicept",),
    "Aritinercept": ("aritinercept",),
    "Blinatumomab": ("blinatumomab",),
    "Descartes-08": ("descartes-08", "decartes-08"),
    "KYV-101": ("kyv-101",),
    "CABA-201": ("caba-201",),
    "NMD670": ("nmd670",),
    "Cladribine": ("cladribine", "克拉屈滨"),
    "Tocilizumab": ("tocilizumab",),
    "Satralizumab": ("satralizumab",),
    "B007": ("b007",),
    "SHR-2173": ("shr-2173",),
    "IM-101": ("im-101",),
    "CNP-106": ("cnp-106",),
    "Vemircopan": ("vemircopan", "alxn2050"),
}

# 期别标记：词边界保证 "phase iii" 不会被误判成 "phase ii"。
_PHASE3_RE = re.compile(r"\bphase\s*(?:3|iii|3b)\b", re.I)
_PHASE2_RE = re.compile(r"\bphase\s*(?:2|ii|2/3|ii/iii)\b", re.I)
_NOT_TRIAL_RE = re.compile(
    r"\b(?:systematic review|scoping review|narrative review|comprehensive review|"
    r"meta-analysis|network meta|indirect comparison|matched-adjusted|comparative efficacy|"
    r"commentary|editorial|letter|perspective|viewpoint|reply|"
    r"real-world|retrospective|cohort|registry|case series|case report|"
    r"pathogenic|biomarker|is it)\b",
    re.I,
)
# 必须是试验类文章本身，而不是摘要里顺带提到既往 III 期试验的其他研究。
_TRIAL_TITLE_RE = re.compile(
    r"\b(?:trial|study|analysis|analyses|results|efficacy|safety|outcomes?|"
    r"randomi[sz]ed|subgroup|pooled)\b",
    re.I,
)


def buildWatchlist(landscape: dict[str, Any] | None = None) -> dict[str, tuple[str, ...]]:
    """把格局主清单与临床管线里的药物并入别名表，返回规范名 → 别名。"""
    watchlist = {name: tuple(aliases) for name, aliases in KEY_DRUG_ALIASES.items()}
    for matrix_key in ("all_competitive_matrix", "competitive_pipeline", "clinical_pipeline_matrix"):
        for item in (landscape or {}).get(matrix_key) or []:
            raw = str(item.get("name") or "").strip()
            if not raw:
                continue
            for name in re.split(r"\s*[/+]\s*", raw):
                name = name.strip()
                if not name:
                    continue
                lowered = name.lower()
                known = any(
                    lowered == canonical.lower() or lowered in aliases
                    for canonical, aliases in watchlist.items()
                )
                if not known:
                    watchlist[name] = (lowered,)
    return watchlist


def matchKeyDrugs(text: Any, watchlist: dict[str, tuple[str, ...]]) -> list[str]:
    """返回文本命中的规范药名，按别名表顺序去重。"""
    low = str(text or "").lower()
    hits: list[str] = []
    for canonical, aliases in watchlist.items():
        for alias in aliases:
            if len(alias) < 4:
                continue
            # 中文别名不走 ASCII 词边界，避免 "艾加莫德" 两侧中文导致失配。
            pattern = (
                re.escape(alias) if not alias.isascii()
                else r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
            )
            if re.search(pattern, low):
                hits.append(canonical)
                break
    return hits


def classifyTrialPhase(article: dict[str, Any]) -> str:
    """只认标题或 PubMed PubType 明确写出的 II/III 期标记。

    摘要不参与期别判定：机制研究、综述和真实世界文章常在摘要里引用既往
    III 期试验，放行会把非试验文章误报成重点药物 II/III 期发表。
    """
    title = str(article.get("title") or "")
    if _NOT_TRIAL_RE.search(title) or not _TRIAL_TITLE_RE.search(title):
        return ""
    pub_types = " | ".join(str(item) for item in article.get("pub_types") or [])
    haystack = " ".join((title, pub_types))
    phase3 = bool(_PHASE3_RE.search(haystack))
    phase2 = bool(_PHASE2_RE.search(haystack))
    if phase3 and phase2:
        return "II/III期"
    if phase3:
        return "III期"
    if phase2:
        return "II期"
    return ""


def selectKeyDrugTrialPublications(
    articles: list[dict[str, Any]],
    watchlist: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    """筛选重点药物 II/III 期文章，返回可直接进入来源频道的最小字段。"""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for article in articles or []:
        pmid = str(article.get("pmid") or "").strip()
        if not pmid or pmid in seen or article.get("mg_core") is False:
            continue
        phase = classifyTrialPhase(article)
        if not phase:
            continue
        title = str(article.get("title") or "")
        # 药名同样只取标题：摘要里常并列多个对照药，会让信息流的药物标签失真。
        drugs = matchKeyDrugs(title, watchlist)
        if not drugs:
            continue
        seen.add(pmid)
        selected.append({
            "pmid": pmid,
            "title": title,
            "date": article.get("entry_date") or article.get("pub_date") or "",
            "phase_label": phase,
            "drugs": drugs,
            "journal": article.get("journal") or "",
            "evidence_level": article.get("evidence_level") or "",
            "url": str(article.get("url") or "") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi": article.get("doi") or "",
        })
    selected.sort(key=lambda item: (str(item["date"]), item["pmid"]), reverse=True)
    return selected
