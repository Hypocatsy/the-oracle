import re
from functools import lru_cache

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag


# Block-level elements that should produce line breaks
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "aside", "header", "footer", "nav",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "tr", "th", "td",
    "blockquote", "pre", "figure", "figcaption",
    "br", "hr",
})


def _extract_text(soup: BeautifulSoup) -> str:
    """Extract text respecting block vs inline structure.

    Block elements get newlines; inline elements (em, strong, span, a, etc.)
    flow naturally within the surrounding text.
    """
    parts: list[str] = []

    for element in soup.descendants:
        if isinstance(element, NavigableString):
            text = str(element)
            # Collapse ALL whitespace (including newlines in source HTML)
            # to single spaces — inline text should flow naturally
            text = re.sub(r"\s+", " ", text)
            if text and text != " ":
                parts.append(text)
            elif text == " ":
                # Preserve single space between inline elements
                parts.append(" ")
        elif element.name in _BLOCK_TAGS:
            parts.append("\n")

    raw = "".join(parts)
    # Collapse multiple blank lines into at most two newlines (one blank line)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    # Strip leading/trailing whitespace per line, remove empty lines at edges
    lines = [line.strip() for line in raw.splitlines()]
    return "\n".join(lines).strip()


def _build_toc_map(book) -> dict[str, str]:
    """Build a mapping of EPUB item filenames to TOC titles.

    Walks the book's table of contents (NCX/NAV) and maps each href
    (stripped of fragment anchors) to its human-readable title.
    """
    toc_map: dict[str, str] = {}

    def _walk(entries):
        for entry in entries:
            if isinstance(entry, tuple):
                # Section: (Section object, list of children)
                section, children = entry
                if hasattr(section, "href") and section.title:
                    href = section.href.split("#")[0]
                    toc_map.setdefault(href, section.title)
                _walk(children)
            elif hasattr(entry, "href") and entry.title:
                href = entry.href.split("#")[0]
                toc_map.setdefault(href, entry.title)

    _walk(book.toc)
    return toc_map


def _extract_heading(soup: BeautifulSoup) -> str | None:
    """Extract chapter heading with proper spacing between text nodes."""
    heading = soup.find(["h1", "h2", "h3"])
    if not heading:
        return None
    # Use " " separator so <h1>CH.05<br/>TITLE</h1> becomes "CH.05 TITLE"
    return heading.get_text(separator=" ", strip=True)


_GENERIC_CHAPTER_RE = re.compile(
    r"^(chapter|part|section|book|volume)\s+(\d+|[ivxlcdm]+|one|two|three|four|"
    r"five|six|seven|eight|nine|ten|eleven|twelve)\b",
    re.IGNORECASE,
)


def _extract_first_text(soup: BeautifulSoup) -> str | None:
    """Fallback title extraction: first short <p> texts in the document.

    Many EPUBs (especially from InDesign) use styled <p> tags instead of
    heading elements for chapter titles. If the first <p> is a generic
    label like "Chapter One", combine it with the next few short <p> tags
    to build a more descriptive title.
    """
    short_texts = []
    for p in soup.find_all("p"):
        text = p.get_text(separator=" ", strip=True)
        if text and len(text) < 60:
            short_texts.append(text)
            if len(short_texts) >= 4:
                break

    if not short_texts:
        return None

    first = short_texts[0]

    # If the first text is generic ("Chapter One", "Part 3", etc.),
    # append subsequent short texts to form a descriptive title
    if _GENERIC_CHAPTER_RE.match(first) and len(short_texts) > 1:
        # Grab the next 1-2 short texts as the subtitle
        subtitle_parts = []
        for t in short_texts[1:3]:
            if len(t) > 50:
                break
            subtitle_parts.append(t)
        if subtitle_parts:
            subtitle = " ".join(subtitle_parts)
            return f"{first}: {subtitle}"

    return first


@lru_cache(maxsize=16)
def get_chapters_cached(file_path: str) -> tuple[dict, ...]:
    """Cached wrapper around extract_epub_text. Returns a tuple for hashability."""
    chapters = extract_epub_text(file_path)
    return tuple(chapters)


