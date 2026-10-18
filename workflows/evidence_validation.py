# =========================================================
# MindBridge Evidence Validation
# =========================================================

def validate_research_evidence(pipeline_result):
    """
    Compare Explanation Agent references with
    Verification Agent records.

    This checks consistency between Agent outputs.
    It does NOT independently verify publications.
    """

    verification = pipeline_result.get("verification", {})
    explanation = pipeline_result.get("result", {})

    if not isinstance(verification, dict):
        raise ValueError("Invalid verification results.")

    if not isinstance(explanation, dict):
        raise ValueError("Invalid explanation results.")

    verified_studies = verification.get("verified_studies", [])
    claim_assessments = verification.get("claim_assessments", [])
    papers = explanation.get("papers", [])

    if not all(
        isinstance(items, list)
        for items in [verified_studies, claim_assessments, papers]
    ):
        raise ValueError("Invalid evidence data structure.")

    # -----------------------------------------------------
    # Build Verification Lookup
    # -----------------------------------------------------

    study_lookup = {}

    for study in verified_studies:

        if not isinstance(study, dict):
            continue

        study_id = study.get("study_id")

        if isinstance(study_id, str) and study_id.strip():
            study_lookup[study_id.strip()] = study

    # -----------------------------------------------------
    # Check Explanation Agent References
    # -----------------------------------------------------

    evidence_records = []

    for paper in papers:

        if not isinstance(paper, dict):
            continue

        study_id = paper.get("study_id")

        if not isinstance(study_id, str):
            study_id = None

        study_id = study_id.strip() if study_id else None

        matching_study = study_lookup.get(study_id)

        if matching_study is None:

            verification_status = "not_confirmed"

        else:

            reported_status = matching_study.get(
                "metadata_status",
                matching_study.get(
                    "verification_status",
                    "not_confirmed"
                )
            )

            if (
                isinstance(reported_status, str)
                and reported_status.strip().lower() == "verified"
            ):

                verification_status = "agent_reported_verified"

            else:

                verification_status = "not_confirmed"

        evidence_records.append({
            "study_id": study_id,
            "title": paper.get("title", "Untitled study"),
            "verification_status": verification_status,
        })

    # -----------------------------------------------------
    # Check Claim Assessments
    # -----------------------------------------------------

    claim_records = []

    for assessment in claim_assessments:

        if not isinstance(assessment, dict):
            continue

        claim_records.append({
            "claim_id": assessment.get("claim_id"),
            "support_status": assessment.get(
                "support_status", "not_reported"
            ),
        })

    # -----------------------------------------------------
    # Return Audit Summary
    # -----------------------------------------------------

    return {
        "total_papers": len(papers),
        "agent_verified_papers": sum(
            record["verification_status"]
            == "agent_reported_verified"
            for record in evidence_records
        ),
        "evidence_records": evidence_records,
        "claim_records": claim_records,
    }