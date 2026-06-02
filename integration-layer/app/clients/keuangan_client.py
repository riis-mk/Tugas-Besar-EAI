"""
HTTP client for the Keuangan SOAP service.

Sends the pre-built SOAP envelope, parses the response, and returns the
fine_id string.  SOAP faults are raised as RuntimeError so the consumer
can decide whether to retry or dead-letter.
"""
from __future__ import annotations

import logging
import os

import requests
from lxml import etree

from app.cdm.models import LateFeeEventCDM
from app.translators.cdm_to_soap import build_create_fine_envelope

logger = logging.getLogger(__name__)

KEUANGAN_SOAP_URL: str = os.getenv("KEUANGAN_SOAP_URL", "http://keuangan:8000/soap")
TNS = "http://keuangan.eai.university/soap"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


def call_create_fine(event: LateFeeEventCDM) -> str:
    """POST a CreateFine SOAP request and return the new fine_id.

    Raises:
        requests.RequestException: network / HTTP error.
        RuntimeError: SOAP Fault returned by the server.
    """
    envelope = build_create_fine_envelope(event)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{TNS}#CreateFine"',
    }

    logger.info("POST SOAP CreateFine → %s  (student=%s)", KEUANGAN_SOAP_URL, event.student.nim)
    response = requests.post(
        KEUANGAN_SOAP_URL,
        data=envelope,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()

    root = etree.fromstring(response.content)

    # Surface any SOAP Fault immediately
    fault = root.find(f".//{{{SOAP_NS}}}Fault")
    if fault is not None:
        faultstring = fault.findtext("faultstring", default="Unknown SOAP Fault")
        raise RuntimeError(f"SOAP Fault from Keuangan service: {faultstring}")

    result = root.find(f".//{{{TNS}}}CreateFineResult")
    if result is None or not result.text:
        raise RuntimeError("CreateFineResult element missing from SOAP response")

    fine_id: str = result.text.strip()
    logger.info("Fine created in Keuangan: fine_id=%s", fine_id)
    return fine_id
