import argparse
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import Config
from src.services.gemini_client import GeminiService
from src.services.tavily_client import TavilyService
from src.pipeline.query_planner import QueryPlanner
from src.pipeline.retriever import Retriever
from src.pipeline.source_filter import SourceFilter
from src.pipeline.summarizer import SourceSummarizer
from src.pipeline.synthesizer import ReportSynthesizer
from src.pipeline.citation_mapper import CitationMapper
from src.models.schemas import ResearchReport
from src.output.markdown_export import export_to_markdown_file
from src.output.json_export import export_to_json_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("research_assistant")


def run_research_pipeline(
    topic: str,
    output_path: str = "output/report.md",
    format_type: str = "markdown",
    depth: str = "standard",
    config: Config = None,
) -> ResearchReport:
    """
    Executes the complete grounded AI research pipeline:
    Query Planning -> Retrieval -> Filtering -> Summarization -> Synthesis -> Citation Mapping -> Export
    """
    if config is None:
        config = Config(check_keys=True)

    # Configure depth parameters
    depth_settings = {
        "quick": {"max_queries": 2, "max_sources": 6},
        "standard": {"max_queries": 4, "max_sources": 12},
        "deep": {"max_queries": 6, "max_sources": 20},
    }
    settings = depth_settings.get(depth.lower(), depth_settings["standard"])

    print(f"\n=======================================================")
    print(f"🚀 AI Research Assistant — Grounded Pipeline")
    print(f"Topic: '{topic}' | Depth: {depth.upper()} ({settings['max_queries']} queries, max {settings['max_sources']} sources)")
    print(f"=======================================================\n")

    # Initialize services
    gemini_svc = GeminiService(api_key=config.gemini_api_key, model_name=config.gemini_model)
    tavily_svc = TavilyService(api_key=config.tavily_api_key)

    # Step 1: Query Planning
    print(" [1/6] Planning search queries with Gemini...")
    planner = QueryPlanner(gemini_svc)
    queries = planner.plan_queries(topic, max_queries=settings["max_queries"])
    print(f"   └─ Planned {len(queries)} search queries:")
    for q in queries:
        print(f"      • {q}")

    # Step 2: Retrieval
    print("\n [2/6] Retrieving web sources via Tavily API...")
    retriever = Retriever(tavily_svc)
    raw_sources = retriever.retrieve_sources(queries)
    print(f"   └─ Retrieved {len(raw_sources)} raw search results.")

    # Step 3: Filtering & Deduplication
    print("\n [3/6] Deduplicating and filtering high-relevance sources...")
    source_filter = SourceFilter(min_score=0.2, max_sources=settings["max_sources"])
    clean_sources = source_filter.filter_sources(raw_sources)
    print(f"   └─ Retained {len(clean_sources)} clean sources.")

    # Step 4: Per-Source Summarization
    print("\n [4/6] Summarizing each source grounded strictly in text...")
    summarizer = SourceSummarizer(gemini_svc)
    summarized_sources = summarizer.summarize_sources(clean_sources)
    print(f"   └─ Completed summaries for {len(summarized_sources)} sources.")

    # Step 5: Synthesis
    print("\n [5/6] Synthesizing report sections and key takeaways...")
    synthesizer = ReportSynthesizer(gemini_svc)
    takeaways, raw_sections, conf_note = synthesizer.synthesize_report(topic, summarized_sources)
    print(f"   └─ Generated {len(takeaways)} key takeaways and {len(raw_sections)} report sections.")

    # Step 6: Citation Mapping & Grounding Validation
    print("\n [6/6] Validating inline citations and grounding...")
    mapper = CitationMapper()
    mapped_sections, warnings = mapper.validate_and_map_citations(raw_sections, summarized_sources)
    if warnings:
        for w in warnings:
            print(f"   ⚠️  {w}")

    # Build final Pydantic ResearchReport
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report = ResearchReport(
        topic=topic,
        generated_at=now_str,
        key_takeaways=takeaways,
        sections=mapped_sections,
        sources=summarized_sources,
        confidence_note=conf_note,
    )

    # Export report to disk
    out_file = Path(output_path)
    if format_type.lower() == "json" or out_file.suffix.lower() == ".json":
        written_path = export_to_json_file(report, out_file)
    else:
        written_path = export_to_markdown_file(report, out_file)

    print(f"\n=======================================================")
    print(f"✅ Research Report successfully generated!")
    print(f"📄 Saved to: {written_path}")
    print(f"=======================================================\n")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="AI Research Assistant — Grounded Research Report Generator"
    )
    parser.add_argument(
        "topic",
        type=str,
        help="Research topic or question to investigate (e.g. 'Quantum Computing in 2026')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output/report.md",
        help="Destination path for output file (default: output/report.md)",
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["markdown", "json"],
        default="markdown",
        help="Export format: markdown or json (default: markdown)",
    )

    args = parser.parse_args()

    try:
        cfg = Config(check_keys=True)
        run_research_pipeline(
            topic=args.topic,
            output_path=args.output,
            format_type=args.format,
            config=cfg,
        )
    except Exception as exc:
        logger.error(f"Execution failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
