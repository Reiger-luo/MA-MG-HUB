"""Canonical MG drug tags for article-level public intelligence views.

Tags mean that a canonical drug name or alias was found in the article's title,
abstract, keywords, MeSH descriptors/qualifiers, or Chemical records. They are
text-level literature signals, not a claim that the drug was the intervention.
"""

from __future__ import annotations

import re
from typing import Any


DRUG_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "efgartigimod",
        "label": "Efgartigimod / 艾加莫德",
        "name_en": "Efgartigimod",
        "name_zh": "艾加莫德",
        "category": "FcRn",
        "patterns": (r"\befgartigimod\b", r"\bvyvgart\b", r"\bargx[- ]?113\b", r"艾加莫德"),
    },
    {
        "id": "rozanolixizumab",
        "label": "Rozanolixizumab / 罗泽利昔珠单抗",
        "name_en": "Rozanolixizumab",
        "name_zh": "罗泽利昔珠单抗",
        "category": "FcRn",
        "patterns": (r"\brozanolixizumab\b", r"\brystiggo\b", r"罗泽利昔珠单抗"),
    },
    {
        "id": "nipocalimab",
        "label": "Nipocalimab / 尼卡利单抗",
        "name_en": "Nipocalimab",
        "name_zh": "尼卡利单抗",
        "category": "FcRn",
        "patterns": (r"\bnipocalimab\b", r"尼卡利单抗"),
    },
    {
        "id": "batoclimab",
        "label": "Batoclimab / 巴托利单抗",
        "name_en": "Batoclimab",
        "name_zh": "巴托利单抗",
        "category": "FcRn",
        "patterns": (r"\bbatoclimab\b", r"巴托利单抗"),
    },
    {
        "id": "telitacicept",
        "label": "Telitacicept / 泰它西普",
        "name_en": "Telitacicept",
        "name_zh": "泰它西普",
        "category": "BAFF/APRIL",
        "patterns": (r"\btelitacicept\b", r"\brc[- ]?18\b", r"泰它西普"),
    },
    {
        "id": "eculizumab",
        "label": "Eculizumab / 依库珠单抗",
        "name_en": "Eculizumab",
        "name_zh": "依库珠单抗",
        "category": "Complement",
        "patterns": (r"\beculizumab\b", r"\bsoliris\b", r"依库珠单抗"),
    },
    {
        "id": "ravulizumab",
        "label": "Ravulizumab / 拉夫利珠单抗",
        "name_en": "Ravulizumab",
        "name_zh": "拉夫利珠单抗",
        "category": "Complement",
        "patterns": (r"\bravulizumab\b", r"\bultomiris\b", r"拉夫利珠单抗"),
    },
    {
        "id": "zilucoplan",
        "label": "Zilucoplan",
        "name_en": "Zilucoplan",
        "name_zh": "",
        "category": "Complement",
        "patterns": (r"\bzilucoplan\b", r"\bzilbrysq\b"),
    },
    {
        "id": "cemdisiran",
        "label": "Cemdisiran",
        "name_en": "Cemdisiran",
        "name_zh": "",
        "category": "Complement",
        "patterns": (r"\bcemdisiran\b",),
    },
    {
        "id": "rituximab",
        "label": "Rituximab / 利妥昔单抗",
        "name_en": "Rituximab",
        "name_zh": "利妥昔单抗",
        "category": "B-cell",
        "patterns": (r"\brituximab\b", r"\bmabthera\b", r"利妥昔单抗"),
    },
    {
        "id": "pyridostigmine",
        "label": "Pyridostigmine / 溴吡斯的明",
        "name_en": "Pyridostigmine",
        "name_zh": "溴吡斯的明",
        "category": "Symptomatic",
        "patterns": (r"\bpyridostigmine\b", r"\bmestinon\b", r"溴吡斯的明"),
    },
    {
        "id": "corticosteroids",
        "label": "Corticosteroids / 糖皮质激素",
        "name_en": "Corticosteroids",
        "name_zh": "糖皮质激素",
        "category": "Immunosuppression",
        "patterns": (r"\bcorticosteroid(?:s)?\b", r"\bglucocorticoid(?:s)?\b", r"\bprednisone\b", r"\bprednisolone\b", r"\bmethylprednisolone\b", r"糖皮质激素"),
    },
    {
        "id": "azathioprine",
        "label": "Azathioprine / 硫唑嘌呤",
        "name_en": "Azathioprine",
        "name_zh": "硫唑嘌呤",
        "category": "Immunosuppression",
        "patterns": (r"\bazathioprine\b", r"硫唑嘌呤"),
    },
    {
        "id": "mycophenolate",
        "label": "Mycophenolate / 吗替麦考酚酯",
        "name_en": "Mycophenolate",
        "name_zh": "吗替麦考酚酯",
        "category": "Immunosuppression",
        "patterns": (r"\bmycophenolate(?:\s+mofetil)?\b", r"\bmycophenolic acid\b", r"吗替麦考酚酯"),
    },
    {
        "id": "tacrolimus",
        "label": "Tacrolimus / 他克莫司",
        "name_en": "Tacrolimus",
        "name_zh": "他克莫司",
        "category": "Immunosuppression",
        "patterns": (r"\btacrolimus\b", r"他克莫司"),
    },
    {
        "id": "cyclosporine",
        "label": "Cyclosporine / 环孢素",
        "name_en": "Cyclosporine",
        "name_zh": "环孢素",
        "category": "Immunosuppression",
        "patterns": (r"\bcyclosporine\b", r"\bciclosporin\b", r"环孢素"),
    },
    {
        "id": "ivig",
        "label": "IVIg / 静脉注射免疫球蛋白",
        "name_en": "IVIg",
        "name_zh": "静脉注射免疫球蛋白",
        "category": "Rescue",
        "patterns": (r"\bIVIg\b", r"\bintravenous immunoglobulin\b", r"静脉注射免疫球蛋白"),
    },
)

_COMPILED = tuple(
    (drug, tuple(re.compile(pattern, re.IGNORECASE) for pattern in drug["patterns"]))
    for drug in DRUG_CATALOG
)


def _article_search_text(article: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "abstract"):
        value = article.get(key)
        if value:
            parts.append(str(value))
    for key in ("keywords", "mesh_terms", "chemicals"):
        values = article.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            if isinstance(value, dict):
                parts.extend(str(value.get(field) or "") for field in ("name", "descriptor"))
                for qualifier in value.get("qualifiers") or []:
                    if isinstance(qualifier, dict):
                        parts.append(str(qualifier.get("name") or ""))
                    else:
                        parts.append(str(qualifier))
            else:
                parts.append(str(value))
    return "\n".join(part for part in parts if part)


def extract_drug_tag_ids(article: dict[str, Any]) -> list[str]:
    text = _article_search_text(article)
    return [
        drug["id"]
        for drug, patterns in _COMPILED
        if any(pattern.search(text) for pattern in patterns)
    ]


def public_drug_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": drug["id"],
            "label": drug["label"],
            "name_en": drug["name_en"],
            "name_zh": drug["name_zh"],
            "category": drug["category"],
        }
        for drug in DRUG_CATALOG
    ]
