"""
Tests for Feature 3: Full-Text Search over Past Reports
"""
import pytest
from src.services.database import DatabaseService
from pathlib import Path


@pytest.fixture()
def db(tmp_path):
    """Fresh DatabaseService backed by a temp SQLite file."""
    return DatabaseService(db_path=tmp_path / "test_synthis.db")


def test_search_returns_matching_report(db):
    db.upsert_report_index(
        report_id="report_batteries",
        topic="Battery Technology Trends",
        generated_at="2026-01-01T00:00:00",
        key_takeaways_text="Lithium costs dropped 40% over five years",
        sections_text="Energy density improvements led by solid-state research",
        source_titles="Nature Energy | Bloomberg NEF",
    )

    results = db.search_reports("battery costs")
    assert len(results) >= 1
    assert results[0]["report_id"] == "report_batteries"


def test_search_no_results_for_unrelated_query(db):
    db.upsert_report_index(
        report_id="report_ai",
        topic="Artificial Intelligence Overview",
        generated_at="2026-01-01T00:00:00",
        key_takeaways_text="Large language models show reasoning capabilities",
        sections_text="Transformer architecture dominates NLP",
        source_titles="OpenAI | DeepMind",
    )
    results = db.search_reports("submarine sandwich")
    assert len(results) == 0


def test_search_ranks_by_relevance(db):
    db.upsert_report_index(
        report_id="report_highly_relevant",
        topic="Solar Energy Costs 2025",
        generated_at="2026-02-01T00:00:00",
        key_takeaways_text="Solar costs solar costs solar costs",
        sections_text="Solar costs dropped significantly",
        source_titles="Solar Times",
    )
    db.upsert_report_index(
        report_id="report_less_relevant",
        topic="Renewable Energy Overview",
        generated_at="2026-01-01T00:00:00",
        key_takeaways_text="Wind energy is growing",
        sections_text="Solar mentioned briefly",
        source_titles="Energy Weekly",
    )
    results = db.search_reports("solar costs")
    assert len(results) >= 1
    # Most relevant should come first (lower BM25 rank = more relevant)
    assert results[0]["report_id"] == "report_highly_relevant"


def test_upsert_updates_existing_index(db):
    db.upsert_report_index(
        report_id="report_update",
        topic="Old Topic",
        generated_at="2026-01-01T00:00:00",
        key_takeaways_text="original content",
        sections_text="",
        source_titles="",
    )
    # Upsert with new content
    db.upsert_report_index(
        report_id="report_update",
        topic="Updated Topic",
        generated_at="2026-01-02T00:00:00",
        key_takeaways_text="revised content",
        sections_text="",
        source_titles="",
    )
    # Old content should not match
    assert len(db.search_reports("original content")) == 0
    # New content should match
    results = db.search_reports("revised content")
    assert len(results) == 1
    assert results[0]["topic"] == "Updated Topic"


def test_empty_query_returns_empty(db):
    results = db.search_reports("")
    assert results == []
