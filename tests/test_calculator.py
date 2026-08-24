import pytest

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