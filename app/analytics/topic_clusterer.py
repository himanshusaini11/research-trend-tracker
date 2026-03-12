from __future__ import annotations

_PREFIX_LEN = 4


def _shared_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


class TopicClusterer:
    """Group keywords into topics by shared prefix (>= 4 chars). Stdlib only."""

    def cluster_keywords(self, keywords: list[str]) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {}  # label → members

        for keyword in keywords:
            matched_label: str | None = None
            for label in clusters:
                if _shared_prefix_len(keyword, label) >= _PREFIX_LEN:
                    matched_label = label
                    break
            if matched_label is not None:
                clusters[matched_label].append(keyword)
            else:
                clusters[keyword] = [keyword]

        return clusters
