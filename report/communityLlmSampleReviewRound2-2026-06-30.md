# MA-MG-HUB 社区语义层 LLM 抽样 Review Round 2

生成时间：2026-06-30

## 1. Review 目的

本轮 review 在 `2026.06-v4c-llm-reviewed` 规则之后执行，目标不是重复第一轮已修复样本，而是检查 v4c 后剩余 P1 风险：

1. FcRn / complement “疑似漏归类”是否是真漏分，还是合理 secondary。
2. `competitiveLandscapeIndirectComparison` 是否仍被普通 comparison / versus / controlled study 误触发。
3. 低置信度文献中，哪些应保留为低置信度，哪些应进入 `unassigned` / review queue。

本轮仍只使用本地 `data/literature-full.json` 的 title、abstract、metadata 和当前 `data/communityAssignments.jsonl`。未联网检索，未读取全文。

## 2. 抽样设计

| 样本桶 | 数量 | 抽样逻辑 |
| --- | ---: | --- |
| FcRn 疑似漏归类 | 12 | 有 FcRn 产品/术语信号但 primary 不是 FcRn，排除第一轮样本 |
| 补体疑似漏归类 | 8 | 有 complement 产品/术语信号但 primary 不是 complement，排除第一轮样本和重复项 |
| competitive v4c 回归 | 17 | v4c 后仍为 competitive primary 的近期样本，排除第一轮样本 |
| 低置信度 diagnosis / clinical | 12 | `diagnosisMonitoringPrediction` / `clinicalSubtypesStratification` 的 low confidence 近期样本 |
| 低置信度 mechanism / efficacy | 8 | `mechanismTranslationalMedicine` / `efficacyBurdenOutcomes` 的 low confidence 近期样本 |
| 合计 | 57 | 全部为第二轮新增样本 |

## 3. 总体结论

| 判断 | 数量 | 说明 |
| --- | ---: | --- |
| 当前 primary 可保留 | 13 | 多数是 HEOR/RWE 合理保护，或 MG-specific 机制文献 |
| 建议修改 primary | 31 | 主要集中在 competitive 误收、产品安全性/RWE/终点边界 |
| 建议 unassigned / review queue | 13 | MG 只是背景、鉴别诊断、并列疾病或 correction/comment |

关键结论：

1. **FcRn / complement 泄漏计数不能直接视为错误。** 例如 HEOR、cost-effectiveness、claims/RWE、direct active comparison、health economic systematic review 保留非产品 primary 是合理的。
2. **competitive 仍是 v4c 后最大问题。** 这轮 17 个 competitive 样本中，只有 2-3 个适合保留 competitive primary；其余多为单药疗效、安全性、诊断比较、亚型比较、方法学应用、健康对照或非 MG 核心人群。
3. **低置信度样本里确实有大量应进入 unassigned 的文献。** 尤其是 botulism、pulmonary embolism、broad neuromuscular disease review、非 MG 主病 case report、全神经病学/全自身免疫病种研究。
4. **安全性社区需要继续增强。** steroid toxicity、pregnancy/postpartum exacerbation、vaccine rare AE、thrombosis、infection under immunosuppression、post-thymectomy complication、drug-induced MG exacerbation 等应优先进入 `safetyMedicationManagement`，而不是 competitive / efficacy / clinical。

## 4. FcRn / Complement 泄漏样本判断

