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
