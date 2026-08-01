"""
Sharing routes — Feature 1: Shareable Read-Only Report Links

Endpoints:
  POST   /api/reports/{report_id}/share   — generate (or return existing) share token
  DELETE /api/reports/{report_id}/share   — revoke token (share_enabled=False)
  GET    /api/public/reports/{token}      — public read-only route (PublicReportDTO)

Design notes:
  - share_token/share_enabled/share_created_at live in the report's .json file.
  - The public endpoint is a completely separate router from the authenticated
    report endpoints — it can never accidentally expose non-shared reports.
  - PublicReportDTO deliberately excludes id, share_token, filter_settings,
    follow_ups, and all session/internal metadata.
  - Annotations (Feature 2) are also excluded — they are strictly private.

Future follow-ups (not built here):
  - Token expiry
  - Password protection
  - Per-viewer access control
"""

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.models.schemas import PublicReportDTO, ResearchReport

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")

# ── Routers ──────────────────────────────────────────────────────────────────

# Authenticated sharing management (POST/DELETE /api/reports/{id}/share)
sharing_router = APIRouter(prefix="/api/reports", tags=["Sharing"])

# Completely separate public router — no shared code path with authenticated routes
public_router = APIRouter(prefix="/api/public", tags=["Public"])


# ── Response models ──────────────────────────────────────────────────────────

class ShareResponse(BaseModel):
    report_id: str
    share_token: str
    share_enabled: bool
    share_created_at: str
    share_url: str   # full URL the caller should expose


class UnshareResponse(BaseModel):
    report_id: str
    share_enabled: bool
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_report_json(report_id: str) -> tuple[ResearchReport, Path]:
    """Load a ResearchReport from its JSON file. Returns (report, path)."""
    safe_id = Path(report_id).name  # strip any path traversal
    json_path = OUTPUT_DIR / f"{safe_id}.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_id}' not found.",
        )
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        report = ResearchReport.model_validate(data)
        return report, json_path
    except Exception as exc:
        logger.error(f"Failed to load report {safe_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read report data.",
        )


def _save_report_json(report: ResearchReport, path: Path) -> None:
    """Persist updated report back to its JSON file."""
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def _build_share_url(token: str, base_url: str = "") -> str:
    """Build the public share URL for a given token.
    base_url is injected by the endpoint from the request if available.
    Frontend route is /shared/{token}.
    """
    if base_url:
        # Strip API path — keep only scheme+host
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    else:
        origin = "http://localhost:5173"   # dev default
    return f"{origin}/shared/{token}"


# ── POST /api/reports/{report_id}/share ──────────────────────────────────────

@sharing_router.post("/{report_id}/share", response_model=ShareResponse)
def share_report(report_id: str):
    """
    Enable sharing for a report.
    Generates a new share_token on first call; re-enables an existing token
    on subsequent calls (same URL is preserved after revoke+re-share).
    """
    report, json_path = _load_report_json(report_id)

    if not report.share_token:
        # First time sharing — generate a fresh token
        report = report.model_copy(update={
            "share_token": secrets.token_urlsafe(24),
            "share_created_at": datetime.now(timezone.utc).isoformat(),
        })

    report = report.model_copy(update={"share_enabled": True})
    _save_report_json(report, json_path)

    return ShareResponse(
        report_id=report_id,
        share_token=report.share_token,
        share_enabled=True,
        share_created_at=report.share_created_at,
        share_url=_build_share_url(report.share_token),
    )


# ── DELETE /api/reports/{report_id}/share ────────────────────────────────────

@sharing_router.delete("/{report_id}/share", response_model=UnshareResponse)
def unshare_report(report_id: str):
    """
    Revoke sharing for a report.
    Sets share_enabled=False immediately — the old token stops resolving.
    The token is kept so re-enabling returns the same URL.
    """
    report, json_path = _load_report_json(report_id)

    if not report.share_enabled:
        return UnshareResponse(
            report_id=report_id,
            share_enabled=False,
            message="Report was already not shared.",
        )

    report = report.model_copy(update={"share_enabled": False})
    _save_report_json(report, json_path)

    return UnshareResponse(
        report_id=report_id,
        share_enabled=False,
        message="Sharing revoked. The link is no longer accessible.",
    )


# ── GET /api/public/reports/{share_token} ────────────────────────────────────

@public_router.get(
    "/reports/{share_token}",
    response_model=PublicReportDTO,
    summary="View a shared report (no auth required)",
)
def get_public_report(share_token: str):
    """
    Public, read-only report view. Resolves a share_token to a report.

    This is a completely separate code path from the authenticated report
    endpoints — it only returns reports that are explicitly share_enabled,
    and it returns a scoped PublicReportDTO (never the full internal object).

    Returns 404 for invalid tokens and for valid-but-disabled tokens
    (we don't leak whether the token ever existed).
    """
    if not share_token or len(share_token) > 64:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    # Scan all JSON files to find the matching token.
    # At <1,000 reports this is fast; for larger scale use a token→id index.
    matched_report: Optional[ResearchReport] = None
    for json_path in OUTPUT_DIR.glob("*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            candidate = ResearchReport.model_validate(data)
            if (
                candidate.share_token == share_token
                and candidate.share_enabled
            ):
                matched_report = candidate
                break
        except Exception:
            continue   # corrupt/unrelated JSON — skip silently

    if not matched_report:
        # Return 404 for both "token not found" and "token exists but disabled"
        # to avoid leaking whether the token ever existed.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or sharing has been disabled.",
        )

    # Build the deliberately scoped public DTO
    return PublicReportDTO(
        topic=matched_report.topic,
        generated_at=matched_report.generated_at,
        key_takeaways=matched_report.key_takeaways,
        sections=matched_report.sections,
        sources=matched_report.sources,
        conflicting_information=matched_report.conflicting_information,
        confidence_note=matched_report.confidence_note,
    )
