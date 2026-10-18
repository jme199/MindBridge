import json
import unittest
from unittest.mock import AsyncMock, patch

from workflows.research_pipeline import (
    extract_agent_json,
    run_research_pipeline,
)


# =========================================================
# 1. Synthetic Test Data
# =========================================================

RESEARCH_DATA = {
    "research_question": "What does research say about exam anxiety?",
    "studies": [
        {
            "study_id": "S1",
            "title": "Synthetic Test Study",
            "verification_status": "unverified",
        }
    ],
    "claims": [
        {
            "claim_id": "C1",
            "claim": "Synthetic test claim",
            "source_study_ids": ["S1"],
        }
    ],
}

VERIFICATION_DATA = {
    "research_question": RESEARCH_DATA["research_question"],
    "verified_studies": [
        {
            "study_id": "S1",
            "metadata_status": "unverified",
        }
    ],
    "claim_assessments": [
        {
            "claim_id": "C1",
            "support_status": "insufficient_evidence",
        }
    ],
}

EXPLANATION_DATA = {
    "status": "completed",
    "summary": "This is a synthetic test report.",
    "papers": [],
    "claims": [],
    "support": [],
}


# =========================================================
# 2. Simulate SciencePal Streaming Events
# =========================================================

def make_mock_events(data):
    """Create synthetic assistant streaming events."""

    text = json.dumps(data, ensure_ascii=False)

    midpoint = len(text) // 2
    chunks = [text[:midpoint], text[midpoint:]]

    events = []

    for chunk in chunks:
        message = {
            "role": "assistant",
            "metadata": {
                "stream_status": "chunk"
            },
            "content": chunk,
        }

        events.append({
            "type": "assistant",
            "content": json.dumps(
                message,
                ensure_ascii=False,
            ),
        })

    return events


def make_mock_run(role, data=None, status="completed"):
    """Simulate a completed or pending Agent run."""

    return {
        "role": role,
        "agent_id": f"mock-{role}-agent",
        "thread_id": f"mock-{role}-thread",
        "run_id": f"mock-{role}-run",
        "status": status,
        "error": None,
        "events": (
            make_mock_events(data)
            if data is not None
            else []
        ),
    }


# =========================================================
# 3. Offline Unit Tests
# =========================================================

class TestResearchPipeline(unittest.IsolatedAsyncioTestCase):

    def test_json_extraction(self):
        """Check whether streaming chunks form valid JSON."""

        events = make_mock_events(RESEARCH_DATA)

        result = extract_agent_json(events)

        self.assertEqual(result, RESEARCH_DATA)

    @patch(
        "workflows.research_pipeline.run_agent",
        new_callable=AsyncMock,
    )
    async def test_complete_pipeline(self, mock_run):
        """Check that all three Agents execute in order."""

        mock_run.side_effect = [
            make_mock_run("research", RESEARCH_DATA),
            make_mock_run("verification", VERIFICATION_DATA),
            make_mock_run("explanation", EXPLANATION_DATA),
        ]

        result = await run_research_pipeline(
            question="What does research say about exam anxiety?",
            api_key="offline-test-key",
        )

        self.assertEqual(result["status"], "completed")

        self.assertEqual(mock_run.await_count, 3)

        roles = [
            call.kwargs["role"]
            for call in mock_run.await_args_list
        ]

        self.assertEqual(
            roles,
            ["research", "verification", "explanation"],
        )

        self.assertEqual(
            result["result"]["summary"],
            "This is a synthetic test report.",
        )

    @patch(
        "workflows.research_pipeline.run_agent",
        new_callable=AsyncMock,
    )
    async def test_running_agent_stops_pipeline(self, mock_run):
        """Check that downstream Agents are not started."""

        mock_run.return_value = make_mock_run(
            role="research",
            status="running",
        )

        result = await run_research_pipeline(
            question="Test research question",
            api_key="offline-test-key",
        )

        self.assertEqual(
            result["status"],
            "pending_or_failed",
        )

        self.assertEqual(result["stage"], "research")

        self.assertEqual(mock_run.await_count, 1)

    @patch(
        "workflows.research_pipeline.run_agent",
        new_callable=AsyncMock,
    )
    async def test_missing_json(self, mock_run):
        """Check that missing JSON stops the workflow."""

        mock_run.return_value = make_mock_run(
            role="research",
            data=None,
            status="completed",
        )

        with self.assertRaises(ValueError):
            await run_research_pipeline(
                question="Test research question",
                api_key="offline-test-key",
            )

        self.assertEqual(mock_run.await_count, 1)

    @patch(
        "workflows.research_pipeline.run_agent",
        new_callable=AsyncMock,
    )
    async def test_no_evidence(self, mock_run):
        """Check that empty research results stop the workflow."""

        empty_data = {
            "research_question": "Test question",
            "studies": [],
            "claims": [],
        }

        mock_run.return_value = make_mock_run(
            role="research",
            data=empty_data,
        )

        result = await run_research_pipeline(
            question="Test question",
            api_key="offline-test-key",
        )

        self.assertEqual(result["status"], "no_evidence")

        self.assertEqual(mock_run.await_count, 1)
    def test_json_with_markdown_fence(self):
        """Check JSON wrapped in Markdown code fences."""

        json_text = json.dumps(
            RESEARCH_DATA,
            ensure_ascii=False,
        )

        message = {
            "role": "assistant",
            "metadata": {
                "stream_status": "chunk"
            },
            "content": f"```json\n{json_text}\n```",
        }

        events = [
            {
                "type": "assistant",
                "content": json.dumps(
                    message,
                    ensure_ascii=False,
                ),
            }
        ]

        result = extract_agent_json(events)

        self.assertEqual(result, RESEARCH_DATA)

    def test_incomplete_json(self):
        """Check that incomplete JSON is rejected."""

        events = make_mock_events(RESEARCH_DATA)

        # Simulate a missing final streaming chunk.
        incomplete_events = events[:-1]

        with self.assertRaises(ValueError):
            extract_agent_json(incomplete_events)

    def test_ignore_non_assistant_events(self):
        """Check that unrelated events are ignored."""

        unrelated_event = {
            "type": "tool",
            "content": "Tool execution information",
        }

        events = (
            [unrelated_event]
            + make_mock_events(RESEARCH_DATA)
        )

        result = extract_agent_json(events)

        self.assertEqual(result, RESEARCH_DATA)


if __name__ == "__main__":
    unittest.main()