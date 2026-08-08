import json

from app.models import ToolCall
from app.generator import Generator
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

    def plan(self, question: str) -> ToolCall | None:
        tools = self.registry.descriptions()

        system_prompt = SYSTEM_PROMPT.format(tools=tools)

        response = self.generator.generate(
            prompt=question,
            system_prompt=system_prompt,
            json_mode=True,
        )

        data = self._parse_response(response)

        if data["tool"] is None:
            return None

        return ToolCall(
            tool=data["tool"],
            arguments=data["arguments"],
        )

    def _parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Planner returned invalid JSON: {response}"
            ) from exc