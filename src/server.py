import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import Config
from src.main import run_research_pipeline
from src.models.schemas import ResearchReport, FilterSettings
from src.output.markdown_export import render_markdown
from src.output.citation_formatter import format_bibliography, BibStyle
from src.output.report_diff import compute_diff, topic_similarity, SimilarReportHint
from src.routes.sharing_routes import sharing_router, public_router
from src.routes.annotation_routes import annotation_router
from src.routes.search_routes import search_router

logger = logging.getLogger("server")

app = FastAPI(
    title="Synthis AI Research API",
    description="Backend API for Grounded AI Research Assistant",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
# sharing_router  : POST/DELETE /api/reports/{id}/share
# public_router   : GET /api/public/reports/{token}  — separate, no auth path
# annotation_router: CRUD /api/reports/{id}/annotations, /api/annotations/{id}
# search_router   : GET /api/reports/search
app.include_router(sharing_router)
app.include_router(public_router)
app.include_router(annotation_router)
app.include_router(search_router)




class ResearchRequest(BaseModel):
    topic: str
    output_filename: Optional[str] = None
    depth: Optional[str] = "standard"
    date_filter: Optional[str] = "any"
    custom_start_date: Optional[str] = None
    custom_end_date: Optional[str] = None
    domain_mode: Optional[str] = "none"
    domain_list: List[str] = Field(default_factory=list)
    source_category: Optional[str] = "general"
    output_language: Optional[str] = "en"

    def get_filter_settings(self) -> FilterSettings:
        return FilterSettings(
            date_filter=self.date_filter or "any",
            custom_start_date=self.custom_start_date,
            custom_end_date=self.custom_end_date,
            domain_mode=self.domain_mode or "none",
            domain_list=self.domain_list or [],
            source_category=self.source_category or "general",
        )


class HealthResponse(BaseModel):
    status: str
    tavily_configured: bool
    gemini_configured: bool
    model: str


class ReportSummary(BaseModel):
    filename: str
    filepath: str
    size_bytes: int
    modified_at: str
    report_id: str                    # filename stem, used as key for share/annotations
    share_enabled: bool = False       # whether this report is currently shared
    unresolved_annotations: int = 0  # badge count for Past Reports drawer


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def get_health():
    cfg = Config(check_keys=False)
    tavily_ok = bool(cfg.tavily_api_key and cfg.tavily_api_key.startswith("tvly-"))
    gemini_ok = bool(cfg.gemini_api_key and len(cfg.gemini_api_key) > 5)

    return HealthResponse(
        status="healthy",
        tavily_configured=tavily_ok,
        gemini_configured=gemini_ok,
        model=cfg.gemini_model,
    )


@app.post("/api/research", response_model=dict, tags=["Research"])
def execute_research(req: ResearchRequest):
    if not req.topic or not req.topic.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Research topic cannot be empty.",
        )

    # Validate filter settings
    try:
        filter_settings = req.get_filter_settings()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    try:
        cfg = Config(check_keys=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    cleaned_topic = req.topic.strip()
    safe_filename = (
        req.output_filename
        or f"report_{cleaned_topic[:20].lower().replace(' ', '_')}.md"
    )
    if not safe_filename.endswith(".md"):
        safe_filename += ".md"

    out_path = Path("output") / safe_filename

    try:
        report: ResearchReport = run_research_pipeline(
            topic=cleaned_topic,
            output_path=str(out_path),
            format_type="markdown",
            depth=req.depth or "standard",
            filter_settings=filter_settings,
            config=cfg,
            output_language=req.output_language or "en",
        )

        md_content = render_markdown(report)

        # ── Check for similar past report (Feature 2) ────────────────
        possible_duplicate = None
        try:
            import json as _json
            current_stem = out_path.stem
            best_sim = 0.0
            best_match = None
            out_dir = Path("output")

            for json_file in out_dir.glob("*.json"):
                if json_file.stem == current_stem:
                    continue
                try:
                    data = _json.loads(json_file.read_text(encoding="utf-8"))
                    past_topic = data.get("topic", "")
                    sim = topic_similarity(cleaned_topic, past_topic)
                    if sim >= 0.5 and sim > best_sim:
                        best_sim = sim
                        best_match = {
                            "report_id": json_file.stem,
                            "topic": past_topic,
                            "generated_at": data.get("generated_at", ""),
                            "similarity": round(sim, 2),
                        }
                except Exception:
                    pass

            if best_match:
                possible_duplicate = best_match
        except Exception as exc:
            logger.warning(f"Failed to check for similar past report: {exc}")

        from src.output.report_stats import compute_stats
        from src.pipeline.source_watchdog import run_watchdog
        stats = compute_stats(report)
        quality = run_watchdog(report.sources)

        return {
            "success": True,
            "report": report.model_dump(),
            "stats": stats.model_dump(),
            "source_quality": quality.model_dump(),
            "markdown": md_content,
            "filename": safe_filename,
            "filepath": str(out_path.resolve()),
            "possible_duplicate": possible_duplicate,
        }
    except Exception as exc:
        logger.error(f"Error generating research report: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(exc)}",
        )


@app.post("/api/research/outline", response_model=dict, tags=["Research"])
def generate_research_outline(req: ResearchRequest):
    if not req.topic or not req.topic.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Research topic cannot be empty.",
        )

    try:
        cfg = Config(check_keys=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    try:
        from src.services.gemini_client import GeminiService
        from src.pipeline.outline_generator import OutlineGenerator

        gemini_svc = GeminiService(api_key=cfg.gemini_api_key, model_name=cfg.gemini_model)
        generator = OutlineGenerator(gemini_svc)
        outline = generator.generate_outline(req.topic.strip(), depth=req.depth or "standard")
        return {"status": "success", "outline": outline.model_dump()}
    except Exception as exc:
        logger.error(f"Error generating outline: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate outline: {str(exc)}",
        )


@app.get("/api/reports", response_model=List[ReportSummary], tags=["Reports"])
def list_reports():
    import json as _json
    from src.services.database import get_db

    out_dir = Path("output")
    if not out_dir.exists():
        return []

    db = get_db()
    reports = []
    for p in out_dir.glob("*.md"):
        stat = p.stat()
        report_id = p.stem

        # Read share_enabled from JSON sidecar (if it exists)
        share_enabled = False
        json_p = p.with_suffix(".json")
        if json_p.exists():
            try:
                data = _json.loads(json_p.read_text(encoding="utf-8"))
                share_enabled = bool(data.get("share_enabled", False))
            except Exception:
                pass

        unresolved = db.count_unresolved_annotations(report_id)

        reports.append(
            ReportSummary(
                filename=p.name,
                filepath=str(p.resolve()),
                size_bytes=stat.st_size,
                modified_at=str(stat.st_mtime),
                report_id=report_id,
                share_enabled=share_enabled,
                unresolved_annotations=unresolved,
            )
        )
    return sorted(reports, key=lambda r: r.modified_at, reverse=True)


@app.get("/api/reports/{filename}", response_model=dict, tags=["Reports"])
def get_report_by_filename(filename: str):
    # Sanitize filename
    safe_name = Path(filename).name
    p = Path("output") / safe_name
    if not p.exists() or not p.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{safe_name}' not found.",
        )

    try:
        md_content = p.read_text(encoding="utf-8")
        return {
            "filename": safe_name,
            "markdown": md_content,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read report: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Bibliography export endpoint
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}/bibliography", response_model=dict, tags=["Reports"])
def get_bibliography(report_id: str, style: str = "apa"):
    """
    Return a formatted bibliography (plain text) for the sources in the given
    report.

    Parameters
    ----------
    report_id : str
        The filename stem of the report (e.g. 'report_ai_tools').
    style : str
        One of 'apa', 'mla', 'chicago'. Defaults to 'apa'.
    """
    import json

    # Validate style early
    valid_styles = ("apa", "mla", "chicago")
    if style.lower() not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid style '{style}'. Choose one of: {', '.join(valid_styles)}.",
        )

    # Resolve the JSON sidecar
    safe_id = Path(report_id).name  # prevents path traversal
    json_path = Path("output") / f"{safe_id}.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No saved report found for report_id '{safe_id}'.",
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        report = ResearchReport.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load report: {exc}",
        )

    if not report.sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report has no sources to format.",
        )

    try:
        text = format_bibliography(report.sources, style.lower())  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "report_id": safe_id,
        "style": style.lower(),
        "source_count": len(report.sources),
        "text": text,
    }


