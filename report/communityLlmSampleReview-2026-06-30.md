# MA-MG-HUB 社区语义层 LLM 抽样 Review

生成时间：2026-06-30

## 1. Review 目的

本次 review 直接使用 LLM 对社区语义层进行抽样仲裁，目标不是立刻改生产规则，而是回答三个问题：

1. 当前 primary community 是否符合文献主语义？
2. 哪些误分来自 taxonomy 边界，哪些来自关键词优先级？
3. 下一轮规则优化应优先改哪里？

本次判断基于本地 `data/literature-full.json` 的 title、abstract、publication type、evidence level，以及当前 `data/communityAssignments.jsonl` 的 primary/secondary/confidence/flags。未重新联网查询 PubMed，未读取全文，因此结论仍是 abstract-level review。

## 2. 抽样设计

样本来自 `communitySemanticQualityAudit-2026-06-30.md` 提示的高风险边界，并按 PMID 去重：

| 样本来源 | 数量 | 目的 |
| --- | ---: | --- |
| FcRn 疑似漏归类 | 12 | 判断 FcRn 产品文献是否被疗效/RWE/补体社区抢走 |
| 补体疑似漏归类 | 12，其中 1 篇与 FcRn/竞争样本重叠 | 判断 eculizumab/ravulizumab/zilucoplan 文献是否被疗效/RWE/FcRn 抢走 |
| competitive 扩展后样本 | 12 | 判断 NMA/ITC 与普通 “versus/comparison” 是否混淆 |
| 低置信度样本 | 9 | 判断 low confidence 是合理保守，还是规则漏掉主语义 |
| 去重后合计 | 44 | 覆盖当前最需要人工校准的边界 |

## 3. 总体结论

| 判断 | 数量 | 说明 |
| --- | ---: | --- |
| primary 可保留 | 15 | 当前主社区基本正确，部分仅需调整 confidence 或 secondary |
| 建议修改 primary | 27 | 多数集中在 FcRn/补体产品主语义、competitive 误收、HEOR/RWE 边界 |
| 建议进入 unassigned/review queue | 2 | MG 只是背景、鉴别诊断或罕见病并列对象，强行归类价值低 |

关键结论：

1. `competitiveLandscapeIndirectComparison` 的扩展方向正确，但需要收窄为药物/治疗策略/卫生经济比较；外科术式比较、健康对照比较不应自动进入竞争格局。
2. FcRn 与补体产品文献的 primary 优先级仍偏弱。若题名/研究目的以 efgartigimod、rozanolixizumab、nipocalimab、eculizumab、ravulizumab、zilucoplan 为核心，应优先进入对应治疗机制社区，疗效/RWE/安全性作为 secondary。
3. 但 claims/HCRU、reimbursement、MCDA、value/access 文献不应被产品名抢走，应保留在 `rweClinicalPathway` 或 `guidelineHeorAccess`。
4. 宽泛综述只是列举 FcRn/补体产品时，不应进入产品社区 primary，应优先考虑 `mechanismTranslationalMedicine` 或后续新增的治疗综述/治疗演进类社区。
5. ICI 相关 Triple-M、免疫抑制感染/肿瘤风险等低置信度样本多数是真实的 `safetyMedicationManagement`，不应因非 MG 主病而全部排除，但需要区分“MG 患者安全问题”和“MG 仅为禁忌/背景”。

## 4. 抽样逐条判断

