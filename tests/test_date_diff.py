import pytest

from tools.date_diff import DateDiffTool


@pytest.mark.parametrize(
    ("start", "end", "days"),
    [
        ("2026-10-17", "2026-12-31", 75),
        ("2026-10-17", "2026-12-25", 69),
        ("2026-10-17", "2026-10-17", 0),
        ("2026-12-25", "2026-10-17", -69),
        ("2028-02-28", "2028-03-01", 2),
    ],
)
def test_date_diff_counts_days(start, end, days):
    assert DateDiffTool().execute({"start": start, "end": end}) == days


@pytest.mark.parametrize("value", ["2026-13-01", "25.12.2026", "Christmas"])
def test_date_diff_rejects_invalid_dates(value):
    with pytest.raises(ValueError, match="Use YYYY-MM-DD"):
        DateDiffTool().execute({"start": "2026-10-17", "end": value})


def test_date_diff_schema_requires_both_dates():
    schema = DateDiffTool().parameters

    assert schema["required"] == ["start", "end"]
    assert schema["additionalProperties"] is False


def test_date_diff_is_registered_in_the_api():
    from app import api

    assert api.registry.get("date_diff").name == "date_diff"
