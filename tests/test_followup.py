from unittest.mock import MagicMock
from src.models.schemas import ResearchReport, KeyTakeaway, ReportSection, Source
from src.pipeline.followup_pipeline import FollowUpPipeline


def test_followup_pipeline_scoped_execution():
    parent_sources = [
        Source(id="S1", url="https://example.com/1", title="S1", snippet="Snippet 1", credibility_tier="primary"),
        Source(id="S2", url="https://example.com/2", title="S2", snippet="Snippet 2", credibility_tier="secondary"),
    ]

    takeaways = [
        KeyTakeaway(text="Quantum computing advances", source_ids=["S1", "S2"], corroboration_count=2)
    ]

    sections = [
        ReportSection(heading="Overview", content="Quantum chips progress rapidly [S1] [S2].")
    ]

    report = ResearchReport(
        topic="Quantum Computing",
        generated_at="2026-07-31 12:00:00 UTC",
        key_takeaways=takeaways,
        sections=sections,
        sources=parent_sources,
    )

    pipeline = FollowUpPipeline.__new__(FollowUpPipeline)
    pipeline.config = MagicMock()
    pipeline.gemini_svc = MagicMock()
    pipeline.gemini_svc.generate_text.side_effect = [
        "quantum computing scalability challenges",  # 1. Targeted query
        "Scalability remains a challenge due to decoherence [S1] [S3].",  # 2. Synthesis answer
    ]

    result = pipeline.execute_followup(
        report=report,
        target_type="takeaway",
        target_id="0",
        question="What are the scalability limits?",
        follow_up_id="fu_1234",
    )

    assert result.follow_up_id == "fu_1234"
    assert result.question == "What are the scalability limits?"
    assert result.target_type == "takeaway"
    assert "[S1]" in result.summary