| PMID | 当前 primary | LLM 建议 | 判断 |
| --- | --- | --- | --- |
| 42322065 | guidelineHeorAccess | 改为 `competitiveLandscapeIndirectComparison` | efgartigimod vs lymphoplasmapheresis，兼有效性/安全性/成本，比较语义强于单纯 HEOR |
| 41837820 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | DFPP vs efgartigimod，直接治疗比较 |
| 41817916 | guidelineHeorAccess | 保留 `guidelineHeorAccess`，但低优先级 | correction to MCDA/value contribution，无需产品 primary |
| 41520205 | guidelineHeorAccess | 保留 `guidelineHeorAccess` | MG health economic systematic review |
| 41422493 | guidelineHeorAccess | 保留 `guidelineHeorAccess` | weight-based therapy cost / payer input，产品只是成本场景 |
| 41389129 | rweClinicalPathway | 保留 `rweClinicalPathway` | claims / observational study of OCS/NSIST use across targeted biologics |
| 41149784 | safetyMedicationManagement | 改为 `efficacyBurdenOutcomes` 或 crisis management 子类 | myasthenic crisis management narrative review，安全性不是主语义 |
| 41139802 | guidelineHeorAccess | 保留 `guidelineHeorAccess` | efgartigimod vs chronic immunoglobulin cost-effectiveness |
| 41132654 | complementAndNovelTargets | 改为 `safetyMedicationManagement` | FAERS safety profile of complement C5 and FcRn inhibitors，安全性主语义最强 |
| 40849050 | guidelineHeorAccess | 改为 `fcrnTargetedTherapy` | efgartigimod vs standard of care in new-onset gMG，临床产品证据，不是 HEOR |
| 40845416 | rweClinicalPathway | 可保留 `rweClinicalPathway`，FcRn secondary | claims / clinical practice steroid reduction after efgartigimod，RWE 保护可接受 |
| 40293925 | complementAndNovelTargets | 改为 `competitiveLandscapeIndirectComparison` | ravulizumab vs efgartigimod patient-experience modeling，直接跨机制比较 |
| 41505161 | fcrnTargetedTherapy | 改为 `mechanismTranslationalMedicine` 或 broad therapy review | broad novel therapy commentary，同时覆盖 FcRn 和 complement，不应由 FcRn 抢 primary |
| 41314023 | efficacyBurdenOutcomes | 改为 `complementAndNovelTargets` | Zilucoplan real-life study，补体产品主语义明确 |
| 41281548 | fcrnTargetedTherapy | 保留 `fcrnTargetedTherapy` | efgartigimod non-responder predictors，eculizumab 是后续背景 |
| 41101818 | fcrnTargetedTherapy | 改为 `efficacyBurdenOutcomes` / rescue management | rescue therapy review，不应由 FcRn 产品词抢 primary |
| 40949050 | rweClinicalPathway | 保留 `rweClinicalPathway` | clinical practice recommendation survey |
| 40631640 | fcrnTargetedTherapy | 改为 `diagnosisMonitoringPrediction` 或 clinical subtype | anti-CASPR2 syndrome unmasked in MG patient；“new treatments”不是 FcRn 产品证据 |
| 40299078 | fcrnTargetedTherapy | 转 review queue / unassigned | correction，无 abstract；不宜给中高置信产品 primary |
| 40014834 | guidelineHeorAccess | 保留 `guidelineHeorAccess`，但降低置信度 | new-to-market neurologic medication costs；MG 只是多个疾病之一 |

## 5. Competitive 回归样本判断

| PMID | 当前 primary | LLM 建议 | 判断 |
| --- | --- | --- | --- |
| 42268448 | competitiveLandscapeIndirectComparison | 改为 `safetyMedicationManagement` 或 review queue | SCIg vs IVIg thromboembolic safety，非 MG-specific competitive landscape |
| 42223343 | competitiveLandscapeIndirectComparison | 改为 `efficacyBurdenOutcomes` | tacrolimus monotherapy remission/relapse/safety，单药疗效证据 |
| 42142527 | competitiveLandscapeIndirectComparison | 改为 `safetyMedicationManagement` 或 unassigned | vaccine rare AE register study，MG 只是潜在 AE 列表之一 |
| 42127347 | competitiveLandscapeIndirectComparison | 改为 `safetyMedicationManagement` / `rweClinicalPathway` | pregnancy/postpartum exacerbation risk cohort |
| 42104835 | competitiveLandscapeIndirectComparison | 转 `unassigned` / methods review | adaptive trial design methodology using MG as application |
| 42101054 | competitiveLandscapeIndirectComparison | 改为 `safetyMedicationManagement` | steroid toxicity real-world study |
| 42048329 | competitiveLandscapeIndirectComparison | 改为 `clinicalSubtypesStratification` | ocular vs generalized MG subtype comparison，不是竞争格局 |
| 42039746 | competitiveLandscapeIndirectComparison | 改为 `mechanismTranslationalMedicine` | gut microbiota / immune homeostasis EAMG mechanism |
| 42018844 | competitiveLandscapeIndirectComparison | 改为 `safetyMedicationManagement` 或 low-confidence RWE | osteoporosis knowledge/health belief controlled study |
| 41998298 | competitiveLandscapeIndirectComparison | 改为 `diagnosisMonitoringPrediction` | live CBA antibody detection diagnostic yield |
| 41987131 | competitiveLandscapeIndirectComparison | 改为 `clinicalSubtypesStratification` | sleep disorders by antibody subtype |
| 41945880 | competitiveLandscapeIndirectComparison | 改为 `efficacyBurdenOutcomes` | amifampridine placebo-controlled trial，疗效/安全性 trial，不是竞争格局 |
| 41726319 | competitiveLandscapeIndirectComparison | 改为 `clinicalSubtypesStratification` | ofatumumab response in AChR vs MuSK subtypes |
| 41546732 | competitiveLandscapeIndirectComparison | 改为 `diagnosisMonitoringPrediction` | botulism vs MG RNS findings，诊断鉴别 |
| 41541106 | competitiveLandscapeIndirectComparison | 转 `unassigned` / review queue | acute neurological disease unit model，MG 非核心 |
| 41502595 | competitiveLandscapeIndirectComparison | 改为 `clinicalSubtypesStratification` / `rweClinicalPathway` | thymoma recurrence; MG not independent factor |
| 41290420 | competitiveLandscapeIndirectComparison | 改为 `complementAndNovelTargets` | inebilizumab as novel target therapy review |

