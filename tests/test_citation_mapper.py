from src.models.schemas import Source, ReportSection
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
    updated_sections, warnings = mapper.validate_and_map_citations(sections, sources)

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
    updated_sections, warnings = mapper.validate_and_map_citations(sections, sources)

    assert len(updated_sections) == 1
    sec = updated_sections[0]
    assert len(sec.citations) == 1
    assert sec.citations[0].source_id == "S1"
    assert "[S99]" not in sec.content
    assert any("Removed hallucinated citation [S99]" in w for w in warnings)
