import tiktoken

from config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    model: str = EMBEDDING_MODEL,
) -> list[str]:
    """Split text into overlapping chunks by token count."""
    if chunk_overlap >= chunk_size:
        raise ValueError(f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})")
    encoder = tiktoken.encoding_for_model(model)
    tokens = encoder.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(encoder.decode(chunk_tokens))
        start += chunk_size - chunk_overlap

    return chunks


def chunk_sections(
    sections: list[dict],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    model: str = EMBEDDING_MODEL,
) -> list[dict]:
    """Chunk sections independently, prepending section title for context.

    Each section dict has: chapter, section (str | None), text.
    Returns list of dicts: {"text": str, "chapter": str, "section": str | None}.
    """
    encoder = tiktoken.encoding_for_model(model)
    results = []

    for section in sections:
        section_title = section.get("section")
        raw_text = section["text"]
        chapter = section["chapter"]

        # Prepend section title to text for better embedding context
        if section_title:
            enriched_text = f"{section_title}\n\n{raw_text}"
        else:
            enriched_text = raw_text

        tokens = encoder.encode(enriched_text)

        if len(tokens) <= chunk_size:
            # Section fits in one chunk
            results.append({
                "text": enriched_text,
                "chapter": chapter,
                "section": section_title,
            })
        else:
            # Split with sliding window, prepend title to each sub-chunk
            start = 0
            while start < len(tokens):
                end = start + chunk_size
                chunk_tokens = tokens[start:end]
                chunk_text = encoder.decode(chunk_tokens)

                # For subsequent sub-chunks, prepend section title
                if start > 0 and section_title:
                    chunk_text = f"{section_title}\n\n{chunk_text}"

                results.append({
                    "text": chunk_text,
                    "chapter": chapter,
                    "section": section_title,
                })
                start += chunk_size - chunk_overlap

    return results
