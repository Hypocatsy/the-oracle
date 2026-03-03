import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from openai import OpenAI

from config import (
    CHAT_MODEL,
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    MAX_UPLOAD_SIZE,
    OPENAI_API_KEY,
    UPLOAD_DIR,
)
from models.schemas import BookResponse, ChapterInfo, UpdateTopicRequest
from services.chunker import chunk_sections, chunk_text
from services.embeddings import generate_embeddings
from services.epub_parser import extract_epub_sections, extract_epub_text, get_chapters_cached
from services.vector_store import (
    _noop_ef,
    delete_book_chunks,
    get_chroma_client,
    store_chunks,
)

router = APIRouter(prefix="/api/books", tags=["books"])

BOOKS_JSON = os.path.join(UPLOAD_DIR, "books.json")


def _load_books() -> list[dict]:
    if not os.path.exists(BOOKS_JSON):
        return []
    try:
        with open(BOOKS_JSON, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        import logging
        logging.getLogger(__name__).error("books.json is corrupt, resetting: %s", e)
        return []


def _save_books(books: list[dict]) -> None:
    with open(BOOKS_JSON, "w") as f:
        json.dump(books, f, indent=2)


def _generate_summary(chunks: list[str], title: str) -> str:
    """Generate a 2-sentence book summary from the first few chunks."""
    preview = "\n\n".join(chunks[:3])
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You summarize books concisely based on excerpt text.",
            },
            {
                "role": "user",
                "content": (
                    f'The book is titled "{title}". '
                    f"Here are opening excerpts:\n\n{preview}\n\n"
                    "Summarize this book in 2 sentences."
                ),
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _ingest_book(book_id: str, file_path: str, title: str) -> None:
    """Background task: extract, chunk, embed, store."""
    try:
        sections = extract_epub_sections(file_path)
        if not sections:
            raise ValueError("No readable text found")

        chunked = chunk_sections(
            sections,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            model=EMBEDDING_MODEL,
        )

        all_chunks = [c["text"] for c in chunked]
        all_metadatas = [
            {
                "book_id": book_id,
                "book_title": title,
                "chapter": c["chapter"],
                "section": c["section"] or "",
            }
            for c in chunked
        ]

        embeddings = generate_embeddings(all_chunks, model=EMBEDDING_MODEL)

        client = get_chroma_client(CHROMA_PERSIST_DIR)
        store_chunks(client, book_id, all_chunks, embeddings, all_metadatas)

        # Generate AI summary from opening chunks
        summary = None
        try:
            summary = _generate_summary(all_chunks, title)
        except Exception:
            pass  # non-critical — summary can be backfilled later

        # Re-load books fresh to avoid clobbering backfill data
        books = _load_books()
        for book in books:
            if book["id"] == book_id:
                # Derive unique chapters from sections for chapter list
                chapters = extract_epub_text(file_path)
                book["status"] = "ready"
                book["chunk_count"] = len(all_chunks)
                book["chapter_count"] = len(chapters)
                book["chapters"] = [
                    {"index": i, "title": ch["chapter"]}
                    for i, ch in enumerate(chapters)
                ]
                if summary:
                    book["summary"] = summary
                break
        _save_books(books)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Ingestion failed for book %s: %s", book_id, e)
        books = _load_books()
        for book in books:
            if book["id"] == book_id:
                book["status"] = "error"
                book["error"] = str(e)
                break
        _save_books(books)


@router.post("/upload", response_model=BookResponse)
async def upload_book(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only EPUB files are supported")

    books = _load_books()
    for book in books:
        if book["filename"] == file.filename:
            raise HTTPException(
                status_code=409, detail="A book with this name already exists"
            )

    book_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{book_id}.epub")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB",
        )
    with open(file_path, "wb") as f:
        f.write(content)

    title = file.filename.rsplit(".", 1)[0].replace("_", " ")

    book_record = {
        "id": book_id,
        "title": title,
        "filename": file.filename,
        "file_type": "epub",
        "status": "processing",
        "chunk_count": 0,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "topic": "",
    }
    books.append(book_record)
    _save_books(books)

    background_tasks.add_task(_ingest_book, book_id, file_path, title)

    return BookResponse(**book_record)


@router.get("/topics")
async def list_topics():
    books = _load_books()
    topics = sorted({b.get("topic", "") for b in books if b.get("topic")})
    return {"topics": topics}


@router.get("", response_model=list[BookResponse])
async def list_books():
    books = _load_books()
    return [BookResponse(**b) for b in books]


@router.patch("/{book_id}/topic")
async def update_book_topic(book_id: str, req: UpdateTopicRequest):
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book["topic"] = req.topic
    _save_books(books)
    return {"updated": True, "topic": req.topic}


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Remove file
    file_path = os.path.join(UPLOAD_DIR, f"{book_id}.epub")
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove from ChromaDB
    try:
        client = get_chroma_client(CHROMA_PERSIST_DIR)
        delete_book_chunks(client, book_id)
    except Exception:
        pass  # collection may not exist yet

    books = [b for b in books if b["id"] != book_id]
    _save_books(books)

    return {"deleted": True}


@router.get("/{book_id}/summary")
async def get_book_summary(book_id: str):
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Return cached summary if available
    if book.get("summary"):
        return {
            "summary": book["summary"],
            "chapter_count": book.get("chapter_count", 0),
        }

    # Backfill: fetch chunks from ChromaDB and generate summary
    try:
        client = get_chroma_client(CHROMA_PERSIST_DIR)
        collection = client.get_collection(
            name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef
        )
        results = collection.get(
            where={"book_id": book_id},
            include=["documents"],
            limit=3,
        )
        chunks = results.get("documents", [])
        if not chunks:
            raise HTTPException(
                status_code=404, detail="No chunks found for this book"
            )

        summary = _generate_summary(chunks, book["title"])

        # Persist back to books.json
        book["summary"] = summary
        _save_books(books)

        return {
            "summary": summary,
            "chapter_count": book.get("chapter_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate summary: {e}"
        )


def _get_book_or_404(book_id: str) -> tuple[dict, list[dict]]:
    """Helper to find a book or raise 404."""
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book, books


def _backfill_chapters(book: dict, books: list[dict]) -> list[dict]:
    """Load chapters from EPUB if not stored in books.json yet."""
    if book.get("chapters"):
        return book["chapters"]
    file_path = os.path.join(UPLOAD_DIR, f"{book['id']}.epub")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="EPUB file not found")
    parsed = list(get_chapters_cached(file_path))
    chapter_list = [
        {"index": i, "title": ch["chapter"]} for i, ch in enumerate(parsed)
    ]
    book["chapters"] = chapter_list
    book["chapter_count"] = len(chapter_list)
    _save_books(books)
    return chapter_list


@router.get("/{book_id}/chapters")
async def list_chapters(book_id: str):
    book, books = _get_book_or_404(book_id)
    chapters = _backfill_chapters(book, books)
    return [ChapterInfo(**ch) for ch in chapters]


@router.get("/{book_id}/chapters/by-title")
async def get_chapter_by_title(book_id: str, title: str):
    book, books = _get_book_or_404(book_id)
    file_path = os.path.join(UPLOAD_DIR, f"{book['id']}.epub")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="EPUB file not found")
    parsed = list(get_chapters_cached(file_path))
    for i, ch in enumerate(parsed):
        if ch["chapter"] == title:
            return {"index": i, "title": ch["chapter"], "text": ch["text"]}
    raise HTTPException(status_code=404, detail="Chapter not found")


@router.get("/{book_id}/chapters/{chapter_index}")
async def get_chapter_by_index(book_id: str, chapter_index: int):
    book, books = _get_book_or_404(book_id)
    file_path = os.path.join(UPLOAD_DIR, f"{book['id']}.epub")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="EPUB file not found")
    parsed = list(get_chapters_cached(file_path))
    if chapter_index < 0 or chapter_index >= len(parsed):
        raise HTTPException(status_code=404, detail="Chapter index out of range")
    ch = parsed[chapter_index]
    return {"index": chapter_index, "title": ch["chapter"], "text": ch["text"]}
