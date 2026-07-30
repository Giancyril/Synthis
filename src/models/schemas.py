from pydantic import BaseModel, Field
from typing import Optional, List


class Source(BaseModel):
    id: str  # short stable ID, e.g. "S1", "S2" — used for citations
    url: str
    title: str
    snippet: str  # Tavily's returned snippet
    summary: Optional[str] = None  # Gemini's per-source summary
    published_date: Optional[str] = None
    relevance_score: Optional[float] = None


class Citation(BaseModel):
    source_id: str
    quote_or_paraphrase: str  # reference back to source content used


class ReportSection(BaseModel):
    heading: str
    content: str  # prose with inline [S1] [S2] style citation markers
    citations: List[Citation] = Field(default_factory=list)


class KeyTakeaway(BaseModel):
    text: str
    source_ids: List[str] = Field(default_factory=list)  # source IDs supporting this takeaway


class ResearchReport(BaseModel):
    topic: str
    generated_at: str
    key_takeaways: List[KeyTakeaway] = Field(default_factory=list)
    sections: List[ReportSection] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    confidence_note: Optional[str] = None
