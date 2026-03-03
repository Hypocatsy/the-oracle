"""Tool implementations for the ReAct agent loop.

Each tool is a plain function returning a dict. Never raises — returns
{"error": ...} on failure so the agent can recover gracefully.
"""

import json
import logging
import os

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    EMBEDDING_MODEL,
    TOP_K,
    UPLOAD_DIR,
)
from services.embeddings import generate_embeddings
from services.epub_parser import get_chapters_cached
from services.vector_store import _noop_ef, get_chroma_client

logger = logging.getLogger(__name__)

BOOKS_JSON = os.path.join(UPLOAD_DIR, "books.json")


def _load_books() -> list[dict]:
    if not os.path.exists(BOOKS_JSON):
        return []
    try:
        with open(BOOKS_JSON, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []


def _get_collection():
    """Get the ChromaDB collection, or None if it doesn't exist."""
    try:
        client = get_chroma_client(CHROMA_PERSIST_DIR)
        collection = client.get_collection(
            name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef
        )
        if collection.count() == 0:
            return None
        return collection
    except Exception:
        return None


def search_book(query: str, book_id: str | None = None, topic: str | None = None) -> dict:
    """Semantic vector search — embed the query and find top-k similar chunks."""
    try:
        collection = _get_collection()
        if collection is None:
            return {"error": "No books have been indexed yet."}

        query_embedding = generate_embeddings([query], model=EMBEDDING_MODEL)[0]

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": TOP_K,
            "include": ["documents", "metadatas", "distances"],
        }
        if book_id:
            query_kwargs["where"] = {"book_id": book_id}
        elif topic:
            # Scope search to all books in this topic
            books = _load_books()
            topic_book_ids = [b["id"] for b in books if b.get("topic") == topic]
            if topic_book_ids:
                if len(topic_book_ids) == 1:
                    query_kwargs["where"] = {"book_id": topic_book_ids[0]}
                else:
                    query_kwargs["where"] = {"book_id": {"$in": topic_book_ids}}

        results = collection.query(**query_kwargs)

        chunks = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            chunks.append({
                "text": results["documents"][0][i],
                "book_title": meta.get("book_title", "Unknown"),
                "chapter": meta.get("chapter", ""),
                "section": meta.get("section", ""),
                "book_id": meta.get("book_id", ""),
                "distance": results["distances"][0][i],
            })

        return {"chunks": chunks, "count": len(chunks)}
    except Exception as e:
        logger.error("search_book failed: %s", e)
        return {"error": f"Search failed: {e}"}


def get_chapter(book_id: str, chapter_title: str) -> dict:
    """Get full chapter text. Includes fuzzy fallback (case-insensitive substring match)."""
    try:
        books = _load_books()
        book = next((b for b in books if b["id"] == book_id), None)
        if not book:
            return {"error": f"Book not found: {book_id}"}

        file_path = os.path.join(UPLOAD_DIR, f"{book_id}.epub")
        if not os.path.exists(file_path):
            return {"error": "EPUB file not found on disk."}

        parsed = list(get_chapters_cached(file_path))

        # Exact match first
        for ch in parsed:
            if ch["chapter"] == chapter_title:
                return {
                    "book_title": book["title"],
                    "chapter": ch["chapter"],
                    "text": ch["text"],
                }

        # Fuzzy fallback: case-insensitive substring
        query_lower = chapter_title.lower()
        for ch in parsed:
            if query_lower in ch["chapter"].lower():
                return {
                    "book_title": book["title"],
                    "chapter": ch["chapter"],
                    "text": ch["text"],
                }

        available = [ch["chapter"] for ch in parsed]
        return {"error": f"Chapter not found: '{chapter_title}'. Available: {available}"}
    except Exception as e:
        logger.error("get_chapter failed: %s", e)
        return {"error": f"Failed to load chapter: {e}"}


def search_by_keyword(keyword: str, book_id: str | None = None, topic: str | None = None) -> dict:
    """Exact text match via ChromaDB $contains. Case-sensitive."""
    try:
        collection = _get_collection()
        if collection is None:
            return {"error": "No books have been indexed yet."}

        get_kwargs: dict = {
            "where_document": {"$contains": keyword},
            "include": ["documents", "metadatas"],
            "limit": TOP_K,
        }
        if book_id:
            get_kwargs["where"] = {"book_id": book_id}
        elif topic:
            books = _load_books()
            topic_book_ids = [b["id"] for b in books if b.get("topic") == topic]
            if topic_book_ids:
                if len(topic_book_ids) == 1:
                    get_kwargs["where"] = {"book_id": topic_book_ids[0]}
                else:
                    get_kwargs["where"] = {"book_id": {"$in": topic_book_ids}}

        results = collection.get(**get_kwargs)

        chunks = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i]
            chunks.append({
                "text": results["documents"][i],
                "book_title": meta.get("book_title", "Unknown"),
                "chapter": meta.get("chapter", ""),
                "section": meta.get("section", ""),
                "book_id": meta.get("book_id", ""),
            })

        return {"chunks": chunks, "count": len(chunks)}
    except Exception as e:
        logger.error("search_by_keyword failed: %s", e)
        return {"error": f"Keyword search failed: {e}"}


def list_books() -> dict:
    """List available books with their chapter lists."""
    try:
        books = _load_books()
        result = []
        for b in books:
            if b.get("status") != "ready":
                continue
            result.append({
                "book_id": b["id"],
                "title": b["title"],
                "topic": b.get("topic", ""),
                "chapters": [ch["title"] for ch in b.get("chapters", [])],
                "chunk_count": b.get("chunk_count", 0),
            })
        return {"books": result, "count": len(result)}
    except Exception as e:
        logger.error("list_books failed: %s", e)
        return {"error": f"Failed to list books: {e}"}


def get_surrounding_context(
    book_id: str, chapter_title: str, text_snippet: str
) -> dict:
    """Get broader context (~1500 chars) around a text snippet within a chapter."""
    chapter_result = get_chapter(book_id, chapter_title)
    if "error" in chapter_result:
        return chapter_result

    full_text = chapter_result["text"]
    pos = full_text.find(text_snippet)

    if pos == -1:
        # Try case-insensitive
        pos = full_text.lower().find(text_snippet.lower())

    if pos == -1:
        return {
            "error": "Snippet not found in chapter text. Try a shorter or different snippet."
        }

    start = max(0, pos - 500)
    end = min(len(full_text), pos + len(text_snippet) + 500)
    context = full_text[start:end]

    return {
        "book_title": chapter_result["book_title"],
        "chapter": chapter_result["chapter"],
        "context": context,
        "snippet_found": True,
    }
