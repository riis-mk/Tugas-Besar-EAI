from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter()


class AcademicStatus(str, Enum):
    ACTIVE    = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    GRADUATED = "GRADUATED"


class StudentCreate(BaseModel):
    nim: str
    name: str
    program_studi: Optional[str] = None
    angkatan: Optional[str] = None


class StatusUpdate(BaseModel):
    status: AcademicStatus
    reason: Optional[str] = None


class LibraryDebtUpdate(BaseModel):
    """Payload dari Integration Layer untuk mencatat utang perpustakaan."""
    amount: float
    notes: Optional[str] = None


@router.post("/", status_code=201)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    student = models.Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/{nim}")
def get_student(nim: str, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.nim == nim).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {
        "id":                 student.id,
        "nim":                student.nim,
        "name":               student.name,
        "academic_status":    student.academic_status,
        "program_studi":      student.program_studi,
        "angkatan":           student.angkatan,
        "library_debt":       student.library_debt,
        "library_debt_notes": student.library_debt_notes,
    }


@router.patch("/{nim}/status")
def update_academic_status(nim: str, payload: StatusUpdate, db: Session = Depends(get_db)):
    """Dipanggil oleh Integration Layer untuk mensuspensi mahasiswa setelah keterlambatan."""
    student = db.query(models.Student).filter(models.Student.nim == nim).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    old_status = student.academic_status
    student.academic_status = payload.status
    db.commit()
    db.refresh(student)

    return {
        "nim":        student.nim,
        "name":       student.name,
        "old_status": old_status,
        "new_status": student.academic_status,
        "reason":     payload.reason,
    }


@router.patch("/{nim}/library-debt")
def update_library_debt(nim: str, payload: LibraryDebtUpdate, db: Session = Depends(get_db)):
    """
    Dipanggil oleh Integration Layer untuk mencatat/menambah utang perpustakaan.
    Nilai `amount` ditambahkan ke total utang yang sudah ada.
    """
    student = db.query(models.Student).filter(models.Student.nim == nim).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.library_debt = (student.library_debt or 0.0) + payload.amount
    if payload.notes:
        existing = student.library_debt_notes or ""
        student.library_debt_notes = (existing + "\n" + payload.notes).strip()

    db.commit()
    db.refresh(student)

    return {
        "nim":                student.nim,
        "name":               student.name,
        "library_debt":       student.library_debt,
        "library_debt_notes": student.library_debt_notes,
    }
