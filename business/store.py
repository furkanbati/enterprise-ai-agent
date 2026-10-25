import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from business.seed import CUSTOMERS, ORDERS, POLICIES


RETURN_WINDOW_DAYS = 30

# A shipment counts as late this many days after its estimated delivery,
# matching the shipping policy.
LATE_AFTER_DAYS = 3

TICKET_NUMBER_OFFSET = 1000

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    member_since TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    placed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    carrier TEXT,
    tracking_number TEXT,
    shipped_at TEXT,
    estimated_delivery TEXT,
    delivered_at TEXT,
    cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders(id),
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    order_id TEXT REFERENCES orders(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

ORDER_COLUMNS = (
    "carrier",
    "tracking_number",
    "shipped_at",
    "estimated_delivery",
    "delivered_at",
    "cancelled_at",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BusinessStore:
    """The store's customer, order and ticket data in SQLite.

    The database is created and filled with the demo data on first use.
    Each call opens its own connection, because tools run in the
    executor's worker threads. Values that depend on today's date (return
    eligibility, late deliveries) are computed here with ``clock``, so the
    model does not have to do date arithmetic.
    """

    def __init__(
        self,
        path: str | Path,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.path = Path(path)
        self.clock = clock
        self._initialized = False
        self._lock = threading.Lock()

    # --- customers -------------------------------------------------------

    def find_customers(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        pattern = f"%{query.strip().lower()}%"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, email, tier, member_since FROM customers
                WHERE lower(email) LIKE ? OR lower(name) LIKE ? OR id = ?
                ORDER BY id LIMIT ?
                """,
                (pattern, pattern, query.strip().upper(), limit),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, email, tier, member_since FROM customers "
                "WHERE id = ?",
                (customer_id,),
            ).fetchone()

        return dict(row) if row else None

    # --- orders ----------------------------------------------------------

    def list_orders(
        self,
        customer_id: str,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM orders WHERE customer_id = ?"
        parameters: list[Any] = [customer_id]

        if status:
            query += " AND status = ?"
            parameters.append(status)

        query += " ORDER BY placed_at DESC LIMIT ?"
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            orders = [
                self._order_summary(connection, dict(row)) for row in rows
            ]

        return orders

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()

            if row is None:
                return None

            order = dict(row)
            items = self._items(connection, order_id)

        today = self.clock().date()
        result: dict[str, Any] = {
            "order_id": order["id"],
            "customer_id": order["customer_id"],
            "placed_at": order["placed_at"],
            "status": order["status"],
            "items": [
                {
                    "sku": item["sku"],
                    "name": item["name"],
                    "quantity": item["quantity"],
                    "unit_price": _money(item["unit_price_cents"]),
                }
                for item in items
            ],
            "total": _money(_total_cents(items)),
            "currency": "EUR",
        }

        for column in ORDER_COLUMNS:
            if order[column] is not None:
                result[column] = order[column]

        result.update(_delivery_facts(order, today))

        return result

    # --- tickets ---------------------------------------------------------

    def create_ticket(
        self,
        customer_id: str,
        category: str,
        priority: str,
        summary: str,
        order_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Open a ticket, or return the open one for the same issue.

        Returns the ticket and whether it was created. A model can repeat a
        call, and a timed-out call keeps running in its thread, so an open
        ticket for the same customer, order and category is reused instead
        of creating a duplicate.
        """

        created_at = self.clock().isoformat(timespec="seconds")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                """
                SELECT * FROM tickets
                WHERE customer_id = ? AND order_id IS ? AND category = ?
                  AND status = 'open'
                """,
                (customer_id, order_id, category),
            ).fetchone()

            if existing is not None:
                connection.commit()
                return _ticket(dict(existing)), False

            cursor = connection.execute(
                """
                INSERT INTO tickets
                    (customer_id, order_id, category, priority, summary,
                     status, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?)
                """,
                (customer_id, order_id, category, priority, summary, created_at),
            )
            row = connection.execute(
                "SELECT * FROM tickets WHERE number = ?",
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        return _ticket(dict(row)), True

    def list_tickets(self, customer_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tickets WHERE customer_id = ? ORDER BY number",
                (customer_id,),
            ).fetchall()

        return [_ticket(dict(row)) for row in rows]

    # --- policies --------------------------------------------------------

    def search_policies(self, query: str, limit: int = 2) -> list[dict[str, str]]:
        """Return the policy sections whose words overlap most with the query.

        A keyword match over six short sections; a document search over
        real policy documents would replace it.
        """

        words = _words(query)
        scored = []

        for policy in POLICIES:
            vocabulary = _words(
                f"{policy['title']} {policy['keywords']} {policy['text']}"
            )
            # Title and keyword matches count double.
            score = len(words & vocabulary) + len(
                words & _words(f"{policy['title']} {policy['keywords']}")
            )

            if score:
                scored.append((score, policy))

        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [
            {"id": policy["id"], "title": policy["title"], "text": policy["text"]}
            for _, policy in scored[:limit]
        ]

    # --- setup -----------------------------------------------------------

    def reset(self) -> None:
        """Delete the database so the next call starts from the demo data."""

        with self._lock:
            self.path.unlink(missing_ok=True)
            self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self._ensure_initialized()

        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return _ClosingConnection(connection)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)

            try:
                connection.executescript(SCHEMA)

                if not connection.execute(
                    "SELECT 1 FROM customers LIMIT 1"
                ).fetchone():
                    _seed(connection)

                connection.commit()
            finally:
                connection.close()

            self._initialized = True

    @staticmethod
    def _items(connection: sqlite3.Connection, order_id: str) -> list[dict]:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT sku, name, quantity, unit_price_cents FROM order_items "
                "WHERE order_id = ? ORDER BY rowid",
                (order_id,),
            ).fetchall()
        ]

    def _order_summary(
        self,
        connection: sqlite3.Connection,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        items = self._items(connection, order["id"])

        return {
            "order_id": order["id"],
            "placed_at": order["placed_at"],
            "status": order["status"],
            "items": [item["name"] for item in items],
            "total": _money(_total_cents(items)),
            "currency": "EUR",
        }


class _ClosingConnection:
    """Context manager that closes the connection, unlike sqlite3's own."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self.connection

    def __exit__(self, *exc_info) -> None:
        if self.connection.in_transaction:
            self.connection.rollback()

        self.connection.close()


def _seed(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        CUSTOMERS,
    )

    for order in ORDERS:
        connection.execute(
            """
            INSERT INTO orders
                (id, customer_id, placed_at, status, carrier, tracking_number,
                 shipped_at, estimated_delivery, delivered_at, cancelled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                order["customer_id"],
                order["placed_at"],
                order["status"],
                *(order.get(column) for column in ORDER_COLUMNS),
            ),
        )
        connection.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
            [(order["id"], *item) for item in order["items"]],
        )

    # Ticket numbers start after the offset: the first ticket is TCK-1001.
    connection.execute(
        "INSERT INTO sqlite_sequence (name, seq) VALUES ('tickets', ?)",
        (TICKET_NUMBER_OFFSET,),
    )