# ---------------------------------------------------------------------------
# Source Credibility Deep-Dive Endpoint (Advanced Feature 1)
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}/sources/{source_id}/credibility", response_model=dict, tags=["Reports"])
def get_source_credibility(report_id: str, source_id: str):
    """
    Returns a detailed CredibilityReport breakdown for a specific source in a report.
    """
    import json
    from src.pipeline.credibility_analyzer import CredibilityAnalyzer

    safe_id = Path(report_id).name
    json_path = Path("output") / f"{safe_id}.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_id}' not found.",
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        report = ResearchReport.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load report: {exc}",
        )

    matched_source = next((s for s in report.sources if s.id.lower() == source_id.lower()), None)
    if not matched_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source ID '{source_id}' not found in report '{safe_id}'.",
        )

    credibility = CredibilityAnalyzer.analyze_source(matched_source)
    return {"status": "success", "credibility": credibility.model_dump()}


# ---------------------------------------------------------------------------
# Keyword & Theme Extractor (Advanced Feature 5)
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}/keywords", response_model=dict, tags=["Reports"])
def get_report_keywords(report_id: str, top_n: int = 15, n_themes: int = 5):
    """
    Returns top keywords and theme clusters extracted from a saved report via TF-IDF-style analysis.
    """
    import json
    from src.output.keyword_extractor import extract_keywords, cluster_themes

    safe_id = Path(report_id).name
    json_path = Path("output") / f"{safe_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Report '{safe_id}' not found.")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        report = ResearchReport.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to load report: {exc}")

    keywords = extract_keywords(report, top_n=top_n)
    themes   = cluster_themes(keywords, n_themes=n_themes)
    return {
        "status": "success",
        "keywords": [k.model_dump() for k in keywords],
        "themes":   [t.model_dump() for t in themes],
    }


