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

        # Re-index IDs and evaluate credibility tier for retained sources
        filtered_sources = []
        for idx, src in enumerate(retained, start=1):
            domain = self._extract_domain(src.url)
            tier = self.classify_credibility(domain)
            updated = src.model_copy(update={"id": f"S{idx}", "credibility_tier": tier})
            filtered_sources.append(updated)

        logger.info(f"Source filter: reduced {len(raw_sources)} raw sources to {len(filtered_sources)} clean sources.")
        return filtered_sources

    @classmethod
    def classify_credibility(cls, domain: str) -> str:
        """
        Classifies domain authority into 'primary', 'secondary', 'low-authority', or 'unrated'.
        Does not fall back to 'low-authority' if unknown — returns 'unrated'.
        """
        if not domain:
            return "unrated"

        d = domain.lower()
        if d.startswith("www."):
            d = d[4:]

        # Check primary TLDs (.gov, .edu, .mil, .int)
        primary_tlds = (".gov", ".edu", ".mil", ".int")
        if any(d.endswith(tld) or f"{tld}." in d for tld in primary_tlds):
            return "primary"

        primary_domains = {
            "w3.org", "iso.org", "ietf.org", "ieee.org", "nist.gov", "who.int",
            "reuters.com", "apnews.com", "bloomberg.com", "afp.com", "cdc.gov", "nasa.gov",
        }
        if d in primary_domains or any(d.endswith("." + pd) for pd in primary_domains):
            return "primary"

        secondary_domains = {
            "nytimes.com", "bbc.com", "bbc.co.uk", "wsj.com", "theguardian.com",
            "washingtonpost.com", "ft.com", "cnbc.com", "forbes.com", "wired.com",
            "techcrunch.com", "arstechnica.com", "nature.com", "sciencedirect.com",
            "arxiv.org", "biorxiv.org", "github.com", "microsoft.com",
            "developer.mozilla.org", "sciencedaily.com", "ieee.org"
        }
        if d in secondary_domains or any(d.endswith("." + sd) for sd in secondary_domains):
            return "secondary"

        low_authority_domains = {
            "reddit.com", "quora.com", "medium.com", "tumblr.com", "substack.com",
            "dev.to", "pinterest.com", "answers.yahoo.com"
        }
        if d in low_authority_domains or any(d.endswith("." + ld) for ld in low_authority_domains):
            return "low-authority"

        return "unrated"

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
