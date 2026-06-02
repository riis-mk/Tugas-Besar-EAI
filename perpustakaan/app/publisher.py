"""
EIP: Publish-Subscribe (publisher side)

Publishes domain events to the library.exchange topic exchange.
The Integration Layer (subscriber) binds to routing key "book.return.#".
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

import pika

logger = logging.getLogger(__name__)

RABBITMQ_URL   = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME  = "library.exchange"
FEE_PER_DAY    = 5_000.0   # IDR


def publish_late_return_event(loan, book, student, overdue_days: int) -> None:
    """Fire-and-forget publish; logs on failure but does not crash the HTTP handler."""
    total_fee = overdue_days * FEE_PER_DAY

    payload = {
        "event_id":   str(uuid4()),
        "event_type": "book.return.late",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "student": {
            "id":   str(student.id),
            "nim":  student.nim,
            "name": student.name,
        },
        "book": {
            "id":    str(book.id),
            "title": book.title,
            "isbn":  book.isbn,
        },
        "loan": {
            "id":           str(loan.id),
            "due_date":     loan.due_date.isoformat(),
            "return_date":  loan.return_date.isoformat(),
            "overdue_days": overdue_days,
            "fee_per_day":  str(FEE_PER_DAY),
            "total_fee":    str(total_fee),
            "currency":     "IDR",
        },
    }

    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="book.return.late",
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,            # persistent
                message_id=payload["event_id"],
            ),
        )
        connection.close()
        logger.info("Published late-return event %s for loan %s", payload["event_id"], loan.id)

    except Exception as exc:
        logger.error("Failed to publish event for loan %s: %s", loan.id, exc)
