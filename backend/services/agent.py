"""ReAct agent loop with OpenAI function calling and SSE streaming."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from openai import AsyncOpenAI

from config import CHAT_MODEL, MAX_AGENT_STEPS, OPENAI_API_KEY, TOP_K
from config import PROJECT_ROOT

AGENT_LOG_DIR = os.path.join(PROJECT_ROOT, "data", "logs")
os.makedirs(AGENT_LOG_DIR, exist_ok=True)
from services.agent_tools import (
    get_chapter,
    get_surrounding_context,
    list_books,
    search_book,
    search_by_keyword,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI function calling schemas
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_book",
            "description": (
                "Semantic vector search across all indexed books (or a specific book). "
                "Returns the most relevant text chunks with metadata. "
                "Use this as your primary search tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — a question or topic to find relevant content for.",
                    },
                    "book_id": {
                        "type": "string",
                        "description": "Optional: limit search to a specific book by its ID.",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional: limit search to books in this topic (e.g. 'Recipes').",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chapter",
            "description": (
                "Retrieve the full text of a specific chapter from a book. "
                "Useful when you need complete context beyond what search chunks provide. "
                "Supports fuzzy matching on chapter title (case-insensitive substring)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {
                        "type": "string",
                        "description": "The book ID.",
                    },
                    "chapter_title": {
                        "type": "string",
                        "description": "The chapter title (or a substring of it).",
                    },
                },
                "required": ["book_id", "chapter_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_keyword",
            "description": (
                "Exact text match (case-sensitive) across indexed chunks. "
                "Useful for finding specific terms, ingredient names, or proper nouns. "
                "Tip: try lowercase if unsure about casing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "The exact keyword or phrase to search for.",
                    },
                    "book_id": {
                        "type": "string",
                        "description": "Optional: limit search to a specific book by its ID.",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_books",
            "description": (
                "List all available books with their titles, chapter lists, and chunk counts. "
                "Use this to discover what content is available before searching."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_surrounding_context",
            "description": (
                "Get broader context (~1500 chars) around a specific text snippet within a chapter. "
                "Useful when a search chunk is too short and you need more surrounding text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {
                        "type": "string",
                        "description": "The book ID.",
                    },
                    "chapter_title": {
                        "type": "string",
                        "description": "The chapter title containing the snippet.",
                    },
                    "text_snippet": {
                        "type": "string",
                        "description": "A short text snippet to locate in the chapter.",
                    },
                },
                "required": ["book_id", "chapter_title", "text_snippet"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

TOOL_DISPATCH: dict[str, callable] = {
    "search_book": search_book,
    "get_chapter": get_chapter,
    "search_by_keyword": search_by_keyword,
    "list_books": list_books,
    "get_surrounding_context": get_surrounding_context,
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """\
You are The Oracle, a wise and knowledgeable assistant that answers questions \
using information from the user's uploaded book library.

Books in the library may have topics (e.g. "Recipes", "Fiction"). You can \
use `list_books` to see each book's topic, and `search_book(topic=...)` to \
scope searches to a specific category.

You have access to tools that let you search and read from the library. \
Follow this process:

1. **Think** about what information you need to answer the question.
2. **Search** using `search_book` (semantic search) as your primary tool. \
   Use `search_by_keyword` for specific terms, names, or ingredients \
   (note: keyword search is case-sensitive, so try lowercase).
3. **Decompose** complex queries. If searching the full question gives poor \
   results, break it into parts. For example "matcha bread" → search for \
   "bread recipe" first, then "matcha" or "green tea" separately, then \
   combine what you find into a helpful answer.
4. **Iterate** if the first search doesn't give enough information — try \
   different queries, broader terms, related concepts, check related \
   chapters, or get surrounding context. Always try at least 2 different \
   search queries before concluding nothing is relevant. \
   But do NOT repeat near-identical searches — if "sangria cake" returned \
   results, don't also search "sangria cake recipe". Move on to \
   synthesizing after 2-3 focused searches.
5. **Synthesize**: Combine information from multiple search results to \
   build the best possible answer. If someone asks for "matcha bread" and \
   you find a bread recipe and matcha/green tea info, combine them into a \
   suggestion — present the bread recipe and explain how to incorporate \
   matcha based on what you learned from the sources.
6. **Answer** with your final response.

CRITICAL rules:
- Base your answers ONLY on information from tool results. Never make up \
  information or give general advice not grounded in the library content.
- If you found content that is RELATED to the question (e.g., user asks \
  about "chocolate chip banana bread" and you find banana bread recipes \
  and chocolate chip cookie info), synthesize it into a helpful answer. \
  That IS relevant — combine the findings creatively.