## 6. 低置信度样本判断

| PMID | 当前 primary | LLM 建议 | 判断 |
| --- | --- | --- | --- |
| 42160148 | clinicalSubtypesStratification | 保留 low-confidence clinical / surgical pathway | thymectomy history/perioperative management，MG-specific 但偏历史综述 |
| 42156031 | diagnosisMonitoringPrediction | 转 `unassigned` | botulism in Japan，MG 只是 differential diagnosis |
| 42104030 | diagnosisMonitoringPrediction | 改为 `guidelineHeorAccess` 或 review queue | correction to MG recommendations，非诊断研究本体 |
| 42074613 | clinicalSubtypesStratification | 改为 `safetyMedicationManagement` | thrombosis risk in neuromuscular medicine includes MG and therapies |
| 42046139 | clinicalSubtypesStratification | 改为 `rweClinicalPathway` 或保留 clinical low | robotic thymectomy evidence/outcomes/surgical practice |
| 42028533 | clinicalSubtypesStratification | 转 `unassigned` | thymic cyst/thymolipoma without MG features |
| 41994709 | diagnosisMonitoringPrediction | 转 `unassigned` | pulmonary embolism case，MG 是背景病史 |
| 41959797 | clinicalSubtypesStratification | 改为 `safetyMedicationManagement` / mechanism secondary | COVID pneumonia risk in MG with type I IFN autoantibodies |
| 41903794 | diagnosisMonitoringPrediction | 转 review queue / possibly unassigned | broad neuromuscular respiratory assessment，MG 不是清晰主语义 |
| 41895003 | diagnosisMonitoringPrediction | 转 `unassigned` | umbrella review of psychiatric/neurological comorbidity，MG 只是可能病种之一 |
| 41883304 | diagnosisMonitoringPrediction | 转 review queue / unassigned | headache in MS/NMOSD/MOGAD/MG cohort，MG 非主问题 |
| 41874899 | clinicalSubtypesStratification | 改为 `safetyMedicationManagement` | delayed cardiac herniation after thymectomy，术后安全/并发症 |
| 42178262 | efficacyBurdenOutcomes | 改为 `safetyMedicationManagement` | biperiden-induced MG symptom exacerbation |
| 42121846 | mechanismTranslationalMedicine | 保留 low-confidence mechanism / review queue | broad skeletal muscle disease cell-death review，MG 不是唯一核心 |
| 42053006 | efficacyBurdenOutcomes | 转 `unassigned` | Lambert-Eaton syndrome during immunotherapy，非 MG |
| 42048741 | mechanismTranslationalMedicine | 保留 `mechanismTranslationalMedicine`，可提高 confidence | MG-specific ceRNA/AChR mechanistic study |
| 42015252 | efficacyBurdenOutcomes | 改为 `rweClinicalPathway` | nationwide hospitalization / crisis / ICU trend study |
| 41882752 | efficacyBurdenOutcomes | 改为 `safetyMedicationManagement` | tuberculosis in MG patient on prednisone，immunosuppression/infection safety |
| 41841320 | efficacyBurdenOutcomes | 转 `unassigned` / review queue | sexual health in neuromuscular diseases，MG 非清晰主语义 |
| 41838109 | efficacyBurdenOutcomes | 转 `unassigned` / review queue | PS-liposome preclinical method across autoimmune disease，MG 非清晰主语义 |

