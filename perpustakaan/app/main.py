from fastapi import FastAPI
from app.database import engine, Base
from app.routers import books, loans

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Perpustakaan Service", version="1.0.0")

app.include_router(books.router,  prefix="/books",  tags=["books"])
app.include_router(loans.router,  prefix="/loans",  tags=["loans"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "perpustakaan"}
