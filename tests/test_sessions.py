from unittest.mock import MagicMock
from src.models.schemas import ResearchReport, KeyTakeaway, Source
from src.services.session_manager import SessionManager


def test_continue_session_initializes_and_deduplicates():
    existing_source = Source(
        id="S1", url="https://example.com/1", title="Source 1", snippet="Snippet 1", summary="Summary 1"
    )
    parent_report = ResearchReport(
        id="rep_100",
        topic="Solid State Batteries",
        generated_at="2026-07-31 10:00:00 UTC",
        key_takeaways=[KeyTakeaway(text="Battery energy density doubled", source_ids=["S1"])],
        sources=[existing_source],
    )

    manager = SessionManager.__new__(SessionManager)
    manager.gemini_svc = MagicMock()
    manager.tavily_svc = MagicMock()

    # Mock planner returning 1 query
    with MagicMock() as mock_planner:
        manager.gemini_svc.generate_text.side_effect = [
            "solid state battery commercialization 2026",  # query planning
            '{"what_changed_summary": "Commercialization timelines accelerated.", "new_takeaways": [{"text": "Pilot production lines started [S2]", "source_ids": ["S2"]}]}',  # delta synthesis
        ]

        # Mock retriever returning 1 new source + 1 duplicate source
        new_raw_sources = [
            Source(id="S1", url="https://example.com/1", title="Source 1", snippet="Snippet 1"),  # duplicate
            Source(id="S2", url="https://example.com/2", title="Source 2", snippet="Snippet 2"),  # new
        ]
        
        with MagicMock() as mock_retriever:
            session = manager.continue_session(
                parent_report=parent_report,
                additional_context="Focus on commercialization",
                depth="quick",
            )

            assert session.session_id.startswith("sess_")
            assert len(session.passes) == 2  # initial pass + new pass
            assert session.what_changed_summary == "Commercialization timelines accelerated."
