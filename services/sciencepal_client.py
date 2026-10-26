import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sciencepal import SciencePal
from services.sciencepal_stream_compat import enable_sciencepal_stream_compat


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
    on_run_started=None,
):
    """
    Execute a SciencePal Agent with timeout protection.

    The timeout covers initiation, streaming, and polling.
    On timeout or cancellation, attempt to stop the remote run.
    """

    # Enable SDK 0.2.2 streaming compatibility
    enable_sciencepal_stream_compat()

    if not api_key:
        raise ValueError("SciencePal API Key is missing.")

    if not agent_id:
        raise ValueError("Agent ID is missing.")

    if not prompt or not prompt.strip():
        raise ValueError("Agent prompt cannot be empty.")

    if max_wait_seconds <= 0 or poll_interval <= 0:
        raise ValueError(
            "Timeout and polling interval must be positive."
        )

    thread_id = None
    run_id = None
    events = []

    async with SciencePal(
        api_key=api_key,
        base_url="https://sciencepal.ai/api",
        timeout=120,
    ) as client:

        # Attempt to stop an unfinished remote run
        async def request_stop(reason):

            if not run_id:
                return

            stop_requested = False

            try:
                await asyncio.wait_for(
                    client.runs.stop(run_id),
                    timeout=5,
                )

                stop_requested = True

            except Exception:
                pass

            save_run_record(
                role,
                agent_id,
                thread_id,
                run_id,
                (
                    f"{reason}_stop_requested"
                    if stop_requested
                    else f"{reason}_stop_unconfirmed"
                ),
            )

        try:

            # ---------------------------------------------
            # Shared timeout for the entire Agent execution
            # ---------------------------------------------

            async with asyncio.timeout(max_wait_seconds):

                # Step 1: Initiate Agent
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

                save_run_record(
                    role,
                    agent_id,
                    thread_id,
                    run_id,
                    "initiated",
                )

                if on_run_started is not None:
                    try:
                        on_run_started({
                            "role": role,
                            "thread_id": thread_id,
                            "run_id": run_id,
                        })
                    except Exception:
                        logging.exception(
                            "Failed to notify caller about the new Agent Run."
                        )

                # Step 2: Collect streaming events
                async for event in client.runs.stream(run_id):

                    events.append(
                        event.model_dump(exclude_none=True)
                    )

                # Step 3: Poll final status
                terminal_statuses = {
                    "completed",
                    "failed",
                    "stopped",
                    "asked",
                }

                final_status = None
                final_error = None

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

            # Step 4: Save completed execution
            save_run_record(
                role,
                agent_id,
                thread_id,
                run_id,
                final_status,
            )

            return {
                "role": role,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "status": final_status,
                "error": final_error,
                "events": events,
            }

        # ---------------------------------------------
        # Timeout
        # ---------------------------------------------

        except TimeoutError:

            await request_stop("timeout")

            return {
                "role": role,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "status": "timed_out",
                "error": (
                    "Agent execution exceeded its time limit. "
                    "Remote cancellation was attempted when "
                    "a Run ID was available."
                ),
                "events": events,
            }

        # ---------------------------------------------
        # External cancellation
        # ---------------------------------------------

        except asyncio.CancelledError:

            await request_stop("cancelled")

            raise

        # ---------------------------------------------
        # API errors
        # ---------------------------------------------

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