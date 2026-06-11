from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.siakad_client import get_student_from_siakad

router = APIRouter()


@router.get("/{nim}")
def get_student(nim: str, db: Session = Depends(get_db)):
    """
    Cari mahasiswa di cache lokal. Jika belum ada, ambil dari SIAKAD dan simpan otomatis.
    Pendaftaran manual tidak didukung — SIAKAD adalah sumber data otoritatif.
    """
    student = db.query(models.Student).filter(models.Student.nim == nim).first()
    if student:
        return student

    # Fetch dari SIAKAD jika belum ada di cache lokal
    siakad_data = get_student_from_siakad(nim)
    if not siakad_data:
        raise HTTPException(
            status_code=404,
            detail=f"Mahasiswa dengan NIM {nim} tidak ditemukan di SIAKAD",
        )

    student = models.Student(nim=siakad_data["nim"], name=siakad_data["name"])
    db.add(student)
    db.commit()
    db.refresh(student)
    return student
