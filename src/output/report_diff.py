"""
Report diffing and topic similarity engine for Synthis research reports.

Computes structured diffs between any two ResearchReport instances:
- New sources retrieved in report B (not in report A)
- Stale sources in report A (not retrieved in report B)
- New key takeaways added in report B
- Contradicted/changed takeaways between report A and B (highlighted for user review)
- Jaccard token similarity for auto-detecting prior reports on similar topics
"""

from __future__ import annotations

import re
from typing import List, Tuple, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from src.models.schemas import ResearchReport, Source, KeyTakeaway


# ---------------------------------------------------------------------------
# DTO Models for Report Diffing
# ---------------------------------------------------------------------------

class TakeawayDiffItem(BaseModel):
    text: str
    source_ids: List[str] = Field(default_factory=list)
    status: str  # "new" | "unchanged" | "contradicted_candidate"
    note: Optional[str] = None


class ReportDiff(BaseModel):
    old_report_id: str
    new_report_id: str
    old_topic: str
    new_topic: str
    topic_similarity: float
    new_sources: List[Source] = Field(default_factory=list)
    stale_sources: List[Source] = Field(default_factory=list)
    shared_sources: List[Source] = Field(default_factory=list)
    new_takeaways: List[TakeawayDiffItem] = Field(default_factory=list)
    contradicted_takeaways: List[TakeawayDiffItem] = Field(default_factory=list)
    unchanged_takeaways: List[TakeawayDiffItem] = Field(default_factory=list)


class SimilarReportHint(BaseModel):
    report_id: str
    topic: str
    generated_at: str
    similarity: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Strip scheme, trailing slashes, www prefix, and query params for URL matching."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = re.sub(r"^www\.", "", host).lower()
        path = parsed.path.rstrip("/") if parsed.netloc else ""
        return f"{host}{path}"
    except Exception:
        return url.strip().lower()


def _tokenize(text: str) -> set[str]:
    """Extract clean word tokens (3+ chars) for string similarity."""
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
    # Stop words filter for topic matching
    stop_words = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was",
        "were", "will", "latest", "overview", "tech", "technology", "2024", "2025", "2026"
    }
    return {w for w in words if w not in stop_words}


def topic_similarity(topic_a: str, topic_b: str) -> float:
    """
    Compute Jaccard token overlap between two topic titles.
    Returns float in range [0.0, 1.0].
    """
    tokens_a = _tokenize(topic_a)
    tokens_b = _tokenize(topic_b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)

    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Diff Calculation
# ---------------------------------------------------------------------------

def _words(text: str) -> set[str]:
    """Extract clean words of length 2+ for takeaway matching."""
    return set(re.findall(r"\b[a-zA-Z0-9]{2,}\b", text.lower()))


def _text_similarity(a: str, b: str) -> float:
    wa = _words(a)
    wb = _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa.intersection(wb)) / len(wa.union(wb))


def compute_diff(old_report: ResearchReport, new_report: ResearchReport, old_id: str = "old", new_id: str = "new") -> ReportDiff:
    """
    Compute a structured diff between an older report and a newer report.
    """
    sim = topic_similarity(old_report.topic, new_report.topic)

    # 1. Source diffing by normalized URL
    old_urls = {normalize_url(s.url): s for s in old_report.sources}
    new_urls = {normalize_url(s.url): s for s in new_report.sources}

    new_sources = [s for norm, s in new_urls.items() if norm not in old_urls]
    stale_sources = [s for norm, s in old_urls.items() if norm not in new_urls]
    shared_sources = [s for norm, s in new_urls.items() if norm in old_urls]

    # 2. Takeaway diffing
    old_takeaways_text = [t.text for t in old_report.key_takeaways]

    new_takeaways: List[TakeawayDiffItem] = []
    contradicted_takeaways: List[TakeawayDiffItem] = []
    unchanged_takeaways: List[TakeawayDiffItem] = []

    negation_words = {
        "not", "no", "failed", "delayed", "delay", "unlike", "however",
        "instead", "never", "decreased", "dropped", "unlikely", "contradict", "opposite"
    }

    for t in new_report.key_takeaways:
        t_words = _words(t.text)

        # Check for near-exact match
        is_exact = any(_text_similarity(t.text, old_t) > 0.70 for old_t in old_takeaways_text)
        if is_exact:
            unchanged_takeaways.append(
                TakeawayDiffItem(text=t.text, source_ids=t.source_ids, status="unchanged")
            )
            continue

        # Check for potential contradiction (2+ overlapping topic words + a negation/delay word)
        has_negation = bool(t_words.intersection(negation_words))
        has_similar_topic_old = any(
            len(_words(t.text).intersection(_words(old_t))) >= 2 for old_t in old_takeaways_text
        )

        if has_negation and has_similar_topic_old:
            contradicted_takeaways.append(
                TakeawayDiffItem(
                    text=t.text,
                    source_ids=t.source_ids,
                    status="contradicted_candidate",
                    note="May contradict or update findings from the prior report.",
                )
            )
        else:
            new_takeaways.append(
                TakeawayDiffItem(text=t.text, source_ids=t.source_ids, status="new")
            )

    return ReportDiff(
        old_report_id=old_id,
        new_report_id=new_id,
        old_topic=old_report.topic,
        new_topic=new_report.topic,
        topic_similarity=round(sim, 2),
        new_sources=new_sources,
        stale_sources=stale_sources,
        shared_sources=shared_sources,
        new_takeaways=new_takeaways,
        contradicted_takeaways=contradicted_takeaways,
        unchanged_takeaways=unchanged_takeaways,
    )
