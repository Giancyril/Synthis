import logging
from typing import List
from src.models.schemas import Source
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

SUMMARIZER_SYSTEM_PROMPT = (
    "You are a strict, factual source summarizer for a grounded research pipeline. "
    "Summarize ONLY the provided snippet/text in 2 to 4 sentences. "
    "CRITICAL REQUIREMENT: Do NOT add any outside knowledge, assumptions, or external facts. "
    "If the text has very limited information, state 'Limited content available' and summarize what is present."
)


class SourceSummarizer:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    def summarize_sources(self, sources: List[Source]) -> List[Source]:
        """
        Summarizes each source individually using Gemini without introducing outside knowledge.
        Updates the `.summary` field on each Source model.
        """
        if not sources:
            return []

        summarized_sources: List[Source] = []

        for source in sources:
            snippet_text = (source.snippet or "").strip()
            if not snippet_text or len(snippet_text) < 15:
                updated = source.model_copy(
                    update={"summary": "Limited content available from source snippet."}
                )
                summarized_sources.append(updated)
                continue

            prompt = (
                f"Source ID: {source.id}\n"
                f"Title: {source.title}\n"
                f"Content Snippet: {snippet_text}\n\n"
                "Provide a concise, grounded 2-4 sentence summary of ONLY the above text."
            )

            try:
                summary = self.gemini_service.generate_text(
                    prompt=prompt,
                    system_instruction=SUMMARIZER_SYSTEM_PROMPT,
                )
                if not summary:
                    summary = snippet_text[:200] + "..."
                updated = source.model_copy(update={"summary": summary.strip()})
            except Exception as exc:
                logger.error(f"Error summarizing source {source.id}: {exc}")
                fallback_summary = snippet_text[:200] + "..." if len(snippet_text) > 200 else snippet_text
                updated = source.model_copy(update={"summary": fallback_summary})

            summarized_sources.append(updated)

        return summarized_sources
