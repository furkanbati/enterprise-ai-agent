from app.models import AgentResult, ToolCall, ToolResult
from app.pipeline import Pipeline

class FakePlanner:
    def __init__(self, tool_call=None):
        self.tool_call = tool_call
        self.calls = []

    def plan(
        self,
        question,
        previous_tool=None,
        previous_error=None,
    ):
        self.calls.append(
            {
                "question": question,
                "previous_tool": previous_tool,
                "previous_error": previous_error,
            }
        )

        return self.tool_call

class FakeExecutor:
    def __init__(self, result):
        self.result = result
        self.received_tool_call = None

    def execute(self, tool_call):
        self.received_tool_call = tool_call
        return self.result


class FakeGenerator:
    def __init__(self, answer="generated answer"):
        self.answer = answer
        self.calls = []

    def generate(self, prompt, system_prompt=None, json_mode=False):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "json_mode": json_mode,
            }
        )
        return self.answer


def test_pipeline_without_tool():
    planner = FakePlanner(tool_call=None)
    executor = FakeExecutor(
        result=ToolResult(success=True, result=42)
    )
    generator = FakeGenerator(answer="Hello!")

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )

    result = pipeline.run("Hello")

    assert isinstance(result, AgentResult)
    assert result.answer == "Hello!"
    assert result.tool is None
    assert result.arguments is None

    assert len(generator.calls) == 1
    assert generator.calls[0]["prompt"] == "Hello"


def test_pipeline_with_successful_tool():
    tool_call = ToolCall(
        tool="calculator",
        arguments={
            "expression": "10 * 5",
        },
    )

    planner = FakePlanner(tool_call=tool_call)

    executor = FakeExecutor(
        result=ToolResult(
            success=True,
            result=50,
        )
    )

    generator = FakeGenerator(
        answer="The answer is 50."
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )

    result = pipeline.run("What is 10 * 5?")

    assert isinstance(result, AgentResult)
    assert result.answer == "The answer is 50."
    assert result.tool == "calculator"
    assert result.arguments == {
        "expression": "10 * 5",
    }
    assert result.tool_result == 50

    assert executor.received_tool_call == tool_call


def test_pipeline_with_failed_tool():
    tool_call = ToolCall(
        tool="calculator",
        arguments={
            "expression": "10 / 0",
        },
    )

    planner = FakePlanner(tool_call=tool_call)

    executor = FakeExecutor(
        result=ToolResult(
            success=False,
            error="division by zero",
        )
    )

    generator = FakeGenerator(
        answer="The calculation could not be completed."
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )

    result = pipeline.run("What is 10 / 0?")

    assert isinstance(result, AgentResult)
    assert result.answer == "The calculation could not be completed."
    assert result.tool == "calculator"
    assert result.arguments == {
        "expression": "10 / 0",
    }
    assert result.error == "division by zero"