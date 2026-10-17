import time

import pytest

from tools.base import ToolRequestRejected
from tools.calculator import CalculatorTool


def test_calculator_evaluates_expression():
    tool = CalculatorTool()

    result = tool.execute(
        {"expression": "6 * 7"},
    )

    assert result == 42


def test_calculator_rejects_empty_expression():
    tool = CalculatorTool()

    with pytest.raises(
        ValueError,
        match="Calculator requires an expression.",
    ):
        tool.execute(
            {"expression": ""},
        )


def test_calculator_metadata():
    tool = CalculatorTool()

    assert tool.name == "calculator"
    assert (
        tool.description
        == "Evaluates a mathematical expression."
    )

@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 ** 10", 1024),
        ("(1 + 2) * 3 - 4 / 2", 7.0),
        ("17 // 5 + 17 % 5", 5),
        ("-3 + +2", -1),
        ("sqrt(16) + abs(-2)", 6.0),
        ("round(pi, 2)", 3.14),
        ("max(1, 5, 3) + min(4, 2)", 7),
        ("int(7.9) + float(1)", 8.0),
        ("2 ** 3000 % 7", pow(2, 3000, 7)),
    ],
)
def test_calculator_supports_arithmetic(expression, expected):
    assert CalculatorTool().execute({"expression": expression}) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "9 ** 4000000",
        "9 ** 999999 + 9 ** 999999",
        "10 ** 1001",
        "(10 ** 600) * (10 ** 600)",
    ],
)
def test_calculator_rejects_results_that_are_too_large(expression):
    start = time.perf_counter()

    with pytest.raises(ValueError, match="exceeds 1000 digits"):
        CalculatorTool().execute({"expression": expression})

    # Rejected before the expensive computation runs.
    assert time.perf_counter() - start < 0.1


def test_calculator_allows_results_up_to_the_limit():
    result = CalculatorTool().execute({"expression": "10 ** 999"})

    assert result == 10**999


@pytest.mark.parametrize(
    "expression",
    [
        "1 << 100000",
        "5 & 3",
        "1 < 2",
        "str(1)",
        "randint(10)",
    ],
)
def test_calculator_rejects_non_arithmetic_operations(expression):
    with pytest.raises(ValueError, match="Unsupported expression"):
        CalculatorTool().execute({"expression": expression})


def test_size_limit_is_reported_as_rejected_request():
    with pytest.raises(ToolRequestRejected):
        CalculatorTool().execute({"expression": "2 ** 5000000"})


def test_unsupported_expression_is_not_a_rejected_request():
    # A malformed expression can be corrected by replanning.
    with pytest.raises(ValueError) as exc_info:
        CalculatorTool().execute({"expression": "2 ^ 3"})

    assert not isinstance(exc_info.value, ToolRequestRejected)
