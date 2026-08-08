from app.models import ToolCall, ToolResult
from app.tool_registry import ToolRegistry


class Executor:

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, tool_call: ToolCall) -> ToolResult:
        try:
            tool = self.registry.get(tool_call.tool)
            result = tool.execute(tool_call.arguments)

            return ToolResult(
                success=True,
                result=result,
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
            )