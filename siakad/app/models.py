import uuid
from sqlalchemy import Column, Float, String, Text
from app.database import Base


class Student(Base):
    __tablename__ = "students"
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nim             = Column(String(20), unique=True, nullable=False)
    name            = Column(String(200), nullable=False)
    academic_status = Column(String(20), default="ACTIVE")   # ACTIVE | SUSPENDED | GRADUATED
    program_studi   = Column(String(100))
    angkatan        = Column(String(4))

    # Informasi utang dari Perpustakaan (diupdate oleh Integration Layer)
    library_debt        = Column(Float, default=0.0, nullable=False)
    library_debt_notes  = Column(Text, nullable=True)
