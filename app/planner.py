import json

from pydantic import ValidationError
from typing import Any
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

        selected_tool = next(
            tool
            for tool in tools
            if tool["name"] == planner_response.tool
        )

        self._validate_arguments(
            planner_response.arguments,
            selected_tool["parameters"],
        )

        return ToolCall(
            tool=planner_response.tool,
            arguments=planner_response.arguments,
        )

    def _validate_arguments(
        self,
        arguments: dict[str, Any],
        parameters: dict[str, Any],
    ) -> None:
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])

        provided = set(arguments)

        missing = set(required) - provided
        unexpected = provided - set(properties)

        if missing:
            raise ValueError(
                f"Missing tool arguments: {sorted(missing)}"
            )

        if unexpected:
            raise ValueError(
                f"Unexpected tool arguments: {sorted(unexpected)}"
            )

        for name, schema in properties.items():
            if name not in arguments:
                continue

            expected_type = schema.get("type")
            value = arguments[name]

            if expected_type == "string" and not isinstance(value, str):
                raise ValueError(
                    f"Tool argument '{name}' must be a string"
                )

            if expected_type == "number" and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
            ):
                raise ValueError(
                    f"Tool argument '{name}' must be a number"
                )

            if expected_type == "boolean" and not isinstance(value, bool):
                raise ValueError(
                    f"Tool argument '{name}' must be a boolean"
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