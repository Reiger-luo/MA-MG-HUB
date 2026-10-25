"""指南/共识可读短名。

g01–gNN 是语料内部 key，对读者没有意义。任何面向页面的文本都必须用这里的短名，
例如「中国 2025 MG 指南」而不是「g23」。

短名按文件名特征匹配；新增语料时在 RULES 里补一条规则，否则回退到
「地区 + 年份」的兜底短名（仍可读，只是不够具体）。
"""
from __future__ import annotations

import re

# 顺序敏感：更具体的规则放前面
RULES: list[tuple[str, str]] = [
    ("MGFA标准", "MGFA 2000 分级标准"),
    ("Data Supplement", "MGFA 2016 国际共识（附录）"),
    ("Table e-1", "MGFA 2016 附表 e-1 药物管理"),
    ("Table e-2", "MGFA 2016 附表 e-2 慎用药物"),
    ("2016-MGFA", "MGFA 2016 国际共识"),
    ("2020-MGFA", "MGFA 2020 国际共识更新"),
    ("罕见病指南", "中国 2019 罕见病诊疗指南"),
    ("免疫吸附", "中国 2022 免疫吸附指南"),
    ("日本", "日本 2022 MG 指南"),
    ("外科治疗", "中国 2022 外科治疗共识"),
    ("自身抗体实验室诊断", "中国 2022 抗体诊断共识"),
    ("静脉注射人免疫球蛋白", "中国 2022 IVIG 指南"),
    ("ACCP", "ACCP 2023 呼吸管理指南"),
    ("德国", "德国 2023 MG 指南"),
    ("MGNet", "MGNet 2023 结局评价指南"),
    ("难治性全身型", "中国 2024 难治性 gMG 共识"),
    ("全病程护理", "中国 2024 护理共识"),
    ("FcRn拮抗剂", "中国 2024 FcRn 专家建议"),
    ("危象前状态", "中国 2024 危象前状态共识"),
    ("北欧", "北欧 2024 MG 指南"),
    ("比利时", "比利时 2024 MG 建议"),
    ("眼肌型", "中国 2025 眼肌型共识"),
    ("2025-中国重症肌无力诊断和治疗指南", "中国 2025 MG 指南"),
    ("以色列", "以色列 2025 MG 指南"),
    ("激素相关并发症", "国际 2025 激素并发症共识"),
    ("意大利", "意大利 2025 激素管理建议"),
    ("英国", "英国 2025 MG 指南"),
    ("管理目标国际共识", "国际 2026 管理目标共识"),
    ("台湾", "中国台湾 2026 MG 指南"),
    ("加拿大EFG", "加拿大 2026 EFG 共识"),
    ("抗体类药物", "中国 2026 抗体药物药学共识"),
    ("补体抑制剂", "中国 2026 补体抑制剂建议"),
    ("临床治疗研究专家共识", "中国 2026 临床治疗研究共识"),
    ("胸腺扩大切除", "中国 2026 胸腺切除围术期共识"),
]

REGION_PREFIX = {"china": "中国", "international": "国际", "taiwan": "中国台湾"}


def short_name(filename: str, region: str = "", year: str = "") -> str:
    """把指南文件名转成可读短名。"""
    name = filename or ""
    for needle, label in RULES:
        if needle in name:
            return label
    # 兜底：地区 + 年份，仍然可读
    found_year = year or ""
    if not found_year:
        match = re.search(r"(19|20)\d{2}", name)
        found_year = match.group(0) if match else ""
    prefix = REGION_PREFIX.get(region, "")
    core = re.sub(r"\.(pdf|docx)$", "", name, flags=re.I)
    core = re.sub(r"^(19|20)\d{2}[-_ ]*", "", core)
    core = re.sub(r"[_（(].*$", "", core).strip(" -_")
    core = core[:18] or "未命名指南"
    return " ".join(part for part in (prefix, found_year, core) if part).strip()