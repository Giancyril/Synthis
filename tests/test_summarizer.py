from unittest.mock import MagicMock
from src.models.schemas import Source
from src.pipeline.summarizer import SourceSummarizer
from src.services.gemini_client import GeminiService


def test_summarizer_populates_summary_field():
    mock_gemini = MagicMock(spec=GeminiService)
    mock_gemini.generate_text.return_value = "This source discusses quantum supremacy achieved in 2026."

    sources = [
        Source(
            id="S1",
            url="https://example.com/quantum",
            title="Quantum News",
            snippet="Scientists at quantum lab achieved groundbreaking fidelity in qubit processing.",
        )
    ]

    summarizer = SourceSummarizer(mock_gemini)
    result = summarizer.summarize_sources(sources)

    assert len(result) == 1
    assert result[0].summary == "This source discusses quantum supremacy achieved in 2026."
    mock_gemini.generate_text.assert_called_once()


def test_summarizer_handles_thin_snippet():
    mock_gemini = MagicMock(spec=GeminiService)

    sources = [
        Source(
            id="S1",
            url="https://example.com/thin",
            title="Thin Page",
            snippet="Short text",  # under 15 chars
        )
    ]

    summarizer = SourceSummarizer(mock_gemini)
    result = summarizer.summarize_sources(sources)

    assert len(result) == 1
    assert "Limited content available" in result[0].summary
    mock_gemini.generate_text.assert_not_called()
