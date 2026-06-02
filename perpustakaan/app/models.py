import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Book(Base):
    __tablename__ = "books"
    id     = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title  = Column(String(500), nullable=False)
    isbn   = Column(String(20), unique=True)
    author = Column(String(200))


class Student(Base):
    __tablename__ = "students"
    id   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nim  = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)


class Loan(Base):
    __tablename__ = "loans"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id     = Column(String, ForeignKey("books.id"), nullable=False)
    student_id  = Column(String, ForeignKey("students.id"), nullable=False)
    loan_date   = Column(Date, nullable=False)
    due_date    = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)

    book    = relationship("Book")
    student = relationship("Student")
