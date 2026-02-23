# =============================================================================
# SmartApply — SQLite Database Module
# =============================================================================
# Persistent storage for job applications, user profiles, agent sessions,
# and memory. All data stored in a single SQLite file inside app/db/.
# =============================================================================

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = os.getenv("SQLITE_DB_PATH", str(Path(__file__).parent / "smartapply.db"))


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize the database schema. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            -- User profile / identity for applications
            CREATE TABLE IF NOT EXISTS user_profile (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT    NOT NULL UNIQUE,
                value       TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            -- Internship job listings discovered by the agent
            CREATE TABLE IF NOT EXISTS jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id     TEXT    UNIQUE,
                title           TEXT    NOT NULL,
                company         TEXT    NOT NULL,
                url             TEXT    NOT NULL,
                location        TEXT,
                description     TEXT,
                source          TEXT,
                date_posted     TEXT,
                date_discovered TEXT    NOT NULL DEFAULT (datetime('now')),
                status          TEXT    NOT NULL DEFAULT 'discovered'
                                CHECK(status IN (
                                    'discovered', 'queued', 'applying',
                                    'applied', 'failed', 'skipped', 'interview'
                                )),
                metadata_json   TEXT
            );

            -- Application attempts (one job can have multiple attempts)
            CREATE TABLE IF NOT EXISTS applications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          INTEGER NOT NULL REFERENCES jobs(id),
                session_id      TEXT,
                started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                completed_at    TEXT,
                status          TEXT    NOT NULL DEFAULT 'in_progress'
                                CHECK(status IN (
                                    'in_progress', 'success', 'partial',
                                    'failed', 'error'
                                )),
                steps_json      TEXT,
                error_message   TEXT,
                screenshot_b64  TEXT
            );

            -- Agent session log (tracks each OpenClaw agent invocation)
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT    NOT NULL UNIQUE,
                task_type       TEXT    NOT NULL,
                prompt          TEXT    NOT NULL,
                started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                completed_at    TEXT,
                status          TEXT    NOT NULL DEFAULT 'running'
                                CHECK(status IN (
                                    'running', 'completed', 'failed', 'timeout'
                                )),
                result_text     TEXT,
                tokens_used     INTEGER,
                model_used      TEXT,
                error_message   TEXT
            );

            -- Agent memory: facts the agent has learned across sessions
            CREATE TABLE IF NOT EXISTS memory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL,
                key         TEXT    NOT NULL,
                value       TEXT    NOT NULL,
                confidence  REAL    DEFAULT 1.0,
                source      TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(category, key)
            );

            -- Indexes for fast lookups
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
            CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
            CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
            CREATE INDEX IF NOT EXISTS idx_agent_sessions_type ON agent_sessions(task_type);
            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category);
        """)
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# User Profile Operations
# =============================================================================

def set_profile(key: str, value: str, db_path: str = DB_PATH) -> None:
    """Set a user profile field (upsert)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO user_profile (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_profile(key: str, db_path: str = DB_PATH) -> Optional[str]:
    """Get a user profile field."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT value FROM user_profile WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def get_all_profile(db_path: str = DB_PATH) -> dict:
    """Get all profile fields as a dict."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


# =============================================================================
# Job Operations
# =============================================================================

def add_job(
    title: str, company: str, url: str,
    location: str = None, description: str = None,
    source: str = None, date_posted: str = None,
    external_id: str = None, metadata: dict = None,
    db_path: str = DB_PATH,
) -> int:
    """Add a discovered job listing. Returns the job id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO jobs
               (external_id, title, company, url, location, description, source, date_posted, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (external_id, title, company, url, location, description,
             source, date_posted, json.dumps(metadata) if metadata else None),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_jobs(status: str = None, limit: int = 50, db_path: str = DB_PATH) -> list[dict]:
    """Get jobs, optionally filtered by status."""
    conn = get_connection(db_path)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY date_discovered DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY date_discovered DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_job_status(job_id: int, status: str, db_path: str = DB_PATH) -> None:
    """Update the status of a job."""
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# Application Operations
# =============================================================================

def create_application(job_id: int, session_id: str = None, db_path: str = DB_PATH) -> int:
    """Start tracking an application attempt. Returns the application id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO applications (job_id, session_id) VALUES (?, ?)",
            (job_id, session_id),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_application(
    app_id: int, status: str,
    steps: list = None, error: str = None,
    screenshot: str = None, db_path: str = DB_PATH,
) -> None:
    """Update an application record."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """UPDATE applications
               SET status=?, completed_at=datetime('now'),
                   steps_json=?, error_message=?, screenshot_b64=?
               WHERE id=?""",
            (status, json.dumps(steps) if steps else None, error, screenshot, app_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_applications(status: str = None, limit: int = 50, db_path: str = DB_PATH) -> list[dict]:
    """Get applications with joined job info."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT a.*, j.title, j.company, j.url AS job_url
            FROM applications a JOIN jobs j ON a.job_id = j.id
        """
        if status:
            query += " WHERE a.status=?"
            query += " ORDER BY a.started_at DESC LIMIT ?"
            rows = conn.execute(query, (status, limit)).fetchall()
        else:
            query += " ORDER BY a.started_at DESC LIMIT ?"
            rows = conn.execute(query, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =============================================================================
# Agent Session Operations
# =============================================================================

def log_session_start(
    session_id: str, task_type: str, prompt: str,
    db_path: str = DB_PATH,
) -> None:
    """Log the start of an agent session."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO agent_sessions (session_id, task_type, prompt)
               VALUES (?, ?, ?)""",
            (session_id, task_type, prompt),
        )
        conn.commit()
    finally:
        conn.close()


def log_session_end(
    session_id: str, status: str,
    result_text: str = None, tokens_used: int = None,
    model_used: str = None, error: str = None,
    db_path: str = DB_PATH,
) -> None:
    """Log the completion of an agent session."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """UPDATE agent_sessions
               SET status=?, completed_at=datetime('now'),
                   result_text=?, tokens_used=?, model_used=?, error_message=?
               WHERE session_id=?""",
            (status, result_text, tokens_used, model_used, error, session_id),
        )
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# Memory Operations (cross-session agent knowledge)
# =============================================================================

def remember(category: str, key: str, value: str,
             confidence: float = 1.0, source: str = None,
             db_path: str = DB_PATH) -> None:
    """Store a fact in agent memory (upsert)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO memory (category, key, value, confidence, source, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(category, key) DO UPDATE SET
                   value=excluded.value, confidence=excluded.confidence,
                   source=excluded.source, updated_at=excluded.updated_at""",
            (category, key, value, confidence, source),
        )
        conn.commit()
    finally:
        conn.close()


def recall(category: str = None, key: str = None, db_path: str = DB_PATH) -> list[dict]:
    """Recall facts from agent memory."""
    conn = get_connection(db_path)
    try:
        if category and key:
            rows = conn.execute(
                "SELECT * FROM memory WHERE category=? AND key=?", (category, key)
            ).fetchall()
        elif category:
            rows = conn.execute(
                "SELECT * FROM memory WHERE category=?", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memory ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def recall_as_context(categories: list[str] = None, db_path: str = DB_PATH) -> str:
    """Format agent memory as context text for prompts."""
    conn = get_connection(db_path)
    try:
        if categories:
            placeholders = ",".join("?" * len(categories))
            rows = conn.execute(
                f"SELECT category, key, value FROM memory WHERE category IN ({placeholders}) "
                "ORDER BY category, key",
                categories,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category, key, value FROM memory ORDER BY category, key"
            ).fetchall()

        if not rows:
            return ""

        lines = []
        current_cat = None
        for r in rows:
            if r["category"] != current_cat:
                current_cat = r["category"]
                lines.append(f"\n## {current_cat}")
            lines.append(f"- {r['key']}: {r['value']}")
        return "\n".join(lines)
    finally:
        conn.close()


# =============================================================================
# Stats / Dashboard
# =============================================================================

def get_stats(db_path: str = DB_PATH) -> dict:
    """Get summary statistics."""
    conn = get_connection(db_path)
    try:
        jobs = dict(conn.execute(
            "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
        ).fetchall() or [])
        apps = dict(conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall() or [])
        sessions = conn.execute(
            "SELECT COUNT(*) as total FROM agent_sessions"
        ).fetchone()
        memories = conn.execute(
            "SELECT COUNT(*) as total FROM memory"
        ).fetchone()
        return {
            "jobs": {r["status"]: r["cnt"] for r in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
            ).fetchall()},
            "applications": {r["status"]: r["cnt"] for r in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
            ).fetchall()},
            "total_sessions": sessions["total"] if sessions else 0,
            "total_memories": memories["total"] if memories else 0,
        }
    finally:
        conn.close()
