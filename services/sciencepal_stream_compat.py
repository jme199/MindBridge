
import json

from sciencepal.api import agent_runs


def enable_sciencepal_stream_compat():
    """
    Work around SciencePal SDK 0.2.2 stream events
    whose content is a dictionary or list.

    Preserve the SDK's original SSE parsing behavior.
    """

    original_parser = agent_runs.parse_sse_stream

    # Avoid applying the patch more than once
    if getattr(original_parser, "_mindbridge_compat", False):
        return

    class ResponseAdapter:
        """Normalize SSE event content before SDK validation."""

        def __init__(self, response):
            self.response = response

        async def aiter_lines(self):
            async for line in self.response.aiter_lines():

                if line.startswith("data: "):
                    payload = line[6:]

                    if payload.strip() != "[DONE]":
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            pass
                        else:
                            if (
                                isinstance(data, dict)
                                and isinstance(
                                    data.get("content"),
                                    (dict, list),
                                )
                            ):
                                data["content"] = json.dumps(
                                    data["content"],
                                    ensure_ascii=False,
                                )

                                line = "data: " + json.dumps(
                                    data,
                                    ensure_ascii=False,
                                )

                yield line

    async def compatible_parser(response):
        wrapped_response = ResponseAdapter(response)

        async for event in original_parser(wrapped_response):
            yield event

    compatible_parser._mindbridge_compat = True

    # Replace the parser used by the SciencePal run client
    agent_runs.parse_sse_stream = compatible_parser
