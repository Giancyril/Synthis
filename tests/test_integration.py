import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.config import Config
from src.main import run_research_pipeline
from src.services.gemini_client import GeminiService
from src.services.tavily_client import TavilyService
from src.models.schemas import ResearchReport


def test_full_pipeline_mocked(tmp_path: Path):
    mock_config = MagicMock(spec=Config)
    mock_config.gemini_api_key = "mock_key"
    mock_config.tavily_api_key = "mock_key"
    mock_config.gemini_model = "gemini-2.5-flash"

    # Patch GeminiService & TavilyService calls
    mock_gemini = MagicMock(spec=GeminiService)
    mock_gemini.generate_text.side_effect = [
        '["query 1", "query 2"]',  # Query planner
        "Summary of source content.",  # Summarizer for S1
        "Summary of source content.",  # Summarizer for S2
        """{
            "key_takeaways": [{"text": "Takeaway 1", "source_ids": ["S1"]}],
            "sections": [{"heading": "Overview", "content": "Evidence [S1]."}],
            "confidence_note": null
        }""",  # Synthesizer
    ]

    mock_tavily = MagicMock(spec=TavilyService)
    mock_tavily.search.return_value = [
        {"url": "https://example.com/1", "title": "Title 1", "snippet": "Snippet 1", "score": 0.9}
    ]

    out_file = tmp_path / "mock_report.md"

    # Run with injected services
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.main.GeminiService", lambda **kw: mock_gemini)
        mp.setattr("src.main.TavilyService", lambda **kw: mock_tavily)

        report = run_research_pipeline(
            topic="Autonomous AI Agents",
            output_path=str(out_file),
            format_type="markdown",
            config=mock_config,
        )

    assert isinstance(report, ResearchReport)
    assert report.topic == "Autonomous AI Agents"
    assert len(report.key_takeaways) == 1
    assert len(report.sections) == 1
    assert len(report.sources) >= 1
    assert out_file.exists()


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration test against real APIs skipped unless RUN_INTEGRATION_TESTS=1",
)
def test_full_pipeline_real_apis(tmp_path: Path):
    cfg = Config(check_keys=True)
    out_file = tmp_path / "real_report.md"

    report = run_research_pipeline(
        topic="Solid state battery technology progress",
        output_path=str(out_file),
        format_type="markdown",
        config=cfg,
    )

    assert isinstance(report, ResearchReport)
    assert len(report.key_takeaways) > 0
    assert len(report.sections) > 0
    assert len(report.sources) > 0
    assert out_file.exists()
