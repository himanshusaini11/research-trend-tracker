from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx

from app.core.logger import get_logger
from app.ingestion.schemas import ArxivPaper

log = get_logger(__name__)

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_BASE_URL = "https://export.arxiv.org/api/query"


def _text(element: ET.Element, tag: str, ns: str = _ATOM_NS) -> str:
    child = element.find(f"{{{ns}}}{tag}")
    return child.text.strip() if child is not None and child.text else ""


class ArxivClient:
    def __init__(
        self,
        categories: list[str],
        max_results: int,
        delay_seconds: float,
    ) -> None:
        self._categories = categories
        self._max_results = max_results
        self._delay_seconds = delay_seconds

    async def fetch_recent(self, days_back: int = 1) -> list[ArxivPaper]:
        since = datetime.now(UTC) - timedelta(days=days_back)
        # arXiv query: one request per category, collected then deduped
        papers: dict[str, ArxivPaper] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for i, category in enumerate(self._categories):
                if i > 0:
                    await asyncio.sleep(self._delay_seconds)
                fetched = await self._fetch_category(client, category, since)
                for p in fetched:
                    papers.setdefault(p.arxiv_id, p)
        log.info("arxiv_fetch_complete", total=len(papers), categories=self._categories)
        return list(papers.values())

    async def _fetch_category(
        self, client: httpx.AsyncClient, category: str, since: datetime
    ) -> list[ArxivPaper]:
        params: dict[str, str | int] = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": self._max_results,
        }
        try:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("arxiv_fetch_error", category=category, error=str(exc))
            return []

        return self._parse_feed(resp.text, since)

    def _parse_feed(self, xml_text: str, since: datetime) -> list[ArxivPaper]:
        root = ET.fromstring(xml_text)
        papers: list[ArxivPaper] = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            try:
                paper = self._parse_entry(entry)
            except Exception as exc:
                log.warning("arxiv_parse_error", error=str(exc))
                continue
            if paper.published_at >= since:
                papers.append(paper)
        return papers

    def _parse_entry(self, entry: ET.Element) -> ArxivPaper:
        raw_id = _text(entry, "id")
        # e.g. http://arxiv.org/abs/2401.00001v1 → 2401.00001
        arxiv_id = raw_id.rstrip("/").split("/")[-1].split("v")[0]

        authors = [
            _text(author, "name")
            for author in entry.findall(f"{{{_ATOM_NS}}}author")
        ]

        categories = [
            el.get("term", "")
            for el in entry.findall(f"{{{_ATOM_NS}}}category")
        ]

        published_str = _text(entry, "published")
        updated_str = _text(entry, "updated")

        pdf_url = ""
        abs_url = ""
        for link in entry.findall(f"{{{_ATOM_NS}}}link"):
            rel = link.get("rel", "")
            href = link.get("href", "")
            title = link.get("title", "")
            if title == "pdf":
                pdf_url = href
            elif rel == "alternate":
                abs_url = href

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=_text(entry, "title").replace("\n", " ").replace("  ", " "),
            abstract=_text(entry, "summary").replace("\n", " ").replace("  ", " "),
            authors=authors,
            categories=[c for c in categories if c],
            published_at=datetime.fromisoformat(published_str.replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(updated_str.replace("Z", "+00:00")),
            pdf_url=pdf_url,
            abs_url=abs_url,
        )
