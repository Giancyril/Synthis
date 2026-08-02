import pytest
from src.models.schemas import ResearchReport, KeyTakeaway, ReportSection, Source
from src.output.executive_brief import generate_brief, ExecutiveBrief


def _make_report():
    return ResearchReport(
        topic="Solid State Battery Breakthroughs",
        generated_at="2026-08-02",
        key_takeaways=[
            KeyTakeaway(text="Takeaway 1 with single source", source_ids=["S1"], corroboration_count=1),
            KeyTakeaway(text="Takeaway 2 with multi-source corroboration", source_ids=["S1", "S2"], corroboration_count=2),
            KeyTakeaway(text="Takeaway 3 with triple corroboration", source_ids=["S1", "S2", "S3"], corroboration_count=3),
            KeyTakeaway(text="Takeaway 4 low priority", source_ids=["S4"], corroboration_count=1),
        ],
        sections=[
            ReportSection(
                heading="Commercialization Timeline",
                content="Energy density reaches 500 Wh/kg by 2026. Production costs fall 40% compared to standard lithium-ion cells [S1].",
            ),
            ReportSection(
                heading="Solid Electrolyte Safety",
                content="Thermal runaway risks decrease by 90% when replacing liquid organic solvents with ceramic separators [S2].",
            ),
        ],
        sources=[
            Source(id="S1", url="https://example.com/1", title="Source 1", snippet="Snippet 1"),
            Source(id="S2", url="https://example.com/2", title="Source 2", snippet="Snippet 2"),
            Source(id="S3", url="https://example.com/3", title="Source 3", snippet="Snippet 3"),
        ],
        confidence_note="Preliminary findings based on lab-scale trials.",
    )


def test_generate_brief_structure():
    report = _make_report()
    brief = generate_brief(report)
    assert isinstance(brief, ExecutiveBrief)
    assert brief.topic == "Solid State Battery Breakthroughs"
    assert len(brief.top_takeaways) <= 3
    assert brief.source_count == 3
    assert brief.confidence_note == "Preliminary findings based on lab-scale trials."


def test_generate_brief_ranks_takeaways_by_corroboration():
    report = _make_report()
    brief = generate_brief(report)
    # Highest corroboration (3 and 2) should come first
    assert "Takeaway 3" in brief.top_takeaways[0]
    assert "Takeaway 2" in brief.top_takeaways[1]


def test_generate_brief_extracts_highlight_stats():
    report = _make_report()
    brief = generate_brief(report)
    assert len(brief.highlight_stats) > 0
    assert any("500 Wh/kg" in stat or "90%" in stat for stat in brief.highlight_stats)


def test_generate_brief_caps_sections():
    report = _make_report()
    brief = generate_brief(report)
    assert len(brief.key_sections) <= 2


def test_generate_brief_empty_report():
    report = ResearchReport(topic="Empty Topic", generated_at="2026-08-02")
    brief = generate_brief(report)
    assert brief.topic == "Empty Topic"
    assert brief.top_takeaways == []
    assert brief.highlight_stats == []
    assert brief.key_sections == []
