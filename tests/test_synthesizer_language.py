"""
Tests for multi-language synthesis instruction injection in ReportSynthesizer.
"""

from unittest.mock import MagicMock
from src.models.schemas import Source
from src.pipeline.synthesizer import ReportSynthesizer


def test_synthesizer_english_prompt_no_lang_instruction():
    mock_gemini = MagicMock()
    mock_gemini.generate_text.return_value = '{"key_takeaways":[],"sections":[]}'

    synthesizer = ReportSynthesizer(mock_gemini)
    sources = [Source(id="S1", url="https://example.com", title="Title", snippet="Snippet")]

    synthesizer.synthesize_report("AI research", sources, output_language="en")

    prompt_sent = mock_gemini.generate_text.call_args.kwargs["prompt"]
    assert "CRITICAL LANGUAGE INSTRUCTION" not in prompt_sent


def test_synthesizer_spanish_prompt_injects_lang_instruction():
    mock_gemini = MagicMock()
    mock_gemini.generate_text.return_value = '{"key_takeaways":[],"sections":[]}'

    synthesizer = ReportSynthesizer(mock_gemini)
    sources = [Source(id="S1", url="https://example.com", title="Title", snippet="Snippet")]

    synthesizer.synthesize_report("AI research", sources, output_language="es")

    prompt_sent = mock_gemini.generate_text.call_args.kwargs["prompt"]
    assert "CRITICAL LANGUAGE INSTRUCTION" in prompt_sent
    assert "Spanish" in prompt_sent
    assert "[S1]" in prompt_sent  # confirms citation markers protection instruction
