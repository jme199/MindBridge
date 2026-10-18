import json

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
    """
    Extract structured JSON from SciencePal streaming events.

    Only assistant text chunks are collected.
    Tool events and unrelated events are ignored.

    Raises ValueError if the response is missing,
    incomplete, or invalid.
    """

    chunks = []

    # -----------------------------------------------------
    # Step 1: Collect assistant text chunks
    # -----------------------------------------------------

    for event in events:

        if not isinstance(event, dict):
            continue

        if event.get("type") != "assistant":
            continue

        raw_content = event.get("content")

        if isinstance(raw_content, dict):
            message = raw_content

        elif isinstance(raw_content, str):
            try:
                message = json.loads(raw_content)
            except json.JSONDecodeError:
                continue

        else:
            continue

        if not isinstance(message, dict):
            continue

        if message.get("role") != "assistant":
            continue

        metadata = message.get("metadata")

        if not isinstance(metadata, dict):
            continue

        if metadata.get("stream_status") != "chunk":
            continue

        content = message.get("content")

        if isinstance(content, str):
            chunks.append(content)

    # -----------------------------------------------------
    # Step 2: Combine streaming chunks
    # -----------------------------------------------------

    response_text = "".join(chunks).strip()

    if not response_text:
        raise ValueError(
            "No assistant JSON response was found."
        )

    # -----------------------------------------------------
    # Step 3: Remove optional Markdown fences
    # -----------------------------------------------------

    if response_text.startswith("```"):

        lines = response_text.splitlines()

        if (
            len(lines) < 3
            or lines[0].strip().lower() not in ("```", "```json")
            or lines[-1].strip() != "```"
        ):
            raise ValueError(
                "Invalid Markdown JSON formatting."
            )

        response_text = "\n".join(lines[1:-1]).strip()

    # -----------------------------------------------------
    # Step 4: Parse JSON
    # -----------------------------------------------------

    try:
        result = json.loads(response_text)

    except json.JSONDecodeError as error:
        raise ValueError(
            "The Agent returned incomplete or invalid JSON."
        ) from error

    # -----------------------------------------------------
    # Step 5: Validate JSON structure
    # -----------------------------------------------------

    if not isinstance(result, dict):
        raise ValueError(
            "Agent response must be a JSON object."
        )

    return result


# =========================================================
# 3. Multi-Agent Research Pipeline
# =========================================================

async def run_research_pipeline(question, api_key, progress_callback=None):
    """
    Execute the three MindBridge research Agents.

    Research -> Verification -> Explanation

    Each stage must complete and return valid structured
    data before the next Agent is called.
    """

    if not question or not question.strip():
        raise ValueError("Research question cannot be empty.")

    if not api_key:
        raise ValueError("SciencePal API Key is missing.")

    run_history = []

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
    # Agent 1: Research
    # -----------------------------------------------------

    notify_progress("research", "running")

    research = await run_agent(
        api_key=api_key,
        agent_id=AGENT_IDS["research"],
        prompt=question,
        role="research",
    )

    run_history.append({
        "role": "research",
        "thread_id": research["thread_id"],
        "run_id": research["run_id"],
        "status": research["status"],
    })

    notify_progress("research", research["status"])

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

    notify_progress("verification", "running")

    verification = await run_agent(
        api_key=api_key,
        agent_id=AGENT_IDS["verification"],
        prompt=verification_prompt,
        role="verification",
    )

    run_history.append({
        "role": "verification",
        "thread_id": verification["thread_id"],
        "run_id": verification["run_id"],
        "status": verification["status"],
    })

    notify_progress("verification", verification["status"])

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

    notify_progress("explanation", "running")

    explanation = await run_agent(
        api_key=api_key,
        agent_id=AGENT_IDS["explanation"],
        prompt=explanation_prompt,
        role="explanation",
    )

    run_history.append({
        "role": "explanation",
        "thread_id": explanation["thread_id"],
        "run_id": explanation["run_id"],
        "status": explanation["status"],
    })

    notify_progress("explanation", explanation["status"])

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