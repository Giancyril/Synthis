from pathlib import Path
from src.models.schemas import ResearchReport


def render_json(report: ResearchReport) -> str:
    """
    Renders a ResearchReport instance into clean JSON format.
    """
    return report.model_dump_json(indent=2)


def export_to_json_file(report: ResearchReport, filepath: str | Path) -> str:
    """
    Exports a ResearchReport to a JSON file on disk.
    Returns absolute string path to the generated file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_json(report)
    path.write_text(content, encoding="utf-8")
    return str(path.resolve())
