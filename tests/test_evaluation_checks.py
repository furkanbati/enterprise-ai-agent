import json

import pytest

from app.models import AgentResult, AgentStep
from evaluation.checks import check, extract_numbers
from evaluation.dataset import CATEGORIES, EvalCase, load_cases
from evaluation.tools import EVALUATION_NOW, FixedDateTimeTool


def step(tool="calculator", success=True, result=None, rejected=False):
    return AgentStep(
        tool=tool,
        arguments={},
        success=success,
        result=result,
        error=None if success else "error",
        rejected=rejected,
    )


def case(**overrides):
    values = {"id": "c1", "category": "single_tool", "question": "Q?"}
    values.update(overrides)

    return EvalCase(**values)


# ----------------------------
# Dataset
# ----------------------------

def write_cases(tmp_path, *cases):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "\n".join(json.dumps(c) for c in cases) + "\n",
        encoding="utf-8",
    )

    return path


def test_bundled_dataset_is_valid_and_covers_every_category():
    cases = load_cases("evaluation/datasets/agent_cases.jsonl")

    assert len(cases) >= 20
    assert {c.category for c in cases} == set(CATEGORIES)


def test_load_cases_rejects_unknown_category(tmp_path):
    path = write_cases(
        tmp_path,
        {"id": "a", "category": "magic", "question": "Q?"},
    )

    with pytest.raises(ValueError, match="unknown category"):
        load_cases(path)


def test_load_cases_rejects_duplicate_ids(tmp_path):
    path = write_cases(
        tmp_path,
        {"id": "a", "category": "no_tool", "question": "Q1?"},
        {"id": "a", "category": "no_tool", "question": "Q2?"},
    )

    with pytest.raises(ValueError, match="unique"):
        load_cases(path)


def test_load_cases_rejects_more_than_one_answer_check(tmp_path):
    path = write_cases(
        tmp_path,
        {
            "id": "a",
            "category": "single_tool",
            "question": "Q?",
            "answer_number": 1,
            "answer_contains": ["one"],
        },
    )

    with pytest.raises(ValueError, match="more than one answer check"):
        load_cases(path)


def test_load_cases_reports_invalid_line(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"id": "a"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_cases(path)


# ----------------------------
# Number extraction
# ----------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234 * 5678 = 7,006,652.", [1234, 5678, 7006652]),
        ("The square root is approximately 11.225.", [11.225]),
        ("It is -3 degrees.", [-3]),
        ("15% of 2480 is 372.0", [15, 2480, 372.0]),
        ("No numbers here.", []),
    ],
)
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected


# ----------------------------
# Tool selection
# ----------------------------

def test_no_tool_case_fails_when_a_tool_is_called():
    result = check(
        case(category="no_tool"),
        AgentResult(answer="Paris", steps=[step("datetime", result="x")]),
    )

    assert result.tools_ok is False
    assert result.failures == ["unexpected tools: datetime"]


def test_missing_required_tool_fails():
    result = check(
        case(required_tools=["calculator"], answer_number=4),
        AgentResult(answer="4"),
    )

    assert result.tools_ok is False
    assert result.passed is False
    assert "missing tools: calculator" in result.failures


def test_allowed_tools_are_optional():
    chain = case(
        category="chain",
        required_tools=["datetime"],
        allowed_tools=["calculator"],
        answer_number=75,
    )

    without = check(chain, AgentResult(answer="75", steps=[step("datetime")]))
    with_calc = check(
        chain,
        AgentResult(
            answer="75",
            steps=[step("datetime"), step("calculator", result=75)],
        ),
    )

    assert without.tools_ok and with_calc.tools_ok


# ----------------------------
# Answers
# ----------------------------

def test_numeric_answer_within_tolerance_passes():
    result = check(
        case(answer_number=11.22, tolerance=0.01),
        AgentResult(answer="It is about 11.225."),
    )

    assert result.answer_ok is True


def test_numeric_answer_outside_tolerance_fails():
    result = check(
        case(answer_number=11.22, tolerance=0.001),
        AgentResult(answer="It is about 11.225."),
    )

    assert result.answer_ok is False
    assert result.failures == ["expected 11.22 in the answer"]


def test_phrase_answer_is_case_insensitive():
    result = check(
        case(category="date", answer_contains=["saturday"]),
        AgentResult(answer="Today is Saturday."),
    )

    assert result.answer_ok is True


def test_case_without_answer_check_passes_on_tools_alone():
    result = check(
        case(category="no_tool"),
        AgentResult(answer="An API is an interface."),
    )

    assert result.answer_ok is None
    assert result.passed is True


# ----------------------------
# Rejection
# ----------------------------

def test_rejection_case_passes_when_the_tool_rejects():
    result = check(
        case(
            category="rejection",
            required_tools=["calculator"],
            expect_rejection=True,
        ),
        AgentResult(
            answer="That number is too large.",
            steps=[step(success=False, rejected=True)],
        ),
    )

    assert result.answer_ok is True


def test_rejection_case_fails_when_the_model_shrinks_the_request():
    # The model computed 2 ** 10 instead of the requested value.
    result = check(
        case(
            category="rejection",
            required_tools=["calculator"],
            expect_rejection=True,
        ),
        AgentResult(answer="It is 1024.", steps=[step(result=1024)]),
    )

    assert result.answer_ok is False
    assert result.failures == ["no tool rejected the request"]


def test_rejection_case_fails_on_success_after_rejection():
    result = check(
        case(
            category="rejection",
            required_tools=["calculator"],
            expect_rejection=True,
        ),
        AgentResult(
            answer="It is 1024.",
            steps=[
                step(success=False, rejected=True),
                step(result=1024),
            ],
        ),
    )

    assert result.answer_ok is False
    assert result.failures == ["a tool succeeded after the rejection"]


# ----------------------------
# Tool verification
# ----------------------------

def test_answer_is_tool_verified_when_a_tool_produced_it():
    result = check(
        case(answer_number=1024),
        AgentResult(
            answer="1024",
            steps=[step(success=False), step(result=1024)],
        ),
    )

    assert result.tool_verified is True


def test_answer_is_not_tool_verified_when_the_model_computed_it():
    # The tool failed and the model stated the corrected value itself.
    result = check(
        case(answer_number=1024),
        AgentResult(answer="1024", steps=[step(success=False)]),
    )

    assert result.answer_ok is True
    assert result.tool_verified is False


def test_tool_verification_does_not_apply_without_a_numeric_answer():
    result = check(
        case(category="date", answer_contains=["2026"]),
        AgentResult(answer="2026", steps=[step("datetime", result="2026")]),
    )

    assert result.tool_verified is None


# ----------------------------
# Fixed clock
# ----------------------------

def test_fixed_datetime_tool_matches_the_real_tool_interface():
    tool = FixedDateTimeTool()

    assert tool.name == "datetime"
    assert tool.execute({}) == "2026-10-17T09:00:00+00:00"
    assert tool.now == EVALUATION_NOW