- If searches returned content that is COMPLETELY UNRELATED to the \
  question (e.g., user asks about "gmail" and you only find cookbook \
  recipes), use match_type "none". Do NOT fabricate an answer from \
  your own knowledge.
- Always present what you found and explain how it relates to the question.
- Cite which book and chapter your information comes from.
- Use "none" when the question is outside the scope of the library \
  (the search results have nothing to do with what was asked). In this \
  case, set the answer to a short message like "This topic isn't \
  covered in your library."

Formatting rules for recipes:
- Use this structure: Recipe Title, blank line, "Ingredients:" heading with \
  each ingredient on its own line prefixed with "- ", blank line, \
  "Instructions:" heading with numbered steps. End with yield/servings if mentioned.
- For non-recipe answers, use clear paragraphs with blank lines between them.

When you have enough information to answer, respond in this exact format:

MATCH_TYPE: full|partial|none
SOURCES: Book Title > Chapter > Section, Book Title > Chapter, ...
---
Your answer here (plain text, as long as needed)

The first line MUST be "MATCH_TYPE: " followed by one of: full, partial, none.
The second line MUST be "SOURCES: " followed by a comma-separated list of the \
sources you actually used in your answer. Each source is formatted as \
"Book Title > Chapter" or "Book Title > Chapter > Section". Only list sources \
whose content you directly referenced or drew from — do NOT list every search \
result. For "none" responses, write "SOURCES: none".
The third line MUST be "---" (three dashes).
Everything after the --- line is your answer.

match_type values:
- "full" — the sources fully answer the question
- "partial" — you synthesized an answer from related content, but the \
  exact thing asked for wasn't found verbatim in the library
