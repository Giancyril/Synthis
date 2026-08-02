import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)


class OutlineSection(BaseModel):
    heading: str
    description: str
    key_questions: List[str]


class ResearchOutline(BaseModel):
    topic: str
    depth: str
    estimated_source_count: int
    recommended_depth: str
    sections: List[OutlineSection]


OUTLINE_SYSTEM_PROMPT = (
    "You are an expert research planner. Given a topic and research depth, produce a high-level research outline "
    "showing key sections, descriptions, and essential questions to be answered. "
    "Output strictly valid JSON adhering to the specified schema."
)


class OutlineGenerator:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    def generate_outline(self, topic: str, depth: str = "standard") -> ResearchOutline:
        depth_map = {
            "quick": {"count": 6, "sections": 3},
            "standard": {"count": 12, "sections": 4},
            "deep": {"count": 20, "sections": 6},
        }
        info = depth_map.get(depth.lower(), depth_map["standard"])

        prompt = (
            f"Topic: {topic}\n"
            f"Depth Mode: {depth} (target: ~{info['sections']} sections, ~{info['count']} sources)\n\n"
            "Generate a structured research outline as JSON with this exact shape:\n"
            "{\n"
            '  "sections": [\n'
            '    {\n'
            '      "heading": "...",\n'
            '      "description": "...",\n'
            '      "key_questions": ["question 1", "question 2"]\n'
            '    }\n'
            '  ],\n'
            '  "recommended_depth": "standard"\n'
            "}"
        )

        try:
            raw_text = self.gemini_service.generate_text(
                prompt=prompt,
                system_instruction=OUTLINE_SYSTEM_PROMPT,
            )
            cleaned = raw_text.strip()
            if "```" in cleaned:
                lines = cleaned.split("\n")
                json_lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(json_lines).strip()

            data = json.loads(cleaned)
            sec_objs = []
            for s in data.get("sections", []):
                if s.get("heading"):
                    sec_objs.append(
                        OutlineSection(
                            heading=s.get("heading", "").strip(),
                            description=s.get("description", "").strip(),
                            key_questions=[str(q).strip() for q in s.get("key_questions", []) if str(q).strip()],
                        )
                    )

            rec_depth = data.get("recommended_depth", depth)

            if not sec_objs:
                raise ValueError("No valid sections returned")

            return ResearchOutline(
                topic=topic,
                depth=depth,
                estimated_source_count=info["count"],
                recommended_depth=rec_depth,
                sections=sec_objs,
            )

        except Exception as exc:
            logger.warning(f"Fallback outline generated due to LLM response issue: {exc}")
            # Fallback outline
            return ResearchOutline(
                topic=topic,
                depth=depth,
                estimated_source_count=info["count"],
                recommended_depth="standard",
                sections=[
                    OutlineSection(
                        heading="Background & Fundamentals",
                        description=f"Overview of core concepts relating to {topic}.",
                        key_questions=[f"What is the foundation of {topic}?", "What problem does it solve?"],
                    ),
                    OutlineSection(
                        heading="Current Industry Developments",
                        description=f"Recent breakthroughs and ongoing initiatives in {topic}.",
                        key_questions=["What are the latest updates?", "Who are the key players?"],
                    ),
                    OutlineSection(
                        heading="Future Outlook & Technical Challenges",
                        description=f"Projected trajectories and roadblocks for {topic}.",
                        key_questions=["What obstacles remain?", "Where is the field heading by 2030?"],
                    ),
                ],
            )
