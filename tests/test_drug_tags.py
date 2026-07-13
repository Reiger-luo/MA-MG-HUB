from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT / "scripts" / "buildChinaAuthorNetwork.py"


def load_network_module():
    spec = importlib.util.spec_from_file_location("buildChinaAuthorNetwork", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def article_with_drugs():
    return {
        "pmid": "9001",
        "title": "Efgartigimod and telitacicept in myasthenia gravis",
        "abstract": "A cohort evaluated efgartigimod; telitacicept was discussed as a comparator.",
        "entry_date": "2026/07/10",
        "pub_date": "2026",
        "china_related": True,
        "author_affiliations": [
            {
                "position": 1,
                "name": "Huashan Author",
                "is_first": True,
                "affiliations": [
                    "Department of Neurology, Huashan Hospital, Fudan University, Shanghai, China."
                ],
            },
            {
                "position": 2,
                "name": "West China Author",
                "is_last": True,
                "affiliations": [
                    "Department of Neurology, West China Hospital, Sichuan University, Chengdu, China."
                ],
            },
        ],
    }


def test_drug_tags_normalize_aliases_and_keep_article_level_scope():
    module = load_network_module()
    tags = module.extract_drug_tag_ids(article_with_drugs())
    assert tags == ["efgartigimod", "telitacicept"]


def test_title_drug_matches_are_authoritative_over_fallback_metadata():
    module = load_network_module()
    article = {
        "pmid": "38436998",
        "title": "Batoclimab vs Placebo for Generalized Myasthenia Gravis",
        "abstract": "The discussion mentions efgartigimod and rozanolixizumab.",
        "keywords": ["nipocalimab"],
        "mesh_terms": [{"descriptor": "Eculizumab"}],
        "chemicals": [{"name": "Ravulizumab"}],
    }

    assert module.extract_drug_tag_ids(article) == ["batoclimab"]


def test_fallback_metadata_is_combined_only_when_title_has_no_catalog_match():
    module = load_network_module()
    article = {
        "title": "Targeted therapies for generalized myasthenia gravis",
        "abstract": "Efgartigimod was evaluated.",
        "keywords": ["Rystiggo"],
        "mesh_terms": [{"descriptor": "Eculizumab"}],
        "chemicals": [{"name": "Tacrolimus"}],
    }

    assert module.extract_drug_tag_ids(article) == [
        "efgartigimod",
        "rozanolixizumab",
        "eculizumab",
        "tacrolimus",
    ]


def test_network_exposes_drug_counts_for_edge_and_hospital_views():
    module = load_network_module()
    payload = module.build_network([article_with_drugs()], source_scope="test")
    paper = payload["papers"]["9001"]
    assert paper["drug_tags"] == ["efgartigimod", "telitacicept"]

    edge = next(iter(payload["edges"]))
    assert edge["drug_counts"] == {"efgartigimod": 1, "telitacicept": 1}

    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes["huashan_hospital"]["all_author_drug_counts"]["efgartigimod"] == 1
    assert nodes["west_china_hospital"]["all_author_drug_counts"]["telitacicept"] == 1
    assert payload["summary"]["drug_paper_counts"] == {"efgartigimod": 1, "telitacicept": 1}