- "none" — searches returned zero results or only completely unrelated content"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_message(msg) -> dict:
    """Convert an OpenAI message object or dict to a JSON-safe dict."""
    if isinstance(msg, dict):
        return msg
    # OpenAI ChatCompletionMessage object
    out = {"role": getattr(msg, "role", "unknown")}
    if msg.content:
        out["content"] = msg.content
    if getattr(msg, "tool_calls", None):
        out["tool_calls"] = [
            {
                "id": tc.id,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return out


def _dump_agent_log(question: str, messages: list) -> None:
    """Write the full message chain to a log file for debugging."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = question[:40].replace(" ", "_").replace("/", "_")
        filename = f"{ts}_{slug}.json"
        filepath = os.path.join(AGENT_LOG_DIR, filename)

        serialized = [_serialize_message(m) for m in messages]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False)

        logger.info("Agent log written to %s", filepath)
    except Exception as e:
        logger.error("Failed to write agent log: %s", e)


def _truncate_tool_result(result: dict, max_chars: int = 4000) -> dict:
    """Cap chunk texts to manage context window size."""
    if "chunks" not in result:
        return result

    truncated = {**result, "chunks": []}
    for chunk in result["chunks"]:
        c = {**chunk}
        if len(c.get("text", "")) > 500:
            c["text"] = c["text"][:500] + "..."
        truncated["chunks"].append(c)

    # If total serialized size is too large, trim number of chunks
    serialized = json.dumps(truncated)
    if len(serialized) > max_chars:
        while len(truncated["chunks"]) > 3 and len(json.dumps(truncated)) > max_chars:
            truncated["chunks"].pop()
        truncated["count"] = len(truncated["chunks"])

    return truncated


def _summarize_tool_result(tool_name: str, result: dict) -> str:
    """Human-readable one-liner for SSE events."""
    if "error" in result:
        return f"Error: {result['error']}"

    if tool_name == "search_book":
        count = result.get("count", 0)
        if count == 0:
            return "No relevant chunks found"
        titles = {c.get("book_title", "") for c in result.get("chunks", [])}
        books_str = ", ".join(t for t in titles if t)
        return f"Found {count} relevant chunks from {books_str}"

    if tool_name == "search_by_keyword":
        count = result.get("count", 0)
        if count == 0:
            return "No exact matches found"
        return f"Found {count} chunks containing the keyword"

    if tool_name == "get_chapter":
        ch = result.get("chapter", "")
        book = result.get("book_title", "")
        text_len = len(result.get("text", ""))
        return f"Loaded chapter '{ch}' from {book} ({text_len} chars)"

    if tool_name == "list_books":
        count = result.get("count", 0)
        return f"Found {count} available book(s)"

    if tool_name == "get_surrounding_context":
        ctx_len = len(result.get("context", ""))
        return f"Retrieved {ctx_len} chars of surrounding context"

    return "Tool completed"


def _strip_section_prefix(text: str, section: str) -> str:
    """Remove the section title prefix that chunk_sections() prepends.

    Chunks are stored as "Section Title\\n\\nactual text..." but the chapter
    text from get_chapters_cached doesn't have these prefixes, so highlighting
    fails if we don't strip them.
    """
    if not section:
        return text
    prefix = f"{section}\n\n"
    if text.startswith(prefix):
        return text[len(prefix):]
    return text



def _parse_source_declaration(decl: str) -> tuple[str, str, str]:
    """Parse 'Book Title > Chapter > Section' into (book_title, chapter, section).

    Handles both 2-part (book > chapter) and 3-part (book > chapter > section).
    """
    parts = [p.strip() for p in decl.split(">")]
    book_title = parts[0] if len(parts) >= 1 else ""
    chapter = parts[1] if len(parts) >= 2 else ""
    section = parts[2] if len(parts) >= 3 else ""
    return (book_title, chapter, section)


def _build_source_index(all_tool_results: list[dict]) -> dict[tuple, list[dict]]:
    """Index all chunks from tool results by (book_title, chapter, section)."""
    index: dict[tuple, list[dict]] = {}
    for entry in all_tool_results:
        result = entry.get("result", {})
        for chunk in result.get("chunks", []):
            key = (
                chunk.get("book_title", "Unknown"),
                chunk.get("chapter", ""),
                chunk.get("section", ""),
            )
            index.setdefault(key, []).append(chunk)
    return index


def _resolve_declared_sources(
    declared_sources: list[str], all_tool_results: list[dict]
) -> list[dict]:
    """Match agent-declared source strings against actual tool result chunks.

    Each declared source is parsed into (book_title, chapter, section) and
    matched against the chunk index. Unmatched declarations (hallucinations)
    are silently dropped.
    """
    index = _build_source_index(all_tool_results)
    sources: list[dict] = []
    seen_keys: set[tuple] = set()

    for decl in declared_sources:
        book_title, chapter, section = _parse_source_declaration(decl)

        # Try exact match first (all three fields)
        matched_chunks = None
        exact_key = (book_title, chapter, section)
        if exact_key in index:
            matched_chunks = index[exact_key]
            match_key = exact_key
        else:
            # Fuzzy: find keys where book_title and chapter match (case-insensitive substring)
            for key, chunks in index.items():
                k_book, k_chapter, k_section = key
                if (book_title.lower() in k_book.lower()
                        and chapter.lower() in k_chapter.lower()
                        and (not section or section.lower() in k_section.lower())):
                    matched_chunks = chunks
                    match_key = key
                    break

        if matched_chunks is None or match_key in seen_keys:
            continue

        seen_keys.add(match_key)
        k_book, k_chapter, k_section = match_key
        first_chunk = matched_chunks[0]
        text = first_chunk.get("text", "")
        clean_text = _strip_section_prefix(text, k_section)

        highlight_texts = []
        for chunk in matched_chunks[:TOP_K]:
            ct = _strip_section_prefix(chunk.get("text", ""), k_section)
            if ct:
                highlight_texts.append(ct)

        sources.append({
            "book_title": k_book,
            "chapter": k_chapter or None,
            "section": k_section or None,
            "page": None,
            "excerpt": clean_text[:500],
            "highlight_text": highlight_texts,
            "book_id": first_chunk.get("book_id", ""),
        })

    return sources



# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def run_agent_stream(
    question: str, book_id: str | None = None, topic: str | None = None
) -> AsyncGenerator[dict, None]:
    """Run the ReAct agent loop, yielding SSE events as dicts."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # If scoped to a specific book, tell the agent
    if book_id:
        messages.append({
            "role": "system",
            "content": f"The user is asking about a specific book (book_id: {book_id}). "
                       f"Prefer searching within this book first.",
        })
    elif topic:
        messages.append({
            "role": "system",
            "content": f"The user is filtering by topic: {topic}. "
                       f"Prefer using search_book(topic=\"{topic}\") to scope results to this category.",
        })

    all_tool_results: list[dict] = []
    step = 0

    try:
        while step < MAX_AGENT_STEPS:
            step += 1

            response = await client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.3,
            )

            choice = response.choices[0]
            message = choice.message

            # If the model has content text (reasoning), emit as thought
            if message.content:
                # Check if it's a final JSON answer (no tool calls)
                if not message.tool_calls:
                    # This is the final answer
                    answer_data = _parse_answer(message.content)
                    match_type = answer_data.get("match_type", "full")

                    if match_type == "none" or not answer_data["declared_sources"]:
                        sources = []
                    else:
                        sources = _resolve_declared_sources(
                            answer_data["declared_sources"],
                            all_tool_results,
                        )

                    _dump_agent_log(question, messages)
                    yield {
                        "type": "answer",
                        "question": question,
                        "answer": answer_data["answer"],
                        "sources": sources,
                        "match_type": match_type,
                    }
                    return
                else:
                    # Model is thinking before calling tools
                    yield {"type": "thought", "content": message.content}

            # Process tool calls
            if message.tool_calls:
                # Append the assistant message with tool_calls to conversation
                messages.append(message)

                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Enforce topic filter on search tools when active
                    if topic and fn_name in ("search_book", "search_by_keyword") and not fn_args.get("book_id"):
                        fn_args["topic"] = topic

                    yield {
                        "type": "tool_call",
                        "tool": fn_name,
                        "args": fn_args,
                        "step": step,
                    }

                    # Dispatch tool (blocking calls wrapped in to_thread)
                    fn = TOOL_DISPATCH.get(fn_name)
                    if fn is None:
                        result = {"error": f"Unknown tool: {fn_name}"}
                    else:
                        result = await asyncio.to_thread(fn, **fn_args)

                    all_tool_results.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result": result,
                    })

                    summary = _summarize_tool_result(fn_name, result)
                    yield {
                        "type": "tool_result",
                        "tool": fn_name,
                        "summary": summary,
                        "step": step,
                    }

                    # Truncate before sending to LLM to save tokens
                    truncated = _truncate_tool_result(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(truncated),
                    })
            else:
                # No tool calls and no content — shouldn't happen, but handle it
                yield {
                    "type": "answer",
                    "question": question,
                    "answer": "I wasn't able to find an answer. Please try rephrasing your question.",
                    "sources": [],
                    "match_type": "none",
                }
                return

        # Hit step limit — force a final answer without tools
        messages.append({
            "role": "system",
            "content": "You have used all available tool steps. Provide your final answer NOW "
                       "based on what you've found so far. Use the MATCH_TYPE/SOURCES/--- format.",
        })

        response = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.3,
        )

        content = response.choices[0].message.content or ""
        answer_data = _parse_answer(content)
        match_type = answer_data.get("match_type", "full")

        if match_type == "none" or not answer_data["declared_sources"]:
            sources = []
        else:
            sources = _resolve_declared_sources(
                answer_data["declared_sources"],
                all_tool_results,
            )

        _dump_agent_log(question, messages)
        yield {
            "type": "answer",
            "question": question,
            "answer": answer_data["answer"],
            "sources": sources,
            "match_type": match_type,
        }

    except Exception as e:
        logger.error("Agent loop error: %s", e, exc_info=True)
        yield {"type": "error", "detail": str(e)}


