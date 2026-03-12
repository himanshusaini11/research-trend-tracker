from __future__ import annotations

import re
from collections import Counter

from app.ingestion.schemas import ArxivPaper, KeywordExtractionResult

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "that", "this",
        "all", "you", "these", "those", "it", "its", "we", "our", "they", "their", "which",
        "who", "what", "how", "when", "where", "as", "if", "not", "no", "also",
        "such", "than", "then", "so", "up", "out", "about", "into", "through",
        "show", "shows", "shown", "use", "used", "using", "based", "paper",
        "propose", "proposed", "presents", "present", "results",
    }
)

_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")  # words of 3+ letters only


class KeywordIndexer:
    """Extract top keywords from a paper's title + abstract using term frequency."""

    def extract_keywords(self, paper: ArxivPaper, top_n: int = 10) -> KeywordExtractionResult:
        text = f"{paper.title} {paper.abstract}".lower()
        tokens = _TOKEN_RE.findall(text)
        filtered = [t for t in tokens if t not in _STOPWORDS]
        top = [word for word, _ in Counter(filtered).most_common(top_n)]
        return KeywordExtractionResult(
            arxiv_id=paper.arxiv_id,
            keywords=top,
            extraction_method="tf_stopword",
        )
