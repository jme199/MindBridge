import copy
import unittest

from workflows.evidence_validation import validate_research_evidence


# =========================================================
# Evidence Validation Unit Tests
# =========================================================

class TestEvidenceValidation(unittest.TestCase):

    def setUp(self):
        """
        Create synthetic research data for offline testing.
        These are fictional studies, not real publications.
        """

        self.pipeline_result = {
            "verification": {
                "verified_studies": [
                    {
                        "study_id": "S1",
                        "metadata_status": "verified",
                    },
                    {
                        "study_id": "S2",
                        "metadata_status": "unverified",
                    },
                ],
                "claim_assessments": [
                    {
                        "claim_id": "C1",
                        "support_status": "supported",
                    },
                    {
                        "claim_id": "C2",
                        "support_status": "insufficient_evidence",
                    },
                ],
            },
            "result": {
                "papers": [
                    {
                        "study_id": "S1",
                        "title": "Synthetic Study A",
                    },
                    {
                        "study_id": "S2",
                        "title": "Synthetic Study B",
                    },
                    {
                        "study_id": "S3",
                        "title": "Synthetic Study C",
                    },
                ]
            },
        }

    # -----------------------------------------------------
    # Test 1: Verified and Unverified Evidence
    # -----------------------------------------------------

    def test_verification_status(self):

        result = validate_research_evidence(
            self.pipeline_result
        )

        self.assertEqual(result["total_papers"], 3)

        self.assertEqual(result["agent_verified_papers"], 1)

        self.assertEqual(
            result["evidence_records"][0]["verification_status"],
            "agent_reported_verified",
        )

        self.assertEqual(
            result["evidence_records"][1]["verification_status"],
            "not_confirmed",
        )

    # -----------------------------------------------------
    # Test 2: Unmatched Study ID
    # -----------------------------------------------------

    def test_unmatched_study(self):

        result = validate_research_evidence(
            self.pipeline_result
        )

        # S3 is not present in Verification Agent records
        study_s3 = result["evidence_records"][2]

        self.assertEqual(
            study_s3["verification_status"],
            "not_confirmed",
        )

    # -----------------------------------------------------
    # Test 3: Missing Study ID
    # -----------------------------------------------------

    def test_missing_study_id(self):

        data = copy.deepcopy(self.pipeline_result)

        data["result"]["papers"].append({
            "title": "Study Without ID"
        })

        result = validate_research_evidence(data)

        last_paper = result["evidence_records"][-1]

        self.assertIsNone(last_paper["study_id"])

        self.assertEqual(
            last_paper["verification_status"],
            "not_confirmed",
        )

    # -----------------------------------------------------
    # Test 4: Claim Assessment Records
    # -----------------------------------------------------

    def test_claim_assessments(self):

        result = validate_research_evidence(
            self.pipeline_result
        )

        claims = result["claim_records"]

        self.assertEqual(len(claims), 2)

        self.assertEqual(
            claims[0]["support_status"],
            "supported",
        )

        self.assertEqual(
            claims[1]["support_status"],
            "insufficient_evidence",
        )

    # -----------------------------------------------------
    # Test 5: Empty Research Results
    # -----------------------------------------------------

    def test_empty_papers(self):

        data = copy.deepcopy(self.pipeline_result)

        data["result"]["papers"] = []

        result = validate_research_evidence(data)

        self.assertEqual(result["total_papers"], 0)

        self.assertEqual(
            result["agent_verified_papers"], 0
        )

        self.assertEqual(
            result["evidence_records"], []
        )

    # -----------------------------------------------------
    # Test 6: Invalid Evidence Structure
    # -----------------------------------------------------

    def test_invalid_evidence_structure(self):

        data = copy.deepcopy(self.pipeline_result)

        # A string is invalid because a list is expected
        data["verification"]["verified_studies"] = (
            "invalid data"
        )

        with self.assertRaises(ValueError):

            validate_research_evidence(data)


if __name__ == "__main__":
    unittest.main()