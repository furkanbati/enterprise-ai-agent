from fastapi.testclient import TestClient

from app import api
from app.agent import Agent
from app.executor import Executor
from app.models import ChatMessage, ChatToolCall


class ScriptedGenerator:
    def __init__(self, messages):
        self.messages = iter(messages)

    def chat(self, messages, tools=None):
        return next(self.messages)


def build_test_agent(messages):
    return Agent(
        generator=ScriptedGenerator(messages),
        executor=Executor(registry=api.registry),
        registry=api.registry,
    )


def calculator_call(expression):
    return ChatMessage(
        content="",
        tool_calls=[
            ChatToolCall(
                name="calculator",
                arguments={"expression": expression},
            )
        ],
    )


def post_question(monkeypatch, agent, question):
    monkeypatch.setattr(api, "agent", agent)

    return TestClient(api.app).post(
        "/chat",
        json={"question": question},
    )


def test_chat_e2e_with_calculator(monkeypatch):
    agent = build_test_agent(
        [
            calculator_call("2 + 2"),
            ChatMessage(content="The answer is 4."),
        ]
    )

    response = post_question(monkeypatch, agent, "What is 2 + 2?")

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
    agent = build_test_agent(
        [ChatMessage(content="Hello! How can I help you?")]
    )

    response = post_question(monkeypatch, agent, "Hello")

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Hello! How can I help you?",
        "tool": None,
        "arguments": None,
        "tool_result": None,
        "error": None,
    }


def test_chat_validation_does_not_reach_agent(monkeypatch):
    class AgentMustNotBeCalled:
        def run(self, question):
            raise AssertionError(
                "Agent must not be called for invalid input."
            )

    response = post_question(monkeypatch, AgentMustNotBeCalled(), "   ")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "question",
    ]


def test_chat_e2e_recovers_after_tool_failure(monkeypatch):
    agent = build_test_agent(
        [
            calculator_call("1 / 0"),
            calculator_call("10 / 2"),
            ChatMessage(content="The answer is 5."),
        ]
    )

    response = post_question(monkeypatch, agent, "What is 10 / 2?")

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


def test_chat_e2e_returns_failure_after_step_limit(monkeypatch):
    agent = build_test_agent(
        [calculator_call("1 / 0")] * api.agent.max_steps
        + [ChatMessage(content="Could not complete request.")]
    )

    response = post_question(monkeypatch, agent, "Calculate 1 / 0")

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
