import logging
from urllib.parse import urlparse
from typing import List
from src.models.schemas import Source

logger = logging.getLogger(__name__)


class SourceFilter:
    def __init__(
        self,
        min_score: float = 0.2,
        max_sources: int = 15,
        max_per_domain: int = 3,
    ):
        self.min_score = min_score
        self.max_sources = max_sources
        self.max_per_domain = max_per_domain

    def filter_sources(self, raw_sources: List[Source]) -> List[Source]:
        """
        Filters and deduplicates a list of Source objects:
        1. Normalizes URLs and removes exact URL duplicates.
        2. Limits sources from a single domain (max_per_domain).
        3. Drops sources below min_score relevance threshold (if relevance_score is present).
        4. Caps total count to max_sources.
        5. Re-assigns contiguous IDs (S1, S2, ...) to retained sources.
        """
        if not raw_sources:
            return []

        seen_urls = set()
        domain_counts = {}
        retained: List[Source] = []

        for source in raw_sources:
            normalized_url = self._normalize_url(source.url)
            if not normalized_url or normalized_url in seen_urls:
                continue

            domain = self._extract_domain(normalized_url)
            if domain_counts.get(domain, 0) >= self.max_per_domain:
                continue

            if source.relevance_score is not None and source.relevance_score < self.min_score:
                continue

            seen_urls.add(normalized_url)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            retained.append(source)
            if len(retained) >= self.max_sources:
                break

        # Re-index IDs so downstream citations use clean S1, S2... references
        filtered_sources = []
        for idx, src in enumerate(retained, start=1):
            updated = src.model_copy(update={"id": f"S{idx}"})
            filtered_sources.append(updated)

        logger.info(f"Source filter: reduced {len(raw_sources)} raw sources to {len(filtered_sources)} clean sources.")
        return filtered_sources

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        cleaned = url.strip().rstrip("/")
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            cleaned = "https://" + cleaned
        return cleaned

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return "unknown"
