import time

from app.executor import Executor
from app.models import ToolCall


class FakeTool:
    def __init__(
        self,
        result=42,
        error=None,
        delay=0,
        delay_times=None,
        fail_times=0,
    ):
        self.result = result
        self.error = error
        self.delay = delay
        self.delay_times = delay_times
        self.fail_times = fail_times
        self.call_count = 0
        self.received_arguments = None

        self.parameters = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    def execute(self, arguments):
        self.call_count += 1
        self.received_arguments = arguments

        if self.delay_times is not None:
            delay = self.delay_times[self.call_count - 1]
        else:
            delay = self.delay

        if delay:
            time.sleep(delay)

        if self.call_count <= self.fail_times:
            raise ConnectionError("temporary failure")

        if self.error:
            raise ValueError(self.error)

        return self.result


class FakeRegistry:
    def __init__(self, tool=None):
        self.tool = tool

    def get(self, name):
        if self.tool is None:
            raise ValueError(f"Unknown tool: {name}")

        return self.tool


def test_execute_success():
    tool = FakeTool(result=42)
    executor = Executor(FakeRegistry(tool))

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    result = executor.execute(tool_call)

    assert result.success is True
    assert result.result == 42
    assert result.error is None
    assert result.tool == "calculator"
    assert result.attempts == 1
    assert result.execution_time > 0


def test_execute_passes_arguments_to_tool():
    tool = FakeTool(result=100)
    executor = Executor(FakeRegistry(tool))

    arguments = {
        "expression": "10 * 10",
    }

    tool_call = ToolCall(
        tool="calculator",
        arguments=arguments,
    )

    executor.execute(tool_call)

    assert tool.received_arguments == arguments


def test_execute_handles_tool_error():
    tool = FakeTool(error="division by zero")
    executor = Executor(FakeRegistry(tool))

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "10 / 0"},
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.result is None
    assert result.error == "division by zero"
    assert result.tool == "calculator"
    assert result.attempts == 1
    assert result.execution_time > 0


def test_execute_handles_unknown_tool():
    executor = Executor(FakeRegistry())

    tool_call = ToolCall(
        tool="unknown",
        arguments={},
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.result is None
    assert result.error == "Unknown tool: unknown"
    assert result.tool == "unknown"
    assert result.attempts == 0
    assert result.execution_time >= 0


def test_execute_rejects_invalid_arguments():
    tool = FakeTool(result=42)
    executor = Executor(FakeRegistry(tool))

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": 123},
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.result is None
    assert "expression" in result.error
    assert result.tool == "calculator"
    assert result.attempts == 0
    assert result.execution_time >= 0
    assert tool.received_arguments is None


def test_execute_rejects_unexpected_arguments():
    tool = FakeTool(result=42)
    executor = Executor(FakeRegistry(tool))

    tool_call = ToolCall(
        tool="calculator",
        arguments={
            "expression": "6 * 7",
            "unexpected": True,
        },
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.result is None
    assert result.tool == "calculator"
    assert result.attempts == 0
    assert result.execution_time >= 0
    assert tool.received_arguments is None


def test_execute_times_out_slow_tool():
    tool = FakeTool(
        result=42,
        delay=0.2,
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.05,
        max_retries=0,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    start = time.perf_counter()

    result = executor.execute(tool_call)

    elapsed = time.perf_counter() - start

    assert result.success is False
    assert result.result is None
    assert result.error == (
        "Tool execution timed out after 0.05 seconds."
    )
    assert result.tool == "calculator"
    assert result.attempts == 1
    assert result.execution_time >= 0.05
    assert elapsed < 0.15


def test_execute_retries_after_timeout():
    tool = FakeTool(
        result=42,
        delay_times=[0.05, 0],
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.01,
        max_retries=1,
        retry_base_delay=0,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    result = executor.execute(tool_call)

    assert result.success is True
    assert result.result == 42
    assert result.error is None
    assert result.tool == "calculator"
    assert result.attempts == 2
    assert tool.call_count == 2


def test_execute_completes_before_timeout():
    tool = FakeTool(
        result=42,
        delay=0.01,
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.1,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    result = executor.execute(tool_call)

    assert result.success is True
    assert result.result == 42
    assert result.error is None
    assert result.tool == "calculator"
    assert result.attempts == 1
    assert result.execution_time >= 0.01


def test_execute_retries_retryable_tool_error():
    tool = FakeTool(
        result=42,
        fail_times=1,
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.1,
        max_retries=1,
        retry_base_delay=0,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    result = executor.execute(tool_call)

    assert result.success is True
    assert result.result == 42
    assert result.tool == "calculator"
    assert result.attempts == 2
    assert result.execution_time > 0
    assert tool.call_count == 2


def test_execute_returns_failure_after_retries_exhausted():
    tool = FakeTool(
        result=42,
        fail_times=3,
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.1,
        max_retries=2,
        retry_base_delay=0,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "6 * 7"},
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.result is None
    assert result.error == "temporary failure"
    assert result.tool == "calculator"
    assert result.attempts == 3
    assert result.execution_time > 0
    assert tool.call_count == 3


def test_execute_does_not_retry_non_retryable_error():
    tool = FakeTool(
        error="division by zero",
    )

    executor = Executor(
        FakeRegistry(tool),
        timeout=0.1,
        max_retries=3,
        retry_base_delay=0,
    )

    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "10 / 0"},
    )

    result = executor.execute(tool_call)

    assert result.success is False
    assert result.error == "division by zero"
    assert result.tool == "calculator"
    assert result.attempts == 1
    assert result.execution_time > 0
    assert tool.call_count == 1