def _remove_heading_from_body(text: str, chapter_title: str) -> str:
    """Remove the heading text from the start of body, handling br/newline variants."""
    if text.startswith(chapter_title):
        return text[len(chapter_title):].lstrip("\n")
    # Heading may use spaces (from separator=" ") while body has newlines (from <br/>)
    # e.g. heading="CH.05 PASTA..." but body starts with "CH.05\nPASTA..."
    title_pattern = re.escape(chapter_title).replace(r"\ ", r"\s+")
    m = re.match(title_pattern, text)
    if m:
        return text[m.end():].lstrip("\n")
    return text


def _split_into_sections(body, chapter_title: str) -> list[dict]:
    """Split a chapter's HTML body into sections at <h2>/<h3> boundaries.

    Returns a list of dicts with keys: chapter, section, text.
    Text before the first sub-heading gets section=None (intro text).
    """
    # Collect all h2/h3 tags in document order
    headings = body.find_all(["h2", "h3"])
    if not headings:
        # No sub-headings — whole chapter is one section
        text = _extract_text(body)
        text = _remove_heading_from_body(text, chapter_title)
        if text.strip():
            return [{"chapter": chapter_title, "section": None, "text": text.strip()}]
        return []

    sections = []

    # Intro text: everything before the first heading
    # We'll collect siblings of body that come before the first heading
    intro_parts = []
    for el in body.children:
        if el in headings or (isinstance(el, Tag) and el.find(["h2", "h3"])):
            break
        if hasattr(el, 'get_text'):
            t = el.get_text(strip=True)
            if t:
                intro_parts.append(t)
        elif isinstance(el, NavigableString):
            t = str(el).strip()
            if t:
                intro_parts.append(t)

    if intro_parts:
        intro_text = "\n".join(intro_parts)
        intro_text = _remove_heading_from_body(intro_text, chapter_title)
        if intro_text.strip():
            sections.append({
                "chapter": chapter_title,
                "section": None,
                "text": intro_text.strip(),
            })

    # Each heading starts a new section — collect content until next heading
    for i, heading in enumerate(headings):
        section_title = heading.get_text(separator=" ", strip=True)

        # Collect all siblings between this heading and the next one
        content_elements = []
        sibling = heading.find_next_sibling()
        next_heading = headings[i + 1] if i + 1 < len(headings) else None
        while sibling and sibling != next_heading:
            content_elements.append(str(sibling))
            sibling = sibling.find_next_sibling()

        if content_elements:
            section_soup = BeautifulSoup("".join(content_elements), "html.parser")
            text = _extract_text(section_soup).strip()
        else:
            text = ""

        if text:
            sections.append({
                "chapter": chapter_title,
                "section": section_title,
                "text": text,
            })

    return sections


def extract_epub_sections(file_path: str) -> list[dict]:
    """Extract sections from an EPUB, split at h2/h3 heading boundaries.

    Returns a flat list of dicts: {"chapter": str, "section": str | None, "text": str}
    """
    book = epub.read_epub(file_path)
    toc_map = _build_toc_map(book)
    all_sections = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        body = soup.body or soup

        full_text = _extract_text(body)
        full_text = re.sub(
            r"^(xml\b.*?\??\s*)?(html\s*)?", "", full_text, flags=re.IGNORECASE,
        ).strip()

        if len(full_text) < 50:
            continue

        chapter_title = (_extract_heading(soup)
                        or toc_map.get(item.get_name())
                        or _extract_first_text(soup)
                        or item.get_name())
        sections = _split_into_sections(body, chapter_title)
        all_sections.extend(sections)

    return all_sections


def extract_epub_text(file_path: str) -> list[dict]:
    """Extract text from an EPUB file, chapter by chapter."""
    book = epub.read_epub(file_path)
    toc_map = _build_toc_map(book)
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")

        # Use <body> if present to skip XML declarations and <html>/<head> noise
        body = soup.body or soup

        text = _extract_text(body)

        # Strip any XML/HTML preamble that leaked through
        text = re.sub(
            r"^(xml\b.*?\??\s*)?(html\s*)?", "", text, flags=re.IGNORECASE,
        ).strip()

        if len(text) < 50:
            continue

        chapter_title = (_extract_heading(soup)
                        or toc_map.get(item.get_name())
                        or _extract_first_text(soup)
                        or item.get_name())
        text = _remove_heading_from_body(text, chapter_title)

        chapters.append({
            "chapter": chapter_title,
            "text": text,
        })

    return chapters
