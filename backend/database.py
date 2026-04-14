"""
database.py — SQLite database for storing runs and VO2max estimates.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional
from config import DATABASE_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            strava_id       INTEGER UNIQUE NOT NULL,
            name            TEXT,
            date            TEXT NOT NULL,       -- ISO date string
            distance_m      REAL NOT NULL,
            duration_s      REAL NOT NULL,
            avg_hr          INTEGER,
            max_hr          INTEGER,
            avg_power       REAL,
            avg_cadence     INTEGER,
            total_ascent    REAL,
            sport_type      TEXT DEFAULT 'Run',
            -- VO2max results
            vo2max          REAL,
            vdot            REAL,
            vo2max_power    REAL,
            vo2max_hr       REAL,
            pct_vo2max      REAL,
            method          TEXT,
            confidence      TEXT,
            run_type        TEXT,
            notes           TEXT,
            -- raw
            raw_json        TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_runs_date ON runs(date);
        CREATE INDEX IF NOT EXISTS idx_runs_strava ON runs(strava_id);

        CREATE TABLE IF NOT EXISTS vo2max_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            vo2max      REAL NOT NULL,
            smoothed    REAL,           -- 4-week rolling average
            confidence  TEXT,
            run_id      INTEGER REFERENCES runs(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_vo2max_date ON vo2max_history(date);
    """)
    conn.commit()
    conn.close()


def upsert_run(
    strava_id: int,
    name: str,
    date: str,
    distance_m: float,
    duration_s: float,
    avg_hr: Optional[int],
    max_hr: Optional[int],
    avg_power: Optional[float],
    avg_cadence: Optional[int],
    total_ascent: Optional[float],
    sport_type: str,
    vo2max_result,
    run_type: str,
    raw_json: dict,
) -> int:
    """Insert or replace a run. Returns the row id."""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO runs (
            strava_id, name, date, distance_m, duration_s,
            avg_hr, max_hr, avg_power, avg_cadence, total_ascent,
            sport_type,
            vo2max, vdot, vo2max_power, vo2max_hr, pct_vo2max,
            method, confidence, run_type, notes,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(strava_id) DO UPDATE SET
            vo2max      = excluded.vo2max,
            vdot        = excluded.vdot,
            vo2max_power = excluded.vo2max_power,
            vo2max_hr   = excluded.vo2max_hr,
            pct_vo2max  = excluded.pct_vo2max,
            method      = excluded.method,
            confidence  = excluded.confidence,
            run_type    = excluded.run_type,
            notes       = excluded.notes
    """, (
        strava_id, name, date, distance_m, duration_s,
        avg_hr, max_hr, avg_power, avg_cadence, total_ascent,
        sport_type,
        vo2max_result.vo2max if vo2max_result else None,
        vo2max_result.vdot if vo2max_result else None,
        vo2max_result.vo2max_power if vo2max_result else None,
        vo2max_result.vo2max_hr if vo2max_result else None,
        vo2max_result.pct_vo2max if vo2max_result else None,
        vo2max_result.method if vo2max_result else None,
        vo2max_result.confidence if vo2max_result else None,
        run_type,
        vo2max_result.notes if vo2max_result else None,
        json.dumps(raw_json),
    ))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_vo2max_history(date: str, vo2max: float, confidence: str, run_id: int):
    """Add a VO2max data point and update rolling average."""
    conn = get_conn()

    # Get last 4 weeks of high/medium confidence points for smoothing
    rows = conn.execute("""
        SELECT vo2max FROM vo2max_history
        WHERE confidence IN ('high', 'medium')
        ORDER BY date DESC LIMIT 8
    """).fetchall()

    recent = [r["vo2max"] for r in rows]
    recent.insert(0, vo2max)
    smoothed = round(sum(recent[:8]) / len(recent[:8]), 1)

    conn.execute("""
        INSERT INTO vo2max_history (date, vo2max, smoothed, confidence, run_id)
        VALUES (?, ?, ?, ?, ?)
    """, (date, vo2max, smoothed, confidence, run_id))
    conn.commit()
    conn.close()


def get_all_runs(limit: int = 500) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM runs
        WHERE vo2max IS NOT NULL
        ORDER BY date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vo2max_history() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT h.*, r.name, r.distance_m, r.run_type
        FROM vo2max_history h
        LEFT JOIN runs r ON r.id = h.run_id
        ORDER BY h.date ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run_exists(strava_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM runs WHERE strava_id = ?", (strava_id,)
    ).fetchone()
    conn.close()
    return row is not None


def get_latest_vo2max() -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("""
        SELECT h.smoothed, h.vo2max, h.date, r.name
        FROM vo2max_history h
        LEFT JOIN runs r ON r.id = h.run_id
        ORDER BY h.date DESC LIMIT 1
    """).fetchone()
    conn.close()
    return dict(row) if row else None
