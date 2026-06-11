from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.publisher import publish_late_return_event
from app.siakad_client import get_student_from_siakad

router = APIRouter()


class LoanCreate(BaseModel):
    book_id: str
    student_nim: str
    loan_date: date
    due_date: date


class ReturnPayload(BaseModel):
    return_date: date


def _get_or_sync_student(nim: str, db: Session) -> models.Student:
    """
    Ambil mahasiswa dari cache lokal. Jika belum ada, sync dari SIAKAD terlebih dahulu.
    Raises HTTPException 404 jika NIM tidak terdaftar di SIAKAD.
    """
    student = db.query(models.Student).filter(models.Student.nim == nim).first()
    if student:
        return student

    siakad_data = get_student_from_siakad(nim)
    if not siakad_data:
        raise HTTPException(
            status_code=404,
            detail=f"Mahasiswa NIM {nim} tidak ditemukan di SIAKAD. Pastikan mahasiswa sudah terdaftar di SIAKAD.",
        )

    student = models.Student(nim=siakad_data["nim"], name=siakad_data["name"])
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.post("/", status_code=201)
def create_loan(payload: LoanCreate, db: Session = Depends(get_db)):
    # Validasi mahasiswa via SIAKAD (auto-sync jika belum ada di cache lokal)
    student = _get_or_sync_student(payload.student_nim, db)

    book = db.query(models.Book).filter(models.Book.id == payload.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Buku tidak ditemukan")

    loan = models.Loan(
        book_id=payload.book_id,
        student_id=student.id,
        loan_date=payload.loan_date,
        due_date=payload.due_date,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


@router.patch("/{loan_id}/return")
def return_book(loan_id: str, payload: ReturnPayload, db: Session = Depends(get_db)):
    loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Peminjaman tidak ditemukan")
    if loan.return_date:
        raise HTTPException(status_code=400, detail="Buku sudah dikembalikan sebelumnya")

    loan.return_date = payload.return_date
    db.commit()
    db.refresh(loan)

    # Trigger integration event jika terlambat
    if payload.return_date > loan.due_date:
        overdue_days = (payload.return_date - loan.due_date).days
        publish_late_return_event(
            loan=loan,
            book=loan.book,
            student=loan.student,
            overdue_days=overdue_days,
        )

    return loan
