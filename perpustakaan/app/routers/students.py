from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models

router = APIRouter()


class StudentCreate(BaseModel):
    nim: str
    name: str


@router.post("/", status_code=201)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Student).filter(models.Student.nim == payload.nim).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student already registered")
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
    return student
