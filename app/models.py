from dataclasses import dataclass
from typing import Any


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