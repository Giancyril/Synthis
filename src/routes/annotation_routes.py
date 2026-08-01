"""
Annotation routes — Feature 2: Personal Notes on Report Sections/Takeaways

Endpoints (all authenticated — never exposed on the public shared view):
  POST   /api/reports/{report_id}/annotations
  GET    /api/reports/{report_id}/annotations
  PATCH  /api/annotations/{id}
  DELETE /api/annotations/{id}

Design notes:
  - Single-user; no auth/identity system required.
  - target_type: "takeaway" | "section" | "source"
  - target_id: index string ("0","1") for takeaways/sections, source id ("S1") for sources.
  - Annotations are stored in SQLite (output/synthis.db) — not in the report JSON.
  - Annotations are NEVER included in PublicReportDTO.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from src.models.schemas import Annotation, AnnotationPatch
from src.services.database import get_db

logger = logging.getLogger(__name__)

VALID_TARGET_TYPES = {"takeaway", "section", "source"}

annotation_router = APIRouter(tags=["Annotations"])


# ── Request body ─────────────────────────────────────────────────────────────

class CreateAnnotationRequest(BaseModel):
    target_type: str   # "takeaway" | "section" | "source"
    target_id: str     # "0", "1", ... or "S1", "S2", ...
    body: str
    author: Optional[str] = None


# ── POST /api/reports/{report_id}/annotations ────────────────────────────────

@annotation_router.post(
    "/api/reports/{report_id}/annotations",
    response_model=Annotation,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(report_id: str, req: CreateAnnotationRequest):
    if req.target_type not in VALID_TARGET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"target_type must be one of: {', '.join(sorted(VALID_TARGET_TYPES))}",
        )
    if not req.body or not req.body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Annotation body cannot be empty.",
        )

    annotation_id = f"ann_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    get_db().create_annotation(
        id=annotation_id,
        report_id=report_id,
        target_type=req.target_type,
        target_id=req.target_id,
        body=req.body.strip(),
        created_at=now,
        updated_at=now,
        author=req.author,
        resolved=False,
    )

    return Annotation(
        id=annotation_id,
        report_id=report_id,
        target_type=req.target_type,
        target_id=req.target_id,
        body=req.body.strip(),
        created_at=now,
        updated_at=now,
        author=req.author,
        resolved=False,
    )


# ── GET /api/reports/{report_id}/annotations ─────────────────────────────────

@annotation_router.get(
    "/api/reports/{report_id}/annotations",
    response_model=List[Annotation],
)
def list_annotations(report_id: str):
    rows = get_db().list_annotations(report_id)
    return [
        Annotation(
            id=r["id"],
            report_id=r["report_id"],
            target_type=r["target_type"],
            target_id=r["target_id"],
            author=r["author"],
            body=r["body"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            resolved=bool(r["resolved"]),
        )
        for r in rows
    ]


# ── PATCH /api/annotations/{id} ──────────────────────────────────────────────

@annotation_router.patch(
    "/api/annotations/{annotation_id}",
    response_model=Annotation,
)
def update_annotation(annotation_id: str, req: AnnotationPatch):
    if req.body is not None and not req.body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Annotation body cannot be empty.",
        )

    now = datetime.now(timezone.utc).isoformat()
    updated = get_db().update_annotation(
        annotation_id=annotation_id,
        body=req.body.strip() if req.body is not None else None,
        resolved=req.resolved,
        author=req.author,
        updated_at=now,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found.",
        )

    row = get_db().get_annotation(annotation_id)
    return Annotation(
        id=row["id"],
        report_id=row["report_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        author=row["author"],
        body=row["body"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved=bool(row["resolved"]),
    )


# ── DELETE /api/annotations/{id} ─────────────────────────────────────────────

@annotation_router.delete(
    "/api/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_annotation(annotation_id: str):
    deleted = get_db().delete_annotation(annotation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found.",
        )
