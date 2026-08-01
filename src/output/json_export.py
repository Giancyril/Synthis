"""
JSON export for ResearchReport.

On every report save, the report is also indexed into the FTS5 table
(Feature 3 — full-text search) so past reports are immediately searchable.
Share fields (share_token, share_enabled, share_created_at) are persisted
as part of the normal model_dump — no special handling needed.
"""

import logging
from pathlib import Path

from src.models.schemas import ResearchReport

logger = logging.getLogger(__name__)


def render_json(report: ResearchReport) -> str:
    """
    Renders a ResearchReport instance into clean JSON format.
    """
    return report.model_dump_json(indent=2)


def export_to_json_file(report: ResearchReport, filepath: str | Path) -> str:
    """
    Exports a ResearchReport to a JSON file on disk.
    Also upserts the report's FTS index row so it's immediately searchable.
    Returns absolute string path to the generated file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_json(report)
    path.write_text(content, encoding="utf-8")

    # ── FTS index upsert ──────────────────────────────────────────────
    try:
        from src.services.database import get_db

        report_id = path.stem  # e.g. "report_ai_tools"
        key_takeaways_text = " | ".join(t.text for t in report.key_takeaways)
        sections_text = " ".join(
            f"{s.heading} {s.content}" for s in report.sections
        )
        source_titles = " ".join(s.title for s in report.sources)

        get_db().upsert_report_index(
            report_id=report_id,
            topic=report.topic,
            generated_at=report.generated_at,
            key_takeaways_text=key_takeaways_text,
            sections_text=sections_text,
            source_titles=source_titles,
        )
    except Exception as exc:
        # Never let indexing failure block the save
        logger.warning(f"FTS index upsert failed for {filepath}: {exc}")

    return str(path.resolve())
