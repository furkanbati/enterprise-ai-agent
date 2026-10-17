from datetime import datetime, timezone

from tools.datetime_tool import DateTimeTool


def test_datetime_tool_metadata():
    tool = DateTimeTool()

    assert tool.name == "datetime"
    assert "day of the week" in tool.description


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

    parsed = datetime.fromisoformat(result["datetime"])

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None
    assert result["weekday"] == parsed.strftime("%A")


def test_datetime_tool_reports_the_weekday_of_its_clock(monkeypatch):
    tool = DateTimeTool()
    saturday = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(tool, "now", lambda: saturday)

    assert tool.execute({}) == {
        "datetime": "2026-10-17T09:00:00+00:00",
        "weekday": "Saturday",
    }