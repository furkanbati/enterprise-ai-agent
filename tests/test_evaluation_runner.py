import json

import pytest

from app.models import AgentResult, AgentStep
from evaluation.dataset import EvalCase
from evaluation.report import render_markdown, report_stem, write_reports
from evaluation.runner import Evaluator


def calculator_step(result=None, success=True):
    return AgentStep(
        tool="calculator",
        arguments={"expression": "6 * 7"},
        success=success,
        result=result,
        error=None if success else "Unsupported expression",
    )


CASES = [
    EvalCase(
        id="greeting",
        category="no_tool",
        question="Say hello.",
        answer_contains=["hello"],
    ),
    EvalCase(
        id="multiply",
        category="single_tool",
        question="What is 6 * 7?",
        required_tools=["calculator"],
        answer_number=42,
    ),
]


class ScriptedAgent:
    """Returns queued results (or raises queued exceptions) per question."""

    def __init__(self, outcomes):
        self.outcomes = {q: list(results) for q, results in outcomes.items()}
        self.questions = []

    def run(self, question):
        self.questions.append(question)
        outcome = self.outcomes[question].pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def make_report(repeats=2):
    agent = ScriptedAgent(
        {
            "Say hello.": [
                AgentResult(answer="Hello!"),
                AgentResult(answer="Hi there!"),
            ],
            "What is 6 * 7?": [
                AgentResult(answer="42", steps=[calculator_step(42)]),
                # Correct number, but stated by the model after a failed call.
                AgentResult(
                    answer="It is 42.",
                    steps=[calculator_step(success=False)],
                ),
            ],
        }
    )
    records = []

    report = Evaluator(agent, repeats=repeats, on_run=records.append).evaluate(
        CASES
    )

    return report, agent, records


def test_evaluator_runs_each_case_repeatedly():
    report, agent, records = make_report()

    assert agent.questions == [
        "Say hello.",
        "Say hello.",
        "What is 6 * 7?",
        "What is 6 * 7?",
    ]
    assert [(r.case_id, r.repeat) for r in records] == [
        ("greeting", 1),
        ("greeting", 2),
        ("multiply", 1),
        ("multiply", 2),
    ]


def test_evaluator_aggregates_rates():
    report, _, _ = make_report()

    overall = report.overall
    assert overall.runs == 4
    assert overall.pass_rate == 0.75
    assert overall.tool_selection_rate == 1.0
    assert overall.answer_accuracy == 0.75
    assert overall.tool_verified_rate == 0.5
    assert overall.mean_steps == 0.5

    by_name = {group.name: group for group in report.categories}
    assert by_name["no_tool"].pass_rate == 0.5
    assert by_name["no_tool"].tool_verified_rate is None
    assert by_name["single_tool"].pass_rate == 1.0
    assert by_name["single_tool"].tool_verified_rate == 0.5


def test_case_summary_counts_failure_reasons():
    report, _, _ = make_report()

    greeting = report.cases[0]
    assert (greeting.passed, greeting.runs) == (1, 2)
    assert greeting.failures == ["answer contains none of: hello (1/2)"]


def test_agent_errors_are_recorded_as_failed_runs():
    agent = ScriptedAgent(
        {"What is 6 * 7?": [ValueError("Generator returned an empty response.")]}
    )

    report = Evaluator(agent, repeats=1).evaluate([CASES[1]])

    record = report.runs[0]
    assert record.passed is False
    assert record.error == "ValueError: Generator returned an empty response."
    assert record.failures == ["agent error: ValueError"]
    assert report.overall.errors == 1


def test_evaluator_rejects_invalid_repeats():
    with pytest.raises(ValueError, match="at least 1"):
        Evaluator(ScriptedAgent({}), repeats=0)


def test_reports_are_written_as_json_and_markdown(tmp_path):
    report, _, _ = make_report()
    metadata = {"Model": "qwen2.5:7b"}

    json_path, markdown_path = write_reports(
        report,
        tmp_path,
        "qwen2.5:7b",
        metadata,
    )

    assert json_path.name == "qwen2.5-7b.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["metadata"] == metadata
    assert data["overall"]["pass_rate"] == 0.75

    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown == render_markdown(report, metadata)
    assert "| **overall** | 4 | 75% | 100% | 75% | 50% |" in markdown
    assert "| `greeting` | no_tool | 1/2 |" in markdown
    assert "### `greeting` (run 2)" in markdown
    assert "answer: Hi there!" in markdown


def test_report_stem_makes_safe_file_names():
    assert report_stem("qwen2.5:7b") == "qwen2.5-7b"
    assert report_stem("library/llama3.1:8b") == "library-llama3.1-8b"
