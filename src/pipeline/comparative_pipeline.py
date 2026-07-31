"""
Comparative Research Pipeline — Feature 2.
Executes a genuinely different report shape for "Topic A vs Topic B" comparisons.
Reuses: Retriever, SourceFilter, SourceSummarizer, CitationMapper — no stage duplication.
"""
import json
import re
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from src.config import Config
from src.models.schemas import (
    ComparisonDimension,
    ComparativeReport,
    FilterSettings,
    Source,
)
from src.services.gemini_client import GeminiService
from src.services.tavily_client import TavilyService
from src.pipeline.retriever import Retriever
from src.pipeline.source_filter import SourceFilter
from src.pipeline.summarizer import SourceSummarizer
from src.pipeline.citation_mapper import CitationMapper

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# System prompts
# ──────────────────────────────────────────────────────────────
DIMENSION_INFERENCE_PROMPT = """\
You are a research strategist. Given two topics for comparison, infer 3 to 6 meaningful,
specific dimensions that are genuinely relevant to both. Avoid generic dimensions that apply
to everything (e.g. "overview", "background"). Tailor them to what makes this particular pair
worth comparing (e.g. for two ML frameworks: "Training Speed", "Ecosystem Maturity",
"Community Support", "Deployment Complexity", "Memory Footprint").

Topics: "{topic_a}" vs "{topic_b}"

Return a JSON array of dimension name strings, and nothing else. Example:
["Dimension 1", "Dimension 2", "Dimension 3"]
"""

COMPARATIVE_SYNTHESIS_PROMPT = """\
You are a comparative research analyst. Given sources about both topics on a specific
comparison dimension, produce a structured analysis.

Topic A: {topic_a}
Topic B: {topic_b}
Dimension: {dimension}

Topic A Sources:
{topic_a_sources}

Topic B Sources:
{topic_b_sources}

Produce a JSON object with these exact keys:
{{
  "topic_a_position": "1-3 sentence factual position for Topic A on this dimension, with inline [S#] citations",
  "topic_a_source_ids": ["S1", "S2"],
  "topic_b_position": "1-3 sentence factual position for Topic B on this dimension, with inline [S#] citations",
  "topic_b_source_ids": ["S3", "S4"],
  "verdict_or_note": "Only include if sources actually support a comparative conclusion; otherwise null"
}}

RULES:
- Only cite source IDs that are present in the sources above.
- If sources are insufficient to make a comparative claim on this dimension, set both positions
  to explain the limitation and set verdict_or_note to null.
- Do not fabricate data.
"""


