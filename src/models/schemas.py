from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime, date


class FilterSettings(BaseModel):
    date_filter: str = "any"  # "any" | "past_year" | "past_5_years" | "custom"
    custom_start_date: Optional[str] = None  # YYYY-MM-DD
    custom_end_date: Optional[str] = None    # YYYY-MM-DD
    domain_mode: str = "none"  # "none" | "include" | "exclude"
    domain_list: List[str] = Field(default_factory=list)
    source_category: str = "general"  # "general" | "news" | "finance"

    @model_validator(mode="after")
    def validate_filter_rules(self):
        if self.date_filter == "custom":
            if not self.custom_start_date or not self.custom_end_date:
                raise ValueError("Both custom_start_date and custom_end_date are required when date_filter is 'custom'.")
            
            try:
                start_dt = datetime.strptime(self.custom_start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(self.custom_end_date, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Dates must be in YYYY-MM-DD format.")

            if start_dt > end_dt:
                raise ValueError(f"custom_start_date ({self.custom_start_date}) cannot be after custom_end_date ({self.custom_end_date}).")
            
            today = date.today()
            if end_dt > today:
                raise ValueError(f"custom_end_date ({self.custom_end_date}) cannot be in the future.")

        if self.domain_mode in ("include", "exclude") and not self.domain_list:
            # Clean empty strings if any
            pass
        return self


class Source(BaseModel):
    id: str  # short stable ID, e.g. "S1", "S2" — used for citations
    url: str
    title: str
    snippet: str  # Tavily's returned snippet
    summary: Optional[str] = None  # Gemini's per-source summary
    published_date: Optional[str] = None
    relevance_score: Optional[float] = None
    credibility_tier: str = "unrated"  # "primary" | "secondary" | "low-authority" | "unrated"


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
    corroboration_count: int = 1


class ConflictPosition(BaseModel):
    claim: str
    source_ids: List[str] = Field(default_factory=list)


class ConflictingTopic(BaseModel):
    topic: str
    positions: List[ConflictPosition] = Field(default_factory=list)


class FollowUpQuery(BaseModel):
    id: str
    parent_report_id: str
    target_type: str  # "takeaway" | "section"
    target_id: str
    question: str
    created_at: str


class FollowUpResult(BaseModel):
    follow_up_id: str
    question: str
    target_type: str
    target_id: str
    new_sources: List[Source] = Field(default_factory=list)
    summary: str
    updated_takeaway_or_section: Optional[str] = None
    merged_into_parent: bool = False
    created_at: str


class ComparisonDimension(BaseModel):
    dimension_name: str
    topic_a_position: str
    topic_a_source_ids: List[str] = Field(default_factory=list)
    topic_b_position: str
    topic_b_source_ids: List[str] = Field(default_factory=list)
    verdict_or_note: Optional[str] = None


class ComparativeReport(BaseModel):
    id: str
    topic_a: str
    topic_b: str
    generated_at: str
    shared_dimensions: List[ComparisonDimension] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    filter_settings: Optional[FilterSettings] = None


class ResearchReport(BaseModel):
    id: Optional[str] = None
    topic: str
    generated_at: str
    key_takeaways: List[KeyTakeaway] = Field(default_factory=list)
    sections: List[ReportSection] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    conflicting_information: List[ConflictingTopic] = Field(default_factory=list)
    confidence_note: Optional[str] = None
    filter_settings: Optional[FilterSettings] = None
    follow_ups: List[FollowUpResult] = Field(default_factory=list)
    # Sharing (Feature 1) — private by default; token generated on demand
    share_token: Optional[str] = None
    share_enabled: bool = False
    share_created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Public DTO — deliberately scoped; never includes internal/private fields
# ---------------------------------------------------------------------------

class PublicReportDTO(BaseModel):
    """Read-only view returned by GET /api/public/reports/{share_token}.
    Excludes: id, share_token, share_enabled, share_created_at,
              filter_settings, follow_ups, session metadata.
    """
    topic: str
    generated_at: str
    key_takeaways: List[KeyTakeaway] = Field(default_factory=list)
    sections: List[ReportSection] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    conflicting_information: List[ConflictingTopic] = Field(default_factory=list)
    confidence_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Annotations (Feature 2) — single-user personal notes; never public
# ---------------------------------------------------------------------------

class Annotation(BaseModel):
    id: str                          # "ann_<8-char hex>"
    report_id: str                   # filename stem, e.g. "report_ai_tools"
    target_type: str                 # "takeaway" | "section" | "source"
    target_id: str                   # index string ("0","1") or source id ("S1")
    author: Optional[str] = None     # display name; None = anonymous
    body: str
    created_at: str                  # ISO-8601
    updated_at: str                  # ISO-8601
    resolved: bool = False


class AnnotationPatch(BaseModel):
    body: Optional[str] = None
    resolved: Optional[bool] = None
    author: Optional[str] = None


# ---------------------------------------------------------------------------
# Search (Feature 3) — full-text search DTOs
# ---------------------------------------------------------------------------

class ReportIndexEntry(BaseModel):
    """Denormalised row inserted into reports_fts on report save."""
    report_id: str
    topic: str
    generated_at: str
    key_takeaways_text: str   # all takeaway texts joined with ' | '
    sections_text: str        # all headings + content joined
    source_titles: str        # all source titles joined


class SearchResultItem(BaseModel):
    report_id: str
    topic: str
    generated_at: str
    snippet: str              # ~150-char highlight around matched term
    rank: float               # FTS5 BM25 score (lower = more relevant)


class PassMetadata(BaseModel):
    report_id: str
    run_at: str
    depth: str = "standard"
    filters_used: Optional[FilterSettings] = None
    additional_context: Optional[str] = None


class ResearchSession(BaseModel):
    session_id: str
    topic: str
    created_at: str
    last_updated_at: str
    passes: List[PassMetadata] = Field(default_factory=list)
    merged_sources: List[Source] = Field(default_factory=list)
    merged_takeaways: List[KeyTakeaway] = Field(default_factory=list)
    what_changed_summary: Optional[str] = None





