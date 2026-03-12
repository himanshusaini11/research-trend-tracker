from datetime import date, datetime

from pydantic import BaseModel


class TrendWindow(BaseModel):
    keyword: str
    category: str
    window_date: date
    count: int
    rank: int | None = None


class TrendSummary(BaseModel):
    keyword: str
    total_count: int
    window_counts: list[TrendWindow]
    velocity: float  # linear regression slope of count over time (positive = growing)


class TopPaper(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    categories: list[str]
    published_at: datetime
    keyword_overlap: int  # number of queried keywords present in this paper


class AnalyticsResult(BaseModel):
    category: str
    window_days: int
    trends: list[TrendSummary]
    generated_at: datetime
