from __future__ import annotations

from datetime import UTC, datetime

from app.ingestion.keyword_indexer import KeywordIndexer
from app.ingestion.schemas import ArxivPaper


def _make_paper(title: str, abstract: str) -> ArxivPaper:
    return ArxivPaper(
        arxiv_id="test-kw-001",
        title=title,
        abstract=abstract,
        authors=["Test Author"],
        categories=["cs.AI"],
        published_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        pdf_url="https://arxiv.org/pdf/test-001",
        abs_url="https://arxiv.org/abs/test-001",
    )


def test_extracts_top_10_keywords(sample_paper: ArxivPaper) -> None:
    result = KeywordIndexer().extract_keywords(sample_paper)
    assert len(result.keywords) == 10


def test_no_stopwords_in_output(sample_paper: ArxivPaper) -> None:
    result = KeywordIndexer().extract_keywords(sample_paper)
    stopwords = {"the", "and", "for", "are", "all", "you"}
    assert not any(kw in stopwords for kw in result.keywords)


def test_keywords_are_lowercase(sample_paper: ArxivPaper) -> None:
    result = KeywordIndexer().extract_keywords(sample_paper)
    assert all(kw == kw.lower() for kw in result.keywords)


def test_short_text_returns_fewer_keywords() -> None:
    paper = _make_paper(title="Neural Net", abstract="Deep learning")
    result = KeywordIndexer().extract_keywords(paper)
    assert len(result.keywords) < 10


def test_extraction_method_field(sample_paper: ArxivPaper) -> None:
    result = KeywordIndexer().extract_keywords(sample_paper)
    assert result.extraction_method == "tfidf_counter"
