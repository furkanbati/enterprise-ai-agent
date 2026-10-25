"""Customer support tools for the online store scenario.

The tools return only what a support conversation needs: no addresses,
phone numbers or payment details. Facts that depend on today's date
(return eligibility, late deliveries) are computed by the store, because
the evaluation showed the model getting date arithmetic wrong.
"""

from typing import Any

from business.store import BusinessStore
from tools.base import Tool


CUSTOMER_ID = {
    "type": "string",
    "description": "Customer ID, for example CUS-1001.",
    "pattern": "^CUS-[0-9]{4}$",
}

ORDER_ID = {
    "type": "string",
    "description": "Order ID, for example ORD-5001.",
    "pattern": "^ORD-[0-9]{4}$",
}

ORDER_STATUSES = ["processing", "shipped", "delivered", "cancelled"]

TICKET_CATEGORIES = [
    "delivery",
    "return",
    "refund",
    "cancellation",
    "damaged_item",
    "warranty",
    "billing",
    "other",
]


class _StoreTool(Tool):

    def __init__(self, store: BusinessStore):
        self.store = store

    def _require_customer(self, customer_id: str) -> dict[str, Any]:
        customer = self.store.get_customer(customer_id)

        if customer is None:
            raise ValueError(
                f"No customer with ID {customer_id}. "
                "Use find_customer to look up the ID."
            )

        return customer


class FindCustomerTool(_StoreTool):

    @property
    def name(self) -> str:
        return "find_customer"

    @property
    def description(self) -> str:
        return (
            "Finds customers by email address, name or customer ID. Returns "
            "up to 5 matches with their customer ID, name, email, membership "
            "tier and member-since date. If several customers match, ask "
            "which one is meant."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Email address, full or partial name, or customer ID.",
                    "minLength": 2,
                    "maxLength": 100,
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        matches = self.store.find_customers(arguments["query"])

        return {"matches": matches, "count": len(matches)}


class ListCustomerOrdersTool(_StoreTool):

    @property
    def name(self) -> str:
        return "list_customer_orders"

    @property
    def description(self) -> str:
        return (
            "Lists a customer's orders, newest first, with order ID, date, "
            "status, item names and total. Use get_order for tracking, "
            "return and cancellation details of one order."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": CUSTOMER_ID,
                "status": {
                    "type": "string",
                    "description": "Only return orders with this status.",
                    "enum": ORDER_STATUSES,
                },
            },
            "required": ["customer_id"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        customer_id = arguments["customer_id"]
        self._require_customer(customer_id)

        orders = self.store.list_orders(
            customer_id,
            status=arguments.get("status"),
        )

        return {"customer_id": customer_id, "orders": orders}


class GetOrderTool(_StoreTool):

    @property
    def name(self) -> str:
        return "get_order"

    @property
    def description(self) -> str:
        return (
            "Returns one order: items, total, status, carrier and tracking "
            "number, and dates. Delivered orders include return_window_ends "
            "and whether the order is returnable today. Shipped orders "
            "include whether the delivery is late. Also says whether the "
            "order can still be cancelled."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"order_id": ORDER_ID},
            "required": ["order_id"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        order = self.store.get_order(arguments["order_id"])

        if order is None:
            raise ValueError(
                f"No order with ID {arguments['order_id']}. Check the ID, "
                "or use list_customer_orders to find the customer's orders."
            )

        return order


class SearchPoliciesTool(_StoreTool):

    @property
    def name(self) -> str:
        return "search_policies"

    @property
    def description(self) -> str:
        return (
            "Searches the store's policies (returns, refunds, shipping and "
            "late deliveries, cancellation, warranty, damaged items) and "
            "returns the matching sections. Use it before stating any policy."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the policy question is about, e.g. 'return window'.",
                    "minLength": 2,
                    "maxLength": 200,
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        sections = self.store.search_policies(arguments["query"])

        if not sections:
            return {
                "sections": [],
                "note": "No policy matches this query. Do not invent one.",
            }

        return {"sections": sections}


class CreateSupportTicketTool(_StoreTool):

    @property
    def name(self) -> str:
        return "create_support_ticket"

    @property
    def description(self) -> str:
        return (
            "Opens a support ticket for a customer, for follow-up by the "
            "support team. Only use it when the user asks for a ticket or "
            "the issue needs follow-up, such as a late or damaged delivery. "
            "If an open ticket already exists for the same customer, order "
            "and category, that ticket is returned instead of a new one."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": CUSTOMER_ID,
                "order_id": ORDER_ID,
                "category": {"type": "string", "enum": TICKET_CATEGORIES},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "high for late or damaged deliveries.",
                },
                "summary": {
                    "type": "string",
                    "description": "One or two sentences describing the issue.",
                    "minLength": 10,
                    "maxLength": 500,
                },
            },
            "required": ["customer_id", "category", "priority", "summary"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        customer_id = arguments["customer_id"]
        order_id = arguments.get("order_id")

        self._require_customer(customer_id)

        if order_id is not None:
            order = self.store.get_order(order_id)

            if order is None:
                raise ValueError(f"No order with ID {order_id}.")

            if order["customer_id"] != customer_id:
                raise ValueError(
                    f"Order {order_id} does not belong to customer "
                    f"{customer_id}."
                )

        ticket, created = self.store.create_ticket(
            customer_id=customer_id,
            order_id=order_id,
            category=arguments["category"],
            priority=arguments["priority"],
            summary=arguments["summary"].strip(),
        )

        return {**ticket, "created": created}


def support_tools(store: BusinessStore) -> list[Tool]:
    return [
        FindCustomerTool(store),
        ListCustomerOrdersTool(store),
        GetOrderTool(store),
        SearchPoliciesTool(store),
        CreateSupportTicketTool(store),
    ]
