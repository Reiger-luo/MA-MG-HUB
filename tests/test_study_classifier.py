from scripts.studyClassifier import classifyEvidence, classifyStudyType, isSignalEligible


def test_randomized_trial_maps_to_level_ii():
    article = {
        "title": "Treatment response in generalized myasthenia gravis",
        "abstract": (
            "We conducted a randomized, double-blind, placebo-controlled trial "
            "in adults with generalized myasthenia gravis."
        ),
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["RCT"]
    assert level == "II"


def test_prior_trial_subgroup_is_not_promoted_to_rct():
    study_type = classifyStudyType(
        ["Journal Article"],
        (
            "This subgroup analysis of a previous randomized trial examined "
            "quality-of-life outcomes without new random allocation."
        ),
        "Subgroup analysis in myasthenia gravis",
    )

    assert study_type != "RCT"


def test_case_report_maps_to_level_iv():
    article = {
        "title": "A case of myasthenia gravis after immune checkpoint inhibition",
        "abstract": "We report a case of a 45-year-old woman with myasthenia gravis.",
        "pub_types": ["Case Reports"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Case Report"]
    assert level == "IV"


def test_case_series_maps_to_level_iv():
    article = {
        "title": "Case series of myasthenia gravis after immunotherapy",
        "abstract": "We describe a case series of five patients with myasthenia gravis.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Case Series"]
    assert level == "IV"


def test_narrative_review_is_ungraded():
    article = {
        "title": "Narrative review of myasthenia gravis management",
        "abstract": "This narrative review summarizes available treatments.",
        "pub_types": ["Review"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Review"]
    assert level is None


def test_mechanism_based_reasoning_maps_to_level_v():
    article = {
        "title": "Mechanism of complement activation in myasthenia gravis",
        "abstract": "This study discusses a mechanism-based pathway for disease pathogenesis.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Mechanism-based Reasoning"]
    assert level == "V"


def test_genetic_omics_association_has_no_official_level():
    article = {
        "title": "Genome-wide association study in myasthenia gravis",
        "abstract": "A GWAS identified genetic association signals in patients with myasthenia gravis.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Genetic/Omics Association"]
    assert level is None


def test_post_marketing_controlled_followup_maps_to_level_iii():
    article = {
        "title": "Post-marketing surveillance of a treatment in myasthenia gravis",
        "abstract": (
            "This post-marketing surveillance study followed 1,250 patients in a registry "
            "cohort to evaluate common adverse events over 24 months."
        ),
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Post-marketing Controlled Follow-up"]
    assert level == "III"


def test_protocol_is_excluded_from_evidence_level():
    article = {
        "title": "Study protocol for a myasthenia gravis trial",
        "abstract": "This article describes the study protocol for a future trial.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Protocol"]
    assert level is None


def test_no_level_original_study_is_signal_eligible():
    """下沉到无等级的原始研究仍可进信号，综述等非原始证据不可进。"""
    biomarker = {
        "pub_types": ["Journal Article"],
        "title": "Cytokine biomarkers associated with treatment response in MG",
        "abstract": "We analyzed biomarker association with clinical response in patients.",
    }
    review = {
        "pub_types": ["Review"],
        "title": "Narrative review of myasthenia gravis management",
        "abstract": "This narrative review summarizes available treatments.",
    }
    bio_types, bio_level = classifyEvidence(biomarker)
    review_types, review_level = classifyEvidence(review)

    assert bio_level is None
    assert isSignalEligible(dict(biomarker, study_types=bio_types, evidence_level=bio_level)) is True
    assert review_level is None
    assert isSignalEligible(dict(review, study_types=review_types, evidence_level=review_level)) is False


def test_blinded_diagnostic_accuracy_maps_to_level_ii():
    """OCEBM 诊断域官方 L2：一致参考标准+盲法+前瞻连续入组（SCREAM 类）。"""
    article = {
        "pub_types": ["Journal Article"],
        "title": "A multicentre, prospective, double-blind study comparing the accuracy of autoantibody diagnostic assays in myasthenia gravis",
        "abstract": (
            "In this prospective, multicentre study we recruited patients with suspected MG "
            "to evaluate the diagnostic accuracy of assays, with sensitivity and specificity "
            "against a reference standard under blinding."
        ),
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Diagnostic Accuracy Study (Blinded)"]
    assert level == "II"


def test_unblinded_diagnostic_accuracy_stays_level_iii():
    """缺盲法/参考标准的诊断准确性研究保守留官方 L3。"""
    article = {
        "pub_types": ["Journal Article"],
        "title": "Diagnostic accuracy of a scale in myasthenia gravis",
        "abstract": "We performed a cross-sectional study of sensitivity and specificity in 200 patients.",
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Diagnostic Accuracy Study"]
    assert level == "III"


def test_prevalence_surveys_map_to_official_levels():
    """OCEBM 患病率域：随机抽样=L1，本地非随机抽样=L3；不是 IV、也不是无等级。"""
    random_sample = {
        "pub_types": ["Journal Article"],
        "title": "Prevalence of myasthenia gravis",
        "abstract": "A population-based survey using a random sample of residents.",
    }
    nonrandom = {
        "pub_types": ["Journal Article"],
        "title": "Prevalence of MG in a clinic",
        "abstract": "A cross-sectional survey of patients attending our clinic.",
    }

    r_types, r_level = classifyEvidence(random_sample)
    n_types, n_level = classifyEvidence(nonrandom)

    assert r_types == ["Prevalence Survey (Random Sample)"]
    assert r_level == "I"
    assert n_types == ["Prevalence Survey"]
    assert n_level == "III"
