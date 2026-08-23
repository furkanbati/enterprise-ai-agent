from app.models import AgentResult, ToolCall, ToolResult
from app.pipeline import Pipeline
from app.config import PIPELINE_MAX_REPLANS
import pytest

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


class SequencedPlanner:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls
        self.calls = []

    def plan(self, question, previous_tool=None, previous_error=None):
        self.calls.append(
            {
                "question": question,
                "previous_tool": previous_tool,
                "previous_error": previous_error,
            }
        )

        return self.tool_calls.pop(0)


class SequencedExecutor:
    def __init__(self, results):
        self.results = results
        self.received_tool_calls = []

    def execute(self, tool_call):
        self.received_tool_calls.append(tool_call)
        return self.results.pop(0)

class FailingGenerator:
    def generate(
        self,
        prompt,
        system_prompt=None,
        json_mode=False,
    ):
        raise RuntimeError(
            "generation failed"
        )

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


def test_pipeline_recovers_with_corrected_tool_call():
    failed_tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "10 / 0"},
    )
    corrected_tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "10 / 2"},
    )
    planner = SequencedPlanner([failed_tool_call, corrected_tool_call])
    executor = SequencedExecutor(
        [
            ToolResult(success=False, error="division by zero"),
            ToolResult(success=True, result=5),
        ]
    )
    generator = FakeGenerator(answer="The answer is 5.")

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )

    result = pipeline.run("What is 10 / 2?")

    assert result.answer == "The answer is 5."
    assert result.tool == "calculator"
    assert result.arguments == {"expression": "10 / 2"}
    assert result.tool_result == 5
    assert result.error is None
    assert executor.received_tool_calls == [
        failed_tool_call,
        corrected_tool_call,
    ]
    assert planner.calls[1]["previous_tool"] == failed_tool_call
    assert planner.calls[1]["previous_error"] == "division by zero"


def test_pipeline_returns_failure_when_replanning_declines_tool():
    failed_tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "10 / 0"},
    )
    planner = SequencedPlanner([failed_tool_call, None])
    executor = SequencedExecutor(
        [ToolResult(success=False, error="division by zero")]
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

    assert result.answer == "The calculation could not be completed."
    assert result.tool == "calculator"
    assert result.arguments == {"expression": "10 / 0"}
    assert result.tool_result is None
    assert result.error == "division by zero"
    assert executor.received_tool_calls == [failed_tool_call]
    assert len(planner.calls) == 2


def test_pipeline_stops_after_max_replans():
    initial_tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "1 / 0"},
    )

    replans = [
        ToolCall(
            tool="calculator",
            arguments={"expression": f"1 / {i}"},
        )
        for i in range(1, PIPELINE_MAX_REPLANS + 1)
    ]

    planner = SequencedPlanner(
        [initial_tool_call, *replans]
    )

    executor = SequencedExecutor(
        [
            ToolResult(
                success=False,
                error=f"failure-{i}",
            )
            for i in range(
                PIPELINE_MAX_REPLANS + 1
            )
        ]
    )

    generator = FakeGenerator(
        answer="Could not complete request."
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )

    result = pipeline.run("calculate")

    assert result.answer == "Could not complete request."
    assert result.tool_result is None
    assert result.error == (
        f"failure-{PIPELINE_MAX_REPLANS}"
    )

    assert len(executor.received_tool_calls) == (
        PIPELINE_MAX_REPLANS + 1
    )

    assert len(planner.calls) == (
        PIPELINE_MAX_REPLANS + 1
    )




class FailingPlanner:
    def plan(self, *args, **kwargs):
        raise ValueError("invalid planner output")


def test_pipeline_propagates_initial_planner_failure():
    pipeline = Pipeline(
        planner=FailingPlanner(),
        executor=FakeExecutor(
            ToolResult(success=True, result=1)
        ),
        generator=FakeGenerator(),
    )

    with pytest.raises(
        ValueError,
        match="invalid planner output",
    ):
        pipeline.run("hello")

class ReplanFailingPlanner:
    def __init__(self):
        self.calls = 0

    def plan(
        self,
        question,
        previous_tool=None,
        previous_error=None,
    ):
        self.calls += 1

        if self.calls == 1:
            return ToolCall(
                tool="calculator",
                arguments={
                    "expression": "10 / 0",
                },
            )

        raise ValueError(
            "replanning failed"
        )


def test_pipeline_propagates_replan_failure():
    planner = ReplanFailingPlanner()

    executor = FakeExecutor(
        ToolResult(
            success=False,
            error="division by zero",
        )
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=FakeGenerator(),
    )

    with pytest.raises(
        ValueError,
        match="replanning failed",
    ):
        pipeline.run("10 / 0")



def test_pipeline_propagates_generator_failure_without_tool():
    planner = FakePlanner(
        tool_call=None,
    )

    pipeline = Pipeline(
        planner=planner,
        executor=FakeExecutor(
            ToolResult(success=True, result=1)
        ),
        generator=FailingGenerator(),
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        pipeline.run("hello")

def test_pipeline_propagates_generator_failure_after_tool_success():
    planner = FakePlanner(
        tool_call=ToolCall(
            tool="calculator",
            arguments={
                "expression": "2 + 2",
            },
        )
    )

    executor = FakeExecutor(
        ToolResult(
            success=True,
            result=4,
        )
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=FailingGenerator(),
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        pipeline.run("2 + 2")

def test_pipeline_propagates_generator_failure_after_tool_failure():
    planner = FakePlanner(
        tool_call=ToolCall(
            tool="calculator",
            arguments={
                "expression": "1 / 0",
            },
        )
    )

    executor = FakeExecutor(
        ToolResult(
            success=False,
            error="division by zero",
        )
    )

    pipeline = Pipeline(
        planner=planner,
        executor=executor,
        generator=FailingGenerator(),
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        pipeline.run("1 / 0")

