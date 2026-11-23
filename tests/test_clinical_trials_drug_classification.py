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


def test_one_drug_one_row_normalization():
    """同一药物的代号/缩写/剂型/剂量组必须归一为同一个规范名。"""
    norm = load_builder_module().normalize_drug_name
    # ChiCTR2600133923 的给药周期片段不是新 FcRn 药，应丢弃。
    assert norm("5 treatment cycles.") == ""
    # NCT06193889 的清淋预处理不是研究药。
    assert norm("Standard lymphodepletion regimen") == ""
    # NCT06371040 / NCT06958939 的剂量组是同一 CAR-T 的不同剂量水平。
    assert norm("CD19-BCMA Targeted CAR-T Dose 1") == norm("CD19-BCMA Targeted CAR-T Dose 2")
    assert norm("Dose level 1 group") == norm("Dose level 4 group") == "SENL103 (CAR-T)"
    # 缩写/全称/大小写/中文名归并。
    assert norm("AZA") == norm("azathioprine") == "Azathioprine (硫唑嘌呤)"
    assert norm("methotrexate") == norm("Methotrexate") == "Methotrexate (甲氨蝶呤)"
    assert norm("Mycophenolic acid") == norm("mycophenolate") == "Mycophenolate (吗替麦考酚酯)"
    assert norm("cyclosporine") == norm("环孢素") == "Cyclosporine (环孢素)"
    assert norm("glucocorticoid") == norm("Steroid Drug") == "Corticosteroids (糖皮质激素)"
    assert norm("Tocilizumab Injection") == norm("Tocilizumab") == "Tocilizumab (托珠单抗)"
    assert norm("RTX therapy") == norm("rituximab") == "Rituximab (利妥昔单抗)"
    assert norm("inebilizumab") == norm("伊奈利珠单抗") == "Inebilizumab (伊奈利珠单抗)"
    assert norm("HIZENTRA ®") == norm("immune globulin") == "IVIg (静注人免疫球蛋白)"
    assert norm("Immediate-Release Tablets") == norm("Sustained-Release Tablets") == "Pyridostigmine (溴吡斯的明)"
    assert norm("250 mg CK-2017357") == norm("500 mg CK-2017357") == "Tirasemtiv (CK-2017357)"


def test_imvt1402_is_not_batoclimab():
    """IMVT-1402 是 Immunovant 新一代 FcRn 抗体，不等于 batoclimab（IMVT-1401）。"""
    norm = load_builder_module().normalize_drug_name
    assert norm("IMVT-1402") == "IMVT-1402"
    for alias in ("batoclimab", "IMVT-1401", "RVT-1401", "HBM9161", "HL161"):
        assert norm(alias) == "Batoclimab (巴托利单抗)", alias
    assert norm("IMVT-1402") != norm("Batoclimab")


def test_tolebrutinib_is_btk_not_il6():
    """SAR442168 = tolebrutinib，是 BTK 抑制剂，不得归入 IL-6 类。"""
    module = load_builder_module()
    assert module.normalize_drug_name("SAR442168") == module.normalize_drug_name("Tolebrutininb")
    assert module.extract_drug_class("", "Tolebrutinib (SAR442168)") == "免疫抑制剂"


def _trial(module, rid, names, *, phase="Phase 1", title="", registry="ClinicalTrials.gov"):
    """构造管线矩阵所需的最小记录；drug_names 按真实管线先经 split_combo_drugs 归一化。"""
    normalized = module.split_combo_drugs(names)
    return {
        "registry": registry,
        "registry_id": rid,
        "drug_name": normalized[0] if normalized else "",
        "drug_names": normalized,
        "title": title or rid,
        "phase_label": phase,
        "status_label": "招募中",
        "sponsor": "Sponsor",
    }


def test_pipeline_matrix_one_row_per_drug():
    """同一规范药名只能出现一行，研究数/最高阶段按合并后的研究汇总。"""
    module = load_builder_module()
    records = [
        _trial(module, "NCT06371040", ["CD19-BCMA Targeted CAR-T Dose 1", "CD19-BCMA Targeted CAR-T Dose 2"], phase="Phase 1"),
        _trial(module, "NCT06958939", ["Dose level 1 group", "Dose level 4 group"], phase="Phase 1"),
        _trial(module, "NCT00814138", ["Methotrexate"], phase="Phase 4"),
        _trial(module, "ChiCTR-IPR-15006081", ["methotrexate"], phase="Phase 2", registry="ChiCTR"),
        _trial(module, "NCT00997412", ["AZA", "Mycophenolic acid"], phase="Phase 3"),
        _trial(module, "NCT001", ["azathioprine"], phase="Phase 4"),
    ]
    matrix = module.build_pipeline_matrix(records)
    names = [m["name"] for m in matrix]
    assert len(names) == len(set(names)), "每个规范药名只能有一行"

    by_name = {m["name"]: m for m in matrix}
    # NCT06371040 的 Dose1/Dose2 合并为一行，只计一次研究。
    car_t = by_name["CD19-BCMA Targeted CAR-T"]
    assert car_t["study_count"] == 1
    assert [t["registry_id"] for t in car_t["trials"]] == ["NCT06371040"]
    # SENL103 的 Dose level 1/4 合并为一行。
    assert by_name["SENL103 (CAR-T)"]["study_count"] == 1
    # 大小写不同的 Methotrexate 合并，研究数=2，最高阶段取 Phase 4。
    mtx = by_name["Methotrexate (甲氨蝶呤)"]
    assert mtx["study_count"] == 2
    assert mtx["highest_phase_label"] == "Phase 4"
    assert {t["registry"] for t in mtx["trials"]} == {"ClinicalTrials.gov", "ChiCTR"}
    # AZA/azathioprine 合并为 2 项；Mycophenolic acid 独立归一为吗替麦考酚酯。
    assert by_name["Azathioprine (硫唑嘌呤)"]["study_count"] == 2
    assert by_name["Mycophenolate (吗替麦考酚酯)"]["study_count"] == 1


def test_pipeline_matrix_class_stable_despite_title_drift():
    """同一药名即便各研究标题含不同机制词，也必须归到同一个分类、只出一行。"""
    module = load_builder_module()
    records = [
        # 两条标题分别含 efgartigimod（FcRn）与 rituximab（B 细胞），但药名相同；
        # 药名自身无关键词时，分类由该药名全部研究题名合并决定，仍只出一行。
        _trial(module, "NCT-A", ["Proprietary-X"], title="Study with efgartigimod induction"),
        _trial(module, "NCT-B", ["Proprietary-X"], title="Study with rituximab comparator"),
    ]
    matrix = module.build_pipeline_matrix(records)
    rows = [m for m in matrix if m["name"] == "Proprietary-X"]
    assert len(rows) == 1, "同一药名不得因标题不同拆成两行"
    assert rows[0]["study_count"] == 2


def test_combined_phase_labels_keep_stage_rank():
    """带空格与不带空格的联合期别必须同权，避免最高阶段被判「未标注」。"""
    module = load_builder_module()
    assert module.PHASE_RANK["Phase 1 / Phase 2"] == module.PHASE_RANK["Phase 1/2"] == 1.5
    assert module.PHASE_RANK["Phase 2 / Phase 3"] == module.PHASE_RANK["Phase 2/3"] == 2.5
    assert module.phase_label(["PHASE1", "PHASE2"]) == "Phase 1 / Phase 2"
