"""Evaluate the agent against the labelled cases with a real model.

Usage (the provider and model default to LLM_PROVIDER and CHAT_MODEL):

    python -m evaluation
    python -m evaluation --model llama3.1:8b --repeats 5
    python -m evaluation --categories chain date
    python -m evaluation --provider openai --model <model>
    python -m evaluation --provider anthropic
"""

import argparse
import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agent import Agent
from app.config import AGENT_MAX_STEPS, LLM_PROVIDER, LLM_PROVIDERS, OLLAMA_HOST
from app.executor import Executor
from app.generator import Generator
from app.providers import create_provider
from app.tool_registry import ToolRegistry
from business.store import BusinessStore
from evaluation.dataset import CATEGORIES, load_cases
from evaluation.report import write_reports
from evaluation.runner import Evaluator, RunRecord
from evaluation.tools import EVALUATION_NOW, FixedDateTimeTool
from tools.calculator import CalculatorTool
from tools.date_diff import DateDiffTool
from tools.support import support_tools


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "agent_cases.jsonl"
DEFAULT_OUTPUT = Path(__file__).parent / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation",
        description="Evaluate the agent against labelled cases.",
    )
    parser.add_argument(
        "--provider",
        choices=LLM_PROVIDERS,
        default=LLM_PROVIDER,
    )
    parser.add_argument(
        "--model",
        help="Defaults to CHAT_MODEL, or the provider's default model.",
    )
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

    generator = Generator(
        provider=create_provider(args.provider, model=args.model),
    )
    model = generator.model

    if not generator.is_available():
        if args.provider == "ollama":
            raise SystemExit(
                f"Model '{model}' is not available at {OLLAMA_HOST}. "
                f"Pull it first: ollama pull {model}"
            )

        raise SystemExit(
            f"Model '{model}' is not available from {args.provider}. "
            "Check the model name and the API key."
        )

    # A fresh copy of the demo data on the evaluation clock, so that
    # tickets from earlier runs and the real date do not change results.
    store = BusinessStore(
        Path(tempfile.mkdtemp()) / "business.db",
        clock=lambda: EVALUATION_NOW,
    )
    registry = ToolRegistry(
        [
            *support_tools(store),
            CalculatorTool(),
            FixedDateTimeTool(),
            DateDiffTool(),
        ]
    )
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
        "Provider": args.provider,
        "Model": model,
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "Dataset": args.dataset.name,
        "Evaluation clock": EVALUATION_NOW.isoformat(),
        "Agent max steps": str(AGENT_MAX_STEPS),
        "Duration": f"{duration_min:.1f} min",
    }

    json_path, markdown_path = write_reports(
        report,
        args.output,
        model,
        metadata,
    )

    overall = report.overall
    print(
        f"\nPass rate {overall.pass_rate:.0%} over {overall.runs} runs. "
        f"Reports: {markdown_path}, {json_path}"
    )


if __name__ == "__main__":
    main()
