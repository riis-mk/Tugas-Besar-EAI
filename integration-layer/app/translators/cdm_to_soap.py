"""
EIP: Message Translator (CDM → SOAP/XML)

Converts a LateFeeEventCDM into a SOAP 1.1 envelope ready to be POSTed to the
Keuangan service.  Using lxml for programmatic XML construction avoids
string-templating pitfalls (escaping, encoding, namespace prefix clashes).
"""
from __future__ import annotations

import logging

from lxml import etree

from app.cdm.models import LateFeeEventCDM

logger = logging.getLogger(__name__)

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS = "http://keuangan.eai.university/soap"


def build_create_fine_envelope(event: LateFeeEventCDM) -> bytes:
    """Return a UTF-8 SOAP 1.1 envelope for the *CreateFine* operation.

    The element names inside <CreateFine> must match the parameter names
    declared in KeuanganService (Spyne rpc decorator).
    """
    nsmap = {"soapenv": SOAP_NS, "tns": TNS}

    envelope = etree.Element(f"{{{SOAP_NS}}}Envelope", nsmap=nsmap)
    etree.SubElement(envelope, f"{{{SOAP_NS}}}Header")   # empty header; required by Spyne validator
    body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")

    op = etree.SubElement(body, f"{{{TNS}}}CreateFine")

    fields: dict[str, str] = {
        "studentNim":  event.student.nim,
        "studentName": event.student.name,
        "loanId":      event.loan.id,
        "bookTitle":   event.book.title,
        "totalFee":    str(event.loan.total_fee),
        "overdueDays": str(event.loan.overdue_days),
        "currency":    event.loan.currency,
    }

    for tag, value in fields.items():
        child = etree.SubElement(op, tag)
        child.text = value

    xml_bytes = etree.tostring(
        envelope,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    logger.debug("SOAP envelope built:\n%s", xml_bytes.decode())
    return xml_bytes
