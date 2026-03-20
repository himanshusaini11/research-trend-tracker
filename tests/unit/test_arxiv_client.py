"""Unit tests for ArxivClient — no real network calls."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.ingestion.arxiv_client import ArxivClient, _text, _ATOM_NS

# ---------------------------------------------------------------------------
# Minimal Atom feed fixture
# ---------------------------------------------------------------------------

_ATOM_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v2</id>
    <title>  Test Paper Title  </title>
    <summary>Test abstract with\nnewlines.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
    <published>2024-01-15T00:00:00Z</published>
    <updated>2024-01-16T00:00:00Z</updated>
    <link rel="alternate" href="https://arxiv.org/abs/2401.00001"/>
    <link title="pdf" href="https://arxiv.org/pdf/2401.00001"/>
  </entry>
</feed>"""

_FEED_FUTURE = _ATOM_FEED  # published 2024-01-15 — after any "since" we use in tests


# ---------------------------------------------------------------------------
# _text helper
# ---------------------------------------------------------------------------

def test_text_returns_element_text() -> None:
    root = ET.fromstring(
        '<root xmlns="http://www.w3.org/2005/Atom"><title>Hello</title></root>'
    )
    assert _text(root, "title") == "Hello"


def test_text_returns_empty_string_for_missing_tag() -> None:
    root = ET.fromstring('<root xmlns="http://www.w3.org/2005/Atom"></root>')
    assert _text(root, "title") == ""


# ---------------------------------------------------------------------------
# ArxivClient construction
# ---------------------------------------------------------------------------

def test_client_stores_constructor_args() -> None:
    client = ArxivClient(categories=["cs.AI", "cs.LG"], max_results=100, delay_seconds=1.5)
    assert client._categories == ["cs.AI", "cs.LG"]
    assert client._max_results == 100
    assert client._delay_seconds == 1.5


# ---------------------------------------------------------------------------
# _parse_entry
# ---------------------------------------------------------------------------

def test_parse_entry_extracts_arxiv_id() -> None:
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert paper.arxiv_id == "2401.00001"


def test_parse_entry_strips_version_suffix() -> None:
    """The 'v2' suffix in the arXiv ID URL must be stripped."""
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert "v" not in paper.arxiv_id


def test_parse_entry_extracts_authors() -> None:
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert paper.authors == ["Alice Smith", "Bob Jones"]


def test_parse_entry_extracts_categories() -> None:
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert "cs.AI" in paper.categories
    assert "cs.LG" in paper.categories


def test_parse_entry_normalises_whitespace_in_title() -> None:
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert paper.title == "Test Paper Title"


def test_parse_entry_extracts_pdf_and_abs_urls() -> None:
    root = ET.fromstring(_ATOM_FEED)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    paper = client._parse_entry(entry)
    assert "pdf" in paper.pdf_url
    assert "abs" in paper.abs_url


# ---------------------------------------------------------------------------
# _parse_feed
# ---------------------------------------------------------------------------

def test_parse_feed_returns_papers_after_cutoff() -> None:
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    since = datetime(2024, 1, 1, tzinfo=UTC)
    papers = client._parse_feed(_ATOM_FEED, since)
    assert len(papers) == 1


def test_parse_feed_filters_papers_before_cutoff() -> None:
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)
    # Set cutoff after the paper's published date
    since = datetime(2024, 2, 1, tzinfo=UTC)
    papers = client._parse_feed(_ATOM_FEED, since)
    assert len(papers) == 0


# ---------------------------------------------------------------------------
# _fetch_category — error path
# ---------------------------------------------------------------------------

async def test_fetch_recent_returns_papers_for_category() -> None:
    """fetch_recent drives the full httpx round-trip and deduplicates papers."""
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.text = _ATOM_FEED
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = mock_resp

    with patch("app.ingestion.arxiv_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep"):
            # days_back=10000 ensures the 2024-01-15 fixture date is always within the window
            papers = await client.fetch_recent(days_back=10000)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.00001"


async def test_fetch_category_returns_empty_list_on_http_error() -> None:
    client = ArxivClient(categories=["cs.AI"], max_results=10, delay_seconds=0)

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.side_effect = httpx.ConnectError("connection refused")

    since = datetime(2024, 1, 1, tzinfo=UTC)
    result = await client._fetch_category(mock_http, "cs.AI", since)
    assert result == []
