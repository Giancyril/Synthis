"""
Search routes — Feature 3: Full-Text Search over Past Reports

Endpoint:
  GET /api/reports/search?q=<query>   — ranked full-text search via SQLite FTS5

Design notes:
  - Uses the reports_fts virtual table (populated/updated by json_export.py on save).
  - Ranking is BM25 (built-in to FTS5).
  - Snippet is extracted by SQLite's snippet() function — ~20 tokens around the match.
  - Returns up to 20 results.
  - Semantic/embedding search is explicitly out of scope for this version.
    Flag: add ChromaDB or similar if semantic intent-matching is needed in future.
"""

import logging
from typing import List

from fastapi import APIRouter, Query
from src.models.schemas import SearchResultItem
from src.services.database import get_db

logger = logging.getLogger(__name__)

search_router = APIRouter(tags=["Search"])


@search_router.get(
    "/api/reports/search",
    response_model=List[SearchResultItem],
    summary="Full-text search across saved reports (SQLite FTS5)",
)
def search_reports(
    q: str = Query(..., min_length=1, description="Search query"),
):
    """
    Search across all saved report content (topic, takeaways, sections,
    source titles) using SQLite FTS5 full-text search with BM25 ranking.

    Results include a snippet showing the matched text in context.

    Future: semantic/embedding-based search (ChromaDB or similar)
    is explicitly NOT part of this implementation — flag as follow-up.
    """
    try:
        rows = get_db().search_reports(query=q, limit=20)
    except Exception as exc:
        logger.error(f"FTS search failed for query '{q}': {exc}")
        # Return empty results rather than 500 — search failure shouldn't crash the app
        return []

    return [
        SearchResultItem(
            report_id=r["report_id"],
            topic=r["topic"],
            generated_at=r["generated_at"],
            snippet=r["snippet"] or "",
            rank=float(r["rank"]),
        )
        for r in rows
    ]
