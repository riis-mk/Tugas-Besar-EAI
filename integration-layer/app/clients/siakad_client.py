"""
HTTP client untuk SIAKAD REST service.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

SIAKAD_REST_URL: str = os.getenv("SIAKAD_REST_URL", "http://siakad:8000")


def suspend_student(student_nim: str, reason: str) -> dict:
    """PATCH /students/{nim}/status → SUSPENDED.

    Raises:
        requests.RequestException: network / HTTP error.
    """
    url = f"{SIAKAD_REST_URL}/students/{student_nim}/status"
    payload = {"status": "SUSPENDED", "reason": reason}

    logger.info("PATCH %s  reason=%r", url, reason[:60])
    response = requests.patch(url, json=payload, timeout=15)
    response.raise_for_status()

    data: dict = response.json()
    logger.info(
        "SIAKAD updated: nim=%s  %s → %s",
        student_nim,
        data.get("old_status"),
        data.get("new_status"),
    )
    return data


def update_library_debt(student_nim: str, amount: float, notes: str) -> dict:
    """PATCH /students/{nim}/library-debt — tambahkan catatan utang perpustakaan ke SIAKAD.

    Raises:
        requests.RequestException: network / HTTP error.
    """
    url = f"{SIAKAD_REST_URL}/students/{student_nim}/library-debt"
    payload = {"amount": amount, "notes": notes}

    logger.info("PATCH %s  amount=%s", url, amount)
    response = requests.patch(url, json=payload, timeout=15)
    response.raise_for_status()

    data: dict = response.json()
    logger.info(
        "SIAKAD library debt updated: nim=%s  total_debt=%s",
        student_nim,
        data.get("library_debt"),
    )
    return data
