from unittest.mock import MagicMock
from src.pipeline.query_planner import QueryPlanner
from src.services.gemini_client import GeminiService


def test_query_planner_returns_list_of_queries():
    mock_gemini = MagicMock(spec=GeminiService)
    mock_gemini.generate_text.return_value = '["artificial intelligence ethics 2026", "AI regulation global policies", "AI safety controversies"]'

    planner = QueryPlanner(mock_gemini)
    queries = planner.plan_queries("AI Ethics")

    assert isinstance(queries, list)
    assert len(queries) == 3
    assert "artificial intelligence ethics 2026" in queries
    mock_gemini.generate_text.assert_called_once()


def test_query_planner_fallback_on_invalid_json():
    mock_gemini = MagicMock(spec=GeminiService)
    mock_gemini.generate_text.return_value = "1. Quantum Computing overview\n2. Quantum Computing applications\n3. Quantum Computing challenges"

    planner = QueryPlanner(mock_gemini)
    queries = planner.plan_queries("Quantum Computing")

    assert isinstance(queries, list)
    assert len(queries) >= 3
    assert any("Quantum Computing" in q for q in queries)


def test_query_planner_empty_topic_returns_empty():
    mock_gemini = MagicMock(spec=GeminiService)
    planner = QueryPlanner(mock_gemini)

    queries = planner.plan_queries("")
    assert queries == []
    mock_gemini.generate_text.assert_not_called()
