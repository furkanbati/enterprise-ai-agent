import ast
import math
import operator
from typing import Any

from simpleeval import InvalidExpression, SimpleEval

from tools.base import Tool, ToolRequestRejected


# Largest integer result the calculator will produce. Results are bounded
# before they are computed so that one expression cannot tie up a CPU core:
# the executor timeout cannot interrupt CPU-bound work that holds the GIL.
MAX_RESULT_DIGITS = 1_000

_MAX_RESULT_BITS = math.ceil(MAX_RESULT_DIGITS * math.log2(10))

_TOO_LARGE = f"Result exceeds {MAX_RESULT_DIGITS} digits."


def _check_size(value: Any) -> Any:
    if isinstance(value, int) and value.bit_length() > _MAX_RESULT_BITS:
        raise ToolRequestRejected(_TOO_LARGE)

    return value


def _multiply(left: Any, right: Any) -> Any:
    if (
        isinstance(left, int)
        and isinstance(right, int)
        and left.bit_length() + right.bit_length() > _MAX_RESULT_BITS + 1
    ):
        raise ToolRequestRejected(_TOO_LARGE)

    return _check_size(left * right)


def _power(base: Any, exponent: Any) -> Any:
    if (
        isinstance(base, int)
        and isinstance(exponent, int)
        and exponent > 0
        and abs(base) > 1
        and (abs(base).bit_length() - 1) * exponent > _MAX_RESULT_BITS
    ):
        raise ToolRequestRejected(_TOO_LARGE)

    return _check_size(base**exponent)


# Arithmetic only. Bit shifts, bitwise and comparison operators are not
# needed for calculations, and shifts can build huge integers cheaply.
OPERATORS = {
    ast.Add: lambda left, right: _check_size(left + right),
    ast.Sub: lambda left, right: _check_size(left - right),
    ast.Mult: _multiply,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _power,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
    "sqrt": math.sqrt,
}

NAMES = {
    "pi": math.pi,
    "e": math.e,
}


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
                    "maxLength": 200,
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> Any:
        expression = arguments.get("expression")

        if not expression:
            raise ValueError("Calculator requires an expression.")

        try:
            # mode="eval" accepts a single expression only. simpleeval would
            # otherwise evaluate the first of "a = 1; a * 2" with a warning
            # and report the partial result as a success.
            ast.parse(expression.strip(), mode="eval")
        except SyntaxError as exc:
            raise ValueError(
                "Invalid expression. Provide one arithmetic expression "
                "without assignments, semicolons or text."
            ) from exc

        evaluator = SimpleEval(
            operators=OPERATORS,
            functions=FUNCTIONS,
            names=NAMES,
        )

        try:
            result = evaluator.eval(expression)
        except (InvalidExpression, KeyError) as exc:
            # simpleeval raises KeyError for disallowed comparison operators.
            raise ValueError(
                "Unsupported expression. Use numbers, + - * / // % **, "
                "parentheses, and abs, round, min, max, int, float, sqrt, "
                "pi or e."
            ) from exc

        return _check_size(result)
