from datetime import datetime, timezone

from tools.datetime_tool import DateTimeTool


# The moment every evaluation run treats as "now", so that answers to
# date questions ("days until Christmas") are stable across runs.
EVALUATION_NOW = datetime(2026, 10, 17, 9, 0, 0, tzinfo=timezone.utc)


class FixedDateTimeTool(DateTimeTool):
    """DateTimeTool with a fixed clock.

    Only the clock is replaced; the name, schema and output format are the
    real tool's, so the evaluation measures what the agent actually sees.
    """

    def __init__(self, fixed_now: datetime = EVALUATION_NOW):
        self.fixed_now = fixed_now

    def now(self) -> datetime:
        return self.fixed_now
