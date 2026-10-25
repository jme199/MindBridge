
import json
import unittest
from unittest.mock import patch

import workflows.research_pipeline as pipeline


class TestSafetyInterrupt(unittest.IsolatedAsyncioTestCase):

    async def test_safety_interrupt_stops_pipeline(self):

        # Record which Agents are called
        called_agents = []

        # Simulate SciencePal Agent execution
        async def fake_run_agent(**kwargs):

            role = kwargs["role"]
            called_agents.append(role)

            # Simulated Research Agent JSON response
            fake_response = {
                "status": "safety_interrupt",
                "studies": [],
                "claims": [],
                "safety_message": (
                    "An urgent safety concern was identified. "
                    "Please seek immediate help from local "
                    "emergency services."
                ),
            }

            return {
                "role": role,
                "thread_id": "fake-thread-001",
                "run_id": "fake-run-001",
                "status": "completed",
                "events": [
                    {
                        "type": "assistant",
                        "content": json.dumps(fake_response),
                    }
                ],
            }

        # Replace real SciencePal calls with fake calls
        with patch(
            "workflows.research_pipeline.run_agent",
            new=fake_run_agent,
        ):

            result = await pipeline.run_research_pipeline(
                question="OFFLINE TEST: simulated safety concern",
                api_key="FAKE_API_KEY",
            )

        # Test 1: Correct pipeline status
        self.assertEqual(
            result["status"],
            "safety_interrupt",
        )

        # Test 2: Pipeline stopped at Research Agent
        self.assertEqual(
            result["stage"],
            "research",
        )

        # Test 3: Safety message returned
        self.assertIn(
            "immediate help",
            result["safety_message"],
        )

        # Test 4: No Verification or Explanation calls
        self.assertEqual(
            called_agents,
            ["research"],
        )

        # Test 5: Only one Agent execution recorded
        self.assertEqual(
            len(result["runs"]),
            1,
        )


    async def test_safety_interrupt_missing_message(self):

        called_agents = []

        async def fake_run_agent(**kwargs):

            called_agents.append(kwargs["role"])

            # Simulate a safety response without safety_message
            fake_response = {
                "status": "safety_interrupt",
                "studies": [],
                "claims": [],
            }

            return {
                "role": kwargs["role"],
                "thread_id": "fake-thread-002",
                "run_id": "fake-run-002",
                "status": "completed",
                "events": [
                    {
                        "type": "assistant",
                        "content": json.dumps(fake_response),
                    }
                ],
            }

        with patch(
            "workflows.research_pipeline.run_agent",
            new=fake_run_agent,
        ):
            result = await pipeline.run_research_pipeline(
                question="OFFLINE TEST: missing safety message",
                api_key="FAKE_API_KEY",
            )

        # Verify fallback safety guidance is displayed
        self.assertEqual(result["status"], "safety_interrupt")

        self.assertIsInstance(result["safety_message"], str)

        self.assertTrue(result["safety_message"].strip())

        # Verify subsequent Agents are not executed
        self.assertEqual(called_agents, ["research"])


if __name__ == "__main__":
    unittest.main()