class ComparativePipeline:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config(check_keys=True)
        self.gemini_svc = GeminiService(
            api_key=self.config.gemini_api_key,
            model_name=self.config.gemini_model,
        )
        self.tavily_svc = TavilyService(api_key=self.config.tavily_api_key)

    def execute(
        self,
        topic_a: str,
        topic_b: str,
        depth: str = "standard",
        filter_settings: Optional[FilterSettings] = None,
    ) -> ComparativeReport:
        if filter_settings is None:
            filter_settings = FilterSettings()

        max_per_query = {"quick": 4, "standard": 6, "deep": 8}.get(depth, 6)

        # ── Stage 1: Infer comparison dimensions ──────────────────────────
        print(f"\n [1/4] Inferring comparison dimensions for '{topic_a}' vs '{topic_b}'...")
        dimensions = self._infer_dimensions(topic_a, topic_b)
        print(f"   └─ {len(dimensions)} dimensions: {', '.join(dimensions)}")

        # ── Stage 2 & 3: Dual retrieval + filter per dimension ────────────
        print(f"\n [2/4] Retrieving and summarizing sources per dimension...")
        retriever = Retriever(self.tavily_svc)
        source_filter = SourceFilter()

        all_sources: List[Source] = []
        # tag: "A" or "B" per source, stored in a parallel list
        source_tags: List[str] = []
        next_id = 1

        for dim in dimensions:
            query_a = f"{topic_a} {dim}"
            query_b = f"{topic_b} {dim}"

            raw_a = retriever.retrieve_sources([query_a], max_results_per_query=max_per_query, filter_settings=filter_settings)
            raw_b = retriever.retrieve_sources([query_b], max_results_per_query=max_per_query, filter_settings=filter_settings)

            # Deduplicate against already-collected sources by URL
            existing_urls = {SourceFilter._normalize_url(s.url) for s in all_sources}

            for tag, raw_batch in [("A", raw_a), ("B", raw_b)]:
                for src in raw_batch:
                    norm = SourceFilter._normalize_url(src.url)
                    if norm not in existing_urls:
                        existing_urls.add(norm)
                        domain = SourceFilter._extract_domain(src.url)
                        tier = SourceFilter.classify_credibility(domain)
                        updated = src.model_copy(update={"id": f"S{next_id}", "credibility_tier": tier})
                        next_id += 1
                        all_sources.append(updated)
                        source_tags.append(tag)

        # ── Stage 4: Summarize all sources (reuse SourceSummarizer unchanged) ──
        print(f"\n [3/4] Summarizing {len(all_sources)} sources...")
        summarizer = SourceSummarizer(self.gemini_svc)
        summarized_sources = summarizer.summarize_sources(all_sources)
        # Rebuild tag map with stable IDs post-summarization
        src_by_id = {s.id: (s, tag) for s, tag in zip(summarized_sources, source_tags)}

        # ── Stage 5: Comparative synthesis per dimension ──────────────────
        print(f"\n [4/4] Synthesising comparative positions per dimension...")
        mapper = CitationMapper()
        built_dimensions: List[ComparisonDimension] = []

        for dim in dimensions:
            a_sources = [s for s, tag in src_by_id.values() if tag == "A"]
            b_sources = [s for s, tag in src_by_id.values() if tag == "B"]

            # Limit context per dimension
            a_sources = a_sources[:6]
            b_sources = b_sources[:6]

            dim_result = self._synthesize_dimension(
                topic_a, topic_b, dim, a_sources, b_sources, mapper, summarized_sources
            )
            built_dimensions.append(dim_result)

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return ComparativeReport(
            id=f"cmp_{uuid.uuid4().hex[:8]}",
            topic_a=topic_a,
            topic_b=topic_b,
            generated_at=now_str,
            shared_dimensions=built_dimensions,
            sources=summarized_sources,
            filter_settings=filter_settings,
        )

    # ──────────────────────────────────────────────────────────────
    def _infer_dimensions(self, topic_a: str, topic_b: str) -> List[str]:
        prompt = DIMENSION_INFERENCE_PROMPT.format(topic_a=topic_a, topic_b=topic_b)
        raw = self.gemini_svc.generate_text(prompt).strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            dims = json.loads(raw)
            if isinstance(dims, list) and all(isinstance(d, str) for d in dims):
                return dims[:6]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: extract quoted strings
        fallback = re.findall(r'"([^"]{3,})"', raw)
        return fallback[:6] if fallback else ["Overview", "Key Advantages", "Limitations", "Use Cases"]

    def _synthesize_dimension(
        self,
        topic_a: str,
        topic_b: str,
        dimension: str,
        a_sources: List[Source],
        b_sources: List[Source],
        mapper: CitationMapper,
        all_sources: List[Source],
    ) -> ComparisonDimension:
        def _format_sources(sources: List[Source]) -> str:
            lines = []
            for s in sources:
                summary = s.summary or s.snippet or "No content."
                lines.append(f"[{s.id}] {s.title}\n{summary}")
            return "\n\n".join(lines) if lines else "No sources available."

        prompt = COMPARATIVE_SYNTHESIS_PROMPT.format(
            topic_a=topic_a,
            topic_b=topic_b,
            dimension=dimension,
            topic_a_sources=_format_sources(a_sources),
            topic_b_sources=_format_sources(b_sources),
        )

        raw = self.gemini_svc.generate_text(prompt).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse JSON for dimension '{dimension}', using fallback.")
            data = {}

        # Validate citations via CitationMapper (no exceptions to grounding rules)
        from src.models.schemas import ReportSection
        pos_a_raw = data.get("topic_a_position", "Insufficient sources for this dimension.")
        pos_b_raw = data.get("topic_b_position", "Insufficient sources for this dimension.")

        sec_a = ReportSection(heading=f"{topic_a} — {dimension}", content=pos_a_raw)
        sec_b = ReportSection(heading=f"{topic_b} — {dimension}", content=pos_b_raw)
        mapped_secs, _, _ = mapper.validate_and_map_citations([sec_a, sec_b], all_sources)

        validated_a = mapped_secs[0].content if len(mapped_secs) > 0 else pos_a_raw
        validated_b = mapped_secs[1].content if len(mapped_secs) > 1 else pos_b_raw

        return ComparisonDimension(
            dimension_name=dimension,
            topic_a_position=validated_a,
            topic_a_source_ids=data.get("topic_a_source_ids", []),
            topic_b_position=validated_b,
            topic_b_source_ids=data.get("topic_b_source_ids", []),
            verdict_or_note=data.get("verdict_or_note"),
        )
