from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT / "scripts"
RULES_PATH = SCRIPTS_DIR / "chinaLocationRules.py"
BUILD_PATH = SCRIPTS_DIR / "build-frontend-data.py"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_rules():
    spec = importlib.util.spec_from_file_location("chinaLocationRules", RULES_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load_rules()
infer = rules.infer_china_location


def test_west_china_hospital_is_chengdu_not_xian():
    """华西医院在四川成都，不得因 raw affiliation 含 xian 被判成陕西西安。"""
    assert infer("West China Hospital, Sichuan University") == {"province": "四川", "city": "成都"}
    assert infer(
        "West China Hospital, Sichuan University",
        Counter({"Dept of Neurology, Xi'an Jiaotong University": 2}),
    ) == {"province": "四川", "city": "成都"}


def test_xian_substring_does_not_hijack_xiangya_or_huashan():
    """裸子串 xian 不得命中 xiangya；华山医院 stays 上海。"""
    assert infer("Xiangya Hospital, Central South University") == {"province": "湖南", "city": "长沙"}
    assert infer(
        "Huashan Hospital, Fudan University", Counter({"Xi'an Medical University": 1})
    ) == {"province": "上海", "city": "上海"}


def test_province_level_cities_are_specific():
    """修复旧表把整个省映射到单一城市的缺陷。"""
    cases = {
        "First Affiliated Hospital of Soochow University": ("江苏", "苏州"),
        "First Affiliated Hospital of Wenzhou Medical University": ("浙江", "温州"),
        "Affiliated Hospital of Qingdao University": ("山东", "青岛"),
        "First Affiliated Hospital of Nanjing Medical University": ("江苏", "南京"),
        "First Affiliated Hospital of Xiamen University": ("福建", "厦门"),
    }
    for affiliation, (province, city) in cases.items():
        assert infer(affiliation) == {"province": province, "city": city}, affiliation


def test_ambiguous_institutions():
    """同名/易混机构按医院实际所在地判定。"""
    cases = {
        "First Affiliated Hospital of Jinan University": ("广东", "广州"),  # 暨南大学
        "Qilu Hospital (Qingdao)": ("山东", "青岛"),
        "China-Japan Union Hospital of Jilin University": ("吉林", "长春"),
        "Air Force Medical Center of PLA": ("北京", "北京"),  # 空军特色医学中心
        "Tangdu Hospital, Air Force Medical University": ("陕西", "西安"),
        "University of Hong Kong-Shenzhen Hospital": ("广东", "深圳"),
        "Jiangsu Normal University": ("江苏", "徐州"),
        "Hainan Hospital of Chinese PLA General Hospital": ("海南", "三亚"),
        "College of Medicine, China Medical University": ("台湾", "台湾"),  # 中国医药大学
        "China Medical University": ("辽宁", "沈阳"),  # 中国医科大学
    }
    for affiliation, (province, city) in cases.items():
        assert infer(affiliation) == {"province": province, "city": city}, affiliation


def test_build_script_delegates_to_authoritative_rules():
    """build-frontend-data.py 必须委托权威规则，避免两套逻辑漂移。"""
    spec = importlib.util.spec_from_file_location("bfd", BUILD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.infer_china_location(
        "West China Hospital, Sichuan University", Counter({"Xi'an University": 1})
    ) == {"province": "四川", "city": "成都"}