def _parse_answer(raw: str) -> dict:
    """Parse the MATCH_TYPE/SOURCES/--- answer format, with fallbacks."""
    cleaned = raw.strip()

    # Primary format: MATCH_TYPE: <type>\nSOURCES: ...\n---\n<answer>
    if cleaned.upper().startswith("MATCH_TYPE:"):
        lines = cleaned.split("\n")
        match_type = lines[0].split(":", 1)[1].strip().lower()
        if match_type not in ("full", "partial", "none"):
            match_type = "full"

        # Parse SOURCES line and find --- separator
        declared_sources: list[str] = []
        separator_idx = None
        for i, line in enumerate(lines[1:], start=1):
            stripped = line.strip()
            if stripped.upper().startswith("SOURCES:"):
                sources_raw = stripped.split(":", 1)[1].strip()
                if sources_raw.lower() != "none" and sources_raw:
                    declared_sources = [s.strip() for s in sources_raw.split(",") if s.strip()]
            elif stripped == "---":
                separator_idx = i
                break

        if separator_idx is not None:
            answer = "\n".join(lines[separator_idx + 1:]).strip()
        else:
            # No separator found — everything after header lines is the answer
            rest = "\n".join(lines[1:])
            answer = rest.strip()

        return {"answer": answer, "match_type": match_type, "declared_sources": declared_sources}

    # Fallback: JSON format (legacy or if LLM ignores instructions)
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
        return {
            "answer": parsed.get("answer", raw),
            "match_type": parsed.get("match_type", "full"),
            "declared_sources": [],
        }
    except (json.JSONDecodeError, AttributeError):
        return {"answer": raw, "match_type": "full", "declared_sources": []}
