import logging
from typing import List
from src.models.schemas import Source
from src.services.tavily_client import TavilyService

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, tavily_service: TavilyService):
        self.tavily_service = tavily_service

    def retrieve_sources(
        self,
        queries: List[str],
        max_results_per_query: int = 5,
        filter_settings: Optional[FilterSettings] = None,
    ) -> List[Source]:
        """
        Executes Tavily searches for a list of queries and constructs initial Source objects.
        """
        if not queries:
            return []

        raw_sources: List[Source] = []
        counter = 1

        for query in queries:
            if not query or not query.strip():
                continue

            try:
                results = self.tavily_service.search(
                    query=query, max_results=max_results_per_query
                )
                for item in results:
                    source_id = f"S{counter}"
                    source = Source(
                        id=source_id,
                        url=item.get("url", ""),
                        title=item.get("title", "") or "Untitled Source",
                        snippet=item.get("snippet", ""),
                        published_date=item.get("published_date"),
                        relevance_score=item.get("score"),
                    )
                    raw_sources.append(source)
                    counter += 1
            except Exception as exc:
                logger.error(f"Error retrieving results for query '{query}': {exc}")

        return raw_sources
