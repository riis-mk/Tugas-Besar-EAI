from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.publisher import publish_late_return_event

router = APIRouter()


class LoanCreate(BaseModel):
    book_id: str
    student_nim: str
    loan_date: date
    due_date: date


class ReturnPayload(BaseModel):
    return_date: date


@router.post("/", status_code=201)
def create_loan(payload: LoanCreate, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.nim == payload.student_nim).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not registered in library system")
    book = db.query(models.Book).filter(models.Book.id == payload.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
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
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.return_date:
        raise HTTPException(status_code=400, detail="Book already returned")

    loan.return_date = payload.return_date
    db.commit()
    db.refresh(loan)

    # Trigger integration event if returned late
    if payload.return_date > loan.due_date:
        overdue_days = (payload.return_date - loan.due_date).days
        publish_late_return_event(
            loan=loan,
            book=loan.book,
            student=loan.student,
            overdue_days=overdue_days,
        )

    return loan
