import pytest

from app.tool_validator import ToolArgumentValidator
from tools.calculator import CalculatorTool


def test_calculator_accepts_expression_with_max_length():
    tool = CalculatorTool()
    validator = ToolArgumentValidator()

    expression = "1" * 200

    validator.validate(
        arguments={"expression": expression},
        schema=tool.parameters,
    )


def test_calculator_rejects_expression_over_max_length():
    tool = CalculatorTool()
    validator = ToolArgumentValidator()

    expression = "1" * 201

    with pytest.raises(
        ValueError,
        match="Invalid tool arguments",
    ):
        validator.validate(
            arguments={"expression": expression},
            schema=tool.parameters,
        )


def test_validator_rejects_invalid_schema():
    validator = ToolArgumentValidator()

    invalid_schema = {
        "type": "not-a-valid-json-schema-type",
    }

    with pytest.raises(
        ValueError,
        match="Invalid tool schema",
    ):
        validator.validate(
            arguments={},
            schema=invalid_schema,
        )