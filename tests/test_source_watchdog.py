import pytest
from src.models.schemas import Source
from src.pipeline.source_watchdog import run_watchdog, SourceQualityReport

def test_watchdog_diverse_sources():
    sources = [
        Source(id="S1", url="https://arxiv.org/abs/1", title="Paper 1", snippet="...", credibility_tier="primary", published_date="2024-01-01"),
        Source(id="S2", url="https://nature.com/articles/2", title="Paper 2", snippet="...", credibility_tier="primary", published_date="2024-01-02"),
        Source(id="S3", url="https://wired.com/story/3", title="Article 3", snippet="...", credibility_tier="secondary", published_date="2024-01-03"),
    ]
    report = run_watchdog(sources)
    assert isinstance(report, SourceQualityReport)
    assert report.domain_diversity_score == 100
    assert report.primary_source_ratio > 0.6
    assert report.echo_chamber_risk == "Low"

def test_watchdog_echo_chamber():
    sources = [
        Source(id="S1", url="https://medium.com/post1", title="Post 1", snippet="...", credibility_tier="low-authority"),
        Source(id="S2", url="https://medium.com/post2", title="Post 2", snippet="...", credibility_tier="low-authority"),
        Source(id="S3", url="https://medium.com/post3", title="Post 3", snippet="...", credibility_tier="low-authority"),
    ]
    report = run_watchdog(sources)
    assert report.echo_chamber_risk == "High"
    assert report.primary_source_ratio == 0.0
    assert any("medium.com" in w for w in report.warnings)

def test_watchdog_empty_sources():
    report = run_watchdog([])
    assert report.domain_diversity_score == 0
    assert report.echo_chamber_risk == "High"