| PMID | 当前 primary | LLM 建议 | 判断 |
| --- | --- | --- | --- |
| 42360473 | efficacyBurdenOutcomes | 保留 `efficacyBurdenOutcomes`，FcRn secondary | HRQoL/fatigue 终点分析，nipocalimab 是干预背景但主问题是结局 |
| 42304705 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | 多种单抗 NMA，竞争比较语义明确 |
| 42254001 | efficacyBurdenOutcomes | 改为 `fcrnTargetedTherapy` | efgartigimod 真实世界产品证据，疗效/RWE 为 secondary |
| 42157574 | efficacyBurdenOutcomes | 改为 `fcrnTargetedTherapy` | nipocalimab Phase 3 疾病控制，产品主语义强 |
| 42096038 | efficacyBurdenOutcomes | 改为 `fcrnTargetedTherapy` | efgartigimod meta-analysis，疗效/安全性为 secondary |
| 42064058 | clinicalSubtypesStratification | 保留 `clinicalSubtypesStratification`，移除 FcRn secondary | thymoma + anti-AMPAR encephalitis case，FcRn 是误触发 |
| 42043767 | rweClinicalPathway | 保留 `rweClinicalPathway`，FcRn secondary | rozanolixizumab claims/HCRU，真实世界路径主语义高于产品机制 |
| 42030590 | complementAndNovelTargets | 保留 `complementAndNovelTargets`，FcRn secondary | C5 + FcRn 联合抑制，补体 primary 可接受 |
| 41928685 | complementAndNovelTargets | 改为 `mechanismTranslationalMedicine` | 宽泛治疗/免疫机制综述，不应由产品词抢占补体 primary |
| 41760990 | complementAndNovelTargets | 改为 `rweClinicalPathway` | early vs late add-on targeted therapy，真实世界治疗路径更强 |
| 41582064 | efficacyBurdenOutcomes | 改为 `fcrnTargetedTherapy` | efgartigimod response/predictors，产品主语义明确 |
| 41572778 | efficacyBurdenOutcomes | 改为 `fcrnTargetedTherapy` | very-late-onset gMG 中 efgartigimod 真实世界证据 |
| 42315783 | efficacyBurdenOutcomes | 改为 `complementAndNovelTargets` | ravulizumab case series，疲劳/QoL 是产品证据的一部分 |
| 42271114 | rweClinicalPathway | 改为 `complementAndNovelTargets` | eculizumab 多中心真实世界研究，补体产品主语义更强 |
| 42266700 | fcrnTargetedTherapy | 改为 `complementAndNovelTargets` | eculizumab rescue after poor efgartigimod response，干预主角是 eculizumab |
| 42168668 | fcrnTargetedTherapy | 保留 `fcrnTargetedTherapy` | efgartigimod 后 AChR antibody overshoot，安全性/亚型 secondary |
| 41979428 | fcrnTargetedTherapy | 改为 `guidelineHeorAccess` 或 `rweClinicalPathway` | new therapies eligibility/access/under-treatment，产品不是主问题 |
| 41925914 | fcrnTargetedTherapy | 改为 `competitiveLandscapeIndirectComparison` | complement inhibitors vs FcRn blockers meta-analysis，比较语义最强 |
| 41904994 | rweClinicalPathway | 改为 `complementAndNovelTargets` | zilucoplan real-world effectiveness/safety，补体产品主语义更强 |
| 41847264 | efficacyBurdenOutcomes | 改为 `complementAndNovelTargets` | eculizumab effectiveness/safety，结局是产品证据 |
| 41591648 | fcrnTargetedTherapy | 改为 `guidelineHeorAccess` | efgartigimod MCDA/value contribution，HEOR/access 主语义高于产品机制 |
| 41553721 | fcrnTargetedTherapy | 改为 `complementAndNovelTargets` | eculizumab fast-acting rescue，efgartigimod 是失败背景 |
| 41524776 | fcrnTargetedTherapy | 改为 `efficacyBurdenOutcomes` 或 `safetyMedicationManagement` | dysphagia management 综述，FcRn/补体只是治疗背景 |
| 40346603 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | novel biologics systematic review/NMA |
| 38642198 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | efgartigimod vs ravulizumab ITC |
| 17694386 | competitiveLandscapeIndirectComparison | 改为 `efficacyBurdenOutcomes` | PLEX dosing RCT，治疗方案疗效更强，非市场竞争格局 |
| 22361692 | competitiveLandscapeIndirectComparison | 改为 `guidelineHeorAccess` | IVIG vs PLEX acute hospital cost comparison，HEOR 主语义 |
| 20027081 | competitiveLandscapeIndirectComparison | 改为 `rweClinicalPathway` 或 `clinicalSubtypesStratification` | thymectomy surgical approach outcomes，不是药物/治疗格局竞争 |
| 24976996 | competitiveLandscapeIndirectComparison | 改为 `rweClinicalPathway` 或 thymoma clinical pathway | VATS vs open thymectomy，外科路径比较 |
| 29683813 | competitiveLandscapeIndirectComparison | 改为 `rweClinicalPathway` | thymectomy technique comparison，临床路径/手术实践语义更强 |
| 39551862 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | efgartigimod vs IVIG impending crisis，主动治疗比较 |
| 35246490 | competitiveLandscapeIndirectComparison | 保留 `competitiveLandscapeIndirectComparison` | eculizumab vs rituximab，治疗竞争语义明确 |
| 30692052 | competitiveLandscapeIndirectComparison | 改为 `efficacyBurdenOutcomes` | thymectomy + prednisone vs prednisone RCT extension，疗效终点主语义 |
| 28265257 | competitiveLandscapeIndirectComparison | 改为 `mechanismTranslationalMedicine` | MG vs healthy controls 的 Breg 机制研究，不是竞争格局 |
| 42102247 | competitiveLandscapeIndirectComparison | 改为 `rweClinicalPathway` 或 surgical pathway | RATS vs VATS narrative review，应从 competitive 排除 |
| 42338513 | safetyMedicationManagement | 保留 `safetyMedicationManagement`，可提高 confidence | ICI 相关 Triple-M adverse event，安全性主语义明确 |
| 42308878 | diagnosisMonitoringPrediction | 转 `unassigned` 或 review queue | menopause in rare diseases，MG 只是并列病种之一 |
| 42289707 | safetyMedicationManagement | 保留 low-confidence safety | MG 患者 steroid 背景下 cryptococcus infection，安全性相关但 MG 语义较弱 |
| 42281359 | diagnosisMonitoringPrediction | 转 `unassigned` 或 review queue | porphyria mimic MG，MG 主要是鉴别诊断阴性背景 |
| 42278719 | safetyMedicationManagement | 保留 `safetyMedicationManagement`，可提高 confidence | ICI Triple-M FAERS pharmacovigilance，安全性主语义强 |
| 42236345 | diagnosisMonitoringPrediction | 改为 `rweClinicalPathway`，guideline/access secondary | French neurologist management/treatment survey |
| 42233901 | safetyMedicationManagement | 保留 `safetyMedicationManagement`，可提高 confidence | ICI Triple-M case series，高死亡率安全信号 |
| 42202343 | safetyMedicationManagement | 保留 low-confidence safety 或 review | cosmetic botulinum toxin 中 MG 禁忌/风险，MG 语义边缘 |
| 42198688 | diagnosisMonitoringPrediction | 改为 `safetyMedicationManagement` | MMF 免疫抑制背景下 EBV+ CNS lymphoma，安全/用药管理更强 |

