import json
from pathlib import Path
from src.models.schemas import ResearchReport, KeyTakeaway, ReportSection, Source, Citation
from src.output.markdown_export import render_markdown, export_to_markdown_file
from src.output.json_export import render_json, export_to_json_file


def test_markdown_and_json_exports(tmp_path: Path):
    report = ResearchReport(
        topic="AI Safety",
        generated_at="2026-07-31 00:00:00 UTC",
        key_takeaways=[KeyTakeaway(text="Safety protocols are expanding.", source_ids=["S1"])],
        sections=[
            ReportSection(
                heading="Overview",
                content="Research shows rapid expansion [S1].",
                citations=[Citation(source_id="S1", quote_or_paraphrase="AI Safety Tech")],
            )
        ],
        sources=[
            Source(
                id="S1",
                url="https://example.com/safety",
                title="AI Safety Tech",
                snippet="Snippet details",
                summary="Summary details",
            )
        ],
        confidence_note=None,
    )

    # Test Markdown rendering
    md_content = render_markdown(report)
    assert "# Research Report: AI Safety" in md_content
    assert "Safety protocols are expanding." in md_content
    assert "[S1]" in md_content
    assert "https://example.com/safety" in md_content

    # Test Markdown export file writing
    md_file = tmp_path / "report.md"
    written_md_path = export_to_markdown_file(report, md_file)
    assert Path(written_md_path).exists()
    assert Path(written_md_path).read_text(encoding="utf-8") == md_content

    # Test JSON rendering
    json_content = render_json(report)
    parsed = json.loads(json_content)
    assert parsed["topic"] == "AI Safety"
    assert len(parsed["sources"]) == 1

    # Test JSON export file writing
    json_file = tmp_path / "report.json"
    written_json_path = export_to_json_file(report, json_file)
    assert Path(written_json_path).exists()
