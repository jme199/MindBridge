import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sciencepal import SciencePal


# Store run identifiers locally for debugging.
# Do not store user messages or API keys.
RUN_LOG = (
    Path(__file__).resolve().parents[1]
    / ".local_runs"
    / "agent_runs.jsonl"
)


def save_run_record(role, agent_id, thread_id, run_id, status):
    """Save minimal Agent execution metadata."""

    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "agent_id": agent_id,
        "thread_id": thread_id,
        "run_id": run_id,
        "status": status,
    }

    with RUN_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


async def run_agent(
    api_key,
    agent_id,
    prompt,
    role,
    max_wait_seconds=180,
    poll_interval=3,
):
    """
    Execute a SciencePal Agent and wait for its final status.

    Features:
    - Save Thread ID and Run ID
    - Collect streaming events
    - Poll execution status
    - Handle API errors
    - Handle timeouts
    - Attempt to stop timed-out runs
    """

    if not api_key:
        raise ValueError("SciencePal API Key is missing.")

    if not agent_id:
        raise ValueError("Agent ID is missing.")

    if not prompt or not prompt.strip():
        raise ValueError("Agent prompt cannot be empty.")

    if max_wait_seconds <= 0 or poll_interval <= 0:
        raise ValueError("Timeout and polling interval must be positive.")

    thread_id = None
    run_id = None
    events = []

    # -----------------------------------------------------
    # Initialize SciencePal Client
    # -----------------------------------------------------

    async with SciencePal(
        api_key=api_key,
        base_url="https://sciencepal.ai/api",
        timeout=120,
    ) as client:

        try:

            # -----------------------------------------------------
            # Step 1: Initiate Agent
            # -----------------------------------------------------

            run = await client.runs.initiate(
                agent_id=agent_id,
                prompt=prompt,
            )

            thread_id = run.thread_id
            run_id = run.agent_run_id

            if not run_id:
                raise RuntimeError(
                    f"{role} Agent did not create a valid Run ID."
                )

            # Save identifiers immediately
            save_run_record(
                role,
                agent_id,
                thread_id,
                run_id,
                "initiated",
            )

            # -----------------------------------------------------
            # Step 2: Stream Events and Poll Status
            # -----------------------------------------------------

            final_status = None
            final_error = None

            try:

                async with asyncio.timeout(max_wait_seconds):

                    # Collect streaming events
                    async for event in client.runs.stream(run_id):

                        events.append(
                            event.model_dump(exclude_none=True)
                        )

                    # Poll until a terminal status is received
                    terminal_statuses = {
                        "completed",
                        "failed",
                        "stopped",
                        "asked",
                    }

                    while True:

                        result = await client.runs.get(run_id)

                        status_value = getattr(
                            result.status,
                            "value",
                            result.status,
                        )

                        final_status = str(status_value).lower()

                        if final_status in terminal_statuses:

                            error = getattr(result, "error", None)

                            final_error = (
                                str(error)
                                if error is not None
                                else None
                            )

                            break

                        await asyncio.sleep(poll_interval)

            # -----------------------------------------------------
            # Step 3: Timeout Handling
            # -----------------------------------------------------

            except TimeoutError:

                stop_requested = False

                try:
                    stop_requested = bool(
                        await asyncio.wait_for(
                            client.runs.stop(run_id),
                            timeout=15,
                        )
                    )

                except Exception:
                    # Stop could not be confirmed.
                    pass

                save_run_record(
                    role,
                    agent_id,
                    thread_id,
                    run_id,
                    (
                        "timeout_stop_requested"
                        if stop_requested
                        else "timeout_stop_unconfirmed"
                    ),
                )

                return {
                    "role": role,
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "run_id": run_id,
                    "status": "timed_out",
                    "error": (
                        "The Agent exceeded the configured time limit. "
                        "A stop was attempted, but the final server "
                        "status has not been independently confirmed."
                    ),
                    "events": events,
                }

            # -----------------------------------------------------
            # Step 4: Save Final Status
            # -----------------------------------------------------

            save_run_record(
                role,
                agent_id,
                thread_id,
                run_id,
                final_status,
            )

            # -----------------------------------------------------
            # Step 5: Return Results
            # -----------------------------------------------------

            return {
                "role": role,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "status": final_status,
                "error": final_error,
                "events": events,
            }

        # -----------------------------------------------------
        # Step 6: API Error Handling
        # -----------------------------------------------------

        except Exception:

            if run_id:
                save_run_record(
                    role,
                    agent_id,
                    thread_id,
                    run_id,
                    "api_error",
                )

            raise