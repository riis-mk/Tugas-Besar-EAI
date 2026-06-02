"""
RabbitMQ Consumer — Integration Layer entry point.

Topology created here (idempotent):

  library.exchange  (topic)
        │  routing_key: book.return.#
        ▼
  library.events.queue  ──(on nack/reject)──▶  library.dlx  ──▶  library.dlq

Pattern highlights:
  • Publish-Subscribe  : topic exchange + binding pattern "book.return.#"
  • Dead-Letter Queue  : x-dead-letter-exchange on the main queue
  • prefetch_count=1   : back-pressure — one in-flight message per consumer
"""
from __future__ import annotations

import logging
import os
import time

import pika
import pika.channel
import pika.spec
from pika.exceptions import AMQPConnectionError

from app.translators.json_to_cdm import map_json_to_cdm
from app.router import route_event

logger = logging.getLogger(__name__)

RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

MAIN_EXCHANGE = "library.exchange"
MAIN_QUEUE    = "library.events.queue"
DLX_EXCHANGE  = "library.dlx"
DLQ_QUEUE     = "library.dlq"
DLQ_ROUTING   = "library.dead"
BINDING_KEY   = "book.return.#"


def _declare_topology(ch: pika.channel.Channel) -> None:
    # 1. Dead-Letter Exchange + Queue
    ch.exchange_declare(exchange=DLX_EXCHANGE, exchange_type="direct", durable=True)
    ch.queue_declare(queue=DLQ_QUEUE, durable=True)
    ch.queue_bind(queue=DLQ_QUEUE, exchange=DLX_EXCHANGE, routing_key=DLQ_ROUTING)

    # 2. Main Exchange (topic — supports wildcard routing keys)
    ch.exchange_declare(exchange=MAIN_EXCHANGE, exchange_type="topic", durable=True)

    # 3. Main Queue with DLQ as the dead-letter target
    ch.queue_declare(
        queue=MAIN_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange":    DLX_EXCHANGE,
            "x-dead-letter-routing-key": DLQ_ROUTING,
        },
    )
    ch.queue_bind(queue=MAIN_QUEUE, exchange=MAIN_EXCHANGE, routing_key=BINDING_KEY)

    logger.info(
        "Topology ready — exchange=%s  queue=%s  dlq=%s",
        MAIN_EXCHANGE, MAIN_QUEUE, DLQ_QUEUE,
    )


def _on_message(
    ch: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    props: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    msg_id = getattr(props, "message_id", "n/a")
    logger.info("← Message received  id=%s  routing_key=%s", msg_id, method.routing_key)

    try:
        # ── EIP: Message Translator ─────────────────────────────────
        event = map_json_to_cdm(body)
        logger.info("CDM mapped  event_type=%s  student_nim=%s", event.event_type, event.student.nim)

        # ── EIP: Content-Based Router ───────────────────────────────
        route_event(event)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("✓ ACK  id=%s", msg_id)

    except ValueError as exc:
        # Permanently malformed — no retry value; send straight to DLQ
        logger.error("✗ REJECT (bad payload, → DLQ)  id=%s  reason=%s", msg_id, exc)
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as exc:
        if method.redelivered:
            # Already retried once; give up and dead-letter
            logger.error("✗ REJECT (retry exhausted, → DLQ)  id=%s  reason=%s", msg_id, exc)
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        else:
            # Transient failure (downstream down, timeout) — requeue once
            logger.warning("↺ NACK (requeue)  id=%s  reason=%s", msg_id, exc)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer() -> None:
    """Connect and consume forever, reconnecting on transient failures."""
    while True:
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            params.heartbeat = 60
            params.blocked_connection_timeout = 300

            connection = pika.BlockingConnection(params)
            ch = connection.channel()
            ch.basic_qos(prefetch_count=1)

            _declare_topology(ch)

            ch.basic_consume(queue=MAIN_QUEUE, on_message_callback=_on_message)
            logger.info("Integration Layer listening on queue '%s' …", MAIN_QUEUE)
            ch.start_consuming()

        except AMQPConnectionError as exc:
            logger.error("RabbitMQ unreachable (%s). Retry in 5 s …", exc)
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Consumer stopped by operator.")
            break
        except Exception as exc:
            logger.exception("Unexpected consumer error: %s. Retry in 5 s …", exc)
            time.sleep(5)
