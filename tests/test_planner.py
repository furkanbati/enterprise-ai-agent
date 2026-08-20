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

