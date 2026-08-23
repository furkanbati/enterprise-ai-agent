import httpx
from fastapi.testclient import TestClient

from app import api
from app.models import AgentResult


class FailingPipeline:
    def __init__(self, error):
        self.error = error

    def run(self, question):
        raise self.error


class SuccessfulPipeline:
    def __init__(self, result):
        self.result = result

    def run(self, question):
        return self.result


class FakeResponseError(Exception):
    pass


def test_health_returns_ok():
    client = TestClient(api.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_successful_response(monkeypatch):
    result = AgentResult(
        answer="The answer is 4.",
        tool="calculator",
        arguments={"expression": "2 + 2"},
        tool_result=4,
        error=None,
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        SuccessfulPipeline(result),
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
        "arguments": {"expression": "2 + 2"},
        "tool_result": 4,
        "error": None,
    }


def test_chat_returns_service_unavailable_when_ai_connection_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(ConnectionError("connection failed")),
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable."
    }


def test_chat_returns_service_unavailable_when_ai_request_times_out(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(
            httpx.TimeoutException("request timed out"),
        ),
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable."
    }


def test_chat_returns_bad_gateway_when_ai_response_error_occurs(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "ResponseError",
        FakeResponseError,
    )

    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(
            FakeResponseError("upstream failure"),
        ),
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The AI service returned an invalid response."
    }


def test_chat_returns_bad_gateway_when_ai_response_is_invalid(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(ValueError("invalid planner response")),
    )

    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The AI service returned an invalid response."
    }

def test_chat_returns_internal_server_error_for_unexpected_exception(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(RuntimeError("internal implementation failure")),
    )

    client = TestClient(
        api.app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 500

    assert "internal implementation failure" not in response.text
    assert "Traceback" not in response.text

def test_chat_rejects_blank_question():
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


def test_chat_rejects_question_that_exceeds_maximum_length():
    client = TestClient(api.app)

    response = client.post(
        "/chat",
        json={"question": "a" * 4_001},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "question",
    ]


def test_ready_returns_ready_when_ai_service_is_available(monkeypatch):
    monkeypatch.setattr(
        api.generator,
        "is_available",
        lambda: True,
    )

    client = TestClient(api.app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_service_unavailable_when_ai_service_is_down(
    monkeypatch,
):
    monkeypatch.setattr(
        api.generator,
        "is_available",
        lambda: False,
    )

    client = TestClient(api.app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable."
    }