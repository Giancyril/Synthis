from typing import List, Optional
from pydantic import BaseModel
from src.models.schemas import ResearchReport


class ExecutiveBrief(BaseModel):
    topic: str
    generated_at: str
    top_takeaways: List[str]           # max 3, highest corroboration first
    highlight_stats: List[str]         # key numeric / factual sentences mined from sections
    key_sections: List[dict]           # max 2: [{heading, summary}]
    source_count: int
    confidence_note: Optional[str] = None


def generate_brief(report: ResearchReport) -> ExecutiveBrief:
    import re

    # 1. Pick top 3 takeaways — prefer highest corroboration_count, then longest text
    takeaways = list(report.key_takeaways or [])
    takeaways.sort(
        key=lambda kt: (getattr(kt, "corroboration_count", 0) or 0, len(kt.text or "")),
        reverse=True,
    )
    top_takeaways = [kt.text for kt in takeaways[:3]]

    # 2. Mine "highlight stats" — short sentences containing numbers from section content
    highlight_stats: List[str] = []
    NUMBER_RE = re.compile(r"\d[\d%,.]*")
    for sec in (report.sections or []):
        content = re.sub(r"\[S\d+\]", "", sec.content or "")
        sentences = re.split(r"(?<=[.!?])\s+", content)
        for sent in sentences:
            stripped = sent.strip()
            if 20 < len(stripped) < 180 and NUMBER_RE.search(stripped):
                highlight_stats.append(stripped)
            if len(highlight_stats) >= 4:
                break
        if len(highlight_stats) >= 4:
            break

    # 3. Pick top 2 sections (longest content first, as a proxy for importance)
    sections = list(report.sections or [])
    sections.sort(key=lambda s: len(s.content or ""), reverse=True)
    key_sections = []
    for sec in sections[:2]:
        raw = re.sub(r"\[S\d+\]", "", sec.content or "").strip()
        # Truncate to first ~300 chars for the brief summary
        summary = raw[:300].rsplit(" ", 1)[0] + ("…" if len(raw) > 300 else "")
        key_sections.append({"heading": sec.heading, "summary": summary})

    return ExecutiveBrief(
        topic=report.topic,
        generated_at=report.generated_at,
        top_takeaways=top_takeaways,
        highlight_stats=highlight_stats,
        key_sections=key_sections,
        source_count=len(report.sources or []),
        confidence_note=report.confidence_note or None,
    )
