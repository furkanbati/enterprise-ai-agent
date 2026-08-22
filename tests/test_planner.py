import pytest
from app.models import ToolCall
from app.planner import Planner


class FakeGenerator:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def generate(self, **kwargs):
        self.last_kwargs = kwargs
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

def test_plan_rejects_invalid_json():
    planner = Planner(
        generator=FakeGenerator(
            response="{"
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Planner returned invalid JSON",
    ):
        planner.plan("test")

def test_plan_rejects_unknown_tool():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": "weather", '
                '"arguments": {}}'
            )
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Planner selected unknown tool",
    ):
        planner.plan("weather")

def test_plan_rejects_extra_fields():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": null, '
                '"arguments": {}, '
                '"extra": true}'
            )
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Planner returned invalid structure",
    ):
        planner.plan("hello")

def test_plan_rejects_empty_tool_name():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": "", '
                '"arguments": {}}'
            )
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Planner returned invalid structure",
    ):
        planner.plan("test")

def test_plan_rejects_arguments_without_tool():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": null, '
                '"arguments": {"x": 1}}'
            )
        ),
        registry=FakeRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="Planner returned invalid structure",
    ):
        planner.plan("test")

def test_parse_response_returns_planner_response():
    planner = create_planner()

    result = planner._parse_response(
        '{"tool": null, "arguments": {}}'
    )

    assert result.tool is None
    assert result.arguments == {}

def test_plan_replans_after_previous_tool_failure():
    planner = Planner(
        generator=FakeGenerator(
            response=(
                '{"tool": "calculator", '
                '"arguments": {"expression": "10 + 5"}}'
            )
        ),
        registry=FakeRegistry(),
    )

    previous_tool = ToolCall(
        tool="calculator",
        arguments={
            "expression": "10 / 0",
        },
    )

    result = planner.plan(
        question="What is 10 / 5?",
        previous_tool=previous_tool,
        previous_error="Division by zero.",
    )

    assert result is not None
    assert result.tool == "calculator"
    assert result.arguments == {
        "expression": "10 + 5",
    }
    assert "Division by zero." in (
        planner.generator.last_kwargs["prompt"]
    )

    assert "10 / 0" in (
        planner.generator.last_kwargs["prompt"]
    )