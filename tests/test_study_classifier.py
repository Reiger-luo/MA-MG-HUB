from scripts.studyClassifier import classifyEvidence, classifyStudyType


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


def test_genetic_omics_association_is_exploratory_level_iv():
    article = {
        "title": "Genome-wide association study in myasthenia gravis",
        "abstract": "A GWAS identified genetic association signals in patients with myasthenia gravis.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Genetic/Omics Association"]
    assert level == "IV"


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
