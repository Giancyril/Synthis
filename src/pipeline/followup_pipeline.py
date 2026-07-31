import re
import logging
from datetime import datetime, timezone
from typing import List, Optional
from src.config import Config
from src.models.schemas import (
    ResearchReport,
    Source,
    FollowUpResult,
    ReportSection,
)
from src.services.gemini_client import GeminiService
from src.pipeline.retriever import Retriever
from src.pipeline.source_filter import SourceFilter
from src.pipeline.summarizer import SourceSummarizer
from src.pipeline.citation_mapper import CitationMapper

logger = logging.getLogger(__name__)


class FollowUpPipeline:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config(check_keys=True)
        self.gemini_svc = GeminiService(self.config)

    def execute_followup(
        self,
        report: ResearchReport,
        target_type: str,
        target_id: str,
        question: str,
        follow_up_id: str,
    ) -> FollowUpResult:
        """
        Executes a scoped mini-pipeline answering a follow-up question on a report takeaway or section.
        """
        # Step a: Identify existing cited sources for the target takeaway/section
        existing_sources_map = {s.id: s for s in report.sources}
        starting_sources: List[Source] = []

        if target_type == "takeaway":
            target_takeaway = None
            if target_id.isdigit():
                idx = int(target_id)
                if 0 <= idx < len(report.key_takeaways):
                    target_takeaway = report.key_takeaways[idx]
            if not target_takeaway:
                for kt in report.key_takeaways:
                    if kt.text == target_id or target_id in kt.text:
                        target_takeaway = kt
                        break
            if target_takeaway:
                for sid in target_takeaway.source_ids:
                    if sid in existing_sources_map:
                        starting_sources.append(existing_sources_map[sid])

        elif target_type == "section":
            target_sec = None
            if target_id.isdigit():
                idx = int(target_id)
                if 0 <= idx < len(report.sections):
                    target_sec = report.sections[idx]
            if not target_sec:
                for sec in report.sections:
                    if sec.heading == target_id or target_id in sec.heading:
                        target_sec = sec
                        break
            if target_sec:
                found_sids = re.findall(r"\[(S\d+)\]", target_sec.content)
                for sid in set(found_sids):
                    if sid in existing_sources_map:
                        starting_sources.append(existing_sources_map[sid])

        # Find max source ID integer in parent report (e.g. S5 -> 5)
        max_existing_id = 0
        for s in report.sources:
            match = re.search(r"\d+", s.id)
            if match:
                max_existing_id = max(max_existing_id, int(match.group(0)))

        # Step b: Generate 1 targeted search query using Gemini
        query_prompt = (
            f"Context Topic: {report.topic}\n"
            f"Target {target_type.capitalize()}: {target_id}\n"
            f"Follow-up Question: {question}\n\n"
            "Generate EXACTLY ONE concise, highly targeted web search query to find relevant information or counter-arguments. "
            "Return ONLY the plain text search query, nothing else."
        )
        targeted_query = self.gemini_svc.generate_text(query_prompt).strip().strip('"').strip("'")
        logger.info(f"FollowUpPipeline: Generated targeted query: '{targeted_query}'")

        # Step c: Execute 1 query and deduplicate against parent sources
        retriever = Retriever(self.config)
        raw_new_sources = retriever.retrieve_sources([targeted_query], filter_settings=report.filter_settings)

        existing_urls = {SourceFilter._normalize_url(s.url) for s in report.sources}
        retained_new: List[Source] = []

        next_id_num = max_existing_id + 1
        for ns in raw_new_sources:
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
                if len(retained_new) >= 4:  # Cap supplemental new sources to ~4
                    break

        # Summarize ONLY new sources
        summarized_new: List[Source] = []
        if retained_new:
            summarizer = SourceSummarizer(self.gemini_svc)
            summarized_new = summarizer.summarize_sources(retained_new)

        # Combined supplemental pool
        supplemental_pool = starting_sources + summarized_new

        # Step d: Scoped Gemini synthesis call answering just the follow-up question
        pool_text_lines = []
        for s in supplemental_pool:
            summary_txt = s.summary or s.snippet or "No details available."
            pool_text_lines.append(f"[{s.id}] {s.title} ({s.url})\nSummary: {summary_txt}")
        pool_str = "\n\n".join(pool_text_lines)

        synthesis_prompt = (
            f"Topic: {report.topic}\n"
            f"Follow-up Question: {question}\n\n"
            f"Available Supplemental Sources:\n{pool_str}\n\n"
            "Provide a concise, evidence-backed answer expanding on the follow-up question. "
            "Include inline citation markers matching the source IDs (e.g. [S1] or [S6]). "
            "Only state facts supported by the supplemental sources above."
        )

        sys_instruction = (
            "You are a research analyst answering a targeted drill-down question. "
            "Strictly cite all statements using [S#] markers from the provided sources."
        )

        raw_response = self.gemini_svc.generate_text(
            prompt=synthesis_prompt, system_instruction=sys_instruction
        ).strip()

        # Step e: Run CitationMapper validation on output
        dummy_section = ReportSection(heading="Follow-Up Answer", content=raw_response)
        mapper = CitationMapper()
        mapped_secs, _, warnings = mapper.validate_and_map_citations(
            [dummy_section], supplemental_pool
        )
        validated_summary = mapped_secs[0].content if mapped_secs else raw_response

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return FollowUpResult(
            follow_up_id=follow_up_id,
            question=question,
            target_type=target_type,
            target_id=target_id,
            new_sources=summarized_new,
            summary=validated_summary,
            merged_into_parent=False,
            created_at=now_str,
        )
