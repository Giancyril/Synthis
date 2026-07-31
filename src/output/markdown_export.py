from pathlib import Path
import json
from src.models.schemas import ResearchReport


def render_markdown(report: ResearchReport) -> str:
    """
    Renders a ResearchReport instance into clean Markdown format with YAML frontmatter,
    title, confidence notes, key takeaways, report sections, and bibliography.
    """
    lines = []

    # Frontmatter block for metadata persistence
    if report.filter_settings:
        lines.append("---")
        lines.append(f"topic: {json.dumps(report.topic)}")
        lines.append(f"date_filter: {json.dumps(report.filter_settings.date_filter)}")
        lines.append(f"custom_start_date: {json.dumps(report.filter_settings.custom_start_date)}")
        lines.append(f"custom_end_date: {json.dumps(report.filter_settings.custom_end_date)}")
        lines.append(f"domain_mode: {json.dumps(report.filter_settings.domain_mode)}")
        lines.append(f"domain_list: {json.dumps(report.filter_settings.domain_list)}")
        lines.append(f"source_category: {json.dumps(report.filter_settings.source_category)}")
        lines.append("---")
        lines.append("")

    lines.append(f"# Research Report: {report.topic}")
    lines.append(f"*Generated on {report.generated_at}*")

    if report.filter_settings:
        scope_parts = []
        df = report.filter_settings.date_filter
        if df == "past_year":
            scope_parts.append("Date: Past year")
        elif df == "past_5_years":
            scope_parts.append("Date: Past 5 years")
        elif df == "custom":
            scope_parts.append(f"Date: {report.filter_settings.custom_start_date} to {report.filter_settings.custom_end_date}")
        else:
            scope_parts.append("Date: Any time")

        if report.filter_settings.domain_mode != "none" and report.filter_settings.domain_list:
            mode_lbl = "Only: " if report.filter_settings.domain_mode == "include" else "Exclude: "
            scope_parts.append(f"Domains ({mode_lbl}{', '.join(report.filter_settings.domain_list)})")

        if report.filter_settings.source_category and report.filter_settings.source_category != "general":
            scope_parts.append(f"Scope: {report.filter_settings.source_category.capitalize()}")

        lines.append(f"*\n**Filter Scope:** {' · '.join(scope_parts)}*")

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

    if report.conflicting_information:
        lines.append("## Conflicting Information & Disagreements")
        lines.append("")
        for conflict in report.conflicting_information:
            lines.append(f"### Disputed: {conflict.topic}")
            for pos in conflict.positions:
                sids_str = ", ".join([f"[{sid}]" for sid in pos.source_ids])
                lines.append(f"- **Claim:** {pos.claim} *({sids_str})*")
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
