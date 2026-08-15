import pytest

from app.tool_registry import ToolRegistry


class FakeTool:
    def __init__(
        self,
        name="calculator",
        description="Performs calculations",
        parameters=None,
    ):
        self._name = name
        self._description = description
        self._parameters = parameters or {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                }
            },
            "required": ["expression"],
        }

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def parameters(self):
        return self._parameters

    def execute(self, arguments):
        return 42


def test_registry_registers_tools():
    tool = FakeTool()

    registry = ToolRegistry([tool])

    assert registry.get("calculator") is tool


def test_registry_get_unknown_tool():
    registry = ToolRegistry([])

    try:
        registry.get("unknown")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Unknown tool: unknown"


def test_registry_returns_tool_descriptions():
    tool = FakeTool()

    registry = ToolRegistry([tool])

    descriptions = registry.descriptions()

    assert descriptions == [
        {
            "name": "calculator",
            "description": "Performs calculations",
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


def test_registry_registers_multiple_tools():
    calculator = FakeTool(
        name="calculator",
        description="Performs calculations",
    )

    datetime_tool = FakeTool(
        name="datetime",
        description="Returns date and time",
        parameters={
            "type": "object",
            "properties": {},
        },
    )

    registry = ToolRegistry(
        [
            calculator,
            datetime_tool,
        ]
    )

    assert registry.get("calculator") is calculator
    assert registry.get("datetime") is datetime_tool

    descriptions = registry.descriptions()

    assert len(descriptions) == 2
    assert descriptions[0]["name"] == "calculator"
    assert descriptions[1]["name"] == "datetime"


def test_registry_rejects_duplicate_tool_names():
    with pytest.raises(
        ValueError,
        match="Duplicate tool name: calculator",
    ):
        ToolRegistry(
            [
                FakeTool(name="calculator"),
                FakeTool(name="calculator"),
            ]
        )
