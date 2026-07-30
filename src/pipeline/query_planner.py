import json
import logging
from typing import List
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

QUERY_PLANNER_SYSTEM_PROMPT = (
    "You are an expert AI research query planner. "
    "Given a user research topic, break it down into 3 to 6 distinct, non-overlapping, "
    "focused web search queries to gather comprehensive, multi-angled information. "
    "Cover background, current state, key debates/controversies, recent developments, and expert opinions. "
    "Output strictly a JSON array of strings containing only the search query strings. "
    "Do not include any extra markdown formatting outside ```json ``` or extra conversational text."
)


class QueryPlanner:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    def plan_queries(self, topic: str, max_queries: int = 5) -> List[str]:
        """
        Generates 3 to 6 targeted search queries for a given research topic.
        """
        if not topic or not topic.strip():
            return []

        prompt = (
            f"Topic: {topic.strip()}\n\n"
            f"Generate between 3 and {max_queries} distinct, highly effective search queries. "
            "Return a JSON array of strings."
        )

        try:
            raw_response = self.gemini_service.generate_text(
                prompt=prompt,
                system_instruction=QUERY_PLANNER_SYSTEM_PROMPT,
            )
            return self._parse_queries(raw_response, topic)
        except Exception as exc:
            logger.error(f"Error during query planning for topic '{topic}': {exc}")
            # Fallback to standard query variations if LLM call fails
            return [
                f"{topic} overview background",
                f"{topic} latest developments current state",
                f"{topic} key debates perspectives",
            ]

    def _parse_queries(self, raw_text: str, fallback_topic: str) -> List[str]:
        cleaned = raw_text.strip()

        # Handle ```json ... ``` code blocks
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
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                result = [str(q).strip() for q in parsed if str(q).strip()]
                if result:
                    return result[:6]
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response from query planner. Falling back to line splitting.")

        # Fallback line parsing
        lines = [
            line.strip().lstrip("-*123456789. ").strip('"')
            for line in raw_text.split("\n")
            if line.strip() and not line.strip().startswith("```")
        ]
        valid_queries = [q for q in lines if len(q) > 5 and not q.lower().startswith("json")]

        if valid_queries:
            return valid_queries[:6]

        return [
            f"{fallback_topic} overview",
            f"{fallback_topic} key details",
            f"{fallback_topic} current status",
        ]
