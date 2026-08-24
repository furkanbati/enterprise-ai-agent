from datetime import datetime

from tools.datetime_tool import DateTimeTool


def test_datetime_tool_metadata():
    tool = DateTimeTool()

    assert tool.name == "datetime"
    assert (
        tool.description
        == "Returns the current date and time."
    )


def test_datetime_tool_parameters():
    tool = DateTimeTool()

    assert tool.parameters == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def test_datetime_tool_returns_current_utc_datetime():
    tool = DateTimeTool()

    result = tool.execute({})

    parsed = datetime.fromisoformat(result)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None