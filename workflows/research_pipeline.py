import json

import asyncio
import time

import logging
from collections import Counter

from services.sciencepal_client import run_agent


# =========================================================
# 1. MindBridge Agent Configuration
# =========================================================

AGENT_IDS = {
    "research": "4598a520-804c-4c73-ad31-79a62f2a73cc",
    "verification": "c0b45f9c-ced0-4ed8-927c-2683023e507a",
    "explanation": "b2731f71-b51a-44e1-beda-c5a4b5b035b6",
}


# =========================================================
# 2. Extract JSON from SciencePal Streaming Events
# =========================================================

def extract_agent_json(events):
    expected_keys = {"studies", "verified_studies", "papers"}

    def as_text(value):
        """Read plain text or JSON-wrapped assistant text."""

        if isinstance(value, dict):

            if expected_keys.intersection(value):
                return json.dumps(value, ensure_ascii=False)

            if value.get("role") not in (None, "assistant"):
                return None

            for key in ("content", "message", "text"):
                if key in value:
                    return as_text(value[key])

            return None

        if isinstance(value, list):

            parts = [as_text(item) for item in value]

            return "".join(
                part for part in parts if part
            ) or None

        if not isinstance(value, str):
            return None

        try:
            decoded = json.loads(value)

        except json.JSONDecodeError:
            return value

        if isinstance(decoded, (dict, list)):

            nested = as_text(decoded)

            return nested if nested is not None else value

        if isinstance(decoded, str):
            return decoded

        return value

    def parse_response(text):
        """Extract a complete structured JSON object."""

        if not isinstance(text, str):
            return None

        text = text.strip()

        # Remove Markdown JSON fences
        if text.startswith("```") and text.endswith("```"):

            lines = text.splitlines()

            if (
                len(lines) >= 3
                and lines[-1].strip() == "```"
            ):
                text = "\n".join(lines[1:-1]).strip()

        # First try parsing the complete response
        try:
            candidate = json.loads(text)

        except json.JSONDecodeError:
            candidate = None

        if (
            isinstance(candidate, dict)
            and expected_keys.intersection(candidate)
        ):
            return candidate

        # Handle explanatory text surrounding a JSON object
        decoder = json.JSONDecoder()

        for index, char in enumerate(text):

            if char != "{":
                continue

            try:
                candidate, _ = decoder.raw_decode(
                    text, index
                )

            except json.JSONDecodeError:
                continue

            if (
                isinstance(candidate, dict)
                and expected_keys.intersection(candidate)
            ):
                return candidate

        return None

    # Collect assistant responses by field
    segments = {
        "content": [],
        "message": [],
    }

    current = {
        "content": [],
        "message": [],
    }

    complete_candidates = []

    for event in events:

        if not isinstance(event, dict):
            continue

        event_type = event.get("type")

        if event_type not in (
            "assistant",
            "assistant_response_end",
        ):
            continue

        # Read both possible response fields
        for field in ("message", "content"):

            text = as_text(event.get(field))

            if not text:
                continue

            parsed = parse_response(text)

            if parsed is not None:
                complete_candidates.append(parsed)

            current[field].append(text)

        # Separate completed assistant responses
        if event_type == "assistant_response_end":

            for field in current:

                if current[field]:

                    segments[field].append(
                        current[field]
                    )

                    current[field] = []

    # Preserve the last response
    for field in current:

        if current[field]:
            segments[field].append(current[field])

    def merge_parts(parts):
        """Support cumulative snapshots and text chunks."""

        if len(parts) > 1 and all(
            later.startswith(earlier)
            for earlier, later in zip(parts, parts[1:])
        ):
            return parts[-1]

        return "".join(parts)

    # Examine recent assistant responses first
    for field in ("message", "content"):

        for parts in reversed(segments[field]):

            response_text = merge_parts(parts)

            parsed = parse_response(response_text)

            if parsed is not None:
                return parsed

    # Fall back to an individually complete response
    if complete_candidates:
        return complete_candidates[-1]

    raise ValueError(
        "No complete structured assistant JSON response was found."
    )


# =========================================================
# 3. Multi-Agent Research Pipeline
# =========================================================

