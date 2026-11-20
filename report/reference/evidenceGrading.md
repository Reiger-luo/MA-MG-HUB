# Oxford CEBM 2011 证据等级规则参考

> 用途：为 MG Intelligence Hub 的自动证据等级脚本提供可追溯依据。该项目只能基于 PubMed title / abstract / PublicationType 做快速筛选，不能替代全文级人工 critical appraisal。

## 正规来源

以下来源于 2026-07-29 复核。Oxford CEBM 官方页面仍以 v2.1 为当前表格，并要求结合介绍文件和背景文件阅读。

1. OCEBM Levels of Evidence Working Group. **The Oxford 2011 Levels of Evidence**. Oxford Centre for Evidence-Based Medicine. [官方说明与下载页](https://www.cebm.ox.ac.uk/resources/levels-of-evidence/ocebm-levels-of-evidence)；[v2.1 表格 PDF](https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-2-1.pdf)

2. Howick J, Chalmers I, Glasziou P, Greenhalgh T, Heneghan C, Liberati A, Moschetti I, Phillips B, Thornton H. **The 2011 Oxford CEBM Levels of Evidence: Introductory Document**. Oxford Centre for Evidence-Based Medicine. [介绍文件 PDF](https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-introduction-2-1.pdf)

3. Howick J, Chalmers I, Glasziou P, Greenhalgh T, Heneghan C, Liberati A, Moschetti I, Phillips B, Thornton H. **Explanation of the 2011 Oxford Centre for Evidence-Based Medicine (OCEBM) Levels of Evidence: Background Document**. Oxford Centre for Evidence-Based Medicine. [背景文件 PDF](https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-background-document-2-1.pdf)

## CEBM 2011 使用原则

- CEBM 2011 是 **按临床问题域（question domain）** 使用的 1–5 级证据搜索启发式，不是所有文章统一套一条 study-design 梯子。
- 官方 introduction 明确说明：Levels **不是** 对证据质量的最终判断，也 **不提供推荐**；使用时需要 judgment and thought。
- 等级可因研究质量、精确性、间接性、不一致性、效应量等因素上调或下调。
- 自动脚本基于 title / abstract 无法稳定判断 blinding、consecutive sampling、reference standard、follow-up completeness、PICO directness 等质量条件，因此本项目输出应标注为 `CEBM 2011-informed screening label`。

## 官方表核心映射（v2.1）

| Question domain                 | Level 1                                                                                                                                       | Level 2                                                                                    | Level 3                                                                                                                                 | Level 4                                                         | Level 5                   |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------- |
| How common is the problem?      | Local and current random sample surveys / censuses                                                                                            | Systematic review of surveys matching local circumstances                                  | Local non-random sample                                                                                                                 | Case-series                                                     | n/a                       |
| Diagnosis / monitoring accuracy | Systematic review of cross-sectional studies with consistently applied reference standard and blinding                                        | Individual cross-sectional study with consistently applied reference standard and blinding | Non-consecutive study or inconsistent reference standard                                                                                | Case-control study or poor / non-independent reference standard | Mechanism-based reasoning |
| Prognosis                       | Systematic review of inception cohort studies                                                                                                 | Inception cohort study                                                                     | Cohort study or control arm of randomized trial                                                                                         | Case-series / case-control / poor-quality prognostic cohort     | n/a                       |
| Treatment benefits              | Systematic review of randomized trials or n-of-1 trials                                                                                       | Randomized trial or observational study with dramatic effect                               | Non-randomized controlled cohort / follow-up study                                                                                      | Case-series / case-control / historically controlled study      | Mechanism-based reasoning |
| Common harms                    | Systematic review of randomized trials / systematic review of nested case-control studies / n-of-1 / observational study with dramatic effect | Individual randomized trial or exceptional observational study with dramatic effect        | Non-randomized controlled cohort / follow-up study, including post-marketing surveillance with sufficient numbers and adequate duration | Case-series / case-control / historically controlled study      | Mechanism-based reasoning |
| Rare harms                      | Systematic review of randomized trials or n-of-1 trial                                                                                        | Randomized trial or exceptional observational study with dramatic effect                   | Non-randomized controlled cohort / follow-up study, including post-marketing surveillance with sufficient numbers and adequate duration | Case-series / case-control / historically controlled study      | Mechanism-based reasoning |
| Screening                       | Systematic review of randomized trials                                                                                                        | Randomized trial                                                                           | Non-randomized controlled cohort / follow-up study                                                                                      | Case-series / case-control / historically controlled study      | Mechanism-based reasoning |

## MG-HUB 自动脚本落地规则

### 明确采用（2026-11-20 按 OCEBM 官方表重构）

本项目**只采用 OCEBM 2011 v2.1 官方表实际存在的等级条目**；官方表没有的研究设计不赋予罗马数字，统一标为「无等级」（`evidence_level = null`），取消旧稿中"未分级/暂未分级"的说法。每一篇文章都经过分类器，因此不存在"尚未分级"状态。

- 输出 I / II / III / IV / V（仅官方表有对应条目者）或无等级（`null`）。
- 官方表内条目：治疗/伤害域 RCT=II、非随机对照队列=III、病例系列/病例对照/历史对照=IV；预后域 inception cohort=II、普通队列=III、低质量预后队列=IV；诊断域合格横断面（一致参考标准+盲法+前瞻/连续入组）=L2、非连续入组/参考标准不一致=L3、病例对照=IV；患病率域随机抽样调查/普查=L1、本地非随机抽样=L3；筛查域 RCT=L2；机制推理=L5。
- 横断面/调查按问题域归位，不整体沉无等级：有诊断词走诊断域（L2/L3/L4），有患病率/调查词走患病率域（L1/L3），两者皆无（如纯 DCE、患者偏好）才归无等级。回顾性队列即使出现 prevalence 词也不判患病率。
- 诊断准确性 L2 判定须摘要同时具备：盲法（double-blind/blinded/masked）+ 参考标准或敏感特异度线索 + 前瞻或连续入组；缺一保守 L3。此 L2 不是 RCT——诊断域 L2 不要求随机分组，SCREAM（PMID 37554174，前瞻多中心双盲、2272 例）即属此类。
- **无等级（原始临床研究，官方表无对应设计，但保留 study_type 且可进信号证据流）**：biomarker 结局关联（Biomarker Prognostic Study）、预测模型开发与外部验证（Prediction Model Development / External Validation）、GWAS/omics/遗传关联（Genetic/Omics Association）、量表验证（Scale Validation）、普通药物警戒（Pharmacovigilance：FAERS/disproportionality/spontaneous report）、无诊断/患病率线索的横断面与 DCE/患者偏好（Cross-Sectional）。这些设计官方表均无条目，不给罗马数字；信号强度按弱处理。有诊断或患病率线索的横断面已按域归 L1/L2/L3，不在无等级内。
- **无等级（非原始临床证据，不进证据流）**：narrative review、editorial、letter、comment、protocol、guideline/consensus、HEOR、animal、in vitro 等。
- Post-marketing surveillance 只有在呈现为 non-randomized controlled cohort / follow-up 且有足够样本量（≥100，识别 `n=123`、`123 patients`、`consisted of 123 patients`）或 large-scale / nationwide / registry 信号时，升为官方伤害域 Level III；`Post-marketing Controlled Follow-up` 保留 III，普通 FAERS 等归无等级。
- 信号准入门控 `scripts/studyClassifier.py::isSignalEligible`：有 I–V 等级，或属于上述 8 类无等级原始研究（`NO_LEVEL_ORIGINAL_TYPES`）；非原始证据不进。综述、评论、动物、体外等不进证据流，避免稀释信号。

### 信号纳入决策的证据上限（第二道门）

证据等级只回答“这篇研究在 CEBM 梯子上属于哪一级”，不直接决定它是否成为本周信号。文献进入 `signals-weekly.js` 之前，还要经过 `scripts/enrich-literature-narrative.py::apply_decision_evidence_ceiling` 这一道确定性闸门，在模型给出 include / background 判断后按研究设计二次收口。要点：

- **判定来源分级结果，不复读原文猜设计**：是否病例级系统综述只读 `studyTypes` 里的 `Systematic Review of Case Reports`，不再用“systematic review + case series”文本共现推断。综述/荟萃分析摘要里出现的 case series 指被纳入的研究，不是本文设计，不据此把综述降为病例级（否则会把明确合并了 RCT 的荟萃分析误判为非对照综述）。
- **“非对照系统综述”由 `studyClassifier.py` 判为 IV 级后即到此为止**：强度由 `normalize_signal_strength` 收口，闸门不再对同一篇做第二次证据上限惩罚。IV 级单臂真实世界研究在 score 达标时仍可成为“中”信号。
- **触发降级的规则**：病例级（`case_level`）、病例级系统综述（`case_based_review`）、V 级证据（`evidence_level_v`）、MG 亚组事件不足（`insufficient_mg_subgroup`）、无对照的单中心回顾性描述队列（`descriptive_single_center`）、体外或计算性探索（`laboratory_or_computational`）；动物证据与缺少有效风险集的死亡者比较直接 `exclude`。明确标注的安全性新信号可豁免上限。
- **降级必须可审计**：降级时覆写 `reason`，另写 `ceilingRule`（命中的规则名）、`preCeilingDecision`、`preCeilingValueScore`、`preCeilingReason`（模型原判断）四个字段，不允许把上限理由拼接在模型原句之后，避免产出“建议纳入…按上限降为背景”的自相矛盾记录。
- 闸门只决定信号层级归属，不改 `evidence_level`；强度与证据等级的封顶关系另见 `normalize_signal_strength`。

### 自动化局限

- 无全文时诊断研究的 consecutive sampling、blinding、reference standard 一致性只能靠摘要显式线索判定：三者齐全给官方 L2，缺任一保守 L3，病例对照 L4，量表验证因官方表无条目归无等级。SCREAM 类双盲多中心准确性研究据此由 III 升 II。
- 无全文时无法可靠判断预后 inception cohort 与 follow-up 质量；脚本只在明确 `inception cohort` 时给 II，其余按摘要信号保守映射到队列 III 或低质量队列 IV。
- 罗马数字只在各自问题域内可比：同为 III 的治疗域非随机对照队列与预后域普通队列，不代表证据强度相同或可互换。
- 输出只用于文献筛选与排序；医学结论、指南引用、材料定稿前必须核查原文。
