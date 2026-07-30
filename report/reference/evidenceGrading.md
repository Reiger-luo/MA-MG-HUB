# Oxford CEBM 2011 证据等级规则参考

> 用途：为 MG Intelligence Hub 的自动证据等级脚本提供可追溯依据。该项目只能基于 PubMed title / abstract / PublicationType 做快速筛选，不能替代全文级人工 critical appraisal。

## 正规来源

1. OCEBM Levels of Evidence Working Group. **The Oxford 2011 Levels of Evidence**. Oxford Centre for Evidence-Based Medicine.  
   官方页面：https://www.cebm.ox.ac.uk/resources/levels-of-evidence/ocebm-levels-of-evidence  
   PDF：https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-2-1.pdf

2. Howick J, Chalmers I, Glasziou P, Greenhalgh T, Heneghan C, Liberati A, Moschetti I, Phillips B, Thornton H. **The 2011 Oxford CEBM Levels of Evidence: Introductory Document**. Oxford Centre for Evidence-Based Medicine.  
   PDF：https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-introduction-2-1.pdf

3. Howick J, Chalmers I, Glasziou P, Greenhalgh T, Heneghan C, Liberati A, Moschetti I, Phillips B, Thornton H. **Explanation of the 2011 Oxford Centre for Evidence-Based Medicine (OCEBM) Levels of Evidence: Background Document**. Oxford Centre for Evidence-Based Medicine.  
   PDF：https://www.cebm.ox.ac.uk/files/levels-of-evidence/cebm-levels-of-evidence-background-document-2-1.pdf

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

### 明确采用

- 输出 I / II / III / IV / V。
- Narrative review、editorial、letter、comment、protocol、guideline/consensus、HEOR、animal、in vitro 等不作为 CEBM 证据等级，保留 study_type 但 `evidence_level = null`。
- Case report / case series / case-control / historical control 归入 Level IV 低等级临床证据桶；不再归入 Level V。
- Level V 只保留给 mechanism-based reasoning。
- Post-marketing surveillance 只有在呈现为 non-randomized controlled cohort / follow-up 且有足够样本量或 large-scale / nationwide / registry 信号时，才升为 Level III；普通 FAERS / disproportionality / spontaneous report 仍为 Level IV 或非证据筛选项，视文本而定。
- GWAS / omics / genetic association / exploratory biomarker association 不自动等同 mechanism-based reasoning；默认归为 exploratory observational association（Level IV），只有明确机制推理文本才给 Level V。

### 自动化局限

- 无全文时无法可靠判断诊断研究的 consecutive sampling、blinding、reference standard 一致性；当前诊断准确性研究按保守 III 桶，诊断 case-control / scale validation 按 IV。
- 无全文时无法可靠判断预后 inception cohort 与 follow-up 质量；脚本只在明确 `inception cohort` 时给 II，其余按摘要信号保守映射。
- 输出只用于文献筛选与排序；医学结论、指南引用、材料定稿前必须核查原文。
