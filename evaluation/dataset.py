import json
from dataclasses import dataclass, field
from pathlib import Path


CATEGORIES = (
    "no_tool",
    "single_tool",
    "date",
    "chain",
    "multi_step",
    "self_correction",
    "rejection",
)


@dataclass
class EvalCase:
    """One question with the behaviour expected from the agent.

    Tool expectations: every tool in ``required_tools`` must be called, and
    no tool outside ``required_tools`` and ``allowed_tools`` may be called.
    An empty ``required_tools`` with no ``allowed_tools`` means the agent
    must answer without tools.

    Answer expectations (at most one kind):
    - ``answer_number``: a number in the answer must match, within
      ``tolerance``.
    - ``answer_contains``: the answer must contain one of these phrases,
      case-insensitively.
    - ``expect_rejection``: a tool must reject the request, and the agent
      must not return a successful tool result afterwards.
    """

    id: str
    category: str
    question: str
    required_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    answer_number: float | None = None
    tolerance: float = 1e-6
    answer_contains: list[str] = field(default_factory=list)
    expect_rejection: bool = False


def load_cases(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []

    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                case = EvalCase(**json.loads(line))
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(
                    f"Invalid evaluation case on line {line_number}: {exc}"
                ) from exc

            _validate(case)
            cases.append(case)

    ids = [case.id for case in cases]

    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case ids must be unique.")

    return cases


def _validate(case: EvalCase) -> None:
    if case.category not in CATEGORIES:
        raise ValueError(
            f"Case '{case.id}' has unknown category '{case.category}'."
        )

    answer_checks = sum(
        [
            case.answer_number is not None,
            bool(case.answer_contains),
            case.expect_rejection,
        ]
    )

    if answer_checks > 1:
        raise ValueError(
            f"Case '{case.id}' defines more than one answer check."
        )

    if case.tolerance < 0:
        raise ValueError(f"Case '{case.id}' has a negative tolerance.")
