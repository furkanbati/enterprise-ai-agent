from datetime import date
from typing import Any

from tools.base import Tool


class DateDiffTool(Tool):
    """Counts the days between two calendar dates.

    Added because the evaluation showed the model doing date arithmetic
    itself after calling the datetime tool, and getting it wrong ("89 days
    until Christmas" instead of 69). The calculator cannot work with dates.
    """

    @property
    def name(self) -> str:
        return "date_diff"

    @property
    def description(self) -> str:
        return (
            "Returns the number of days from the start date to the end date. "
            "The result is negative if the end date is before the start date. "
            "Use the datetime tool first to get today's date."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format.",
                    "maxLength": 10,
                },
                "end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format.",
                    "maxLength": 10,
                },
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> int:
        start = self._parse(arguments["start"], "start")
        end = self._parse(arguments["end"], "end")

        return (end - start).days

    @staticmethod
    def _parse(value: str, field: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid {field} date '{value}'. Use YYYY-MM-DD, "
                "for example 2026-12-25."
            ) from exc
