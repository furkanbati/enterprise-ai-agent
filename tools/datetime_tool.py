from datetime import datetime, timezone
from typing import Any

from tools.base import Tool


class DateTimeTool(Tool):

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return "Returns the current date and time."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        return datetime.now(timezone.utc).isoformat()