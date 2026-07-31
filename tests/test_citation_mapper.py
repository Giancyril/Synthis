from src.models.schemas import Source, ReportSection, KeyTakeaway
from src.pipeline.citation_mapper import CitationMapper


def test_citation_mapper_validates_known_citations():
    sources = [
        Source(id="S1", url="https://example.com/s1", title="Source 1", snippet="S1 snippet"),
        Source(id="S2", url="https://example.com/s2", title="Source 2", snippet="S2 snippet"),
    ]

    sections = [
        ReportSection(
            heading="Introduction",
            content="This is backed by evidence [S1] and also [S2].",
        )
    ]

    mapper = CitationMapper()
    updated_sections, takeaways, warnings = mapper.validate_and_map_citations(sections, sources)

    assert len(updated_sections) == 1
    sec = updated_sections[0]
    assert len(sec.citations) == 2
    assert sec.citations[0].source_id == "S1"
    assert sec.citations[1].source_id == "S2"


def test_citation_mapper_strips_hallucinated_citations():
    sources = [
        Source(id="S1", url="https://example.com/s1", title="Source 1", snippet="S1 snippet")
    ]

    sections = [
        ReportSection(
            heading="Analysis",
            content="Valid statement [S1] but this one is fake [S99].",
        )
    ]

    mapper = CitationMapper()
    updated_sections, takeaways, warnings = mapper.validate_and_map_citations(sections, sources)

    assert len(updated_sections) == 1
    sec = updated_sections[0]
    assert len(sec.citations) == 1
    assert sec.citations[0].source_id == "S1"
    assert "[S99]" not in sec.content
    assert any("Removed hallucinated citation [S99]" in w for w in warnings)


def test_citation_mapper_takeaway_corroboration():
    sources = [
        Source(id="S1", url="https://a.com", title="S1", snippet="S1"),
        Source(id="S2", url="https://b.com", title="S2", snippet="S2"),
    ]

    takeaways = [
        KeyTakeaway(text="Multi-sourced claim", source_ids=["S1", "S2", "S99"]),
        KeyTakeaway(text="Single-sourced claim", source_ids=["S1"]),
    ]

    mapper = CitationMapper()
    _, updated_takeaways, _ = mapper.validate_and_map_citations([], sources, takeaways=takeaways)

    assert len(updated_takeaways) == 2
    assert updated_takeaways[0].source_ids == ["S1", "S2"]
    assert updated_takeaways[0].corroboration_count == 2
    assert updated_takeaways[1].corroboration_count == 1


def test_citation_mapper_recency_audit_staleness():
    from datetime import date, timedelta
    from src.pipeline.citation_mapper import CitationMapper

    old_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
    sources = [
        Source(id="S1", url="https://a.com", title="S1", snippet="S1", published_date=old_date),
        Source(id="S2", url="https://b.com", title="S2", snippet="S2", published_date=old_date),
    ]
    note = CitationMapper.audit_recency_and_confidence(sources, existing_note=None)
    assert note is not None
    assert "year old" in note


def test_citation_mapper_recency_audit_missing_dates():
    from src.pipeline.citation_mapper import CitationMapper

    sources = [
        Source(id="S1", url="https://a.com", title="S1", snippet="S1", published_date=None),
        Source(id="S2", url="https://b.com", title="S2", snippet="S2", published_date=None),
        Source(id="S3", url="https://c.com", title="S3", snippet="S3", published_date=None),
    ]
    note = CitationMapper.audit_recency_and_confidence(sources, existing_note=None)
    assert note is not None
    assert "unavailable" in note


def test_citation_mapper_recency_audit_fresh_sources():
    from datetime import date, timedelta
    from src.pipeline.citation_mapper import CitationMapper

    recent_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    sources = [
        Source(id="S1", url="https://a.com", title="S1", snippet="S1", published_date=recent_date),
        Source(id="S2", url="https://b.com", title="S2", snippet="S2", published_date=recent_date),
    ]
    # Fresh sources should not trigger any warning
    note = CitationMapper.audit_recency_and_confidence(sources, existing_note=None)
    assert note is None


