import re
from urllib.parse import urlparse
from typing import List, Optional
from pydantic import BaseModel
from src.models.schemas import Source


class CredibilityReport(BaseModel):
    source_id: str
    url: str
    domain: str
    credibility_tier: str  # "primary" | "secondary" | "low-authority" | "unrated"
    tier_reason: str
    domain_age_hint: Optional[str] = None
    bias_indicators: List[str] = []
    trust_score: int  # 0 to 100


PRIMARY_DOMAINS = {
    "w3.org", "iso.org", "ietf.org", "ieee.org", "nist.gov", "who.int",
    "reuters.com", "apnews.com", "bloomberg.com", "afp.com", "cdc.gov", "nasa.gov",
    "nih.gov", "fda.gov", "usgs.gov", "noaa.gov", "cern.ch", "arxiv.org",
    "nature.com", "sciencedirect.com", "cell.com", "thelancet.com", "pnas.org",
    "acm.org", "springer.com", "wiley.com", "oxfordjournals.org"
}

SECONDARY_DOMAINS = {
    "nytimes.com", "bbc.com", "bbc.co.uk", "wsj.com", "theguardian.com",
    "washingtonpost.com", "ft.com", "cnbc.com", "forbes.com", "wired.com",
    "techcrunch.com", "arstechnica.com", "biorxiv.org", "github.com", "microsoft.com",
    "developer.mozilla.org", "sciencedaily.com", "economist.com", "theatlantic.com",
    "politico.com", "engadget.com", "theverge.com", "zdnet.com", "venturebeat.com"
}

LOW_AUTHORITY_DOMAINS = {
    "reddit.com", "quora.com", "medium.com", "tumblr.com", "substack.com",
    "dev.to", "pinterest.com", "answers.yahoo.com", "buzzfeed.com", "wikipedia.org",
    "wikihow.com", "wordpress.com", "blogspot.com"
}


class CredibilityAnalyzer:
    @staticmethod
    def extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return "unknown"

    @classmethod
    def analyze_source(cls, source: Source) -> CredibilityReport:
        domain = cls.extract_domain(source.url)
        tier = source.credibility_tier or "unrated"
        reasons = []
        bias = []
        score = 50  # baseline

        # Tier breakdown
        if domain.endswith((".gov", ".edu", ".mil", ".int")) or domain in PRIMARY_DOMAINS or any(domain.endswith("." + pd) for pd in PRIMARY_DOMAINS):
            tier = "primary"
            tier_reason = "Recognized governmental, academic, or top-tier peer-reviewed institution."
            score += 35
        elif domain in SECONDARY_DOMAINS or any(domain.endswith("." + sd) for sd in SECONDARY_DOMAINS):
            tier = "secondary"
            tier_reason = "Established mainstream news organization or technical documentation authority."
            score += 20
        elif domain in LOW_AUTHORITY_DOMAINS or any(domain.endswith("." + ld) for ld in LOW_AUTHORITY_DOMAINS):
            tier = "low-authority"
            tier_reason = "User-generated content platform, forum, or unverified self-publishing site."
            score -= 25
            bias.append("Potential User-Generated Content / Unverified Post")
        else:
            tier_reason = "Domain authority unclassified; assessed based on content recency and snippet quality."

        # Published date check
        if source.published_date:
            reasons.append(f"Publication date confirmed: {source.published_date}")
            score += 5
        else:
            reasons.append("Publication date missing (treated as n.d.)")

        # Relevance score check
        if source.relevance_score is not None:
            rel = source.relevance_score
            score += int(rel * 10)
            reasons.append(f"Vector search relevance score: {rel:.2f}")

        # Snippet quality check
        snippet_len = len(source.snippet) if source.snippet else 0
        if snippet_len > 250:
            score += 5
        elif snippet_len < 80:
            score -= 5
            bias.append("Very short snippet content")

        # HTTPS check
        if source.url.startswith("https://"):
            score += 5
        else:
            bias.append("Non-HTTPS unencrypted URL")
            score -= 10

        # Clamp score between 10 and 99
        final_score = max(10, min(99, score))

        return CredibilityReport(
            source_id=source.id,
            url=source.url,
            domain=domain,
            credibility_tier=tier,
            tier_reason=tier_reason,
            domain_age_hint="Established domain" if tier in ("primary", "secondary") else "Unverified domain age",
            bias_indicators=bias,
            trust_score=final_score,
        )
