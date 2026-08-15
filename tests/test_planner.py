import pytest

from app.planner import Planner


class FakeGenerator:
    def __init__(self, response):
        self.response = response

    def generate(self, **kwargs):
        return self.response


class FakeRegistry:
    def descriptions(self):
        return [
            {
                "name": "calculator",
                "description": "Performs calculations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                        }
                    },
                    "required": ["expression"],
                },
            }
        ]


def create_planner():
    return Planner(
        generator=None,
        registry=None,
    )


def test_valid_arguments():
    planner = create_planner()

    planner._validate_arguments(
        arguments={
            "expression": "10 / 2",
        },
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                }
            },
            "required": ["expression"],
        },
    )


def test_missing_arguments():
    planner = create_planner()

    with pytest.raises(
        ValueError,
        match="Missing tool arguments",
    ):
        planner._validate_arguments(
            arguments={},
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                    }
                },
                "required": ["expression"],
            },
        )


def test_unexpected_arguments():
    planner = create_planner()

    with pytest.raises(
        ValueError,
        match="Unexpected tool arguments",
    ):
        planner._validate_arguments(
            arguments={
                "expression": "10 / 2",
                "foo": "bar",
            },
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                    }
                },
                "required": ["expression"],
            },
        )


def test_rejects_wrong_string_type():
    planner = create_planner()

    with pytest.raises(
        ValueError,
        match="must be a string",
    ):
        planner._validate_arguments(
            arguments={
                "expression": 125,
            },
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                    }
                },
                "required": ["expression"],
            },
        )


def test_rejects_wrong_boolean_type():
    planner = create_planner()

    with pytest.raises(
        ValueError,
        match="must be a boolean",
    ):
        planner._validate_arguments(
            arguments={
                "enabled": "true",
            },
            parameters={
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                    }
                },
                "required": ["enabled"],
            },
        )


def test_plan_returns_tool_call():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": "calculator", '
                '"arguments": {"expression": "10 / 2"}}'
            )
        ),
        registry=FakeRegistry(),
    )

    result = planner.plan("What is 10 / 2?")

    assert result is not None
    assert result.tool == "calculator"
    assert result.arguments == {
        "expression": "10 / 2",
    }


def test_plan_returns_none_when_no_tool_required():
    planner = Planner(
        generator=FakeGenerator(
            response='{"tool": null, "arguments": {}}'
        ),
        registry=FakeRegistry(),
    )

    result = planner.plan("Hello")

    assert result is None


def test_plan_rejects_invalid_arguments():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": "calculator", '
                '"arguments": {"foo": "bar"}}'
            )
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Missing tool arguments",
    ):
        planner.plan("What is 10 / 2?")