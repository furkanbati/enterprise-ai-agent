import json
import re
from dataclasses import asdict
from pathlib import Path

from evaluation.runner import EvaluationReport, GroupSummary, RunRecord


MAX_TRACE_TEXT = 160


def report_stem(model: str) -> str:
    """File name for a model's report, e.g. 'qwen2.5:7b' -> 'qwen2.5-7b'."""

    return re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-") or "model"


def write_reports(
    report: EvaluationReport,
    output_dir: str | Path,
    model: str,
    metadata: dict[str, str],
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = report_stem(model)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"

    json_path.write_text(
        json.dumps(
            {"metadata": metadata, **asdict(report)},
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown(report, metadata),
        encoding="utf-8",
    )

    return json_path, markdown_path


def render_markdown(report: EvaluationReport, metadata: dict[str, str]) -> str:
    lines = [
        "# Agent Evaluation Report",
        "",
        *[f"- **{key}:** {value}" for key, value in metadata.items()],
        f"- **Cases:** {len(report.cases)}, each run {report.repeats} "
        f"time(s) ({report.overall.runs} runs)",
        "",
        "## Summary",
        "",
        _summary_header(),
        _summary_row(report.overall, bold=True),
        *[_summary_row(group) for group in report.categories],
        "",
        "- **Pass:** tool selection and answer checks both passed.",
        "- **Answer:** answer accuracy, over runs whose case defines an "
        "answer check.",
        "- **Tool-verified:** the expected number was produced by a tool "
        "rather than stated by the model, over cases with a numeric answer.",
        "",
        "## Cases",
        "",
        "| Case | Category | Passed | Failure reasons |",
        "|---|---|---|---|",
    ]

    for case in report.cases:
        reasons = "; ".join(case.failures) or "—"
        lines.append(
            f"| `{case.case_id}` | {case.category} | "
            f"{case.passed}/{case.runs} | {_escape(reasons)} |"
        )

    failing = _first_failure_per_case(report.runs)

    if failing:
        lines += [
            "",
            "## Failure Traces",
            "",
            "The first failing run of each case.",
        ]

        questions = {case.case_id: case.question for case in report.cases}

        for record in failing:
            lines += [
                "",
                f"### `{record.case_id}` (run {record.repeat})",
                "",
                f"**Question:** {questions[record.case_id]}",
                "",
                "```text",
                *_trace_lines(record),
                "```",
            ]

    return "\n".join(lines).rstrip() + "\n"


def _summary_header() -> str:
    return (
        "| Group | Runs | Pass | Tool selection | Answer | Tool-verified "
        "| Mean steps | Mean latency (s) | Errors |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )


def _summary_row(group: GroupSummary, bold: bool = False) -> str:
    name = f"**{group.name}**" if bold else group.name

    return (
        f"| {name} | {group.runs} | {_pct(group.pass_rate)} "
        f"| {_pct(group.tool_selection_rate)} "
        f"| {_pct(group.answer_accuracy)} "
        f"| {_pct(group.tool_verified_rate)} "
        f"| {group.mean_steps:.1f} | {group.mean_latency_s:.1f} "
        f"| {group.errors} |"
    )


def _first_failure_per_case(runs: list[RunRecord]) -> list[RunRecord]:
    seen: set[str] = set()
    failing: list[RunRecord] = []

    for record in runs:
        if not record.passed and record.case_id not in seen:
            seen.add(record.case_id)
            failing.append(record)

    return failing


def _trace_lines(record: RunRecord) -> list[str]:
    lines = []

    for index, step in enumerate(record.steps, start=1):
        if step["success"]:
            outcome = _short(step["result"])
        elif step.get("rejected"):
            outcome = f"rejected: {_short(step['error'])}"
        else:
            outcome = f"error: {_short(step['error'])}"

        arguments = json.dumps(step["arguments"], ensure_ascii=False)
        lines.append(f"{index}. {step['tool']} {arguments} -> {outcome}")

    if record.error:
        lines.append(f"agent error: {_short(record.error)}")
    else:
        lines.append(f"answer: {_short(record.answer)}")

    lines.append(f"failed: {'; '.join(record.failures)}")

    return lines


def _short(value) -> str:
    text = " ".join(str(value).split())

    if len(text) <= MAX_TRACE_TEXT:
        return text

    return text[:MAX_TRACE_TEXT] + "…"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _escape(text: str) -> str:
    return text.replace("|", "\\|")
