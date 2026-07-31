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
        )

        md_content = render_markdown(report)

        return {
            "success": True,
            "report": report.model_dump(),
            "markdown": md_content,
            "filename": safe_filename,
            "filepath": str(out_path.resolve()),
        }
    except Exception as exc:
        logger.error(f"Error generating research report: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(exc)}",
        )


@app.get("/api/reports", response_model=List[ReportSummary], tags=["Reports"])
def list_reports():
    out_dir = Path("output")
    if not out_dir.exists():
        return []

    reports = []
    for p in out_dir.glob("*.md"):
        stat = p.stat()
        reports.append(
            ReportSummary(
                filename=p.name,
                filepath=str(p.resolve()),
                size_bytes=stat.st_size,
                modified_at=str(stat.st_mtime),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)

