from dataclasses import dataclass, field
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
class ChatToolCall:
    """A tool call requested by the model through native tool calling."""

    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """An assistant message: text content and/or requested tool calls."""

    content: str
    tool_calls: list[ChatToolCall] = field(default_factory=list)


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    success: bool
    result: Any = None
    error: str | None = None
    tool: str | None = None
    attempts: int = 0
    execution_time: float = 0.0
    # False when the failure cannot be fixed by replanning.
    retryable: bool = True


@dataclass
class AgentStep:
    """One tool call made while answering a request."""

    tool: str
    arguments: dict[str, Any]
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
    steps: list[AgentStep] = field(default_factory=list)