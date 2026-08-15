from fastapi.testclient import TestClient

from app import api


class FailingPipeline:
    def __init__(self, error):
        self.error = error

    def run(self, question):
        raise self.error


def test_chat_returns_service_unavailable_when_ai_connection_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(ConnectionError("connection failed")),
    )
    client = TestClient(api.app)

    response = client.post("/chat", json={"question": "Hello"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable."
    }


def test_chat_returns_bad_gateway_when_ai_response_is_invalid(monkeypatch):
    monkeypatch.setattr(
        api,
        "pipeline",
        FailingPipeline(ValueError("invalid planner response")),
    )
    client = TestClient(api.app)

    response = client.post("/chat", json={"question": "Hello"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The AI service returned an invalid response."
    }


def test_chat_rejects_blank_question():
    client = TestClient(api.app)

    response = client.post("/chat", json={"question": "   "})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "question"]


def test_chat_rejects_question_that_exceeds_maximum_length():
    client = TestClient(api.app)

    response = client.post("/chat", json={"question": "a" * 4_001})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "question"]


def test_ready_returns_ready_when_ai_service_is_available(monkeypatch):
    monkeypatch.setattr(api.generator, "is_available", lambda: True)
    client = TestClient(api.app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_service_unavailable_when_ai_service_is_down(
    monkeypatch,
):
    monkeypatch.setattr(api.generator, "is_available", lambda: False)
    client = TestClient(api.app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable."
    }
