import json
import logging

from prometheus_client import Counter
from pydantic import ValidationError

from app.config import PLANNER_MAX_RETRIES
from app.generator import Generator
from app.models import PlannerResponse, ToolCall
from app.tool_registry import ToolRegistry


SYSTEM_PROMPT = """
You are an AI agent planner.

Your job is to decide whether a tool is required to answer
the user's request.

Available tools:
{tools}

If a tool is required, return ONLY valid JSON:

{{
"tool": "tool_name",
"arguments": {{
"argument_name": "value"
}}
}}

If no tool is required, return ONLY:

{{
"tool": null,
"arguments": {{}}
}}

Do not include markdown.
Do not include explanations.
"""


CORRECTION_PROMPT = """
{prompt}

Your previous response could not be used:
{error}

Previous response:
{response}

Return ONLY valid JSON in the required format, using one of the
available tools or "tool": null.
"""

# Limit on how much of an invalid response is echoed back to the model.
MAX_ECHOED_RESPONSE_CHARS = 1_000


logger = logging.getLogger(__name__)


PLANNER_RETRIES_TOTAL = Counter(
    "agent_planner_retries_total",
    "Total number of planner retries after invalid model output.",
)


class Planner:

    def __init__(
        self,
        generator: Generator,
        registry: ToolRegistry,
        max_retries: int = PLANNER_MAX_RETRIES,
    ):
        self.generator = generator
        self.registry = registry
        self.max_retries = max_retries

    def plan(
        self,
        question: str,
        previous_tool=None,
        previous_error: str | None = None,
    ) -> ToolCall | None:
        tools = self.registry.descriptions()

        system_prompt = SYSTEM_PROMPT.format(
            tools=tools,
        )

        prompt = question

        if previous_error:
            prompt = f"""
User question:
{question}

A previous tool attempt failed.

Previous tool:
{previous_tool.tool}

Previous arguments:
{previous_tool.arguments}

Previous error:
{previous_error}

Try to correct the tool call if the error can be corrected.

IMPORTANT:
- Do not change the user's requested operation.
- Do not invent different values.
- Do not replace the user's requested calculation with another calculation.
- If the requested operation itself is invalid or cannot be completed,
  return:
  {{
    "tool": null,
    "arguments": {{}}
  }}
"""

        tool_names = [tool["name"] for tool in tools]
        attempt_prompt = prompt

        for attempt in range(self.max_retries + 1):
            response = self.generator.generate(
                prompt=attempt_prompt,
                system_prompt=system_prompt,
                json_mode=True,
            )

            try:
                return self._to_tool_call(response, tool_names)

            except ValueError as exc:
                if attempt >= self.max_retries:
                    raise

                # Models often fix malformed output once they see the error,
                # so give the error back instead of failing the request.
                logger.warning(
                    "Planner output was invalid, retrying %s/%s: %s",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )

                PLANNER_RETRIES_TOTAL.inc()

                attempt_prompt = CORRECTION_PROMPT.format(
                    prompt=prompt,
                    error=str(exc)[:MAX_ECHOED_RESPONSE_CHARS],
                    response=response[:MAX_ECHOED_RESPONSE_CHARS],
                )

    def _to_tool_call(
        self,
        response: str,
        tool_names: list[str],
    ) -> ToolCall | None:
        planner_response = self._parse_response(response)

        if planner_response.tool is None:
            return None

        if planner_response.tool not in tool_names:
            raise ValueError(
                f"Planner selected unknown tool: "
                f"{planner_response.tool}. "
                f"Available tools: {', '.join(tool_names)}"
            )

        return ToolCall(
            tool=planner_response.tool,
            arguments=planner_response.arguments,
        )

    def _parse_response(
        self,
        response: str,
    ) -> PlannerResponse:
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Planner returned invalid JSON: {response}"
            ) from exc

        try:
            return PlannerResponse.model_validate(data)
        except ValidationError as exc:
            raise ValueError(
                f"Planner returned invalid structure: {data}"
            ) from exc