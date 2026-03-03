from pydantic import BaseModel


class ChapterInfo(BaseModel):
    index: int
    title: str


class BookResponse(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    status: str
    chunk_count: int
    uploaded_at: str
    summary: str | None = None
    chapter_count: int = 0
    chapters: list[ChapterInfo] = []
    topic: str = ""


class UpdateTopicRequest(BaseModel):
    topic: str


class QueryRequest(BaseModel):
    question: str
    book_id: str | None = None
    topic: str | None = None


class SourceReference(BaseModel):
    book_title: str
    chapter: str | None
    section: str | None = None
    page: int | None
    excerpt: str
    highlight_text: list[str] = []
    book_id: str | None = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReference]
    match_type: str = "full"


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


# ---------------------------------------------------------------------------
# SSE event models (documentation only — raw dicts used for streaming)
# ---------------------------------------------------------------------------


class AgentThoughtEvent(BaseModel):
    type: str = "thought"
    content: str


class AgentToolCallEvent(BaseModel):
    type: str = "tool_call"
    tool: str
    args: dict
    step: int


class AgentToolResultEvent(BaseModel):
    type: str = "tool_result"
    tool: str
    summary: str
    step: int


class AgentAnswerEvent(BaseModel):
    type: str = "answer"
    question: str
    answer: str
    sources: list[SourceReference]
    match_type: str = "full"


class AgentErrorEvent(BaseModel):
    type: str = "error"
    detail: str
