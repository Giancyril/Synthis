import pytest
from src.models.schemas import ResearchReport, KeyTakeaway, ReportSection, Source
from src.output.keyword_extractor import extract_keywords, cluster_themes, KeywordResult, ThemeCluster


def _make_report():
    return ResearchReport(
        topic="Quantum Computing",
        generated_at="2026-08-02",
        key_takeaways=[
            KeyTakeaway(text="Quantum processors use quantum entanglement for computation.", source_ids=["S1"]),
            KeyTakeaway(text="Superconducting quantum chips show exponential speedup.", source_ids=["S2"]),
        ],
        sections=[
            ReportSection(
                heading="Quantum Hardware Advances",
                content="Quantum computers leverage qubits and quantum superposition. Superconducting circuits dominate hardware development.",
            ),
        ],
        sources=[
            Source(id="S1", url="https://arxiv.org/q1", title="Quantum Paper 1",
                   snippet="quantum entanglement processors computation speedup"),
            Source(id="S2", url="https://nature.com/q2", title="Quantum Paper 2",
                   snippet="superconducting quantum chips exponential computation"),
        ],
    )


def test_extract_keywords_returns_list():
    report = _make_report()
    kws = extract_keywords(report, top_n=10)
    assert isinstance(kws, list)
    assert len(kws) > 0
    assert all(isinstance(k, KeywordResult) for k in kws)


def test_extract_keywords_no_stop_words():
    report = _make_report()
    kws = extract_keywords(report, top_n=15)
    stop = {"the", "and", "for", "with", "is", "are"}
    for kw in kws:
        assert kw.keyword not in stop


def test_extract_keywords_weights_normalized():
    report = _make_report()
    kws = extract_keywords(report, top_n=15)
    assert kws[0].weight == 1.0
    for kw in kws:
        assert 0.0 < kw.weight <= 1.0


def test_extract_keywords_empty_report():
    report = ResearchReport(topic="Empty", generated_at="2026-08-02")
    kws = extract_keywords(report)
    assert kws == []


def test_cluster_themes_returns_clusters():
    report = _make_report()
    kws = extract_keywords(report, top_n=15)
    clusters = cluster_themes(kws, n_themes=3)
    assert isinstance(clusters, list)
    assert len(clusters) <= 3
    assert all(isinstance(c, ThemeCluster) for c in clusters)


def test_cluster_themes_empty():
    clusters = cluster_themes([], n_themes=5)
    assert clusters == []


def test_keywords_top_n_respected():
    report = _make_report()
    kws = extract_keywords(report, top_n=5)
    assert len(kws) <= 5
