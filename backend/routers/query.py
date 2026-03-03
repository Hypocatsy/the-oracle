import json
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI

from config import CHAT_MODEL, CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR, EMBEDDING_MODEL, OPENAI_API_KEY, TOP_K, UPLOAD_DIR
from models.schemas import QueryRequest, QueryResponse, SourceReference, SuggestionsResponse
from services.agent import run_agent_stream
from services.embeddings import generate_embeddings
from services.qa import generate_answer, retrieve_relevant_chunks
from services.vector_store import get_chroma_client, _noop_ef

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger(__name__)

SUGGESTIONS_JSON = os.path.join(UPLOAD_DIR, "suggestions.json")


def _load_suggestions_cache() -> dict | None:
    if not os.path.exists(SUGGESTIONS_JSON):
        return None
    try:
        with open(SUGGESTIONS_JSON, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None


def _save_suggestions_cache(book_ids: list[str], suggestions: list[str]) -> None:
    with open(SUGGESTIONS_JSON, "w") as f:
        json.dump({"book_ids": sorted(book_ids), "suggestions": suggestions}, f, indent=2)


def _get_ready_book_ids() -> list[str]:
    books_json = os.path.join(UPLOAD_DIR, "books.json")
    if not os.path.exists(books_json):
        return []
    try:
        with open(books_json, "r") as f:
            books = json.load(f)
        return sorted(b["id"] for b in books if b.get("status") == "ready")
    except (json.JSONDecodeError, ValueError):
        return []


def regenerate_suggestions() -> list[str]:
    """Generate fresh suggestions from ChromaDB and cache them. Called after upload/delete."""
    try:
        client = get_chroma_client(CHROMA_PERSIST_DIR)
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef)
        if collection.count() == 0:
            return []

        sample = collection.peek(limit=10)
        context_parts = []
        for i in range(len(sample["ids"])):
            meta = sample["metadatas"][i]
            excerpt = sample["documents"][i][:200]
            context_parts.append(f"[{meta.get('book_title', 'Unknown')}]: {excerpt}")

        context = "\n\n".join(context_parts)

        llm = OpenAI(api_key=OPENAI_API_KEY)
        response = llm.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Based on these book excerpts, suggest 3 interesting questions "
                        "a reader might ask. Return only the questions, one per line."
                    ),
                },
                {"role": "user", "content": context},
            ],
            temperature=0.7,
        )

        lines = [
            line.lstrip("0123456789.-) ").strip()
            for line in response.choices[0].message.content.strip().splitlines()
            if line.strip()
        ]
        suggestions = lines[:3]

        book_ids = _get_ready_book_ids()
        _save_suggestions_cache(book_ids, suggestions)
        return suggestions
    except Exception as e:
        logger.error("Failed to regenerate suggestions: %s", e)
        return []


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions():
    book_ids = _get_ready_book_ids()
    if not book_ids:
        return SuggestionsResponse(suggestions=[])

    cache = _load_suggestions_cache()
    if cache and cache.get("book_ids") == sorted(book_ids):
        return SuggestionsResponse(suggestions=cache["suggestions"])

    # Cache miss or stale — regenerate
    suggestions = regenerate_suggestions()
    return SuggestionsResponse(suggestions=suggestions)


@router.post("/query", response_model=QueryResponse)
async def query_books(req: QueryRequest):
    client = get_chroma_client(CHROMA_PERSIST_DIR)

    try:
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef)
        if collection.count() == 0:
            raise ValueError("empty")
    except Exception:
        return QueryResponse(
            question=req.question,
            answer="Upload some books first so The Oracle has something to consult!",
            sources=[],
        )

    try:
        query_embedding = generate_embeddings(
            [req.question], model=EMBEDDING_MODEL
        )[0]

        chunks = retrieve_relevant_chunks(client, query_embedding, top_k=TOP_K, book_id=req.book_id)

        result = generate_answer(req.question, chunks, model=CHAT_MODEL)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    sources = [SourceReference(**s) for s in result["sources"]]

    return QueryResponse(
        question=req.question,
        answer=result["answer"],
        sources=sources,
        match_type=result.get("match_type", "full"),
    )


@router.post("/query/stream")
async def query_books_stream(req: QueryRequest):
    """SSE streaming endpoint for the ReAct agent loop."""
    client = get_chroma_client(CHROMA_PERSIST_DIR)

    try:
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef)
        if collection.count() == 0:
            raise ValueError("empty")
    except Exception:
        # No books — return immediate answer as SSE
        async def empty_stream():
            event = {
                "type": "answer",
                "question": req.question,
                "answer": "Upload some books first so The Oracle has something to consult!",
                "sources": [],
                "match_type": "none",
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_stream():
        try:
            async for event in run_agent_stream(req.question, req.book_id, req.topic):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {"type": "error", "detail": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
