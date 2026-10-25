import threading
from datetime import datetime, timezone

import pytest

from app.agent import Agent
from app.executor import Executor
from app.models import ChatMessage, ChatToolCall, ToolCall
from app.tool_registry import ToolRegistry
from business.store import BusinessStore
from tools.support import support_tools


NOW = datetime(2026, 10, 17, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return BusinessStore(tmp_path / "business.db", clock=lambda: NOW)


@pytest.fixture
def executor(store):
    return Executor(ToolRegistry(support_tools(store)), timeout=2.0, max_retries=0)


def run(executor, tool, **arguments):
    return executor.execute(ToolCall(tool=tool, arguments=arguments))


# --- store -----------------------------------------------------------------


def test_database_is_created_with_demo_data_on_first_use(tmp_path):
    store = BusinessStore(tmp_path / "nested" / "business.db")

    assert not store.path.exists()
    assert store.get_customer("CUS-1001")["name"] == "Elif Yılmaz"
    assert store.path.exists()


def test_late_shipment_is_computed_from_the_clock(store):
    order = store.get_order("ORD-5001")

    assert order["days_past_estimated_delivery"] == 9
    assert order["delivery_late"] is True
    assert order["cancellable"] is False


def test_shipment_within_estimate_is_not_late(store):
    order = store.get_order("ORD-5007")

    assert order["days_past_estimated_delivery"] == 0
    assert order["delivery_late"] is False


@pytest.mark.parametrize(
    ("order_id", "window_ends", "returnable"),
    [
        ("ORD-5002", "2026-10-14", False),
        ("ORD-5004", "2026-10-31", True),
    ],
)
def test_return_window_is_computed_from_the_delivery_date(
    store, order_id, window_ends, returnable
):
    order = store.get_order(order_id)

    assert order["return_window_ends"] == window_ends
    assert order["returnable"] is returnable


def test_order_totals_are_computed_from_items(store):
    order = store.get_order("ORD-5002")

    assert order["total"] == 104.8
    assert [item["quantity"] for item in order["items"]] == [2, 1]


def test_only_processing_orders_are_cancellable(store):
    assert store.get_order("ORD-5003")["cancellable"] is True
    assert store.get_order("ORD-5006")["cancellable"] is False


def test_policy_search_ranks_the_matching_section_first(store):
    assert store.search_policies("can I cancel my order")[0]["id"] == "cancellation"
    assert store.search_policies("my delivery is late")[0]["id"] == "shipping"
    assert store.search_policies("pizza") == []


def test_reset_restores_the_demo_data(store):
    store.create_ticket("CUS-1001", "delivery", "high", "Package is late.", "ORD-5001")

    store.reset()

    assert store.list_tickets("CUS-1001") == []


def test_concurrent_identical_tickets_create_one_ticket(store):
    results = []

    def create():
        results.append(
            store.create_ticket(
                "CUS-1001", "delivery", "high", "Package is late.", "ORD-5001"
            )
        )

    threads = [threading.Thread(target=create) for _ in range(5)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert sum(created for _, created in results) == 1
    assert len({ticket["ticket_id"] for ticket, _ in results}) == 1
    assert len(store.list_tickets("CUS-1001")) == 1


# --- tools -----------------------------------------------------------------


def test_find_customer_returns_all_matches(executor):
    result = run(executor, "find_customer", query="elif")

    assert result.success
    assert [match["id"] for match in result.result["matches"]] == [
        "CUS-1001",
        "CUS-1006",
    ]


def test_find_customer_by_email_returns_no_private_details(executor):
    result = run(executor, "find_customer", query="daniel.weber@example.com")

    assert result.result["matches"] == [
        {
            "id": "CUS-1002",
            "name": "Daniel Weber",
            "email": "daniel.weber@example.com",
            "tier": "standard",
            "member_since": "2025-11-02",
        }
    ]


def test_list_customer_orders_filters_by_status(executor):
    result = run(
        executor, "list_customer_orders", customer_id="CUS-1002", status="delivered"
    )

    assert [order["order_id"] for order in result.result["orders"]] == ["ORD-5004"]


def test_list_customer_orders_rejects_unknown_customer(executor):
    result = run(executor, "list_customer_orders", customer_id="CUS-9999")

    assert not result.success
    assert "find_customer" in result.error


def test_order_id_format_is_validated_before_running(executor):
    result = run(executor, "get_order", order_id="5001")

    assert not result.success
    assert result.retryable


def test_get_order_reports_unknown_order(executor):
    result = run(executor, "get_order", order_id="ORD-9999")

    assert not result.success
    assert "No order with ID ORD-9999" in result.error


def test_search_policies_says_when_nothing_matches(executor):
    result = run(executor, "search_policies", query="pizza")

    assert result.result["sections"] == []
    assert "Do not invent" in result.result["note"]


def test_create_ticket_reuses_the_open_ticket_for_the_same_issue(executor):
    arguments = {
        "customer_id": "CUS-1001",
        "order_id": "ORD-5001",
        "category": "delivery",
        "priority": "high",
        "summary": "Headphones are six days late.",
    }

    first = run(executor, "create_support_ticket", **arguments)
    second = run(executor, "create_support_ticket", **arguments)
    other = run(
        executor, "create_support_ticket", **{**arguments, "category": "refund"}
    )

    assert first.result["ticket_id"] == "TCK-1001"
    assert first.result["created"] is True
    assert second.result["ticket_id"] == "TCK-1001"
    assert second.result["created"] is False
    assert other.result["ticket_id"] == "TCK-1002"


def test_create_ticket_rejects_another_customers_order(executor):
    result = run(
        executor,
        "create_support_ticket",
        customer_id="CUS-1002",
        order_id="ORD-5001",
        category="delivery",
        priority="high",
        summary="Package has not arrived.",
    )

    assert not result.success
    assert "does not belong to customer CUS-1002" in result.error


def test_create_ticket_validates_category(executor):
    result = run(
        executor,
        "create_support_ticket",
        customer_id="CUS-1001",
        category="complaint",
        priority="high",
        summary="Package has not arrived.",
    )

    assert not result.success


# --- agent -----------------------------------------------------------------


class ScriptedGenerator:
    def __init__(self, messages):
        self.messages = list(messages)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append([dict(message) for message in messages])
        return self.messages.pop(0)


def test_agent_handles_a_late_delivery_and_opens_a_ticket(store):
    registry = ToolRegistry(support_tools(store))
    generator = ScriptedGenerator(
        [
            ChatMessage(
                content="",
                tool_calls=[
                    ChatToolCall(
                        name="find_customer",
                        arguments={"query": "elif.yilmaz@example.com"},
                    )
                ],
            ),
            ChatMessage(
                content="",
                tool_calls=[
                    ChatToolCall(name="get_order", arguments={"order_id": "ORD-5001"})
                ],
            ),
            ChatMessage(
                content="",
                tool_calls=[
                    ChatToolCall(
                        name="create_support_ticket",
                        arguments={
                            "customer_id": "CUS-1001",
                            "order_id": "ORD-5001",
                            "category": "delivery",
                            "priority": "high",
                            "summary": "ORD-5001 is 9 days past its estimate.",
                        },
                    )
                ],
            ),
            ChatMessage(content="Ticket TCK-1001 is open for ORD-5001."),
        ]
    )
    agent = Agent(
        generator=generator,
        executor=Executor(registry, timeout=2.0, max_retries=0),
        registry=registry,
    )

    result = agent.run("Elif's headphones have not arrived. Please open a ticket.")

    assert [step.tool for step in result.steps] == [
        "find_customer",
        "get_order",
        "create_support_ticket",
    ]
    assert all(step.success for step in result.steps)
    assert result.tool_result["ticket_id"] == "TCK-1001"

    # Tool results reach the model as JSON.
    order_message = generator.calls[2][-1]
    assert order_message["role"] == "tool"
    assert '"delivery_late": true' in order_message["content"]
