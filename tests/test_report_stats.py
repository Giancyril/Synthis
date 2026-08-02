import pytest
from src.models.schemas import ResearchReport, KeyTakeaway, ReportSection, Source
from src.output.report_stats import compute_stats, ReportStats

def test_compute_stats_basic():
    report = ResearchReport(
        topic="Quantum Computing",
        generated_at="2026-08-02",
        key_takeaways=[
            KeyTakeaway(text="Quantum computers use qubits [S1].", source_ids=["S1"]),
            KeyTakeaway(text="Superconducting circuits are promising [S1] [S2].", source_ids=["S1", "S2"]),
        ],
        sections=[
            ReportSection(
                heading="Overview",
                content="Quantum computational superiority demonstrated in cryptographic applications [S1] [S2]. Architectural scalability remains challenging.",
            )
        ],
        sources=[
            Source(id="S1", url="https://ibm.com", title="IBM Quantum", snippet="Overview"),
            Source(id="S2", url="https://google.com", title="Google Quantum", snippet="Details"),
        ],
    )

    stats = compute_stats(report)
    assert isinstance(stats, ReportStats)
    assert stats.word_count > 0
    assert stats.reading_time_minutes >= 1
    assert stats.unique_sources_count == 2
    assert stats.avg_sources_per_takeaway == 1.5
    assert stats.complexity_label in ("Introductory", "Intermediate", "Advanced")
    assert stats.citation_density > 0.0

def test_compute_stats_empty_report():
    report = ResearchReport(
        topic="Empty Topic",
        generated_at="2026-08-02",
    )
    stats = compute_stats(report)
    assert stats.word_count == 0
    assert stats.reading_time_minutes == 0
    assert stats.unique_sources_count == 0
    assert stats.complexity_label == "Introductory"
