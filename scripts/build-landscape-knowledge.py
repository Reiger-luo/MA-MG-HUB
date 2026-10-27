#!/usr/bin/env python3
"""生成诊治格局的「诊疗现状」与「临床问题」两个知识产物。

内容原则：
- 指南立场只引用本地 guideline-divergence.json 已回验语料（gNN 短名）；
- 文献引文不手写标题/期刊，统一按 PMID 从 literature-full.json 反查，查不到即报错（fail closed）；
- 每条陈述带角标引用，中文指南与指南类文献不生成链接，英文 PMID 文献生成 PubMed 链接。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "literature-full.json"
DIVERGENCE_PATH = ROOT / "data" / "guideline-divergence.json"
OUT_CHAPTERS = ROOT / "data" / "treatmentChapters.js"
OUT_QUESTIONS = ROOT / "data" / "clinicalQuestions.js"

full = json.loads(FULL_PATH.read_text())
articles = full if isinstance(full, list) else full.get("items") or full.get("articles") or []
BY_PMID = {str(a.get("pmid")): a for a in articles}
divergence = json.loads(DIVERGENCE_PATH.read_text())
GUIDELINES = {c["key"]: c for c in divergence["corpus"]}


def A(pmid: str) -> dict:
    """文献引用：按 PMID 反查本地库，查不到直接报错。"""
    article = BY_PMID.get(str(pmid))
    if not article:
        raise SystemExit(f"PMID {pmid} 不在本地文献库，禁止虚构引用")
    return {"kind": "article", "pmid": str(pmid)}


def G(key: str) -> dict:
    if key not in GUIDELINES:
        raise SystemExit(f"指南代号 {key} 不在语料库")
    return {"kind": "guideline", "key": key}


def build_refs(items: list[dict], used_keys: list[str]) -> list[dict]:
    refs = []
    for idx, item in enumerate(items, start=1):
        if item["kind"] == "guideline":
            g = GUIDELINES[item["key"]]
            refs.append({
                "n": idx,
                "kind": "guideline",
                "text": f"{g['short_name']}（{g['year']}）",
                "lang": "zh" if g["region"] in ("china", "taiwan") else "en",
            })
        else:
            a = BY_PMID[item["pmid"]]
            year = str(a.get("pub_date") or a.get("entry_date") or "")[:4]
            refs.append({
                "n": idx,
                "kind": "article",
                "pmid": item["pmid"],
                "text": f"{a.get('title', '')}. {a.get('journal', '')}. {year}.",
                "url": a.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{item['pmid']}/",
                "lang": "en",
            })
    return refs


def collect_keys(statements: list[dict], branches: list[dict]) -> list[str]:
    keys = []
    for st in statements:
        for r in st.get("refs", []):
            keys.append(r["pmid"] if r["kind"] == "article" else r["key"])
    for br in branches:
        for side in br["sides"]:
            for r in side.get("refs", []):
                keys.append(r["pmid"] if r["kind"] == "article" else r["key"])
    seen = []
    for k in keys:
        if k not in seen:
            seen.append(k)
    return seen


def finalize(body: dict) -> dict:
    """把 statements/branches 里的引用键收集为带编号的参考文献表。"""
    statements = body.get("statements", [])
    branches = body.get("branches", [])
    keys = collect_keys(statements, branches)
    items = []
    for k in keys:
        items.append(G(k) if k in GUIDELINES else A(k))
    ref_map = {}
    refs = build_refs(items, keys)
    for item, ref in zip(items, refs):
        key = item["pmid"] if item["kind"] == "article" else item["key"]
        ref_map[key] = ref["n"]
    body["refs"] = refs
    body["ref_map"] = ref_map
    return body


CHAPTERS = [
    {
        "id": "goals",
        "title": "治疗目标与达标定义",
        "summary": "MSE/MMS 已成中外共同底线，分歧集中在激素剂量阈值与是否追求停药缓解。",
        "statements": [
            {"text": "中国 2025 MG 指南把最小症状表达（MSE）设为治疗目标，即 MG-ADL 0 或 1 分，同时限定药物不良反应不超过 CTCAE 1 级；部分中国文件另把泼尼松 5~10 mg/d 写进达标条件。", "refs": [G("g23"), G("g33")]},
            {"text": "国际文件采用同一目标框架，但激素阈值更严：日本 2022、英国 2025 与国际 2026 管理目标共识都以泼尼松龙 ≤5 mg/d 作为达标条件。", "refs": [G("g09"), G("g27"), G("g28")]},
            {"text": "部分国际指南进一步把完全稳定缓解（CSR，停药缓解）列为理想目标；MGFA 2016 附录则只要求 MMS 或更好且副作用 ≤CTCAE 1 级，未设激素剂量阈值。", "refs": [G("g21"), G("g24"), G("g02")]},
        ],
        "branches": [
            {
                "topic": "达标时的激素剂量上限",
                "sides": [
                    {"label": "中国", "text": "2025 MG 指南允许泼尼松 5~10 mg/d 仍算达标；2026 临床治疗研究共识收紧到 ≤5 mg/d。", "refs": [G("g23"), G("g33")]},
                    {"label": "国际", "text": "日本、英国与国际 2026 共识统一按 ≤5 mg/d 执行；MGFA 2016 不设剂量阈值。", "refs": [G("g09"), G("g27"), G("g28"), G("g02")]},
                ],
            },
            {
                "topic": "是否把停药缓解列为目标",
                "sides": [
                    {"label": "中国", "text": "以 MMS/MSE 或更好加不良反应 ≤1 级为达标，未把停药缓解列为首要目标。", "refs": [G("g16"), G("g23")]},
                    {"label": "国际", "text": "比利时 2024 把 CSR 列为理想目标并允许稳定 2 年后减停；以色列 2025 把停药缓解、药物缓解或 MMS 并列为首选目标。", "refs": [G("g21"), G("g24")]},
                ],
            },
        ],
    },
    {
        "id": "steroid",
        "title": "糖皮质激素方案与减量",
        "summary": "减量节奏国际更慢、目标更低；真实世界的“靶向药助减激素”仍是观察性证据。",
        "statements": [
            {"text": "中国 2025 MG 指南建议每 2 周减 5 mg 或 0.1 mg/kg，减至 5~10 mg/d 维持或减停；眼肌型共识另给出隔日维持的递减方案。", "refs": [G("g23"), G("g22")]},
            {"text": "英国 2025 的阶梯更慢：每 2~4 周减 5 mg 至 20 mg，再减 2~2.5 mg 至 10 mg，之后每月减 1 mg，目标 5 mg/d；激素需求 ≥7 mg/d 即提示加用非激素免疫抑制。", "refs": [G("g27")]},
            {"text": "国际 2026 管理目标共识要求把激素减至 ≤10 mg/d、理想 ≤5 mg/d，必要时换药并密切监测恶化；以色列 2025 把最佳维持量定在 5~7.5 mg/d。", "refs": [G("g28"), G("g24")]},
            {"text": "真实世界队列观察到靶向治疗伴随激素减量，但多为单臂、小样本、短随访；激素相关并发症与减量的关系仍在积累证据。", "refs": [A("42127467"), A("42420579")]},
        ],
        "branches": [
            {
                "topic": "减量速度与维持量",
                "sides": [
                    {"label": "中国", "text": "每 2 周减 5 mg 或 0.1 mg/kg，维持区间 5~10 mg/d；眼肌型可按每 2~4 周减 5~10 mg 的递减方案。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "英国按月阶梯减量，目标 5 mg/d；国际 2026 理想 ≤5 mg/d；以色列最佳 5~7.5 mg/d。", "refs": [G("g27"), G("g28"), G("g24")]},
                ],
            },
        ],
    },
    {
        "id": "targeted",
        "title": "靶向生物制剂定位（FcRn 与补体抑制剂）",
        "summary": "两类靶向药均已进入中外指南，但中国线位靠前、国际强调传统治疗失败后再用。",
        "statements": [
            {"text": "中国 2026 抗体药物药学共识对艾加莫德用于 AChR 抗体阳性成人全身型 MG 给出 1a 强推荐；中国 2026 补体抑制剂建议把终末补体 C5 列为核心干预策略。", "refs": [G("g31"), G("g32")]},
            {"text": "中国部分共识把 FcRn 拮抗剂或补体抑制剂用于高活动性患者的一线治疗，但明确注明这一做法尚未获得国际共识。", "refs": [G("g33")]},
            {"text": "国际 2026 管理目标共识要求常规治疗 6~12 个月未控制症状才启动靶向治疗；以色列 2025 把艾加莫德和 nipocalimab 列为五线选择。", "refs": [G("g28"), G("g24")]},
            {"text": "支撑各品种进入指南的关键随机证据包括：艾加莫德 ADAPT、rozanolixizumab MycarinG、zilucoplan RAISE、ravulizumab CHAMPION、依库珠单抗 REGAIN、nipocalimab Vivacity-MG3。", "refs": [A("34146511"), A("37059507"), A("37059508"), A("38319212"), A("29066163"), A("39862879")]},
        ],
        "branches": [
            {
                "topic": "靶向药的治疗线位",
                "sides": [
                    {"label": "中国", "text": "艾加莫德用于 AChR 阳性成人 gMG 联合治疗为强推荐；危象前/危象等急性加重在感染控制后可用；部分共识提及高活动性可作一线。", "refs": [G("g31"), G("g16"), G("g33")]},
                    {"label": "国际", "text": "北欧、比利时等多定位为传统免疫抑制无效后的二线或替代；以色列列为五线；2026 国际共识设 6~12 个月传统治疗未达标的前置条件。", "refs": [G("g20"), G("g21"), G("g24"), G("g28")]},
                ],
            },
            {
                "topic": "补体抑制剂的适用指征",
                "sides": [
                    {"label": "中国", "text": "依库珠单抗用于 AChR 阳性难治性 gMG，900 mg 每周 ×4 周后 1200 mg 每 2 周；用药前需脑膜炎球菌疫苗接种。", "refs": [G("g16")]},
                    {"label": "国际", "text": "日本限定 IVIg 或血浆置换无法控制时使用；多国要求在其他免疫治疗未达标后再考虑，并强调疫苗或预防性抗生素。", "refs": [G("g09"), G("g27")]},
                ],
            },
        ],
    },
    {
        "id": "rescue",
        "title": "抢救治疗：IVIG、血浆置换与免疫吸附",
        "summary": "IVIG/PLEX 的抢救地位未被靶向药取代；MuSK 人群与剂量分层是主要分歧点。",
        "statements": [
            {"text": "中国 2022 IVIG 指南把 IVIG 列为 MG 危象和中重度全身型加重期的有效短期治疗，疗效与血浆置换相当，总量 2 g/kg、2~5 天用完（ⅠA 级）。", "refs": [G("g12")]},
            {"text": "MuSK 抗体阳性难治性 gMG：中国 2024 共识明确加重期选用血浆置换或 LPE、不推荐 IVIG；MGFA 2016 附录记载 MuSK-MG 对 PLEX 反应迅速良好、IVIG 应答率仅 11%~46%。", "refs": [G("g16"), G("g02")]},
            {"text": "双重滤过血浆置换与艾加莫德的前瞻对照研究提示抢救路径正在被重新评估，但尚不足以改写指南推荐。", "refs": [A("42764579")]},
        ],
        "branches": [
            {
                "topic": "MuSK 阳性患者能否用 IVIG",
                "sides": [
                    {"label": "中国", "text": "2024 难治性共识明确不推荐 IVIG，应选血浆置换/LPE；2022 IVIG 指南也注明 MuSK 阳性者疗效欠佳。", "refs": [G("g16"), G("g12")]},
                    {"label": "国际", "text": "MGFA 2016 以 PLEX 为优先但未完全否定 IVIG；日本 2022 仅推荐血浆置换，未把 IVIG 列为 MuSK 选项。", "refs": [G("g02"), G("g09")]},
                ],
            },
            {
                "topic": "IVIG 抢救剂量",
                "sides": [
                    {"label": "中国", "text": "多为固定足量：0.4 g·kg⁻¹·d⁻¹ ×5 天（总 2 g/kg）；围术期可用 3~5 天。", "refs": [G("g12"), G("g34")]},
                    {"label": "国际", "text": "英国按病情分层：显著球部症状但无需通气者 1 g/kg 分 2~3 天、5~7 天无反应可重复；濒临通气衰竭者 2 g/kg 分 5 天。", "refs": [G("g27"), G("g04")]},
                ],
            },
        ],
    },
    {
        "id": "thymectomy",
        "title": "胸腺切除与胸腺瘤处理",
        "summary": "MGTX 确立了非胸腺瘤 AChR 阳性 GMG 的手术获益，分歧集中在年龄上限与眼肌型适应证。",
        "statements": [
            {"text": "中国 2025 MG 指南建议非胸腺瘤 AChR 抗体阳性 GMG 在 18~65 岁早期手术，确诊 2 年内为宜、最晚不超过 5 年；<18 岁和 >65 岁结合病情与影像决定。", "refs": [G("g23")]},
            {"text": "国际推荐核心年龄更窄：英国、比利时等以 <50 岁为主，50~65 岁仅讨论或考虑，>65 岁一般不推荐。", "refs": [G("g27"), G("g21"), G("g20")]},
            {"text": "随机证据来自 MGTX：胸腺切除联合泼尼松优于单用泼尼松，长期随访显示获益可维持；中国另有外科治疗与围术期管理共识规范手术路径。", "refs": [A("27959594"), A("30692052"), G("g10"), G("g34")]},
        ],
        "branches": [
            {
                "topic": "手术年龄上限与眼肌型适应证",
                "sides": [
                    {"label": "中国", "text": "窗口放宽至 65 岁；眼肌型对胆碱酯酶抑制剂反应不足、无法耐受免疫抑制或难治性 AChR 阳性者也可考虑手术。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "以 <50 岁为推荐核心，50~65 岁仅个体化讨论；>65 岁一般不推荐。", "refs": [G("g27"), G("g21")]},
                ],
            },
        ],
    },
    {
        "id": "ocular",
        "title": "眼肌型 MG 的处理",
        "summary": "中国倾向早期联合免疫抑制，国际多为先对症、不足再阶梯加药。",
        "statements": [
            {"text": "中国 2025 MG 指南建议眼肌型首选胆碱酯酶抑制剂对症治疗，同时为快速持久达标联合免疫抑制（Ⅱb/B）；糖皮质激素为基础免疫治疗（Ⅰb/A），无效、不耐受或高转化风险者加非激素类免疫抑制剂。", "refs": [G("g23")]},
            {"text": "国际多为阶梯式：英国先用溴吡斯的明、不足再加泼尼松龙；以色列一线溴吡斯的明、二线激素±AZA/MMF/MTX；日本先胆碱酯酶抑制剂，必要时低剂量泼尼松龙。", "refs": [G("g27"), G("g24"), G("g09")]},
            {"text": "眼肌型向全身型转化的风险是早期干预的主要依据：英国 2025 引用约 50% 患者 2 年内、75% 患者 3 年内发展为全身型 MG。", "refs": [G("g27")]},
        ],
        "branches": [
            {
                "topic": "是否常规联合免疫抑制",
                "sides": [
                    {"label": "中国", "text": "在对症治疗同时即建议联合免疫抑制，偏向早期疾病修饰以降低全身化风险。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "先对症、疗效不足再加免疫抑制，强调阶梯式加药；低剂量激素常作为第二步。", "refs": [G("g27"), G("g24"), G("g09")]},
                ],
            },
        ],
    },
    {
        "id": "access",
        "title": "药物可及性与专科路径",
        "summary": "国际用专科中心、MDT 与报销标准限制新药使用，中国路径更宽、强调医保可承受。",
        "statements": [
            {"text": "中国 2024 FcRn 专家建议提出在医保能承受的范围内规律接受 FcRn 拮抗剂长期维持治疗，未设专科中心或 MDT 前置门槛。", "refs": [G("g18")]},
            {"text": "英国 2025 规定靶向药仅经专科门诊 MG MDT 讨论、早期可及项目或临床试验获得；比利时要求 NMRC 神经科医生处方且须符合报销标准。", "refs": [G("g27"), G("g21")]},
        ],
        "branches": [
            {
                "topic": "新药可及路径",
                "sides": [
                    {"label": "中国", "text": "强调医保可承受与长期维持，未设专科前置门槛；需同时关注超适应证使用与长期费用。", "refs": [G("g18"), G("g16")]},
                    {"label": "国际", "text": "以专科中心、MDT 与报销标准控制使用；以色列将靶向药限为五线且限明确难治者。", "refs": [G("g27"), G("g21"), G("g24")]},
                ],
            },
        ],
    },
]


QUESTION_GROUPS = [
    {
        "id": "fcrn",
        "title": "FcRn 治疗",
        "questions": [
            {
                "id": "q-fcrn-compare",
                "question": "不同 FcRn 拮抗剂之间如何选药？能否直接比较疗效？",
                "stance": "可谨慎回答",
                "whyOpen": "没有头对头随机试验，各注册研究入组人群、给药方案与背景治疗不同。",
                "answer": [
                    {"text": "ADAPT、MycarinG、Vivacity-MG3 均为安慰剂对照设计，不能据此比较品种间优劣。", "refs": [A("34146511"), A("37059507"), A("39862879")]},
                    {"text": "已有间接比较研究，但其结论依赖调整假设，不能替代头对头证据。", "refs": [A("41817915")]},
                    {"text": "现阶段选择更多落在给药途径、周期安排、可及性与患者偏好；指南按类别推荐，未按品种排次序。", "refs": [G("g28"), G("g31")]},
                ],
                "keywords": ["efgartigimod", "rozanolixizumab", "nipocalimab", "fcrn", "indirect comparison"],
            },
            {
                "id": "q-fcrn-predict",
                "question": "哪些患者更可能从 FcRn 治疗获益？有没有可靠的疗效预测指标？",
                "stance": "可谨慎回答",
                "whyOpen": "目前没有被前瞻验证的预测标志物，亚组与事后分析均属探索性。",
                "answer": [
                    {"text": "batoclimab III 期事后分析提示血清 IgG 快速下降与短期临床改善相关，可作为药效学参考，但不能用作选药或停药门槛。", "refs": [A("42867600")]},
                    {"text": "ADAPT 亚组分析显示不同诊断时长、既往治疗背景的患者均可应答，支持较广人群使用，但均属事后探索。", "refs": [A("42234197")]},
                    {"text": "AChR 抗体亚型与应答的关联仍停留在机制研究层面，尚无临床可用的分层标准。", "refs": [A("42242900")]},
                ],
                "keywords": ["fcrn", "efgartigimod", "response", "predictor", "igg", "subgroup"],
            },
            {
                "id": "q-fcrn-safety",
                "question": "FcRn 降低 IgG 会带来多少感染风险？疫苗和免疫球蛋白如何管理？",
                "stance": "可谨慎回答",
                "whyOpen": "长期低 IgG 状态下的感染谱与疫苗时机缺乏统一方案。",
                "answer": [
                    {"text": "ADAPT 及其开放扩展随访中总体耐受性良好，未出现新的安全信号；皮下剂型的长期扩展数据方向一致。", "refs": [A("34146511"), A("38318236"), A("42699831")]},
                    {"text": "nipocalimab 已有针对疫苗与病毒感染 IgG 应答的研究，提示需要关注免疫球蛋白管理，但个体化意义仍待评估。", "refs": [A("42084498")]},
                    {"text": "各指南把感染筛查、活动性感染控制后用药作为前提；具体疫苗接种时机尚无一致推荐。", "refs": [G("g31"), G("g16")]},
                ],
                "keywords": ["fcrn", "infection", "igg", "vaccine", "immunoglobulin", "safety"],
            },
            {
                "id": "q-fcrn-schedule",
                "question": "周期性给药与持续给药哪种更好？复发后如何再治疗？",
                "stance": "证据不足",
                "whyOpen": "没有比较两种给药策略的随机试验，复治时机也无统一标准。",
                "answer": [
                    {"text": "ADAPT 采用按需周期给药，Vivacity-MG3 采用每周持续给药，两种方案各自有效，无法据此判断优劣。", "refs": [A("34146511"), A("39862879")]},
                    {"text": "真实世界已有非周期性给药探索，但样本小、属观察性，不能作为方案选择依据。", "refs": [A("42162585")]},
                    {"text": "开放扩展研究中重复周期治疗仍有获益描述；实际复治多以症状驱动，缺乏统一间隔标准。", "refs": [A("38318236")]},
                ],
                "keywords": ["fcrn", "cyclic", "weekly", "retreatment", "relapse", "schedule"],
            },
            {
                "id": "q-fcrn-special",
                "question": "FcRn 能用于 MuSK 阳性、血清阴性或危象患者吗？",
                "stance": "可谨慎回答",
                "whyOpen": "注册试验以 AChR 阳性 gMG 为主，特殊人群证据多为病例系列与个案。",
                "answer": [
                    {"text": "MuSK 阳性使用艾加莫德的诱导与维持治疗有个案系列报道，不能外推为该类人群的确证疗效。", "refs": [A("40144041")]},
                    {"text": "血清阴性 MG 的系统综述显示该组人群异质性大、治疗证据总体有限；三重血清阴性难治者使用 rozanolixizumab 仅见个案。", "refs": [A("42387811"), A("41211783")]},
                    {"text": "危象/危象前使用艾加莫德的报告逐渐增多（含皮下给药个案）；中国部分共识在感染控制后给出推荐，国际指南尚未形成一致意见。", "refs": [A("39735402"), A("38939234"), G("g16"), G("g31")]},
                ],
                "keywords": ["fcrn", "musk", "seronegative", "crisis", "efgartigimod"],
            },
        ],
    },
    {
        "id": "complement",
        "title": "补体抑制与抢救路径",
        "questions": [
            {
                "id": "q-complement-refractory",
                "question": "补体抑制剂无应答或耐药时怎么办？",
                "stance": "证据不足",
                "whyOpen": "缺少预测无应答的统一指标，换药与联合次序没有随机证据。",
                "answer": [
                    {"text": "需先确认诊断、依从性与罕见药理原因；已有 ravulizumab 无应答而 zilucoplan 有效的 C5 p.Arg885 变异个案，提示基因检测在特定情形有价值。", "refs": [A("41771246")]},
                    {"text": "REGAIN 中部分患者应答不足，目前尚无公认的应答预测流程。", "refs": [A("29066163")]},
                    {"text": "同类内换药或换靶点的次序主要参考个案与小系列，指南未给固定流程。", "refs": [A("34590717"), A("38572524")]},
                ],
                "keywords": ["complement", "eculizumab", "ravulizumab", "zilucoplan", "refractory", "c5"],
            },
            {
                "id": "q-rescue-role",
                "question": "靶向治疗时代，IVIG 和血浆置换的位置变了吗？",
                "stance": "可谨慎回答",
                "whyOpen": "新型靶向药进入抢救场景后，传统抢救治疗的排序需要重新评估。",
                "answer": [
                    {"text": "中外指南仍把 IVIG/PLEX 作为危象与中重度加重期的短期抢救基础，剂量与分层各有差异。", "refs": [G("g12"), G("g27"), G("g04")]},
                    {"text": "双重滤过血浆置换与艾加莫德的前瞻对照提示抢救路径正在被重新评估，但证据尚不足以改写指南。", "refs": [A("42764579")]},
                    {"text": "MuSK 阳性患者仍优先血浆置换，IVIG 在该人群应答率低。", "refs": [G("g16"), G("g02")]},
                ],
                "keywords": ["ivig", "plasmapheresis", "plex", "crisis", "rescue", "dfpp"],
            },
        ],
    },
    {
        "id": "special",
        "title": "特殊人群与长期管理",
        "questions": [
            {
                "id": "q-special-population",
                "question": "老年、妊娠、儿童患者能否使用新型靶向药？",
                "stance": "证据不足",
                "whyOpen": "这些人群基本被注册试验排除，证据来自药物警戒、开放标签与真实世界小系列。",
                "answer": [
                    {"text": "妊娠：ravulizumab 已有全球药物警戒分析，但样本与观察期有限，不能视为确定性安全结论；FcRn 类妊娠数据更少。", "refs": [A("42853533")]},
                    {"text": "儿童/青少年：依库珠单抗有开放标签 III 期数据；其他品种多为回顾性资料与个案。", "refs": [A("38810600"), A("42749614")]},
                    {"text": "老年：晚发 MG 的系统综述提示严重程度与长期结局异质性大；补体类在老年难治患者中的快速应答仅见单中心队列。", "refs": [A("42842206"), A("42646495")]},
                ],
                "keywords": ["elderly", "pregnancy", "juvenile", "pediatric", "adolescent", "older"],
            },
            {
                "id": "q-steroid-sparing",
                "question": "靶向治疗能真正减停激素吗？目标应该怎么定？",
                "stance": "可谨慎回答",
                "whyOpen": "激素节约效应多来自单臂真实世界观察，缺乏对照；达标定义中外不完全一致。",
                "answer": [
                    {"text": "真实世界队列观察到艾加莫德治疗伴随激素减量，但多为单臂、小样本、短随访，不能据此确证激素节约效应。", "refs": [A("42127467")]},
                    {"text": "中国 35 例队列中 4 周诱导后日均泼尼松平均减少 8 mg，属于短期观察，共病亚组结论为探索性。", "refs": [A("42903245")]},
                    {"text": "指南目标较一致地指向 MSE/MMS 加泼尼松 ≤5 mg/d（部分中国文件 5~10 mg/d）；是否以停药缓解为目标，中外仍有分歧。", "refs": [G("g23"), G("g28"), G("g24")]},
                ],
                "keywords": ["steroid", "prednisone", "tapering", "steroid-sparing", "mse", "mms"],
            },
        ],
    },
    {
        "id": "seronegative",
        "title": "分型与诊断",
        "questions": [
            {
                "id": "q-seronegative",
                "question": "血清阴性 MG 如何诊断与治疗？",
                "stance": "可谨慎回答",
                "whyOpen": "血清阴性人群异质性大，指南未给出独立的靶向治疗路径。",
                "answer": [
                    {"text": "血清阴性不等于排除 MG：需结合重复抗体检测、电生理与临床特征，并鉴别其他神经肌肉病；2026 年系统综述对此有专门梳理。", "refs": [A("42387811"), A("42104987")]},
                    {"text": "治疗证据多来自小样本；三重血清阴性难治性 gMG 使用 rozanolixizumab 抢救成功仅见个案报道。", "refs": [A("41211783")]},
                    {"text": "现阶段按表型与既往治疗反应个体化处理，靶向药选择不能简单套用 AChR 阳性人群证据。", "refs": [G("g23"), G("g28")]},
                ],
                "keywords": ["seronegative", "double-seronegative", "triple-seronegative", "diagnosis", "antibody"],
            },
        ],
    },
]


def build():
    chapters = [finalize(dict(ch)) for ch in CHAPTERS]
    groups = []
    for group in QUESTION_GROUPS:
        questions = []
        for q in group["questions"]:
            body = dict(q)
            body["statements"] = body.pop("answer")
            body["branches"] = []
            finalize(body)
            body["answer"] = body.pop("statements")
            body.pop("branches", None)
            questions.append(body)
        groups.append({"id": group["id"], "title": group["title"], "questions": questions})

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from common.io import atomic_write_js_global
    atomic_write_js_global(OUT_CHAPTERS, "MG_TREATMENT_CHAPTERS", {
        "generated_at": stamp,
        "version": "2026-10-27-v1",
        "basis": "34 份中外指南/共识（已回验立场卡）+ 本地 PubMed 证据库；引文按 PMID 反查生成",
        "update_rule": "周更后仅高等级证据（I/II 级或新指南原文）且经人工确认才写入正文；候选证据先入待确认队列",
        "chapters": chapters,
    }, header="/* 诊疗现状章节：由 scripts/build-landscape-knowledge.py 生成，请勿手动编辑 */\n")
    atomic_write_js_global(OUT_QUESTIONS, "MG_CLINICAL_QUESTIONS", {
        "generated_at": stamp,
        "version": "2026-10-27-v1",
        "basis": "基于指南语料、PubMed 摘要证据与未解决问题梳理；问题与答案均可滚动修订",
        "update_rule": "问题可新增/退役；证据更新需高等级且经人工确认；候选证据入待确认队列",
        "groups": groups,
    }, header="/* 临床问题库：由 scripts/build-landscape-knowledge.py 生成，请勿手动编辑 */\n")
    print(f"chapters={len(chapters)} question_groups={len(groups)}")
    print("OK")


if __name__ == "__main__":
    build()
