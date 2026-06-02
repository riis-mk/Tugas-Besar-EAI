import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Integer, DateTime
from app.database import Base


class Fine(Base):
    __tablename__ = "fines"
    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_nim  = Column(String(50),  nullable=False)
    student_name = Column(String(200), nullable=False)
    loan_id      = Column(String(36),  nullable=False, unique=True)
    book_title   = Column(String(500), nullable=False)
    overdue_days = Column(Integer,     nullable=False)
    total_fee    = Column(Numeric(15, 2), nullable=False)
    currency     = Column(String(3),   default="IDR")
    status       = Column(String(20),  default="ACTIVE")
    created_at   = Column(DateTime,    default=datetime.utcnow)
