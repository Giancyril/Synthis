import time
import logging
from typing import List, Dict, Any
from tavily import TavilyClient

logger = logging.getLogger(__name__)


class TavilyService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = TavilyClient(api_key=api_key) if api_key else None

    def search(
        self,
        query: str,
        max_results: int = 5,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> List[Dict[str, Any]]:
        """
        Executes search via Tavily API with exponential backoff retry logic.
        Returns a list of dicts with keys: url, title, snippet, score, published_date.
        """
        if not self.client:
            raise ValueError("Tavily API key is missing. Cannot perform search.")

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.search(
                    query=query,
                    max_results=max_results,
                    include_answer=False,
                    include_raw_content=False,
                )
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
