from typing import List
from urllib.parse import urlparse
from pydantic import BaseModel
from src.models.schemas import Source


class SourceQualityReport(BaseModel):
    domain_diversity_score: int  # 0 to 100
    primary_source_ratio: float  # e.g. 0.33
    recency_score: int  # 0 to 100
    echo_chamber_risk: str  # "Low" | "Medium" | "High"
    warnings: List[str]
    recommendations: List[str]


def run_watchdog(sources: List[Source]) -> SourceQualityReport:
    if not sources:
        return SourceQualityReport(
            domain_diversity_score=0,
            primary_source_ratio=0.0,
            recency_score=0,
            echo_chamber_risk="High",
            warnings=["No sources retrieved."],
            recommendations=["Run search with broader criteria or remove restrictive domain filters."],
        )

    # 1. Domain diversity calculation
    domains = []
    for s in sources:
        try:
            d = urlparse(s.url).netloc.lower().replace("www.", "")
            domains.append(d or "unknown")
        except Exception:
            domains.append("unknown")

    unique_domains = set(domains)
    total_sources = len(sources)
    domain_diversity_ratio = len(unique_domains) / total_sources
    domain_diversity_score = int(min(100, domain_diversity_ratio * 100))

    # 2. Primary source ratio
    primary_count = sum(1 for s in sources if (s.credibility_tier or "").lower() == "primary")
    secondary_count = sum(1 for s in sources if (s.credibility_tier or "").lower() == "secondary")
    low_auth_count = sum(1 for s in sources if (s.credibility_tier or "").lower() == "low-authority")
    primary_source_ratio = round(primary_count / total_sources, 2)

    # 3. Recency score
    dated_sources = [s for s in sources if s.published_date]
    if dated_sources:
        recency_score = int(min(100, (len(dated_sources) / total_sources) * 100))
    else:
        recency_score = 30

    # 4. Echo chamber risk & Warnings / Recommendations
    warnings = []
    recommendations = []

    # Check max frequency of any single domain
    from collections import Counter
    domain_counts = Counter(domains)
    most_common_domain, max_freq = domain_counts.most_common(1)[0]
    domain_share = max_freq / total_sources

    if domain_share > 0.4:
        echo_risk = "High"
        warnings.append(f"High concentration of results from single domain '{most_common_domain}' ({max_freq}/{total_sources} sources).")
        recommendations.append("Apply domain exclusion filters to diversify reference sources.")
    elif domain_diversity_score < 50:
        echo_risk = "Medium"
        warnings.append("Limited domain diversity across retrieved sources.")
        recommendations.append("Broaden search query terms to cover different web sectors.")
    elif low_auth_count > primary_count + secondary_count:
        echo_risk = "High"
        warnings.append("Low-authority / user-generated sources outnumber verified institutional sources.")
        recommendations.append("Filter search scope or include domain allowlists (e.g. .edu, .gov).")
    else:
        echo_risk = "Low"

    if primary_count == 0:
        warnings.append("Zero primary academic/governmental sources retrieved.")
        recommendations.append("Consider restricting search to scholar or official domain scopes.")

    if not warnings:
        warnings.append("Source portfolio meets all diversity, recency, and credibility benchmarks.")

    if not recommendations:
        recommendations.append("Source distribution is balanced across authoritative domains.")

    return SourceQualityReport(
        domain_diversity_score=domain_diversity_score,
        primary_source_ratio=primary_source_ratio,
        recency_score=recency_score,
        echo_chamber_risk=echo_risk,
        warnings=warnings,
        recommendations=recommendations,
    )
