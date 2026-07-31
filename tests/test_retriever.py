from unittest.mock import MagicMock
from src.pipeline.retriever import Retriever
from src.services.tavily_client import TavilyService
from src.models.schemas import Source, FilterSettings


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


def test_retriever_passes_filter_settings_to_tavily():
    mock_tavily = MagicMock(spec=TavilyService)
    mock_tavily.search.return_value = []

    retriever = Retriever(mock_tavily)
    filters = FilterSettings(
        date_filter="custom",
        custom_start_date="2024-01-01",
        custom_end_date="2024-12-31",
        domain_mode="include",
        domain_list=["arxiv.org", "*.edu"],
        source_category="news",
    )
    queries = ["query 1", "query 2"]
    retriever.retrieve_sources(queries, filter_settings=filters)

    assert mock_tavily.search.call_count == 2
    for call in mock_tavily.search.call_args_list:
        _, kwargs = call
        assert kwargs["start_date"] == "2024-01-01"
        assert kwargs["end_date"] == "2024-12-31"
        assert kwargs["include_domains"] == ["arxiv.org", "*.edu"]
        assert kwargs["topic"] == "news"


def test_retriever_empty_queries():
    mock_tavily = MagicMock(spec=TavilyService)
    retriever = Retriever(mock_tavily)
    sources = retriever.retrieve_sources([])
    assert sources == []
    mock_tavily.search.assert_not_called()
