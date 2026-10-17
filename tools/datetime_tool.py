from datetime import datetime, timezone
from typing import Any

from tools.base import Tool


class DateTimeTool(Tool):

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return (
            "Returns the current UTC date and time as an ISO 8601 timestamp, "
            "together with the day of the week."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, str]:
        now = self.now()

        # The weekday is computed here because models asked to derive it
        # from the timestamp named the wrong day (see evaluation results).
        return {
            "datetime": now.isoformat(),
            "weekday": now.strftime("%A"),
        }

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
