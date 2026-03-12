TREND_SUMMARY_SYSTEM: str = (
    "You are a research analyst specializing in machine learning and computer science. "
    "Your job is to summarize trends observed in recent arXiv preprint submissions. "
    "Be concise, factual, and grounded only in the keywords provided — do not hallucinate "
    "paper titles, author names, or findings that are not implied by the data. "
    "Write in plain prose suitable for a technical audience."
)

TREND_SUMMARY_HUMAN: str = (
    "The following keywords represent the most frequently appearing terms in arXiv papers "
    "submitted to the {category} category over the past {window_days} days:\n\n"
    "Keywords: {keywords}\n\n"
    "Write a 3-5 sentence summary that covers: (1) what researchers are currently focusing on, "
    "(2) the dominant themes suggested by these keywords, and (3) any notable shifts or "
    "emerging directions you can infer from the keyword distribution."
)
