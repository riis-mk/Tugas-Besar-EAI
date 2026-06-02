from fastapi import FastAPI
from app.database import engine, Base
from app.routers import students

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SIAKAD Service", version="1.0.0")

app.include_router(students.router, prefix="/students", tags=["students"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "siakad"}
