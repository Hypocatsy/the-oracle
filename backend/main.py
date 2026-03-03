import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import UPLOAD_DIR, CHROMA_PERSIST_DIR
from routers import books, query

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

app = FastAPI(title="The Oracle", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(query.router)


@app.get("/health")
def health():
    return {"status": "ok"}
