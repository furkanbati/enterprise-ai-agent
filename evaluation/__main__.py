"""Evaluate the agent against the labelled cases with a real model.

Usage (with Ollama reachable at OLLAMA_HOST):

    python -m evaluation
    python -m evaluation --model llama3.1:8b --repeats 5
    python -m evaluation --categories chain date
"""

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agent import Agent
from app.config import AGENT_MAX_STEPS, CHAT_MODEL, OLLAMA_HOST
from app.executor import Executor
from app.generator import Generator
from app.tool_registry import ToolRegistry
from evaluation.dataset import CATEGORIES, load_cases
from evaluation.report import write_reports
from evaluation.runner import Evaluator, RunRecord
from evaluation.tools import EVALUATION_NOW, FixedDateTimeTool
from tools.calculator import CalculatorTool


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "agent_cases.jsonl"
DEFAULT_OUTPUT = Path(__file__).parent / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation",
        description="Evaluate the agent against labelled cases.",
    )
    parser.add_argument("--model", default=CHAT_MODEL)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=CATEGORIES,
        help="Only run cases from these categories.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Tool failures are expected during evaluation; keep the output readable.
    logging.getLogger().setLevel(logging.ERROR)

    cases = load_cases(args.dataset)

    if args.categories:
        cases = [case for case in cases if case.category in args.categories]

    generator = Generator(model=args.model)

    if not generator.is_available():
        raise SystemExit(
            f"Model '{args.model}' is not available at {OLLAMA_HOST}. "
            f"Pull it first: ollama pull {args.model}"
        )

    registry = ToolRegistry([CalculatorTool(), FixedDateTimeTool()])
    agent = Agent(
        generator=generator,
        executor=Executor(registry),
        registry=registry,
    )

    total = len(cases) * args.repeats
    completed = 0

    def show_progress(record: RunRecord) -> None:
        nonlocal completed
        completed += 1
        status = "pass" if record.passed else "FAIL"
        print(
            f"[{completed:>3}/{total}] {status} {record.case_id} "
            f"(run {record.repeat}, {record.latency_s:.1f}s)",
            flush=True,
        )

    started = time.perf_counter()
    evaluator = Evaluator(agent, repeats=args.repeats, on_run=show_progress)
    report = evaluator.evaluate(cases)
    duration_min = (time.perf_counter() - started) / 60

    metadata = {
        "Model": args.model,
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "Dataset": args.dataset.name,
        "Evaluation clock": EVALUATION_NOW.isoformat(),
        "Agent max steps": str(AGENT_MAX_STEPS),
        "Duration": f"{duration_min:.1f} min",
    }

    json_path, markdown_path = write_reports(
        report,
        args.output,
        args.model,
        metadata,
    )

    overall = report.overall
    print(
        f"\nPass rate {overall.pass_rate:.0%} over {overall.runs} runs. "
        f"Reports: {markdown_path}, {json_path}"
    )


if __name__ == "__main__":
    main()
