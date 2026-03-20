from datetime import datetime

from pydantic import BaseModel, field_validator


class ArxivPaper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published_at: datetime
    updated_at: datetime
    pdf_url: str
    abs_url: str


class KeywordExtractionResult(BaseModel):
    arxiv_id: str
    keywords: list[str]
    extraction_method: str


class IngestionResult(BaseModel):
    papers_fetched: int
    papers_new: int
    papers_skipped: int
    keywords_indexed: int
    errors: list[str]
    duration_seconds: float


# ---------------------------------------------------------------------------
# Semantic Scholar schemas
# ---------------------------------------------------------------------------

class SemanticScholarAuthor(BaseModel):
    author_id: str
    author_name: str

    @field_validator("author_id", "author_name", mode="before")
    @classmethod
    def _coerce_str(cls, v: object) -> str:
        return str(v) if v is not None else ""


class SemanticScholarPaperRef(BaseModel):
    """A single citation or reference entry — only the Semantic Scholar paper ID."""

    paper_id: str

    @field_validator("paper_id", mode="before")
    @classmethod
    def _coerce_str(cls, v: object) -> str:
        return str(v) if v is not None else ""


class SemanticScholarPaper(BaseModel):
    """Parsed response from the Semantic Scholar /paper/{id} endpoint."""

    semantic_scholar_id: str
    arxiv_id: str
    year: int | None
    authors: list[SemanticScholarAuthor]
    citations: list[SemanticScholarPaperRef]
    references: list[SemanticScholarPaperRef]
