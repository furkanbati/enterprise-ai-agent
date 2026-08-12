from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str | None
    arguments: dict[str, Any]

    @model_validator(mode="after")
    def validate_tool_arguments(self):
        if self.tool is None and self.arguments:
            raise ValueError(
                "Arguments must be empty when no tool is selected"
            )

        if self.tool is not None and not self.tool.strip():
            raise ValueError(
                "Tool name cannot be empty"
            )

        return self


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    success: bool
    result: Any = None
    error: str | None = None


@dataclass
class AgentResult:
    answer: str
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    tool_result: Any = None
    error: str | None = None