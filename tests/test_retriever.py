from unittest.mock import MagicMock
from src.pipeline.retriever import Retriever
from src.services.tavily_client import TavilyService
from src.models.schemas import Source


def test_retriever_returns_sources():
    mock_tavily = MagicMock(spec=TavilyService)
    mock_tavily.search.return_value = [
        {
            "url": "https://example.com/ai-1",
            "title": "AI Ethics 2026",
            "snippet": "Snippet content 1",
            "score": 0.95,
            "published_date": "2026-01-01",
        },
        {
            "url": "https://example.com/ai-2",
            "title": "AI Safety",
            "snippet": "Snippet content 2",
            "score": 0.88,
            "published_date": "2026-01-02",
        },
    ]

    retriever = Retriever(mock_tavily)
    queries = ["AI Ethics query", "AI Safety query"]
    sources = retriever.retrieve_sources(queries, max_results_per_query=2)

    assert isinstance(sources, list)
    assert len(sources) == 4
    assert all(isinstance(s, Source) for s in sources)
    assert sources[0].id == "S1"
    assert sources[0].url == "https://example.com/ai-1"
    assert sources[1].id == "S2"
    assert sources[2].id == "S3"
    assert mock_tavily.search.call_count == 2


def test_retriever_empty_queries():
    mock_tavily = MagicMock(spec=TavilyService)
    retriever = Retriever(mock_tavily)
    sources = retriever.retrieve_sources([])
    assert sources == []
    mock_tavily.search.assert_not_called()
