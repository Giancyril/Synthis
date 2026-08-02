"""
Tests for src/output/report_diff.py
"""

import pytest
from src.models.schemas import ResearchReport, Source, KeyTakeaway
from src.output.report_diff import (
    normalize_url,
    topic_similarity,
    compute_diff,
    ReportDiff,
)


def test_normalize_url():
    assert normalize_url("https://www.nature.com/articles/123/") == "nature.com/articles/123"
    assert normalize_url("http://arxiv.org/abs/123?ref=1") == "arxiv.org/abs/123"


def test_topic_similarity_identical():
    sim = topic_similarity("Solid state batteries 2026", "Solid state batteries 2026")
    assert sim == 1.0


def test_topic_similarity_similar():
    sim = topic_similarity("Solid state battery technology 2026", "Solid state battery advances")
    assert sim > 0.4


def test_topic_similarity_different():
    sim = topic_similarity("Quantum computing algorithms", "mRNA vaccine development")
    assert sim == 0.0


def test_compute_diff_new_and_stale_sources():
    s1 = Source(id="S1", url="https://example.com/s1", title="S1", snippet="snip1")
    s2 = Source(id="S2", url="https://example.com/s2", title="S2", snippet="snip2")
    s3 = Source(id="S3", url="https://example.com/s3", title="S3", snippet="snip3")

    old_report = ResearchReport(
        topic="AI in Healthcare",
        generated_at="2026-01-01",
        sources=[s1, s2],
        key_takeaways=[KeyTakeaway(text="AI helps diagnostics", source_ids=["S1"])],
    )

    new_report = ResearchReport(
        topic="AI in Healthcare Systems",
        generated_at="2026-02-01",
        sources=[s2, s3],  # s1 is stale, s3 is new, s2 is shared
        key_takeaways=[
            KeyTakeaway(text="AI helps diagnostics", source_ids=["S2"]),
            KeyTakeaway(text="AI reduces hospital waiting time dramatically", source_ids=["S3"]),
        ],
    )

    diff = compute_diff(old_report, new_report, "old_rep", "new_rep")

    assert len(diff.new_sources) == 1
    assert diff.new_sources[0].id == "S3"

    assert len(diff.stale_sources) == 1
    assert diff.stale_sources[0].id == "S1"

    assert len(diff.shared_sources) == 1
    assert diff.shared_sources[0].id == "S2"

    assert diff.topic_similarity >= 0.5


def test_compute_diff_contradicted_takeaway():
    old_report = ResearchReport(
        topic="Commercial fusion energy timeline",
        generated_at="2026-01-01",
        sources=[],
        key_takeaways=[KeyTakeaway(text="Commercial fusion expected by year 2028", source_ids=[])],
    )

    new_report = ResearchReport(
        topic="Commercial fusion energy timeline",
        generated_at="2026-02-01",
        sources=[],
        key_takeaways=[
            KeyTakeaway(
                text="Commercial fusion not expected until 2035 due to grid infrastructure delay",
                source_ids=[],
            )
        ],
    )

    diff = compute_diff(old_report, new_report)
    assert len(diff.contradicted_takeaways) == 1
    assert "not expected" in diff.contradicted_takeaways[0].text
