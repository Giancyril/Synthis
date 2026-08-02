import pytest
from unittest.mock import MagicMock
from src.pipeline.outline_generator import OutlineGenerator, ResearchOutline

def test_outline_generator_success():
    mock_gemini = MagicMock()
    mock_gemini.generate_text.return_value = '''{
        "sections": [
            {
                "heading": "Introduction to Solid State Batteries",
                "description": "Fundamental physics and chemical structure.",
                "key_questions": ["What electrolyte is used?"]
            }
        ],
        "recommended_depth": "deep"
    }'''

    generator = OutlineGenerator(mock_gemini)
    outline = generator.generate_outline("Solid State Batteries", "deep")
    assert isinstance(outline, ResearchOutline)
    assert outline.topic == "Solid State Batteries"
    assert outline.estimated_source_count == 20
    assert len(outline.sections) == 1
    assert outline.sections[0].heading == "Introduction to Solid State Batteries"

def test_outline_generator_fallback():
    mock_gemini = MagicMock()
    mock_gemini.generate_text.side_effect = Exception("LLM Error")

    generator = OutlineGenerator(mock_gemini)
    outline = generator.generate_outline("Quantum Computing", "standard")
    assert isinstance(outline, ResearchOutline)
    assert len(outline.sections) >= 3
    assert outline.sections[0].heading == "Background & Fundamentals"
