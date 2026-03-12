from datetime import datetime

from pydantic import BaseModel, HttpUrl


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
