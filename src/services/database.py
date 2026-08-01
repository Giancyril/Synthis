"""
DatabaseService — single SQLite database for Synthis.

Tables created on first use:
  annotations  — Feature 2: single-user personal notes on reports
  reports_fts  — Feature 3: FTS5 full-text search index over saved reports

All share_token/share_enabled fields live directly in the report JSON files
(Feature 1 doesn't need a separate table — the report JSON IS the source of truth).
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)

# Default database path — alongside the saved reports
_DEFAULT_DB_PATH = Path("output") / "synthis.db"


class DatabaseService:
    """Lightweight SQLite-backed persistence layer."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema initialisation (idempotent — safe to call on every startup)
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            # ── Annotations table ────────────────────────────────────────
            conn.execute("""
                CREATE TABLE IF NOT EXISTS annotations (
                    id          TEXT PRIMARY KEY,
                    report_id   TEXT NOT NULL,
                    target_type TEXT NOT NULL CHECK(target_type IN ('takeaway','section','source')),
                    target_id   TEXT NOT NULL,
                    author      TEXT,
                    body        TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    resolved    INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ann_report ON annotations(report_id);"
            )

            # ── FTS5 search index ────────────────────────────────────────
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
                    report_id UNINDEXED,
                    topic,
                    generated_at UNINDEXED,
                    key_takeaways_text,
                    sections_text,
                    source_titles,
                    tokenize='porter unicode61'
                )
            """)

        logger.info(f"DatabaseService ready at {self.db_path}")

    # ------------------------------------------------------------------
    # Annotation CRUD
    # ------------------------------------------------------------------

    def create_annotation(
        self,
        id: str,
        report_id: str,
        target_type: str,
        target_id: str,
        body: str,
        created_at: str,
        updated_at: str,
        author: Optional[str] = None,
        resolved: bool = False,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO annotations
                   (id, report_id, target_type, target_id, author, body,
                    created_at, updated_at, resolved)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (id, report_id, target_type, target_id, author, body,
                 created_at, updated_at, int(resolved)),
            )

    def list_annotations(self, report_id: str) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM annotations WHERE report_id = ? ORDER BY created_at ASC",
                (report_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_annotation(self, annotation_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_annotation(
        self,
        annotation_id: str,
        body: Optional[str],
        resolved: Optional[bool],
        author: Optional[str],
        updated_at: str,
    ) -> bool:
        """Returns True if a row was updated."""
        updates: list[str] = ["updated_at = ?"]
        params: list = [updated_at]

        if body is not None:
            updates.append("body = ?")
            params.append(body)
        if resolved is not None:
            updates.append("resolved = ?")
            params.append(int(resolved))
        if author is not None:
            updates.append("author = ?")
            params.append(author)

        params.append(annotation_id)
        sql = f"UPDATE annotations SET {', '.join(updates)} WHERE id = ?"

        with self._connect() as conn:
            cur = conn.execute(sql, params)
        return cur.rowcount > 0

    def delete_annotation(self, annotation_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM annotations WHERE id = ?", (annotation_id,)
            )
        return cur.rowcount > 0

    def count_unresolved_annotations(self, report_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM annotations WHERE report_id = ? AND resolved = 0",
                (report_id,),
            ).fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # FTS index operations
    # ------------------------------------------------------------------

    def upsert_report_index(
        self,
        report_id: str,
        topic: str,
        generated_at: str,
        key_takeaways_text: str,
        sections_text: str,
        source_titles: str,
    ) -> None:
        """Insert or replace a report's FTS index row."""
        with self._connect() as conn:
            # FTS5 doesn't support ON CONFLICT — delete first then insert
            conn.execute(
                "DELETE FROM reports_fts WHERE report_id = ?", (report_id,)
            )
            conn.execute(
                """INSERT INTO reports_fts
                   (report_id, topic, generated_at,
                    key_takeaways_text, sections_text, source_titles)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (report_id, topic, generated_at,
                 key_takeaways_text, sections_text, source_titles),
            )

    def search_reports(self, query: str, limit: int = 20) -> List[dict]:
        """
        Full-text search over reports_fts using FTS5 MATCH.
        Returns rows sorted by BM25 rank (most relevant first).
        Snippet is extracted from whichever indexed column matched.
        """
        if not query or not query.strip():
            return []

        # Sanitise: FTS5 MATCH syntax is sensitive to special chars
        safe_query = query.strip().replace('"', '""')

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT
                       report_id,
                       topic,
                       generated_at,
                       snippet(reports_fts, 3, '<mark>', '</mark>', '…', 20) AS snippet,
                       bm25(reports_fts) AS rank
                   FROM reports_fts
                   WHERE reports_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Module-level singleton — initialised lazily on first import
# ---------------------------------------------------------------------------

_db: Optional[DatabaseService] = None


def get_db() -> DatabaseService:
    global _db
    if _db is None:
        _db = DatabaseService()
    return _db
