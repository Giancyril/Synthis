import logging
from datetime import date, timedelta
from typing import List, Optional, Dict, Any
from src.models.schemas import Source, FilterSettings
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
        Executes Tavily searches for a list of queries with filter parameters applied to every query.
        Constructs initial Source objects.
        """
        if not queries:
            return []

        search_params = self._build_search_params(filter_settings)

        raw_sources: List[Source] = []
        counter = 1

        for query in queries:
            if not query or not query.strip():
                continue

            try:
                results = self.tavily_service.search(
                    query=query,
                    max_results=max_results_per_query,
                    start_date=search_params.get("start_date"),
                    end_date=search_params.get("end_date"),
                    include_domains=search_params.get("include_domains"),
                    exclude_domains=search_params.get("exclude_domains"),
                    topic=search_params.get("topic"),
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

    @staticmethod
    def _build_search_params(filter_settings: Optional[FilterSettings]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if not filter_settings:
            return params

        # 1. Date filter mapping
        today = date.today()
        if filter_settings.date_filter == "past_year":
            params["start_date"] = (today - timedelta(days=365)).strftime("%Y-%m-%d")
            params["end_date"] = today.strftime("%Y-%m-%d")
        elif filter_settings.date_filter == "past_5_years":
            params["start_date"] = (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
            params["end_date"] = today.strftime("%Y-%m-%d")
        elif filter_settings.date_filter == "custom":
            params["start_date"] = filter_settings.custom_start_date
            params["end_date"] = filter_settings.custom_end_date

        # 2. Domain mode mapping
        cleaned_domains = [
            d.strip() for d in filter_settings.domain_list if d and d.strip()
        ]
        if filter_settings.domain_mode == "include" and cleaned_domains:
            params["include_domains"] = cleaned_domains
        elif filter_settings.domain_mode == "exclude" and cleaned_domains:
            params["exclude_domains"] = cleaned_domains

        # 3. Source category mapping (Tavily's topic parameter)
        if filter_settings.source_category in ("general", "news", "finance"):
            params["topic"] = filter_settings.source_category

        return params