def _delivery_facts(order: dict[str, Any], today: date) -> dict[str, Any]:
    facts: dict[str, Any] = {}

    if order["status"] == "delivered" and order["delivered_at"]:
        window_ends = date.fromisoformat(order["delivered_at"]) + timedelta(
            days=RETURN_WINDOW_DAYS
        )
        facts["return_window_ends"] = window_ends.isoformat()
        facts["returnable"] = today <= window_ends

    if order["status"] == "shipped" and order["estimated_delivery"]:
        overdue = (today - date.fromisoformat(order["estimated_delivery"])).days
        facts["days_past_estimated_delivery"] = max(overdue, 0)
        facts["delivery_late"] = overdue >= LATE_AFTER_DAYS

    facts["cancellable"] = order["status"] == "processing"

    return facts


def _ticket(row: dict[str, Any]) -> dict[str, Any]:
    ticket = {
        "ticket_id": f"TCK-{row['number']}",
        "customer_id": row["customer_id"],
        "category": row["category"],
        "priority": row["priority"],
        "summary": row["summary"],
        "status": row["status"],
        "created_at": row["created_at"],
    }

    if row["order_id"]:
        ticket["order_id"] = row["order_id"]

    return ticket


def _total_cents(items: list[dict[str, Any]]) -> int:
    return sum(item["quantity"] * item["unit_price_cents"] for item in items)


def _money(cents: int) -> float:
    return round(cents / 100, 2)


def _words(text: str) -> set[str]:
    words = set(re.findall(r"[a-z]+", text.lower()))

    # Crude stemming so that "returns", "returned" and "return" match.
    return {re.sub(r"(ing|ed|es|s)$", "", word) or word for word in words}
