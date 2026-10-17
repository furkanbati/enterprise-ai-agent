import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Protocol

from app.models import AgentResult
from evaluation.checks import check
from evaluation.dataset import CATEGORIES, EvalCase


class SupportsRun(Protocol):
    def run(self, question: str) -> AgentResult:
        ...


@dataclass
class RunRecord:
    case_id: str
    category: str
    repeat: int
    passed: bool
    tools_ok: bool
    answer_ok: bool | None
    tool_verified: bool | None
    failures: list[str]
    answer: str
    steps: list[dict[str, Any]]
    latency_s: float
    error: str | None = None


@dataclass
class GroupSummary:
    name: str
    runs: int
    pass_rate: float
    tool_selection_rate: float
    # Rates over the runs where the check applies; None when it never does.
    answer_accuracy: float | None
    tool_verified_rate: float | None
    mean_steps: float
    mean_latency_s: float
    errors: int


@dataclass
class CaseSummary:
    case_id: str
    category: str
    question: str
    runs: int
    passed: int
    failures: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    repeats: int
    overall: GroupSummary
    categories: list[GroupSummary]
    cases: list[CaseSummary]
    runs: list[RunRecord]


class Evaluator:
    def __init__(
        self,
        agent: SupportsRun,
        repeats: int = 3,
        on_run: Callable[[RunRecord], None] | None = None,
    ):
        if repeats < 1:
            raise ValueError("repeats must be at least 1.")

        self.agent = agent
        self.repeats = repeats
        self.on_run = on_run

    def evaluate(self, cases: list[EvalCase]) -> EvaluationReport:
        runs: list[RunRecord] = []

        for case in cases:
            for repeat in range(1, self.repeats + 1):
                record = self._run_once(case, repeat)
                runs.append(record)

                if self.on_run is not None:
                    self.on_run(record)

        categories = [
            summarize(category, [r for r in runs if r.category == category])
            for category in CATEGORIES
            if any(r.category == category for r in runs)
        ]

        return EvaluationReport(
            repeats=self.repeats,
            overall=summarize("overall", runs),
            categories=categories,
            cases=[_summarize_case(case, runs) for case in cases],
            runs=runs,
        )

    def _run_once(self, case: EvalCase, repeat: int) -> RunRecord:
        started = time.perf_counter()

        try:
            result = self.agent.run(case.question)

        except Exception as exc:
            # A failed request is a result to report, not a reason to stop.
            return RunRecord(
                case_id=case.id,
                category=case.category,
                repeat=repeat,
                passed=False,
                tools_ok=False,
                answer_ok=False,
                tool_verified=False if case.answer_number is not None else None,
                failures=[f"agent error: {type(exc).__name__}"],
                answer="",
                steps=[],
                latency_s=time.perf_counter() - started,
                error=f"{type(exc).__name__}: {exc}",
            )

        latency_s = time.perf_counter() - started
        outcome = check(case, result)

        return RunRecord(
            case_id=case.id,
            category=case.category,
            repeat=repeat,
            passed=outcome.passed,
            tools_ok=outcome.tools_ok,
            answer_ok=outcome.answer_ok,
            tool_verified=outcome.tool_verified,
            failures=outcome.failures,
            answer=result.answer,
            steps=[asdict(step) for step in result.steps],
            latency_s=latency_s,
        )


def summarize(name: str, runs: list[RunRecord]) -> GroupSummary:
    answer_checks = [r.answer_ok for r in runs if r.answer_ok is not None]
    verified_checks = [
        r.tool_verified for r in runs if r.tool_verified is not None
    ]

    return GroupSummary(
        name=name,
        runs=len(runs),
        pass_rate=_rate(r.passed for r in runs),
        tool_selection_rate=_rate(r.tools_ok for r in runs),
        answer_accuracy=_rate(answer_checks) if answer_checks else None,
        tool_verified_rate=(
            _rate(verified_checks) if verified_checks else None
        ),
        mean_steps=mean(len(r.steps) for r in runs) if runs else 0.0,
        mean_latency_s=mean(r.latency_s for r in runs) if runs else 0.0,
        errors=sum(r.error is not None for r in runs),
    )


def _summarize_case(case: EvalCase, runs: list[RunRecord]) -> CaseSummary:
    case_runs = [r for r in runs if r.case_id == case.id]
    reasons = Counter(
        failure for r in case_runs for failure in r.failures
    )

    return CaseSummary(
        case_id=case.id,
        category=case.category,
        question=case.question,
        runs=len(case_runs),
        passed=sum(r.passed for r in case_runs),
        failures=[
            f"{reason} ({count}/{len(case_runs)})"
            for reason, count in reasons.most_common()
        ],
    )


def _rate(values) -> float:
    values = list(values)

    return sum(bool(v) for v in values) / len(values) if values else 0.0
