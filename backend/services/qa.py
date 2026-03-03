import json as _json

from openai import OpenAI

from config import CHAT_MODEL, CHROMA_COLLECTION_NAME, OPENAI_API_KEY, TOP_K
from services.vector_store import _noop_ef

SYSTEM_PROMPT = """You are The Oracle, a knowledgeable assistant that answers \
questions based ONLY on the provided book excerpts.

Rules:
- Answer ONLY using information from the provided context
- If the context doesn't contain enough information, say so clearly
- Cite which book and chapter/page your answer comes from
- Do not make up information or use knowledge outside the provided context

Formatting rules for recipes:
- Always use this structure: Recipe Title, then a blank line, then \
"Ingredients:" as a heading followed by each ingredient on its own line \
prefixed with "- ", then a blank line, then "Instructions:" as a heading \
followed by numbered steps (1. 2. 3. etc.), each on its own line. \
End with yield/servings if mentioned.
- For non-recipe answers, use clear paragraphs with blank lines between them.

You MUST respond with a JSON object (no markdown fencing):
{
  "match_type": "full" | "partial" | "none",
  "answer": "your answer here"
}

The "answer" field supports newlines for formatting. Use them for structure.

match_type values:
- "full" — the context fully answers the question
- "partial" — the context has related content but cannot fully satisfy the query
- "none" — nothing in the context is relevant to the question"""


def retrieve_relevant_chunks(
    client,
    query_embedding: list[float],
    top_k: int = TOP_K,
    book_id: str | None = None,
) -> list[dict]:
    """Find the most relevant chunks for a query using cosine similarity."""
    collection = client.get_collection(name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef)

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if book_id:
        query_kwargs["where"] = {"book_id": book_id}

    results = collection.query(**query_kwargs)

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return chunks


def build_context_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the LLM prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        source = f"[{meta.get('book_title', 'Unknown')}"
        if meta.get("chapter"):
            source += f", {meta['chapter']}"
        if meta.get("section"):
            source += f" > {meta['section']}"
        if meta.get("page"):
            source += f", Page {meta['page']}"
        source += "]"
        context_parts.append(f"--- Excerpt {i + 1} {source} ---\n{chunk['text']}")

    return "\n\n".join(context_parts)


def generate_answer(
    question: str,
    chunks: list[dict],
    model: str = CHAT_MODEL,
) -> dict:
    """Generate an AI answer from retrieved chunks."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    context = build_context_prompt(chunks)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ],
            temperature=0.3,
        )
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}") from e

    raw = response.choices[0].message.content

    # Parse JSON response for match_type + answer
    # The model may wrap in ```json ... ``` fences
    match_type = "full"
    answer = raw
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Strip markdown code fences
        cleaned = cleaned.split("\n", 1)[-1]  # remove ```json line
        cleaned = cleaned.rsplit("```", 1)[0]  # remove closing ```
        cleaned = cleaned.strip()
    try:
        parsed = _json.loads(cleaned)
        answer = parsed.get("answer", raw)
        match_type = parsed.get("match_type", "full")
    except (_json.JSONDecodeError, AttributeError):
        pass  # Fallback: treat raw text as the answer

    # Group chunks by (book, chapter, section), keeping top chunks for highlighting.
    # Chunks arrive sorted by distance (best first from ChromaDB).
    grouped: dict[tuple, dict] = {}
    for chunk in chunks:
        meta = chunk["metadata"]
        key = (meta.get("book_title", "Unknown"), meta.get("chapter"), meta.get("section"), meta.get("page"))
        if key not in grouped:
            grouped[key] = {"meta": meta, "texts": []}
        # Strip section title prefix that chunk_sections() prepends —
        # chapter text from get_chapters_cached doesn't have it
        text = chunk["text"]
        section = meta.get("section", "")
        if section:
            prefix = f"{section}\n\n"
            if text.startswith(prefix):
                text = text[len(prefix):]
        grouped[key]["texts"].append(text)

    sources = []
    for key, group in grouped.items():
        meta = group["meta"]
        # Use the best chunk for the excerpt, but skip very short ones
        best_text = group["texts"][0]
        excerpt = best_text[:500].rstrip()
        if len(best_text) > 500:
            excerpt += "…"
        # Send top chunks for highlighting (bounded by TOP_K retrieval limit)
        highlight = group["texts"][:TOP_K]
        section = meta.get("section") or None
        sources.append({
            "book_title": meta.get("book_title", "Unknown"),
            "chapter": meta.get("chapter"),
            "section": section,
            "page": meta.get("page"),
            "excerpt": excerpt,
            "highlight_text": highlight,
            "book_id": meta.get("book_id"),
        })

    # Don't return sources for irrelevant matches
    if match_type == "none":
        sources = []

    return {"answer": answer, "sources": sources, "match_type": match_type}
