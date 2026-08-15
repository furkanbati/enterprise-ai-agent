from tools.base import Tool


class ToolRegistry:

    def __init__(self, tools: list[Tool]):
        self._tools = {}

        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(
                    f"Duplicate tool name: {tool.name}"
                )

            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        return self._tools[name]

    def descriptions(self) -> list[dict]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]
