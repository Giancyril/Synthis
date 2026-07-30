from src.models.schemas import Source
from src.pipeline.source_filter import SourceFilter


def test_source_filter_deduplicates_urls():
    sources = [
        Source(id="S1", url="https://example.com/article", title="A1", snippet="S1"),
        Source(id="S2", url="https://example.com/article/", title="A2", snippet="S2"),  # duplicate with trailing slash
        Source(id="S3", url="https://other.com/article", title="A3", snippet="S3"),
    ]

    sf = SourceFilter()
    filtered = sf.filter_sources(sources)

    assert len(filtered) == 2
    assert filtered[0].id == "S1"
    assert filtered[1].id == "S2"
    assert filtered[0].url == "https://example.com/article"
    assert filtered[1].url == "https://other.com/article"


def test_source_filter_relevance_threshold_and_cap():
    sources = [
        Source(id="S1", url="https://a.com/1", title="A1", snippet="S1", relevance_score=0.9),
        Source(id="S2", url="https://b.com/2", title="A2", snippet="S2", relevance_score=0.1),  # below 0.2
        Source(id="S3", url="https://c.com/3", title="A3", snippet="S3", relevance_score=0.8),
        Source(id="S4", url="https://d.com/4", title="A4", snippet="S4", relevance_score=0.7),
    ]

    sf = SourceFilter(min_score=0.2, max_sources=2)
    filtered = sf.filter_sources(sources)

    assert len(filtered) == 2
    assert filtered[0].id == "S1"
    assert filtered[1].id == "S2"
    assert filtered[0].url == "https://a.com/1"
    assert filtered[1].url == "https://c.com/3"


def test_source_filter_per_domain_limit():
    sources = [
        Source(id="S1", url="https://news.com/1", title="N1", snippet="S1"),
        Source(id="S2", url="https://news.com/2", title="N2", snippet="S2"),
        Source(id="S3", url="https://news.com/3", title="N3", snippet="S3"),
        Source(id="S4", url="https://news.com/4", title="N4", snippet="S4"),  # 4th from same domain
    ]

    sf = SourceFilter(max_per_domain=2)
    filtered = sf.filter_sources(sources)

    assert len(filtered) == 2
