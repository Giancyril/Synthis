import json
import logging
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from src.models.schemas import (
    Source,
    KeyTakeaway,
    ReportSection,
    ConflictingTopic,
    ConflictPosition,
    ResearchReport,
)
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = (
    "You are a master research synthesizer producing grounded, evidence-backed intelligence reports. "
    "CRITICAL GROUNDING RULES:\n"
    "1. Only make claims that are strictly supported by the provided source summaries.\n"
    "2. Every key takeaway must list the exact supporting Source IDs (e.g. ['S1', 'S3']).\n"
    "3. Every section's prose content must include inline citation markers matching the source IDs, such as [S1] or [S2] [S4].\n"
    "4. If sources conflict or disagree on any facts, dates, numbers, or conclusions, explicitly structure these in 'conflicting_information'.\n"
    "5. If source coverage is thin on any angle, state that clearly rather than filling gaps from general memory.\n"
    "6. Output MUST be valid JSON adhering strictly to the required schema."
)


class ReportSynthesizer:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    def synthesize_report(
        self, topic: str, sources: List[Source]
    ) -> Tuple[List[KeyTakeaway], List[ReportSection], List[ConflictingTopic], Optional[str]]:
        """
        Synthesizes per-source summaries into key takeaways, report sections, and structured conflicting_information.
        Returns (key_takeaways, sections, conflicting_information, confidence_note).
        """
        if not sources:
            confidence_note = "No web search sources were retrieved. Report cannot be synthesized."
            return [], [], [], confidence_note

        source_payloads = []
        for s in sources:
            summary_text = s.summary or s.snippet or "No details available."
            source_payloads.append(
                f"[{s.id}] Title: {s.title}\nURL: {s.url}\nSummary: {summary_text}"
            )
        formatted_sources = "\n\n".join(source_payloads)

        prompt = (
            f"Topic: {topic}\n\n"
            f"Retrieved Sources:\n{formatted_sources}\n\n"
            "Produce a JSON object with four keys:\n"
            "1. 'key_takeaways': array of objects with 'text' (string) and 'source_ids' (array of strings, e.g. ['S1', 'S2']).\n"
            "2. 'sections': array of objects with 'heading' (string) and 'content' (string with inline [S#] citations).\n"
            "3. 'conflicting_information': array of objects representing detected disagreements between sources. "
            "Each object has 'topic' (string) and 'positions' (array of objects with 'claim' (string) and 'source_ids' (array of strings)). "
            "Only include if genuine conflicts exist among sources, otherwise return an empty array [].\n"
            "4. 'confidence_note': (optional string) warning if sources are thin or conflicting.\n\n"
            "Example JSON output shape:\n"
            "{\n"
            '  "key_takeaways": [{"text": "...", "source_ids": ["S1"]}],\n'
            '  "sections": [{"heading": "Overview", "content": "According to research [S1],..."}],\n'
            '  "conflicting_information": [\n'
            '    {\n'
            '      "topic": "Commercial Availability Timeline",\n'
            '      "positions": [\n'
            '        {"claim": "Available by 2026", "source_ids": ["S1"]},\n'
            '        {"claim": "Delayed until 2028+", "source_ids": ["S3"]}\n'
            '      ]\n'
            '    }\n'
            '  ],\n'
            '  "confidence_note": null\n'
            "}"
        )

        try:
            raw_text = self.gemini_service.generate_text(
                prompt=prompt,
                system_instruction=SYNTHESIZER_SYSTEM_PROMPT,
            )
            takeaways, sections, conflicts, conf_note = self._parse_synthesis_output(raw_text, sources)
            return takeaways, sections, conflicts, conf_note
        except Exception as exc:
            logger.error(f"Error during report synthesis: {exc}")
            # Fallback output
            fallback_takeaways = [
                KeyTakeaway(text=f"Summary of {topic} based on retrieved sources.", source_ids=[s.id for s in sources[:3]])
            ]
            fallback_sections = [
                ReportSection(
                    heading="Research Overview",
                    content=" ".join([f"{s.title}: {s.summary or s.snippet} [{s.id}]" for s in sources[:5]]),
                )
            ]
            return fallback_takeaways, fallback_sections, [], "Synthesis generated via fallback due to model error."

    def _parse_synthesis_output(
        self, raw_text: str, sources: List[Source]
    ) -> Tuple[List[KeyTakeaway], List[ReportSection], List[ConflictingTopic], Optional[str]]:
        cleaned = raw_text.strip()
        if "```" in cleaned:
            lines = cleaned.split("\n")
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```"):
                    inside = not inside
                    continue
                if inside or not line.strip().startswith("```"):
                    json_lines.append(line)
            cleaned = "\n".join(json_lines).strip()

        try:
            data = json.loads(cleaned)
            takeaways = []
            for t in data.get("key_takeaways", []):
                text = t.get("text", "").strip()
                s_ids = [str(sid).strip() for sid in t.get("source_ids", []) if str(sid).strip()]
                if text:
                    takeaways.append(KeyTakeaway(text=text, source_ids=s_ids))

            sections = []
            for sec in data.get("sections", []):
                heading = sec.get("heading", "").strip()
                content = sec.get("content", "").strip()
                if heading and content:
                    sections.append(ReportSection(heading=heading, content=content))

            conflicts: List[ConflictingTopic] = []
            for item in data.get("conflicting_information", []):
                c_topic = item.get("topic", "").strip()
                raw_positions = item.get("positions", [])
                positions: List[ConflictPosition] = []
                for pos in raw_positions:
                    claim = pos.get("claim", "").strip()
                    pos_sids = [str(sid).strip() for sid in pos.get("source_ids", []) if str(sid).strip()]
                    if claim:
                        positions.append(ConflictPosition(claim=claim, source_ids=pos_sids))
                if c_topic and positions:
                    conflicts.append(ConflictingTopic(topic=c_topic, positions=positions))

            conf_note = data.get("confidence_note")

            if len(sources) <= 2 and not conf_note:
                conf_note = "Limited number of sources retrieved — findings should be treated as preliminary."

            return takeaways, sections, conflicts, conf_note
        except Exception as exc:
            logger.warning(f"Failed to parse synthesis JSON output: {exc}")
            raise exc

