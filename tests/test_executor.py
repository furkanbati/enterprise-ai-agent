import pytest

from app.executor import Executor
from app.models import ToolCall


class FakeTool:
    def __init__(self, result=42, error=None):
        self.result = result
        self.error = error
        self.received_arguments = None

    def execute(self, arguments):
        self.received_arguments = arguments

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