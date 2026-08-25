from fastapi.testclient import TestClient

from app import api
from app.executor import Executor
from app.pipeline import Pipeline
from app.planner import Planner


class ControlledGenerator:
    def __init__(self, responses):
        self.responses = iter(responses)

    def generate(
        self,
        prompt,
        system_prompt=None,
        json_mode=False,
    ):
        return next(self.responses)


def build_test_pipeline(responses):
    generator = ControlledGenerator(responses)

    planner = Planner(
        generator=generator,
        registry=api.registry,
    )

    executor = Executor(
        registry=api.registry,
    )

    return Pipeline(
        planner=planner,
        executor=executor,
        generator=generator,
    )


def test_chat_e2e_with_calculator(monkeypatch):
    pipeline = build_test_pipeline(
        [
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "2 + 2"}}'
            ),
            "The answer is 4.",
        ]
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        pipeline,
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "What is 2 + 2?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The answer is 4.",
        "tool": "calculator",
        "arguments": {
            "expression": "2 + 2",
        },
        "tool_result": 4,
        "error": None,
    }


def test_chat_e2e_without_tool(monkeypatch):
    pipeline = build_test_pipeline(
        [
            '{"tool": null, "arguments": {}}',
            "Hello! How can I help you?",
        ]
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        pipeline,
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Hello! How can I help you?",
        "tool": None,
        "arguments": None,
        "tool_result": None,
        "error": None,
    }


def test_chat_validation_does_not_reach_pipeline(monkeypatch):
    class PipelineMustNotBeCalled:
        def run(self, question):
            raise AssertionError(
                "Pipeline must not be called for invalid input."
            )

    monkeypatch.setattr(
        api,
        "pipeline",
        PipelineMustNotBeCalled(),
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "question",
    ]


def test_chat_e2e_recovers_after_tool_failure(monkeypatch):
    pipeline = build_test_pipeline(
        [
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "1 / 0"}}'
            ),
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "10 / 2"}}'
            ),
            "The answer is 5.",
        ]
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        pipeline,
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "What is 10 / 2?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The answer is 5.",
        "tool": "calculator",
        "arguments": {
            "expression": "10 / 2",
        },
        "tool_result": 5,
        "error": None,
    }


def test_chat_e2e_returns_failure_after_replan_limit(
    monkeypatch,
):
    pipeline = build_test_pipeline(
        [
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "1 / 0"}}'
            ),
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "1 / 0"}}'
            ),
            (
                '{"tool": "calculator", '
                '"arguments": {"expression": "1 / 0"}}'
            ),
            "Could not complete request.",
        ]
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        pipeline,
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Calculate 1 / 0"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Could not complete request.",
        "tool": "calculator",
        "arguments": {
            "expression": "1 / 0",
        },
        "tool_result": None,
        "error": "division by zero",
    }