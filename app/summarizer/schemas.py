from datetime import datetime

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    category: str
    window_days: int = 7
    top_n: int = 10


class TrendSummaryOutput(BaseModel):
    category: str
    window_days: int
    summary: str
    keywords_covered: list[str]
    generated_at: datetime
    model_used: str
