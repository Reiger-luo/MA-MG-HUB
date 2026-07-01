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


def test_case_report_maps_to_level_v():
    article = {
        "title": "A case of myasthenia gravis after immune checkpoint inhibition",
        "abstract": "We report a case of a 45-year-old woman with myasthenia gravis.",
        "pub_types": ["Case Reports"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Case Report"]
    assert level == "V"


def test_protocol_is_excluded_from_evidence_level():
    article = {
        "title": "Study protocol for a myasthenia gravis trial",
        "abstract": "This article describes the study protocol for a future trial.",
        "pub_types": ["Journal Article"],
    }

    study_types, level = classifyEvidence(article)

    assert study_types == ["Protocol"]
    assert level is None