## 5. 下一轮规则修改队列

### P0：产品主语义优先级

1. FcRn 产品词命中 title 且研究类型为 clinical trial、real-world effectiveness、case series、meta-analysis/product effectiveness 时，提升 `fcrnTargetedTherapy` primary。
2. 补体产品词命中 title 且研究对象是 eculizumab/ravulizumab/zilucoplan effectiveness/safety/rescue 时，提升 `complementAndNovelTargets` primary。
3. 加入产品主角判断：`after poor response to efgartigimod` 这类标题中，若 intervention 是 eculizumab，应判补体 primary，而不是 FcRn primary。

### P0：HEOR/RWE 保护规则

1. 若 title/abstract 命中 claims、HCRU、resource utilization、cost、MCDA、value、reimbursement、access、eligibility、treatment program，应优先保护 `rweClinicalPathway` 或 `guidelineHeorAccess`。
2. 产品名可作为 secondary/facet，不自动覆盖 HEOR/RWE 主语义。

### P0：competitive 收窄规则

1. 保留 NMA、ITC、systematic review comparing biologics、active treatment A vs B。
2. 排除 `healthy controls`、`MG versus healthy controls`、biomarker case/control 的机制研究。
3. 排除胸腺手术入路比较、外科技术比较，转入 `rweClinicalPathway` / `clinicalSubtypesStratification`。
4. 成本比较进入 `guidelineHeorAccess`，不进入 competitive primary。

### P1：低置信度安全性细化

1. ICI-related myositis/myocarditis/MG overlap、Triple-M、FAERS pharmacovigilance 应提高 `safetyMedicationManagement` confidence。
2. MG 只是并列罕见病、禁忌、鉴别诊断阴性或背景病史时，允许进入 `unassigned` / review queue。

### P1：宽泛综述处理

1. Broad review 只列举 FcRn/补体/其他靶点时，不应被单个产品社区抢占。
2. 若后续 broad therapy evolution 文献持续增多，可考虑新增或拆分“治疗演进/治疗策略综述”子类；当前可暂归 `mechanismTranslationalMedicine` 或 `rweClinicalPathway`，并保留多 secondary。

## 6. 对当前 Phase 的影响

这份 LLM review 说明社区语义层 v4b 已能形成可用底座，但距离“动态诊治格局”的自动输入还差一轮规则修正：

1. 先处理 P0 规则，重跑 `buildCommunityData.py`、graph、wiki topic coverage、quality audit。
2. 再做一次小样本复核，确认 `competitive`、FcRn、补体、HEOR/RWE 的误分下降。
3. 指标稳定后，再进入 Phase 4 动态诊治格局，让 LLM 基于社区变化生成月度洞察。

因此，本报告建议：下一步不是继续增加前端展示，而是先把上述 P0 规则落实为 `scripts/buildCommunityData.py` 的可解释规则，并重建数据产物。

## 7. v4c 落实结果

2026-06-30 已将本报告的 P0 规则回写到 `scripts/buildCommunityData.py`，版本升级为 `2026.06-v4c-llm-reviewed`，方法标记为 `ruleBasedLlmReviewed`。

本次回写覆盖：

1. 产品主语义优先级：FcRn / complement 产品 title-level evidence 会优先进入对应治疗社区。
2. HEOR/RWE 保护：claims、HCRU、MCDA、value、access、eligibility、treatment program 不再被产品词自动抢走。
3. competitive 收窄：外科术式、健康对照、单纯 PLEX 剂量比较不再作为竞争格局 primary。
4. 安全性增强：ICI Triple-M、FAERS、mycophenolate、opportunistic infection 等用药风险信号可进入安全性社区。

重跑后的核心指标：

| 指标 | v4b | v4c |
| --- | ---: | ---: |
| 已归类 | 8847 | 8931 |
| 未归类 | 1788 | 1704 |
| 低置信度 | 2771 | 2433 |
| 冲突归类 | 2118 | 1995 |
| 临床亚型与人群分层 | 2584 | 2379 |
| 竞争格局与间接比较 | 631 | 453 |
| 安全性与用药管理 | 846 | 1132 |
| 真实世界证据与临床路径 | 671 | 945 |

固定抽样回归中，38 个明确期望 primary 的样本已全部命中。剩余没有设为硬期望的样本保留为人工 review / unassigned 策略讨论对象。