async def run_research_pipeline(question, api_key, progress_callback=None):
    """
    Execute the three MindBridge research Agents.

    Research -> Verification -> Explanation

    All three Agents share a total execution budget
    of 170 seconds, with approximately 10 seconds
    reserved for overhead.
    """

    if not question or not question.strip():
        raise ValueError("Research question cannot be empty.")

    if not api_key:
        raise ValueError("SciencePal API Key is missing.")

    run_history = []

    # -----------------------------------------------------
    # Shared Pipeline Time Budget
    # -----------------------------------------------------

    PIPELINE_TIMEOUT = 170

    deadline = time.monotonic() + PIPELINE_TIMEOUT

    # Reserve time for subsequent Agents
    reserved_after = {
        "research": 90,
        "verification": 40,
        "explanation": 0,
    }

    # -----------------------------------------------------
    # Progress Callback
    # -----------------------------------------------------

    def notify_progress(role, status):
        """
        Report Agent execution progress to the frontend.
        """

        if progress_callback is not None:
            progress_callback(role, status)

    # -----------------------------------------------------
    # Shared Agent Execution Function
    # -----------------------------------------------------

    async def run_with_budget(role, prompt):
        """
        Execute an Agent using the remaining
        shared pipeline time budget.
        """

        remaining = deadline - time.monotonic()

        available = remaining - reserved_after[role]

        # Do not start if insufficient time remains
        if available <= 5:

            notify_progress(role, "timed_out")

            return {
                "thread_id": None,
                "run_id": None,
                "status": "timed_out",
                "events": [],
            }

        notify_progress(role, "running")

        result = await run_agent(
            api_key=api_key,
            agent_id=AGENT_IDS[role],
            prompt=prompt,
            role=role,
            max_wait_seconds=max(
                1, int(available) - 5
            ),
        )

        notify_progress(role, result["status"])

        return result

    # -----------------------------------------------------
    # Agent 1: Research
    # -----------------------------------------------------

    research = await run_with_budget(
        "research",
        question,
    )

    run_history.append({
        "role": "research",
        "thread_id": research["thread_id"],
        "run_id": research["run_id"],
        "status": research["status"],
    })

    if research["status"] != "completed":
        return {
            "status": "pending_or_failed",
            "stage": "research",
            "runs": run_history,
        }

    research_data = extract_agent_json(
        research["events"]
    )

    if not isinstance(research_data.get("studies"), list):
        raise ValueError(
            "Research Agent did not return a valid studies list."
        )

    if not research_data["studies"]:
        return {
            "status": "no_evidence",
            "stage": "research",
            "research": research_data,
            "runs": run_history,
        }

    # -----------------------------------------------------
    # Agent 2: Verification
    # -----------------------------------------------------

    verification_prompt = (
        "Independently verify the following research evidence. "
        "Follow your system prompt and return structured JSON.\n\n"
        + json.dumps(research_data, ensure_ascii=False)
    )

    verification = await run_with_budget(
        "verification",
        verification_prompt,
    )

    run_history.append({
        "role": "verification",
        "thread_id": verification["thread_id"],
        "run_id": verification["run_id"],
        "status": verification["status"],
    })

    if verification["status"] != "completed":
        return {
            "status": "pending_or_failed",
            "stage": "verification",
            "runs": run_history,
        }

    verification_data = extract_agent_json(
        verification["events"]
    )

    if not isinstance(
        verification_data.get("verified_studies"), list
    ):
        raise ValueError(
            "Verification Agent returned invalid study data."
        )

    if not isinstance(
        verification_data.get("claim_assessments"), list
    ):
        raise ValueError(
            "Verification Agent returned invalid claim data."
        )

    # -----------------------------------------------------
    # Agent 3: Explanation
    # -----------------------------------------------------

    explanation_prompt = (
        "Generate a clear, evidence-grounded research report "
        "using only the verification results below. "
        "Follow your system prompt and return structured JSON.\n\n"
        + json.dumps(verification_data, ensure_ascii=False)
    )

    explanation = await run_with_budget(
        "explanation",
        explanation_prompt,
    )

    run_history.append({
        "role": "explanation",
        "thread_id": explanation["thread_id"],
        "run_id": explanation["run_id"],
        "status": explanation["status"],
    })

    if explanation["status"] != "completed":
        return {
            "status": "pending_or_failed",
            "stage": "explanation",
            "runs": run_history,
        }

    explanation_data = extract_agent_json(
        explanation["events"]
    )

    if not isinstance(explanation_data.get("papers"), list):
        raise ValueError(
            "Explanation Agent returned invalid papers data."
        )

    # -----------------------------------------------------
    # Final Result
    # -----------------------------------------------------

    return {
        "status": "completed",
        "research": research_data,
        "verification": verification_data,
        "result": explanation_data,
        "runs": run_history,
    }