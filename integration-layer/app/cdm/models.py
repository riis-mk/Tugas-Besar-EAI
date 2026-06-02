"""
Canonical Data Model (CDM) — technology-agnostic intermediate representation.

Every upstream message format (JSON, XML, CSV, …) must be normalised into
these models before any routing or translation takes place. This decouples
producers from consumers so that adding a new downstream system only
requires a new translator, not changes to existing ones.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventType(str, Enum):
    BOOK_RETURN_LATE = "book.return.late"


class StudentCDM(BaseModel):
    id: str
    nim: str
    name: str


class BookCDM(BaseModel):
    id: str
    title: str
    isbn: Optional[str] = None


class LoanCDM(BaseModel):
    id: str
    due_date: datetime
    return_date: datetime
    overdue_days: int
    fee_per_day: Decimal
    total_fee: Decimal
    currency: str = "IDR"


class LateFeeEventCDM(BaseModel):
    """CDM for a student returning a book after the due date."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    student: StudentCDM
    book: BookCDM
    loan: LoanCDM
