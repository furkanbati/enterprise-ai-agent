from datetime import datetime, timezone
from typing import Any

from tools.datetime_tool import DateTimeTool


# The moment every evaluation run treats as "now", so that answers to
# date questions ("days until Christmas") are stable across runs.
EVALUATION_NOW = datetime(2026, 10, 17, 9, 0, 0, tzinfo=timezone.utc)


class FixedDateTimeTool(DateTimeTool):
    """DateTimeTool with a fixed clock, using the same name and schema."""

    def __init__(self, now: datetime = EVALUATION_NOW):
        self.now = now

    def execute(self, arguments: dict[str, Any]) -> str:
        return self.now.isoformat()
