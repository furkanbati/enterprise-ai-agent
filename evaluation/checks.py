import math
import re
from dataclasses import dataclass, field

from app.models import AgentResult
from evaluation.dataset import EvalCase


# Numbers with optional sign, thousands separators and decimals:
# "7,006,652", "-3", "11.225", "2852.0".
NUMBER_PATTERN = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


@dataclass
class CheckResult:
    tools_ok: bool
    answer_ok: bool | None
    # Whether the expected number was produced by a tool, not by the model.
    # None when the case has no numeric answer.
    tool_verified: bool | None
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.tools_ok and self.answer_ok is not False


def check(case: EvalCase, result: AgentResult) -> CheckResult:
    failures: list[str] = []

    tools_ok = _check_tools(case, result, failures)
    answer_ok = _check_answer(case, result, failures)
    tool_verified = _check_tool_verified(case, result)

    return CheckResult(
        tools_ok=tools_ok,
        answer_ok=answer_ok,
        tool_verified=tool_verified,
        failures=failures,
    )


def extract_numbers(text: str) -> list[float]:
    return [
        float(match.replace(",", ""))
        for match in NUMBER_PATTERN.findall(text)
    ]


def numbers_match(actual: float, expected: float, tolerance: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=tolerance)


def _check_tools(
    case: EvalCase,
    result: AgentResult,
    failures: list[str],
) -> bool:
    called = {step.tool for step in result.steps}
    required = set(case.required_tools)
    permitted = required | set(case.allowed_tools)

    missing = required - called
    unexpected = called - permitted

    if missing:
        failures.append(f"missing tools: {', '.join(sorted(missing))}")

    if unexpected:
        failures.append(f"unexpected tools: {', '.join(sorted(unexpected))}")

    return not missing and not unexpected


def _check_answer(
    case: EvalCase,
    result: AgentResult,
    failures: list[str],
) -> bool | None:
    answer = result.answer

    if case.answer_number is not None:
        found = extract_numbers(answer)

        if any(
            numbers_match(number, case.answer_number, case.tolerance)
            for number in found
        ):
            return True

        failures.append(
            f"expected {case.answer_number:g} in the answer"
        )
        return False

    if case.answer_contains:
        lowered = answer.lower()

        if any(phrase.lower() in lowered for phrase in case.answer_contains):
            return True

        failures.append(
            "answer contains none of: " + ", ".join(case.answer_contains)
        )
        return False

    if case.expect_rejection:
        rejected_at = next(
            (
                index
                for index, step in enumerate(result.steps)
                if step.rejected
            ),
            None,
        )

        if rejected_at is None:
            failures.append("no tool rejected the request")
            return False

        if any(step.success for step in result.steps[rejected_at + 1:]):
            failures.append("a tool succeeded after the rejection")
            return False

        if not answer.strip():
            failures.append("empty answer after the rejection")
            return False

        return True

    return None


def _check_tool_verified(
    case: EvalCase,
    result: AgentResult,
) -> bool | None:
    if case.answer_number is None:
        return None

    return any(
        numbers_match(number, case.answer_number, case.tolerance)
        for step in result.steps
        if step.success
        for number in _numbers_in(step.result)
    )


def _numbers_in(value) -> list[float]:
    """Numbers in a tool result, including those inside dicts and lists.

    Strings are not searched: "ORD-5001" is an ID, not the number 5001.
    """

    if isinstance(value, bool):
        return []

    if isinstance(value, (int, float)):
        return [value]

    if isinstance(value, dict):
        value = list(value.values())

    if isinstance(value, list):
        return [number for item in value for number in _numbers_in(item)]

    return []
