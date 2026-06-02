"""
EIP: Content-Based Router

Inspects the CDM event_type and dispatches to the correct handler chain.
Adding a new event type = adding a new elif branch + handler function,
with zero changes to the consumer or translators.
"""
from __future__ import annotations

import logging

from app.cdm.models import EventType, LateFeeEventCDM
from app.clients.keuangan_client import call_create_fine
from app.clients.siakad_client import suspend_student

logger = logging.getLogger(__name__)


def route_event(event: LateFeeEventCDM) -> None:
    """Main routing decision point."""
    if event.event_type == EventType.BOOK_RETURN_LATE:
        _handle_late_return(event)
    else:
        logger.warning("No route defined for event_type=%s — message discarded", event.event_type)


# ── Private handlers ────────────────────────────────────────────────────────

def _handle_late_return(event: LateFeeEventCDM) -> None:
    """
    Orchestrates the late-return flow:
      1. Keuangan  — create fine (SOAP/XML)
      2. SIAKAD    — suspend student (REST/JSON)   ← only if step 1 succeeds
    """
    nim = event.student.nim

    logger.info(
        "[Router] BOOK_RETURN_LATE  student=%s  loan=%s  fee=%s %s  days=%d",
        nim, event.loan.id, event.loan.total_fee, event.loan.currency, event.loan.overdue_days,
    )

    # Step 1: bill the student
    fine_id = call_create_fine(event)

    # Step 2: suspend academic access (only after billing confirms)
    reason = (
        f"Keterlambatan pengembalian buku \"{event.book.title}\" "
        f"selama {event.loan.overdue_days} hari. "
        f"Denda: {event.loan.currency} {event.loan.total_fee}. "
        f"Referensi tagihan: {fine_id}."
    )
    suspend_student(student_nim=nim, reason=reason)

    logger.info(
        "[Router] Flow selesai — event_id=%s  fine_id=%s  student=%s SUSPENDED",
        event.event_id, fine_id, nim,
    )
