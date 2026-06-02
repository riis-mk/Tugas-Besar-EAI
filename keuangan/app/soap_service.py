"""
Keuangan SOAP Service (Spyne)

Exposes a single operation: CreateFine
WSDL available at: GET /soap?wsdl
"""
from __future__ import annotations

import logging

from spyne import Application, ServiceBase, Unicode, Integer as SpyneInt
from spyne import rpc
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication

from app.database import SessionLocal, engine, Base
from app import models

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

TNS = "http://keuangan.eai.university/soap"


class KeuanganService(ServiceBase):

    @rpc(
        Unicode, Unicode, Unicode, Unicode, Unicode, SpyneInt, Unicode,
        _returns=Unicode,
        _in_variable_names={
            "student_nim":  "studentNim",
            "student_name": "studentName",
            "loan_id":      "loanId",
            "book_title":   "bookTitle",
            "total_fee":    "totalFee",
            "overdue_days": "overdueDays",
            "currency":     "currency",
        },
    )
    def CreateFine(ctx, student_nim, student_name, loan_id, book_title,
                   total_fee, overdue_days, currency):
        """Create a fine record and return the generated fine_id."""
        db = SessionLocal()
        try:
            fine = models.Fine(
                student_nim=student_nim,
                student_name=student_name,
                loan_id=loan_id,
                book_title=book_title,
                total_fee=total_fee,
                overdue_days=overdue_days,
                currency=currency or "IDR",
                status="ACTIVE",
            )
            db.add(fine)
            db.commit()
            db.refresh(fine)
            logger.info("Fine created: id=%s student=%s amount=%s", fine.id, student_nim, total_fee)
            return fine.id
        except Exception as exc:
            db.rollback()
            logger.error("CreateFine failed: %s", exc)
            raise
        finally:
            db.close()


soap_application = Application(
    [KeuanganService],
    tns=TNS,
    in_protocol=Soap11(validator="lxml"),
    out_protocol=Soap11(),
)

wsgi_soap_app = WsgiApplication(soap_application)
