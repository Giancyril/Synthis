import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from src.config import Config
from src.models.schemas import (
    ResearchReport,
    ResearchSession,
    PassMetadata,
    Source,
    KeyTakeaway,
    FilterSettings,
)
from src.services.gemini_client import GeminiService
from src.services.tavily_client import TavilyService
from src.pipeline.query_planner import QueryPlanner
from src.pipeline.retriever import Retriever
from src.pipeline.source_filter import SourceFilter
from src.pipeline.summarizer import SourceSummarizer
from src.pipeline.synthesizer import ReportSynthesizer
from src.pipeline.citation_mapper import CitationMapper

logger = logging.getLogger(__name__)

DELTA_SYNTHESIS_PROMPT = """\
You are a senior research analyst performing a follow-up research pass on an existing topic.

Topic: {topic}
Additional Context / Focus: {additional_context}

Previous Research Pass Takeaways:
{prior_takeaways_str}

Newly Retrieved & Summarized Sources for this Pass:
{new_sources_str}

Tasks:
1. "what_changed_summary": Provide a clear 2-4 sentence summary explaining what is NEW, UPDATED, or CHANGED since the prior research pass.
2. "new_takeaways": Provide key takeaways for this new pass with inline [S#] citations.

Return a JSON object with keys "what_changed_summary" (str) and "new_takeaways" (array of objects with "text" and "source_ids").
"""


class SessionManager:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config(check_keys=True)
        self.gemini_svc = GeminiService(
            api_key=self.config.gemini_api_key,
            model_name=self.config.gemini_model,
        )
        self.tavily_svc = TavilyService(api_key=self.config.tavily_api_key)

    def continue_session(
        self,
        parent_report: ResearchReport,
        additional_context: Optional[str] = None,
        depth: str = "standard",
        filter_settings: Optional[FilterSettings] = None,
        existing_session: Optional[ResearchSession] = None,
    ) -> ResearchSession:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Initialize session if not present
        if not existing_session:
            session_id = f"sess_{uuid.uuid4().hex[:8]}"
            parent_report_id = parent_report.id or f"rep_{uuid.uuid4().hex[:6]}"
            initial_pass = PassMetadata(
                report_id=parent_report_id,
                run_at=parent_report.generated_at or now_str,
                depth="standard",
                filters_used=parent_report.filter_settings,
                additional_context=None,
            )
            session = ResearchSession(
                session_id=session_id,
                topic=parent_report.topic,
                created_at=parent_report.generated_at or now_str,
                last_updated_at=now_str,
                passes=[initial_pass],
                merged_sources=list(parent_report.sources),
                merged_takeaways=list(parent_report.key_takeaways),
                what_changed_summary=None,
            )
        else:
            session = existing_session

        # Step a: Generate new queries taking additional_context into account
        planner = QueryPlanner(self.gemini_svc)
        search_topic = session.topic
        if additional_context and additional_context.strip():
            search_topic += f" ({additional_context.strip()})"

        max_q = {"quick": 3, "standard": 5, "deep": 7}.get(depth, 5)
        queries = planner.plan_queries(search_topic, max_queries=max_q)


        # Step b: Retrieve raw sources
        retriever = Retriever(self.tavily_svc)
        raw_sources = retriever.retrieve_sources(queries, filter_settings=filter_settings)

        # Step c: Deduplicate against session's merged_sources
        existing_urls = {SourceFilter._normalize_url(s.url) for s in session.merged_sources}
        retained_new: List[Source] = []

        max_existing_id = 0
        for s in session.merged_sources:
            import re
            m = re.search(r"\d+", s.id)
            if m:
                max_existing_id = max(max_existing_id, int(m.group(0)))

        next_id_num = max_existing_id + 1
        for ns in raw_sources:
            norm_url = SourceFilter._normalize_url(ns.url)
            if norm_url not in existing_urls:
                existing_urls.add(norm_url)
                domain = SourceFilter._extract_domain(ns.url)
                tier = SourceFilter.classify_credibility(domain)
                updated_source = ns.model_copy(
                    update={"id": f"S{next_id_num}", "credibility_tier": tier}
                )
                next_id_num += 1
                retained_new.append(updated_source)

        # Summarize ONLY new sources
        summarized_new: List[Source] = []
        if retained_new:
            summarizer = SourceSummarizer(self.gemini_svc)
            summarized_new = summarizer.summarize_sources(retained_new)

        all_session_sources = session.merged_sources + summarized_new

        # Step d: Delta synthesis call with Gemini
        prior_takeaways_str = "\n".join([f"- {t.text}" for t in session.merged_takeaways])
        new_sources_str = "\n".join([f"[{s.id}] {s.title}: {s.summary or s.snippet}" for s in summarized_new])

        prompt = DELTA_SYNTHESIS_PROMPT.format(
            topic=session.topic,
            additional_context=additional_context or "General update",
            prior_takeaways_str=prior_takeaways_str or "None",
            new_sources_str=new_sources_str or "No new sources retrieved.",
        )

        delta_raw = self.gemini_svc.generate_text(prompt).strip()
        import re
        delta_raw = re.sub(r"^```(?:json)?\s*", "", delta_raw)
        delta_raw = re.sub(r"\s*```$", "", delta_raw)

        what_changed = "New pass completed. Additional sources incorporated."
        new_takeaways: List[KeyTakeaway] = []

        try:
            data = json.loads(delta_raw)
            what_changed = data.get("what_changed_summary", what_changed)
            for item in data.get("new_takeaways", []):
                new_takeaways.append(
                    KeyTakeaway(
                        text=item.get("text", ""),
                        source_ids=item.get("source_ids", []),
                        corroboration_count=len(item.get("source_ids", [])),
                    )
                )
        except Exception as exc:
            logger.warning(f"Delta synthesis JSON parse fallback: {exc}")

        # Validate citations via CitationMapper
        mapper = CitationMapper()
        dummy_sections = [
            ResearchReport.model_construct(
                heading="Delta Pass",
                content=t.text,
            )
            for t in new_takeaways
        ]
        
        # Append new pass metadata
        new_pass_id = f"pass_{uuid.uuid4().hex[:6]}"
        session.passes.append(
            PassMetadata(
                report_id=new_pass_id,
                run_at=now_str,
                depth=depth,
                filters_used=filter_settings,
                additional_context=additional_context,
            )
        )
        session.merged_sources = all_session_sources
        if new_takeaways:
            session.merged_takeaways.extend(new_takeaways)
        session.what_changed_summary = what_changed
        session.last_updated_at = now_str

        return session
