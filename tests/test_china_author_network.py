from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT / "scripts" / "buildChinaAuthorNetwork.py"


def load_module():
    spec = importlib.util.spec_from_file_location("buildChinaAuthorNetwork", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_articles():
    return [
        {
            "pmid": "1001",
            "title": "Mainland hospital collaboration in myasthenia gravis",
            "journal": "Test Journal",
            "entry_date": "2026/07/01",
            "pub_date": "2026",
            "evidence_level": "III",
            "study_types": ["Retrospective Cohort"],
            "china_related": True,
            "author_affiliations": [
                {
                    "position": 1,
                    "name": "Li Wei",
                    "is_first": True,
                    "is_corresponding": False,
                    "affiliations": [
                        "Department of Neurology, Huashan Hospital, Fudan University, Shanghai, China."
                    ],
                },
                {
                    "position": 2,
                    "name": "Zhang Min",
                    "is_first": False,
                    "is_corresponding": False,
                    "affiliations": [
                        "School of Medicine, Fudan University, Shanghai, China."
                    ],
                },
                {
                    "position": 3,
                    "name": "Wang Qiang",
                    "is_first": False,
                    "is_last": True,
                    "is_corresponding": False,
                    "affiliations": [
                        "Department of Neurology, Peking University First Hospital, Beijing, China."
                    ],
                },
            ],
        },
        {
            "pmid": "1002",
            "title": "Hong Kong myasthenia gravis cohort",
            "journal": "Test Journal",
            "entry_date": "2026/07/02",
            "pub_date": "2026",
            "evidence_level": "IV",
            "study_types": ["Cross-Sectional"],
            "china_related": True,
            "author_affiliations": [
                {
                    "position": 1,
                    "name": "Chan Ada",
                    "is_first": True,
                    "affiliations": [
                        "Department of Medicine, Queen Mary Hospital, The University of Hong Kong, Hong Kong, China."
                    ],
                },
                {
                    "position": 2,
                    "name": "Lee Ben",
                    "is_last": True,
                    "affiliations": [
                        "School of Medicine, The University of Hong Kong, Hong Kong, China."
                    ],
                },
            ],
        },
    ]


def test_build_network_uses_last_author_as_corresponding_and_preserves_data_vs_display_thresholds():
    module = load_module()

    payload = module.build_network(sample_articles(), source_scope="test")

    assert payload["inclusion_policy"]["data_edge_threshold"] == 1
    assert payload["display_policy"]["default_edge_weight_min"] == 5
    assert payload["display_policy"]["default_geo_scope"] == "mainland"
    assert payload["inclusion_policy"]["corresponding_fallback"] == "last_author_as_corresponding"

    mainland_edges = [edge for edge in payload["edges"] if edge["source"] != edge["target"]]
    assert len(mainland_edges) == 1
    edge = mainland_edges[0]
    assert edge["edge_weight"] == 1
    assert edge["paper_ids"] == ["1001"]

    paper = payload["papers"]["1001"]
    roles = {(author["name"], author["role"]) for author in paper["authors_graph"]}
    assert ("Li Wei", "first") in roles
    assert ("Wang Qiang", "corresponding") in roles
    assert paper["authors_graph"][1]["role_source"] == "last_author_fallback"


def test_build_network_keeps_hong_kong_as_filter_layer_and_does_not_translate_labels():
    module = load_module()

    payload = module.build_network(sample_articles(), source_scope="test")

    nodes = {node["label"]: node for node in payload["nodes"]}
    assert "Queen Mary Hospital, The University of Hong Kong" in nodes
    assert nodes["Queen Mary Hospital, The University of Hong Kong"]["geo_scope"] == "hong_kong"
    assert "label_zh" not in nodes["Queen Mary Hospital, The University of Hong Kong"]

    assert "School of Medicine, Fudan University" not in nodes
    excluded = payload["audit"]["non_hospital_institutions_excluded"]
    assert any("School of Medicine, Fudan University" in item["label"] for item in excluded)

    heatmap_scopes = {row["geo_scope"] for row in payload["heatmap"]}
    assert "mainland" in heatmap_scopes
    assert "hong_kong" in heatmap_scopes


def test_hospital_canonicalization_and_last_location_token():
    module = load_module()

    huashan = module.hospital_from_affiliation(
        "Department of Neurology, Huashan Hospital Shanghai Medical College, Fudan University, Shanghai, China."
    )
    assert huashan and huashan["label"] == "Huashan Hospital"

    reversed_huashan = module.hospital_from_affiliation(
        "Department of Neurology, Fudan University Huashan Hospital, Shanghai, China."
    )
    assert reversed_huashan and reversed_huashan["label"] == "Huashan Hospital"

    location = module.infer_location(
        "Fuzhou General Hospital of Nanjing Military Command, Second Military Medical University, Fuzhou, China."
    )
    assert location["province"] == "Fujian"
    assert location["city"] == "Fuzhou"
