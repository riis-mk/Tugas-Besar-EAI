"""
HTTP client for the SIAKAD REST service.
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
