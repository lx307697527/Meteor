"""HistoryRepo — SQLite CRUD for recognition history with search and app filtering."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voiceime.protocols import HistoryProvider, HistoryRecord
from voiceime.utils.paths import history_db_path

logger = logging.getLogger("voiceime.history.repository")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    raw_text TEXT,
    language TEXT,
    app_name TEXT,
    app_title TEXT,
    audio_duration_ms INTEGER,
    inference_time_ms INTEGER,
    is_polished INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_app ON history(app_name);
"""


class HistoryRepo:
    """SQLite-backed recognition history with search and integrity recovery."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or history_db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        # Check for corruption before first connection
        if self._path.exists() and self._path.stat().st_size > 0:
            corrupted = False
            try:
                test_conn = sqlite3.connect(str(self._path))
                result = test_conn.execute("PRAGMA integrity_check").fetchone()
                test_conn.close()
                if isinstance(result, tuple):
                    corrupted = result[0] != "ok"
                else:
                    corrupted = str(result) != "ok"
            except Exception:
                try:
                    test_conn.close()
                except Exception:
                    pass
                corrupted = True
            if corrupted:
                self._rebuild_before_connect()
        self._init_db()

    def _rebuild_before_connect(self) -> None:
        """Backup and remove corrupted database before any connection."""
        bak = self._path.with_suffix(".sqlite.bak")
        try:
            self._path.replace(bak)
            logger.info("Corrupted DB backed up to %s", bak)
        except OSError:
            try:
                self._path.unlink()
            except OSError:
                pass

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path), check_same_thread=False
            )
            self._conn.row_factory = _row_to_record
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    # ── CRUD ──────────────────────────────────────────────

    def save(self, record: HistoryRecord) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO history
               (created_at, text, raw_text, language, app_name, app_title,
                audio_duration_ms, inference_time_ms, is_polished)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.created_at or datetime.now(timezone.utc).isoformat(),
                record.text,
                record.raw_text,
                record.language,
                record.app_name,
                record.app_title,
                record.audio_duration_ms,
                record.inference_time_ms,
                1 if record.is_polished else 0,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get_by_id(self, record_id: int) -> HistoryRecord | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM history WHERE id = ?", (record_id,)
        ).fetchone()
        return row

    def search(
        self,
        query: str = "",
        app_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HistoryRecord]:
        conn = self._get_conn()
        clauses: list[str] = []
        params: list[Any] = []

        if query:
            clauses.append("text LIKE ?")
            params.append(f"%{query}%")
        if app_filter:
            clauses.append("app_name = ?")
            params.append(app_filter)

        where = " AND ".join(clauses)
        sql = f"SELECT * FROM history"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        return conn.execute(sql, params).fetchall()

    def delete(self, record_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
        conn.commit()
        return cursor.rowcount > 0

    def clear_all(self) -> int:
        conn = self._get_conn()
        raw_conn = self._get_raw_conn()
        count = raw_conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        conn.execute("DELETE FROM history")
        conn.commit()
        return count

    @property
    def total_count(self) -> int:
        raw_conn = self._get_raw_conn()
        return raw_conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    def _get_raw_conn(self) -> sqlite3.Connection:
        """Get connection without row_factory for aggregate queries."""
        conn = self._get_conn()
        conn.row_factory = None
        return conn

    # ── Integrity ─────────────────────────────────────────

    def check_integrity(self) -> bool:
        raw_conn = self._get_raw_conn()
        result = raw_conn.execute("PRAGMA integrity_check").fetchone()
        if isinstance(result, tuple):
            ok = result[0] == "ok"
        else:
            ok = str(result) == "ok"
        if not ok:
            logger.warning("SQLite integrity check failed, rebuilding")
            self._rebuild()
        # Restore row_factory
        self._get_conn().row_factory = _row_to_record
        return ok

    def _rebuild(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        bak = self._path.with_suffix(".sqlite.bak")
        try:
            self._path.replace(bak)
            logger.info("Corrupted DB backed up to %s", bak)
        except OSError:
            # If rename fails, just delete the corrupted file
            try:
                self._path.unlink()
            except OSError:
                pass
        self._init_db()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _row_to_record(cursor: sqlite3.Cursor, row: tuple) -> HistoryRecord:
    columns = [desc[0] for desc in cursor.description]
    values = dict(zip(columns, row))
    return HistoryRecord(
        id=values["id"],
        created_at=values["created_at"],
        text=values["text"],
        raw_text=values.get("raw_text"),
        language=values.get("language"),
        app_name=values.get("app_name"),
        app_title=values.get("app_title"),
        audio_duration_ms=values.get("audio_duration_ms"),
        inference_time_ms=values.get("inference_time_ms"),
        is_polished=bool(values.get("is_polished", 0)),
    )
