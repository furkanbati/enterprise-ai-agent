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

class SequenceGenerator:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


VALID_CALCULATOR_RESPONSE = (
    '{"tool": "calculator", "arguments": {"expression": "2 + 2"}}'
)


@pytest.mark.parametrize(
    ("invalid_response", "expected_error"),
    [
        ("{", "Planner returned invalid JSON"),
        ('{"tool": null, "arguments": {}, "x": 1}', "invalid structure"),
        ('{"tool": "weather", "arguments": {}}', "unknown tool: weather"),
    ],
)
def test_plan_retries_with_error_feedback(invalid_response, expected_error):
    generator = SequenceGenerator(
        [invalid_response, VALID_CALCULATOR_RESPONSE]
    )
    planner = Planner(
        generator=generator,
        registry=FakeRegistry(),
        max_retries=1,
    )

    result = planner.plan("What is 2 + 2?")

    assert result == ToolCall(
        tool="calculator",
        arguments={"expression": "2 + 2"},
    )
    assert len(generator.calls) == 2

    correction_prompt = generator.calls[1]["prompt"]
    assert "What is 2 + 2?" in correction_prompt
    assert expected_error in correction_prompt
    assert invalid_response in correction_prompt
    assert generator.calls[1]["json_mode"] is True


def test_plan_raises_after_retries_are_exhausted():
    generator = SequenceGenerator(["{", "{", "{"])
    planner = Planner(
        generator=generator,
        registry=FakeRegistry(),
        max_retries=2,
    )

    with pytest.raises(ValueError, match="Planner returned invalid JSON"):
        planner.plan("test")

    assert len(generator.calls) == 3


def test_plan_does_not_retry_when_retries_are_disabled():
    generator = SequenceGenerator(["{", VALID_CALCULATOR_RESPONSE])
    planner = Planner(
        generator=generator,
        registry=FakeRegistry(),
        max_retries=0,
    )

    with pytest.raises(ValueError, match="Planner returned invalid JSON"):
        planner.plan("test")

    assert len(generator.calls) == 1


def test_unknown_tool_error_lists_available_tools():
    planner = Planner(
        generator=FakeGenerator('{"tool": "weather", "arguments": {}}'),
        registry=FakeRegistry(),
        max_retries=0,
    )

    with pytest.raises(ValueError, match="Available tools: calculator"):
        planner.plan("weather")


def test_plan_truncates_long_invalid_response_in_correction_prompt():
    long_response = "x" * 5_000
    generator = SequenceGenerator([long_response, VALID_CALCULATOR_RESPONSE])
    planner = Planner(
        generator=generator,
        registry=FakeRegistry(),
        max_retries=1,
    )

    planner.plan("test")

    assert "x" * 1_001 not in generator.calls[1]["prompt"]
