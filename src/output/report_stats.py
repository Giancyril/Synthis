import re
from typing import List, Optional
from pydantic import BaseModel
from src.models.schemas import ResearchReport


class ReportStats(BaseModel):
    word_count: int
    reading_time_minutes: int
    unique_sources_count: int
    avg_sources_per_takeaway: float
    complexity_label: str  # "Introductory" | "Intermediate" | "Advanced"
    citation_density: float  # citations per 100 words


def compute_stats(report: ResearchReport) -> ReportStats:
    # 1. Total word count across takeaways and section contents
    text_parts = []
    for kt in report.key_takeaways or []:
        text_parts.append(kt.text)
    for sec in report.sections or []:
        text_parts.append(sec.heading)
        text_parts.append(sec.content)

    full_text = " ".join(text_parts)
    # Remove citation tags like [S1] [S2] for clean word count
    clean_text = re.sub(r"\[S\d+\]", "", full_text)
    words = clean_text.split()
    word_count = len(words)

    # 2. Reading time: average reading speed = 200 words per minute (minimum 1 min if > 0 words)
    reading_time = max(1, round(word_count / 200)) if word_count > 0 else 0

    # 3. Unique sources count
    unique_sources = len(report.sources or [])

    # 4. Avg sources per takeaway
    takeaways = report.key_takeaways or []
    if takeaways:
        total_sids = sum(len(kt.source_ids or []) for kt in takeaways)
        avg_sources_per_takeaway = round(total_sids / len(takeaways), 1)
    else:
        avg_sources_per_takeaway = 0.0

    # 5. Citation density (citations per 100 words)
    citations_count = len(re.findall(r"\[S\d+\]", full_text))
    if word_count > 0:
        citation_density = round((citations_count / word_count) * 100, 1)
    else:
        citation_density = 0.0

    # 6. Complexity classification
    # Based on average word length + technical density heuristic
    if word_count == 0:
        complexity = "Introductory"
    else:
        avg_word_len = sum(len(w) for w in words) / word_count
        long_words = [w for w in words if len(w) >= 8]
        long_word_ratio = len(long_words) / word_count

        if avg_word_len > 5.8 or long_word_ratio > 0.22 or unique_sources >= 10:
            complexity = "Advanced"
        elif avg_word_len > 5.0 or long_word_ratio > 0.15 or unique_sources >= 5:
            complexity = "Intermediate"
        else:
            complexity = "Introductory"

    return ReportStats(
        word_count=word_count,
        reading_time_minutes=reading_time,
        unique_sources_count=unique_sources,
        avg_sources_per_takeaway=avg_sources_per_takeaway,
        complexity_label=complexity,
        citation_density=citation_density,
    )
