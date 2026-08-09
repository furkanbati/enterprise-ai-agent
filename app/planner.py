import json

from pydantic import ValidationError

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


class Planner:

    def __init__(
        self,
        generator: Generator,
        registry: ToolRegistry,
    ):
        self.generator = generator
        self.registry = registry

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

        response = self.generator.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
        )

        planner_response = self._parse_response(response)

        if planner_response.tool is None:
            return None

        if planner_response.tool not in {
            tool["name"] for tool in tools
        }:
            raise ValueError(
                f"Planner selected unknown tool: "
                f"{planner_response.tool}"
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