"""Demo data for the customer support scenario: an online electronics store.

The dates are chosen around the evaluation clock (2026-10-17), so that the
data contains a late delivery, a return window that has just closed, one
that is still open, and orders that can still be cancelled.
"""

CUSTOMERS = [
    # id, name, email, tier, member_since
    ("CUS-1001", "Elif Yılmaz", "elif.yilmaz@example.com", "gold", "2023-03-12"),
    ("CUS-1002", "Daniel Weber", "daniel.weber@example.com", "standard", "2025-11-02"),
    ("CUS-1003", "Sofia Rossi", "sofia.rossi@example.com", "standard", "2024-06-20"),
    ("CUS-1004", "Mehmet Kaya", "mehmet.kaya@example.com", "silver", "2022-09-01"),
    ("CUS-1005", "Hannah Schmidt", "hannah.schmidt@example.com", "standard", "2026-08-15"),
    ("CUS-1006", "Elif Demir", "elif.demir@example.com", "standard", "2025-02-10"),
]

ORDERS = [
    {
        "id": "ORD-5001",
        "customer_id": "CUS-1001",
        "placed_at": "2026-10-02",
        "status": "shipped",
        "carrier": "DHL",
        "tracking_number": "DHL-7781203345",
        "shipped_at": "2026-10-03",
        "estimated_delivery": "2026-10-08",
        "items": [("AUD-220", "Noise-cancelling headphones", 1, 24900)],
    },
    {
        "id": "ORD-5002",
        "customer_id": "CUS-1001",
        "placed_at": "2026-09-10",
        "status": "delivered",
        "carrier": "UPS",
        "tracking_number": "UPS-1Z993A0410",
        "shipped_at": "2026-09-11",
        "estimated_delivery": "2026-09-15",
        "delivered_at": "2026-09-14",
        "items": [
            ("CHG-065", "USB-C charger 65W", 2, 2990),
            ("STD-110", "Aluminium laptop stand", 1, 4500),
        ],
    },
    {
        "id": "ORD-5003",
        "customer_id": "CUS-1002",
        "placed_at": "2026-10-14",
        "status": "processing",
        "items": [("MON-427", "27-inch 4K monitor", 1, 38900)],
    },
    {
        "id": "ORD-5004",
        "customer_id": "CUS-1002",
        "placed_at": "2026-09-28",
        "status": "delivered",
        "carrier": "DHL",
        "tracking_number": "DHL-7780551920",
        "shipped_at": "2026-09-29",
        "estimated_delivery": "2026-10-02",
        "delivered_at": "2026-10-01",
        "items": [
            ("KEY-087", "Mechanical keyboard", 1, 11900),
            ("MOU-301", "Wireless mouse", 1, 5900),
        ],
    },
    {
        "id": "ORD-5005",
        "customer_id": "CUS-1003",
        "placed_at": "2026-10-09",
        "status": "delivered",
        "carrier": "GLS",
        "tracking_number": "GLS-60451877",
        "shipped_at": "2026-10-10",
        "estimated_delivery": "2026-10-15",
        "delivered_at": "2026-10-13",
        "items": [("WAT-045", "Smartwatch", 1, 19900)],
    },
    {
        "id": "ORD-5006",
        "customer_id": "CUS-1004",
        "placed_at": "2026-08-20",
        "status": "cancelled",
        "cancelled_at": "2026-08-21",
        "items": [("TAB-110", "10-inch tablet", 1, 32900)],
    },
    {
        "id": "ORD-5007",
        "customer_id": "CUS-1004",
        "placed_at": "2026-10-12",
        "status": "shipped",
        "carrier": "UPS",
        "tracking_number": "UPS-1Z993A0877",
        "shipped_at": "2026-10-13",
        "estimated_delivery": "2026-10-20",
        "items": [
            ("CAM-108", "1080p webcam", 1, 7900),
            ("LGT-012", "LED ring light", 1, 3450),
        ],
    },
    {
        "id": "ORD-5008",
        "customer_id": "CUS-1005",
        "placed_at": "2026-10-15",
        "status": "processing",
        "items": [("CAS-014", "Phone case", 3, 1990)],
    },
]

POLICIES = [
    {
        "id": "returns",
        "title": "Returns",
        "keywords": "return send back exchange refund window days",
        "text": (
            "Items can be returned within 30 days of delivery if they are "
            "in their original condition. Opened software and personalised "
            "items cannot be returned. Return shipping is free for gold and "
            "silver members; other customers pay 4.90 EUR."
        ),
    },
    {
        "id": "refunds",
        "title": "Refunds",
        "keywords": "refund money back payment reimburse",
        "text": (
            "Refunds are issued to the original payment method within 5 to 7 "
            "business days after the returned item arrives at the warehouse. "
            "For cancelled orders the refund is issued within 2 business days."
        ),
    },
    {
        "id": "shipping",
        "title": "Shipping and late deliveries",
        "keywords": "shipping delivery late delayed arrive tracking carrier lost",
        "text": (
            "Standard shipping takes 3 to 5 business days after dispatch and "
            "is free. If an order has not arrived 3 days after its estimated "
            "delivery date, it is treated as late: open a delivery ticket so "
            "the shipment can be traced, and offer a replacement or a refund "
            "if the carrier cannot locate it."
        ),
    },
    {
        "id": "cancellation",
        "title": "Order cancellation",
        "keywords": "cancel cancellation stop order",
        "text": (
            "Orders can be cancelled free of charge until they are shipped. "
            "Orders that have already shipped cannot be cancelled and must be "
            "returned after delivery instead."
        ),
    },
    {
        "id": "warranty",
        "title": "Warranty",
        "keywords": "warranty broken defect faulty repair guarantee",
        "text": (
            "All electronics have a 2-year warranty covering manufacturing "
            "defects. Accidental damage is not covered. Warranty claims need "
            "the order number and a description of the fault."
        ),
    },
    {
        "id": "damaged",
        "title": "Damaged items",
        "keywords": "damaged broken arrived crushed defective box",
        "text": (
            "Items that arrive damaged must be reported within 7 days of "
            "delivery, with a photo of the item and the packaging. A "
            "replacement is sent once the report is confirmed."
        ),
    },
]
