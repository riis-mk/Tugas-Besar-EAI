"""
EIP: Message Translator

Converts the raw JSON bytes published by the Perpustakaan service into the
Canonical Data Model (CDM).  Any field-name mismatches, unit conversions, or
type coercions live here so the rest of the integration layer never touches
raw wire formats.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

from app.cdm.models import (
    BookCDM,
    EventType,
    LateFeeEventCDM,
    LoanCDM,
    StudentCDM,
)

logger = logging.getLogger(__name__)


def map_json_to_cdm(raw_body: bytes) -> LateFeeEventCDM:
    """Parse *raw_body* (UTF-8 JSON) and return a validated CDM object.

    Raises:
        ValueError: payload is malformed JSON or is missing required fields.
    """
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Non-JSON payload received: {exc}") from exc

    try:
        student_raw = data["student"]
        book_raw = data["book"]
        loan_raw = data["loan"]

        return LateFeeEventCDM(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            student=StudentCDM(
                id=student_raw["id"],
                nim=student_raw["nim"],
                name=student_raw["name"],
            ),
            book=BookCDM(
                id=book_raw["id"],
                title=book_raw["title"],
                isbn=book_raw.get("isbn"),
            ),
            loan=LoanCDM(
                id=loan_raw["id"],
                due_date=datetime.fromisoformat(loan_raw["due_date"]),
                return_date=datetime.fromisoformat(loan_raw["return_date"]),
                overdue_days=int(loan_raw["overdue_days"]),
                fee_per_day=Decimal(str(loan_raw["fee_per_day"])),
                total_fee=Decimal(str(loan_raw["total_fee"])),
                currency=loan_raw.get("currency", "IDR"),
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"CDM mapping failed — missing/invalid field: {exc}") from exc
