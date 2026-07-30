from unittest.mock import MagicMock
from src.models.schemas import Source
from src.pipeline.synthesizer import ReportSynthesizer
from src.services.gemini_client import GeminiService


def test_synthesizer_generates_takeaways_and_sections():
    mock_gemini = MagicMock(spec=GeminiService)
    mock_gemini.generate_text.return_value = """
    {
        "key_takeaways": [
            {"text": "Quantum computers reached 1000 qubits.", "source_ids": ["S1"]}
        ],
        "sections": [
            {"heading": "Overview", "content": "Recent advances indicate rapid progress [S1]."}
        ],
        "confidence_note": null
    }
    """

    sources = [
        Source(id="S1", url="https://example.com", title="Quantum Tech", snippet="Content")
    ]

    synthesizer = ReportSynthesizer(mock_gemini)
    takeaways, sections, conf_note = synthesizer.synthesize_report("Quantum Computing", sources)

    assert len(takeaways) == 1
    assert takeaways[0].text == "Quantum computers reached 1000 qubits."
    assert takeaways[0].source_ids == ["S1"]
    assert len(sections) == 1
    assert sections[0].heading == "Overview"
    assert "[S1]" in sections[0].content
