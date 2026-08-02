import pytest
from src.models.schemas import Source
from src.pipeline.credibility_analyzer import CredibilityAnalyzer, CredibilityReport

def test_analyze_primary_source():
    src = Source(
        id="S1",
        url="https://arxiv.org/abs/2401.12345",
        title="Deep Research Methods",
        snippet="Detailed paper on deep research methods in artificial intelligence and agentic workflows.",
        published_date="2024-01-15",
        relevance_score=0.92,
    )
    report = CredibilityAnalyzer.analyze_source(src)
    assert report.source_id == "S1"
    assert report.domain == "arxiv.org"
    assert report.credibility_tier == "primary"
    assert report.trust_score >= 80
    assert "arxiv.org" in report.url

def test_analyze_secondary_source():
    src = Source(
        id="S2",
        url="https://www.wired.com/story/ai-agents-news/",
        title="Wired AI Article",
        snippet="An overview of AI agents changing technology industries across the globe.",
        published_date="2024-02-01",
        relevance_score=0.75,
    )
    report = CredibilityAnalyzer.analyze_source(src)
    assert report.credibility_tier == "secondary"
    assert 60 <= report.trust_score <= 95

def test_analyze_low_authority_source():
    src = Source(
        id="S3",
        url="https://reddit.com/r/technology/comments/12345",
        title="Reddit Post",
        snippet="Short comment.",
        published_date=None,
        relevance_score=0.3,
    )
    report = CredibilityAnalyzer.analyze_source(src)
    assert report.credibility_tier == "low-authority"
    assert report.trust_score < 60
    assert len(report.bias_indicators) > 0

def test_http_bias_indicator():
    src = Source(
        id="S4",
        url="http://example.com/info",
        title="Example Info",
        snippet="Some general information snippet that is long enough to satisfy basic length requirements.",
    )
    report = CredibilityAnalyzer.analyze_source(src)
    assert "Non-HTTPS unencrypted URL" in report.bias_indicators
