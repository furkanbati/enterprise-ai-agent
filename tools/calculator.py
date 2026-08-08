from typing import Any

from simpleeval import simple_eval

from tools.base import Tool


class CalculatorTool(Tool):

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluates a mathematical expression."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate.",
                }
            },
            "required": ["expression"],
        }

    def execute(self, arguments: dict[str, Any]) -> Any:
        expression = arguments.get("expression")

        if not expression:
            raise ValueError("Calculator requires an expression.")

        return simple_eval(expression)