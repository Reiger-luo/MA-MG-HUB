"""临床试验药物机制归类与别名合并回归测试。

固定三条历史缺陷：
1. GenSci136 中美两条注册被拆成「其他」两行，且 Phase 1/2 被降为「未标注」。
2. 可识别机制的在研分子（BAFF/APRIL、补体、FcRn、细胞治疗等）滞留「其他」。
3. 同一分子的代号与通用名（RC18/ripertamab/UCB7665/FK506/IGIV-C）未归并。

测试直接加载 builder 模块，不改写任何已发布产物。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
BUILDER_PATH = PROJECT / "scripts" / "build-clinical-trials-data.py"


def load_builder_module():
    spec = importlib.util.spec_from_file_location("build_clinical_trials_data", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gensci136_two_names_merge_to_one_canonical():
    module = load_builder_module()
    cn = module.normalize_drug_name("注射用GenSci136")
    us = module.normalize_drug_name("GenSci136 for injection")
    assert cn == us == "GenSci136 (BAFF/APRIL双拮抗)"


def test_gensci136_classified_as_b_cell_axis():
    module = load_builder_module()
    assert module.extract_drug_class("", "GenSci136 (BAFF/APRIL双拮抗)") == "B细胞/抗CD19/CD20"
    # 标题兜底同样归入 B 细胞轴（中国注册题名）。
    assert module.extract_drug_class("GenSci136在重症肌无力患者中的Ib/II期临床试验", "注射用GenSci136") == "B细胞/抗CD19/CD20"


def test_known_alias_merges():
    module = load_builder_module()
    norm = module.normalize_drug_name
    assert norm("RC18 160mg") == "Telitacicept (泰它西普)"
    assert norm("ripertamab") == "Rituximab (利妥昔单抗)"
    assert norm("UCB7665") == "Rozanolixizumab (罗泽利昔珠单抗)"
    assert norm("FK506 therapy") == "Tacrolimus (他克莫司)"
    assert norm("IGIV-C") == "IVIg (静注人免疫球蛋白)"
    assert norm("EA5注射液皮下制剂") == "EA5 (抗C5单抗)"
    assert norm("ATG (rabbit)") == "Anti-Thymocyte Globulin (ATG)"
    assert norm("Decartes-08") == norm("Descartes-08") == "Descartes-08"


def test_known_mechanism_reclassifications():
    module = load_builder_module()
    cls = lambda name: module.extract_drug_class("", name)
    # FcRn
    assert cls("Orilanolimab (ALXN1830)") == "FcRn 拮抗剂"
    # 补体
    assert cls("Vemircopan (ALXN2050)") == "补体抑制剂"
    assert cls("CG001注射液") == "补体抑制剂"
    assert cls("EA5 (抗C5单抗)") == "补体抑制剂"
    assert cls("IM-101 (抗C5单抗)") == "补体抑制剂"
    # B 细胞轴
    for name in ("Belimumab", "Povetacicept", "Aritinercept", "TAK-079", "CABA-201",
                 "MuSK-CAART", "CD19-CAR-NK Cells Injection", "anito-cel", "Blinatumomab"):
        assert cls(name) == "B细胞/抗CD19/CD20", name
    # 免疫抑制 / 免疫调节 / 胆碱酯酶
    assert cls("Cyclophosphamide") == "免疫抑制剂"
    assert cls("Tofacitinib 5 MG") == "免疫抑制剂"
    assert cls("CNP-106") == "免疫调节"
    assert cls("CV-MG01") == "免疫调节"
    assert cls("SHR-2173") == "免疫调节"
    assert cls("Neostigmine") == "胆碱酯酶抑制剂"


def test_combined_phase_labels_keep_stage_rank():
    """带空格与不带空格的联合期别必须同权，避免最高阶段被判「未标注」。"""
    module = load_builder_module()
    assert module.PHASE_RANK["Phase 1 / Phase 2"] == module.PHASE_RANK["Phase 1/2"] == 1.5
    assert module.PHASE_RANK["Phase 2 / Phase 3"] == module.PHASE_RANK["Phase 2/3"] == 2.5
    assert module.phase_label(["PHASE1", "PHASE2"]) == "Phase 1 / Phase 2"