## 7. 下一轮规则修正建议

### P0.5：Competitive 再收窄

`competitiveLandscapeIndirectComparison` 不能再依赖普通 `comparison`、`comparative`、`versus`、`controlled study` 触发。建议增加三层门槛：

1. 保留条件：title 或 abstract 明确出现 drug / treatment strategy A vs B、NMA、ITC、head-to-head、cross-product evidence synthesis。
2. 排除条件：healthy controls、disease subtype comparison、diagnostic differential comparison、controlled study、risk cohort、methodology application、single drug trial。
3. 路由规则：diagnostic comparison -> `diagnosisMonitoringPrediction`；subtype comparison -> `clinicalSubtypesStratification`；safety risk cohort -> `safetyMedicationManagement`；single drug RCT -> `efficacyBurdenOutcomes`。

### P0.5：Safety override

安全性主语义需要压过 competitive / efficacy / clinical：

- steroid toxicity
- pregnancy / postpartum exacerbation risk
- vaccine rare adverse events
- thrombosis / VTE
- infection under immunosuppression
- post-thymectomy complication
- drug-induced MG exacerbation
- FAERS / pharmacovigilance

### P1：Unassigned 更积极

以下情况建议更积极进入 `unassigned` / review queue：

1. MG 只是 differential diagnosis。
2. MG 只是并列病种之一，title 不含 MG。
3. correction/comment 无 abstract 且没有明确主语义。
4. 非 MG 主病 case report 仅在病史中提到 MG。
5. broad neuromuscular / neurologic / autoimmune review 只把 MG 放在长列表中。

## 8. 对 Phase 4 的影响

第二轮 review 不推翻 v4c 的总体方向，但说明 **Phase 4 动态诊治格局前最好先做一轮 P0.5 competitive cleanup**。

如果现在直接进入 Phase 4，动态诊治格局可能会把一部分“疾病负担、安全风险、诊断研究、亚型研究”误读成竞争格局变化。建议先修 `competitiveLandscapeIndirectComparison` 和 safety override，再重跑数据产物和审计。

## 9. v4d 落地结果

2026-06-30 已将本轮 P0.5 cleanup 回写到 `scripts/buildCommunityData.py`，版本升级为 `2026.06-v4d-p05-cleanup`，方法标记为 `ruleBasedLlmReviewedP05Cleanup`。

本次回写覆盖：

1. `competitiveLandscapeIndirectComparison` 收窄为严格治疗策略、跨产品比较、NMA/ITC 或 evidence synthesis；普通 `versus` / `comparison` / `controlled study` 不再自动进入竞争格局。
2. `safetyMedicationManagement` 增强 steroid toxicity、pregnancy/postpartum risk、vaccine rare AE、thrombosis、infection under immunosuppression、post-thymectomy complication、drug-induced exacerbation、FAERS/pharmacovigilance 等 override。
3. MG 只是 differential diagnosis、并列病种、非 MG 主病 case history、方法学应用或无 abstract correction/comment 时，更积极进入 `unassigned` / review queue。

重跑后的核心指标：

| 指标 | v4c | v4d |
| --- | ---: | ---: |
| 已归类 | 8931 | 7890 |
| 未归类 | 1704 | 2745 |
| 低置信度 | 2433 | 1120 |
| 冲突归类 | 1995 | 1481 |
| 竞争格局与间接比较 | 453 | 51 |
| 安全性与用药管理 | 1132 | 1647 |
| 临床亚型与人群分层 | 2379 | 2055 |

解释：

- v4d 是质量优先版本，主动牺牲一部分覆盖率，把 MG 背景文献、长列表疾病综述和非核心方法学文章推入 `unassigned`。
- 这不是数据丢失，而是把“可用于格局判断的社区 primary”与“待审弱信号”分开。
- 固定回归集中，第一轮核心样本 38/38 命中，第二轮哨兵样本 18/18 命中。

Phase 4 可以基于 v4d 进入，但动态诊治格局生成时应忽略 unassigned 文献的自动结论，只把它们作为待审信号池。
