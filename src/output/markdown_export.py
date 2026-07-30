from pathlib import Path
from src.models.schemas import ResearchReport


def render_markdown(report: ResearchReport) -> str:
    """
    Renders a ResearchReport instance into clean Markdown format with title,
    confidence notes, key takeaways, report sections, and bibliography.
    """
    lines = []
    lines.append(f"# Research Report: {report.topic}")
    lines.append(f"*Generated on {report.generated_at}*")
    lines.append("")

    if report.confidence_note:
        lines.append(f"> **Notice:** {report.confidence_note}")
        lines.append("")

    lines.append("## Executive Summary & Key Takeaways")
    lines.append("")
    if report.key_takeaways:
        for kt in report.key_takeaways:
            sources_str = ", ".join([f"[{sid}]" for sid in kt.source_ids]) if kt.source_ids else ""
            sources_tag = f" *({sources_str})*" if sources_str else ""
            lines.append(f"- {kt.text}{sources_tag}")
    else:
        lines.append("- No key takeaways generated.")
    lines.append("")

    lines.append("---")
    lines.append("")

    if report.sections:
        for sec in report.sections:
            lines.append(f"## {sec.heading}")
            lines.append("")
            lines.append(sec.content)
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## References & Sources")
    lines.append("")

    if report.sources:
        for src in report.sources:
            summary_info = f"\n  > *Summary:* {src.summary}" if src.summary else ""
            lines.append(f"- **[{src.id}]** [{src.title}]({src.url}){summary_info}")
    else:
        lines.append("No sources recorded.")

    return "\n".join(lines)


def export_to_markdown_file(report: ResearchReport, filepath: str | Path) -> str:
    """
    Exports a ResearchReport to a Markdown file on disk.
    Returns absolute string path to the generated file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_markdown(report)
    path.write_text(content, encoding="utf-8")
    return str(path.resolve())
