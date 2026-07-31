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


class ResearchReport(BaseModel):
    topic: str
    generated_at: str
    key_takeaways: List[KeyTakeaway] = Field(default_factory=list)
    sections: List[ReportSection] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    conflicting_information: List[ConflictingTopic] = Field(default_factory=list)
    confidence_note: Optional[str] = None
    filter_settings: Optional[FilterSettings] = None

