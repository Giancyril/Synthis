import time
import logging
from typing import List, Dict, Any, Optional

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

logger = logging.getLogger(__name__)


class TavilyService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if TavilyClient and api_key:
            self.client = TavilyClient(api_key=api_key)
        else:
            self.client = None

    def search(
        self,
        query: str,
        max_results: int = 5,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        topic: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> List[Dict[str, Any]]:
        """
        Executes search via Tavily API with exponential backoff retry logic.
        Passes native Tavily search parameters (start_date, end_date, include_domains, exclude_domains, topic).
        Returns a list of dicts with keys: url, title, snippet, score, published_date.
        """
        if not self.client:
            raise ValueError("Tavily client is not initialized or API key is missing.")

        search_kwargs: Dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }

        if start_date:
            search_kwargs["start_date"] = start_date
        if end_date:
            search_kwargs["end_date"] = end_date
        if include_domains:
            search_kwargs["include_domains"] = include_domains
        if exclude_domains:
            search_kwargs["exclude_domains"] = exclude_domains
        if topic and topic in ("general", "news", "finance"):
            search_kwargs["topic"] = topic

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.search(**search_kwargs)
                results = response.get("results", [])
                formatted = []
                for item in results:
                    formatted.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "") or item.get("snippet", ""),
                        "score": item.get("score", 0.0),
                        "published_date": item.get("published_date"),
                    })
                return formatted
            except Exception as exc:
                logger.warning(
                    f"Tavily search attempt {attempt}/{max_retries} failed for query '{query}': {exc}"
                )
                if attempt == max_retries:
                    logger.error(f"Exhausted retries for Tavily search query: '{query}'")
                    raise exc
                time.sleep(backoff_factor ** attempt)

        return []