# ---------------------------------------------------------------------------
# Executive Brief Endpoint (Advanced Feature 6)
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}/brief", response_model=dict, tags=["Reports"])
def get_executive_brief(report_id: str):
    """
    Returns a condensed, boardroom-ready Executive Brief for a report.
    """
    import json
    from src.output.executive_brief import generate_brief

    safe_id = Path(report_id).name
    json_path = Path("output") / f"{safe_id}.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_id}' not found.",
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        report = ResearchReport.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load report: {exc}",
        )

    brief = generate_brief(report)
    return {"status": "success", "brief": brief.model_dump()}


# ---------------------------------------------------------------------------
# Report diffing endpoint (Output Feature 2)
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}/diff", response_model=dict, tags=["Reports"])
def get_report_diff(report_id: str, against: str):
    """
    Compute a structured diff between report_id (new) and against (old).

    Parameters
    ----------
    report_id : str
        The primary (newer) report filename stem (e.g. 'report_ai_tools_v2').
    against : str
        The reference (older) report filename stem (e.g. 'report_ai_tools').
    """
    import json

    safe_new = Path(report_id).name
    safe_old = Path(against).name

    new_path = Path("output") / f"{safe_new}.json"
    old_path = Path("output") / f"{safe_old}.json"

    if not new_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_new}' not found.",
        )
    if not old_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison baseline report '{safe_old}' not found.",
        )

    try:
        new_data = json.loads(new_path.read_text(encoding="utf-8"))
        old_data = json.loads(old_path.read_text(encoding="utf-8"))
        new_report = ResearchReport.model_validate(new_data)
        old_report = ResearchReport.model_validate(old_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load reports for diffing: {exc}",
        )

    try:
        diff = compute_diff(old_report, new_report, old_id=safe_old, new_id=safe_new)
        return {"status": "success", "diff": diff.model_dump()}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diff computation failed: {exc}",
        )


class FollowUpRequest(BaseModel):
    report: Optional[ResearchReport] = None
    filename: Optional[str] = None
    target_type: str  # "takeaway" | "section"
    target_id: str
    question: str


