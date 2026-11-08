from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterable, List, Optional

from poem_reciter.models import EvaluationResult, Poem
from poem_reciter.repository import extract_poem_chars

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS poems (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    file_order               INTEGER NOT NULL,
    header                   TEXT NOT NULL UNIQUE,
    title                    TEXT NOT NULL,
    dynasty                  TEXT NOT NULL DEFAULT '现代',
    author                   TEXT NOT NULL,
    text                     TEXT NOT NULL,
    char_count               INTEGER NOT NULL,
    attempt_count            INTEGER NOT NULL DEFAULT 0,
    perfect_count            INTEGER NOT NULL DEFAULT 0,
    cumulative_total_chars   INTEGER NOT NULL DEFAULT 0,
    cumulative_correct_chars INTEGER NOT NULL DEFAULT 0,
    cumulative_wrong_chars   INTEGER NOT NULL DEFAULT 0,
    cumulative_extra_chars   INTEGER NOT NULL DEFAULT 0,
    char_accuracy            REAL,
    avg_accuracy             REAL,
    last_attempted_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_poems_author ON poems(author);
CREATE INDEX IF NOT EXISTS idx_poems_dynasty ON poems(dynasty);
CREATE INDEX IF NOT EXISTS idx_poems_file_order ON poems(file_order);

CREATE TABLE IF NOT EXISTS recitation_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    poem_id         INTEGER NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    submitted_text  TEXT NOT NULL,
    total_chars     INTEGER NOT NULL,
    correct_chars   INTEGER NOT NULL,
    wrong_chars     INTEGER NOT NULL,
    extra_chars     INTEGER NOT NULL DEFAULT 0,
    accuracy        REAL NOT NULL,
    is_perfect      INTEGER NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_poem_id ON recitation_attempts(poem_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON recitation_attempts(created_at);
"""


class StatsStore:
    """SQLite-backed store for poem metadata and recitation attempt statistics."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._memory_conn: Optional[sqlite3.Connection] = None

        if not self._is_memory:
            path_obj = Path(self.db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.execute("PRAGMA foreign_keys = ON;")
            return self._memory_conn

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _close_if_file(self, conn: sqlite3.Connection) -> None:
        if not self._is_memory:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.executescript(_SCHEMA_SQL)
        finally:
            self._close_if_file(conn)

    def sync_poems(self, poems: Iterable[Poem]) -> None:
        """Upsert poems from the repository into the SQLite poems table."""
        conn = self._connect()
        try:
            with conn:
                for poem in poems:
                    char_count = len(extract_poem_chars(poem.text))
                    dynasty = poem.dynasty or "现代"
                    conn.execute(
                        """
                        INSERT INTO poems (file_order, header, title, dynasty, author, text, char_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(header) DO UPDATE SET
                            file_order = excluded.file_order,
                            title      = excluded.title,
                            dynasty    = excluded.dynasty,
                            author     = excluded.author,
                            text       = excluded.text,
                            char_count = excluded.char_count
                        """,
                        (
                            poem.id,
                            poem.header,
                            poem.title,
                            dynasty,
                            poem.author,
                            poem.text,
                            char_count,
                        ),
                    )
        finally:
            self._close_if_file(conn)

    def record_attempt(self, result: EvaluationResult) -> dict:
        """Persist a recitation attempt and update rolling poem statistics (both Metric A and Metric B)."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT id FROM poems WHERE header = ?",
                    (result.header,),
                ).fetchone()
                if row is None:
                    raise KeyError(f"Poem with header '{result.header}' not found in database.")
                db_poem_id = row["id"]

                conn.execute(
                    """
                    INSERT INTO recitation_attempts (
                        poem_id, submitted_text, total_chars, correct_chars,
                        wrong_chars, extra_chars, accuracy, is_perfect, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        db_poem_id,
                        result.submitted_text,
                        result.total_chars,
                        result.correct_chars,
                        result.wrong_chars,
                        result.extra_chars,
                        result.accuracy,
                        1 if result.is_correct else 0,
                        now_iso,
                    ),
                )

                agg = conn.execute(
                    """
                    SELECT
                        COUNT(id) AS attempt_count,
                        COALESCE(SUM(is_perfect), 0) AS perfect_count,
                        COALESCE(SUM(total_chars), 0) AS cumulative_total_chars,
                        COALESCE(SUM(correct_chars), 0) AS cumulative_correct_chars,
                        COALESCE(SUM(wrong_chars), 0) AS cumulative_wrong_chars,
                        COALESCE(SUM(extra_chars), 0) AS cumulative_extra_chars,
                        CASE
                            WHEN SUM(total_chars) > 0
                            THEN SUM(correct_chars) * 1.0 / SUM(total_chars)
                            ELSE NULL
                        END AS char_accuracy,
                        AVG(accuracy) AS avg_accuracy,
                        MAX(created_at) AS last_attempted_at
                    FROM recitation_attempts
                    WHERE poem_id = ?
                    """,
                    (db_poem_id,),
                ).fetchone()

                conn.execute(
                    """
                    UPDATE poems SET
                        attempt_count            = ?,
                        perfect_count            = ?,
                        cumulative_total_chars   = ?,
                        cumulative_correct_chars = ?,
                        cumulative_wrong_chars   = ?,
                        cumulative_extra_chars   = ?,
                        char_accuracy            = ?,
                        avg_accuracy             = ?,
                        last_attempted_at        = ?
                    WHERE id = ?
                    """,
                    (
                        agg["attempt_count"],
                        agg["perfect_count"],
                        agg["cumulative_total_chars"],
                        agg["cumulative_correct_chars"],
                        agg["cumulative_wrong_chars"],
                        agg["cumulative_extra_chars"],
                        agg["char_accuracy"],
                        agg["avg_accuracy"],
                        agg["last_attempted_at"],
                        db_poem_id,
                    ),
                )

                updated = conn.execute(
                    "SELECT * FROM poems WHERE id = ?",
                    (db_poem_id,),
                ).fetchone()
                return self._format_poem_row(updated)
        finally:
            self._close_if_file(conn)

    def get_poem_stats(self, header: str) -> Optional[dict]:
        """Return rolling stats for a single poem by header."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM poems WHERE header = ?",
                (header,),
            ).fetchone()
            return self._format_poem_row(row) if row is not None else None
        finally:
            self._close_if_file(conn)

    def get_aggregated_stats(
        self,
        group_by: str = "poem",
        recited_only: bool = False,
    ) -> dict:
        """Query aggregated statistics across poems, authors, or dynasties."""
        if group_by not in ("poem", "author", "dynasty"):
            raise ValueError(f"Unsupported group_by dimension: {group_by}")

        conn = self._connect()
        try:
            summary_row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM poems) AS total_poems,
                    (SELECT COUNT(*) FROM poems WHERE attempt_count > 0) AS recited_poems,
                    COUNT(a.id) AS attempt_count,
                    COALESCE(SUM(a.is_perfect), 0) AS perfect_count,
                    COALESCE(SUM(a.total_chars), 0) AS total_chars,
                    COALESCE(SUM(a.correct_chars), 0) AS correct_chars,
                    COALESCE(SUM(a.wrong_chars), 0) AS wrong_chars,
                    COALESCE(SUM(a.extra_chars), 0) AS extra_chars,
                    CASE
                        WHEN SUM(a.total_chars) > 0
                        THEN SUM(a.correct_chars) * 1.0 / SUM(a.total_chars)
                        ELSE NULL
                    END AS char_accuracy,
                    AVG(a.accuracy) AS avg_accuracy
                FROM recitation_attempts a
                """
            ).fetchone()

            summary = {
                "total_poems": summary_row["total_poems"],
                "recited_poems": summary_row["recited_poems"],
                "attempt_count": summary_row["attempt_count"],
                "perfect_count": summary_row["perfect_count"],
                "total_chars": summary_row["total_chars"],
                "correct_chars": summary_row["correct_chars"],
                "wrong_chars": summary_row["wrong_chars"],
                "extra_chars": summary_row["extra_chars"],
                "char_accuracy": (
                    round(summary_row["char_accuracy"], 4)
                    if summary_row["char_accuracy"] is not None
                    else None
                ),
                "avg_accuracy": (
                    round(summary_row["avg_accuracy"], 4)
                    if summary_row["avg_accuracy"] is not None
                    else None
                ),
            }

            if group_by == "poem":
                where_clause = "WHERE attempt_count > 0" if recited_only else ""
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM poems
                    {where_clause}
                    ORDER BY (attempt_count > 0) DESC, file_order ASC
                    """
                ).fetchall()
                items = [self._format_poem_row(r) for r in rows]
            elif group_by == "author":
                having_clause = "HAVING COUNT(a.id) > 0" if recited_only else ""
                rows = conn.execute(
                    f"""
                    SELECT
                        p.author AS key,
                        p.dynasty AS dynasty,
                        COUNT(DISTINCT p.id) AS total_poems,
                        COUNT(DISTINCT a.poem_id) AS recited_poems,
                        COUNT(a.id) AS attempt_count,
                        COALESCE(SUM(a.is_perfect), 0) AS perfect_count,
                        COALESCE(SUM(a.total_chars), 0) AS total_chars,
                        COALESCE(SUM(a.correct_chars), 0) AS correct_chars,
                        COALESCE(SUM(a.wrong_chars), 0) AS wrong_chars,
                        COALESCE(SUM(a.extra_chars), 0) AS extra_chars,
                        CASE
                            WHEN SUM(a.total_chars) > 0
                            THEN SUM(a.correct_chars) * 1.0 / SUM(a.total_chars)
                            ELSE NULL
                        END AS char_accuracy,
                        AVG(a.accuracy) AS avg_accuracy,
                        MAX(a.created_at) AS last_attempted_at
                    FROM poems p
                    LEFT JOIN recitation_attempts a ON p.id = a.poem_id
                    GROUP BY p.author
                    {having_clause}
                    ORDER BY (COUNT(a.id) > 0) DESC, COUNT(a.id) DESC, COUNT(DISTINCT p.id) DESC, MIN(p.file_order) ASC
                    """
                ).fetchall()
                items = [self._format_group_row(r, include_dynasty=True) for r in rows]
            else:  # group_by == "dynasty"
                having_clause = "HAVING COUNT(a.id) > 0" if recited_only else ""
                rows = conn.execute(
                    f"""
                    SELECT
                        p.dynasty AS key,
                        COUNT(DISTINCT p.id) AS total_poems,
                        COUNT(DISTINCT a.poem_id) AS recited_poems,
                        COUNT(a.id) AS attempt_count,
                        COALESCE(SUM(a.is_perfect), 0) AS perfect_count,
                        COALESCE(SUM(a.total_chars), 0) AS total_chars,
                        COALESCE(SUM(a.correct_chars), 0) AS correct_chars,
                        COALESCE(SUM(a.wrong_chars), 0) AS wrong_chars,
                        COALESCE(SUM(a.extra_chars), 0) AS extra_chars,
                        CASE
                            WHEN SUM(a.total_chars) > 0
                            THEN SUM(a.correct_chars) * 1.0 / SUM(a.total_chars)
                            ELSE NULL
                        END AS char_accuracy,
                        AVG(a.accuracy) AS avg_accuracy,
                        MAX(a.created_at) AS last_attempted_at
                    FROM poems p
                    LEFT JOIN recitation_attempts a ON p.id = a.poem_id
                    GROUP BY p.dynasty
                    {having_clause}
                    ORDER BY (COUNT(a.id) > 0) DESC, COUNT(a.id) DESC, COUNT(DISTINCT p.id) DESC, MIN(p.file_order) ASC
                    """
                ).fetchall()
                items = [self._format_group_row(r, include_dynasty=False) for r in rows]

            return {
                "group_by": group_by,
                "recited_only": recited_only,
                "summary": summary,
                "items": items,
            }
        finally:
            self._close_if_file(conn)

    @staticmethod
    def _format_poem_row(row: sqlite3.Row) -> dict:
        return {
            "poem_id": row["file_order"],
            "header": row["header"],
            "title": row["title"],
            "dynasty": row["dynasty"],
            "author": row["author"],
            "char_count": row["char_count"],
            "attempt_count": row["attempt_count"],
            "perfect_count": row["perfect_count"],
            "total_chars": row["cumulative_total_chars"],
            "correct_chars": row["cumulative_correct_chars"],
            "wrong_chars": row["cumulative_wrong_chars"],
            "extra_chars": row["cumulative_extra_chars"],
            "char_accuracy": (
                round(row["char_accuracy"], 4) if row["char_accuracy"] is not None else None
            ),
            "avg_accuracy": (
                round(row["avg_accuracy"], 4) if row["avg_accuracy"] is not None else None
            ),
            "last_attempted_at": row["last_attempted_at"],
        }

    @staticmethod
    def _format_group_row(row: sqlite3.Row, include_dynasty: bool = False) -> dict:
        item = {
            "key": row["key"],
            "total_poems": row["total_poems"],
            "recited_poems": row["recited_poems"],
            "attempt_count": row["attempt_count"],
            "perfect_count": row["perfect_count"],
            "total_chars": row["total_chars"],
            "correct_chars": row["correct_chars"],
            "wrong_chars": row["wrong_chars"],
            "extra_chars": row["extra_chars"],
            "char_accuracy": (
                round(row["char_accuracy"], 4) if row["char_accuracy"] is not None else None
            ),
            "avg_accuracy": (
                round(row["avg_accuracy"], 4) if row["avg_accuracy"] is not None else None
            ),
            "last_attempted_at": row["last_attempted_at"],
        }
        if include_dynasty:
            item["dynasty"] = row["dynasty"]
        return item