@app.post("/api/research/follow-up", response_model=dict, tags=["Research"])
def execute_followup(req: FollowUpRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Follow-up question cannot be empty.",
        )

    report_obj = req.report
    if not report_obj and req.filename:
        safe_name = Path(req.filename).name
        p = Path("output") / safe_name
        if p.exists():
            # If JSON exists, load schema directly
            json_p = p.with_suffix(".json")
            if json_p.exists():
                import json
                data = json.loads(json_p.read_text(encoding="utf-8"))
                report_obj = ResearchReport.model_validate(data)

    if not report_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid ResearchReport object or filename must be provided.",
        )

    try:
        from src.pipeline.followup_pipeline import FollowUpPipeline
        import uuid

        pipeline = FollowUpPipeline()
        follow_up_id = f"fu_{uuid.uuid4().hex[:8]}"
        result = pipeline.execute_followup(
            report=report_obj,
            target_type=req.target_type,
            target_id=req.target_id,
            question=req.question.strip(),
            follow_up_id=follow_up_id,
        )
        return {"status": "success", "result": result.model_dump()}
    except Exception as exc:
        logger.error(f"Follow-up execution failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Follow-up pipeline failed: {str(exc)}",
        )


class CompareRequest(BaseModel):
    topic_a: str
    topic_b: str
    depth: str = "standard"
    date_filter: str = "any"
    custom_start_date: Optional[str] = None
    custom_end_date: Optional[str] = None
    domain_mode: str = "none"
    domain_list: List[str] = Field(default_factory=list)
    source_category: str = "general"

    def get_filter_settings(self) -> FilterSettings:
        return FilterSettings(
            date_filter=self.date_filter,
            custom_start_date=self.custom_start_date,
            custom_end_date=self.custom_end_date,
            domain_mode=self.domain_mode,
            domain_list=self.domain_list,
            source_category=self.source_category,
        )


@app.post("/api/research/compare", response_model=dict, tags=["Research"])
def execute_comparative_research(req: CompareRequest):
    if not req.topic_a or not req.topic_a.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topic A cannot be empty.")
    if not req.topic_b or not req.topic_b.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topic B cannot be empty.")

    try:
        filter_settings = req.get_filter_settings()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        cfg = Config(check_keys=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    try:
        from src.pipeline.comparative_pipeline import ComparativePipeline
        pipeline = ComparativePipeline(config=cfg)
        cmp_report = pipeline.execute(
            topic_a=req.topic_a.strip(),
            topic_b=req.topic_b.strip(),
            depth=req.depth or "standard",
            filter_settings=filter_settings,
        )
        return {"status": "success", "report": cmp_report.model_dump()}
    except Exception as exc:
        logger.error(f"Comparative pipeline failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparative research failed: {str(exc)}",
        )


class ContinueRequest(BaseModel):
    report: Optional[ResearchReport] = None
    filename: Optional[str] = None
    additional_context: Optional[str] = None
    depth: str = "standard"


@app.post("/api/research/continue", response_model=dict, tags=["Sessions"])
def continue_research_session(req: ContinueRequest):
    report_obj = req.report
    if not report_obj and req.filename:
        safe_name = Path(req.filename).name
        p = Path("output") / safe_name
        if p.exists():
            json_p = p.with_suffix(".json")
            if json_p.exists():
                import json
                data = json.loads(json_p.read_text(encoding="utf-8"))
                report_obj = ResearchReport.model_validate(data)

    if not report_obj:
        # Construct fallback ResearchReport from filename/topic
        cleaned_topic = (req.filename or "Topic").replace(".md", "").replace("_", " ")
        report_obj = ResearchReport(topic=cleaned_topic, generated_at="Past Report")

    try:
        from src.services.session_manager import SessionManager
        manager = SessionManager()
        session = manager.continue_session(
            parent_report=report_obj,
            additional_context=req.additional_context,
            depth=req.depth,
        )
        return {"status": "success", "session": session.model_dump()}
    except Exception as exc:
        logger.error(f"Session continuation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session continuation failed: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)

