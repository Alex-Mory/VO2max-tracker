"""
database.py — PostgreSQL database for storing runs and VO2max estimates.
"""

import psycopg2
import psycopg2.extras
import json
import os
from typing import Optional


# Railway provides this automatically
DATABASE_URL = os.environ["DATABASE_URL"]


def get_conn():
    """
    Return a new PostgreSQL connection.
    """
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# ---------------------------------------------------------------------
# RUNS
# ---------------------------------------------------------------------

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
    """
    Insert or update a run. Returns the run id.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO runs (
            strava_id, name, date, distance_m, duration_s,
            avg_hr, max_hr, avg_power, avg_cadence, total_ascent,
            sport_type,
            vo2max, vdot, vo2max_power, vo2max_hr, pct_vo2max,
            method, confidence, run_type, notes,
            raw_json
        )
        VALUES (
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s
        )
        ON CONFLICT (strava_id) DO UPDATE SET
            vo2max        = EXCLUDED.vo2max,
            vdot          = EXCLUDED.vdot,
            vo2max_power  = EXCLUDED.vo2max_power,
            vo2max_hr     = EXCLUDED.vo2max_hr,
            pct_vo2max    = EXCLUDED.pct_vo2max,
            method        = EXCLUDED.method,
            confidence    = EXCLUDED.confidence,
            run_type      = EXCLUDED.run_type,
            notes         = EXCLUDED.notes
        RETURNING id
        """,
        (
            strava_id,
            name,
            date,
            distance_m,
            duration_s,
            avg_hr,
            max_hr,
            avg_power,
            avg_cadence,
            total_ascent,
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
        ),
    )

    run_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return run_id


def run_exists(strava_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM runs WHERE strava_id = %s",
        (strava_id,),
    )
    exists = cur.fetchone() is not None

    conn.close()
    return exists


def get_all_runs(limit: int = 500) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM runs
        WHERE vo2max IS NOT NULL
        ORDER BY date DESC
        LIMIT %s
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------
# VO2MAX HISTORY
# ---------------------------------------------------------------------

def insert_vo2max_history(
    date: str,
    vo2max: float,
    confidence: str,
    run_id: int,
):
    """
    Insert VO2max datapoint and compute rolling average.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT vo2max
        FROM vo2max_history
        WHERE confidence IN ('high', 'medium')
        ORDER BY date DESC
        LIMIT 8
        """
    )

    recent = [r["vo2max"] for r in cur.fetchall()]
    recent.insert(0, vo2max)
    smoothed = round(sum(recent[:8]) / len(recent[:8]), 1)

    cur.execute(
        """
        INSERT INTO vo2max_history (
            date, vo2max, smoothed, confidence, run_id
        )
        VALUES (%s,%s,%s,%s,%s)
        """,
        (date, vo2max, smoothed, confidence, run_id),
    )

    conn.commit()
    conn.close()


def get_vo2max_history() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            h.*,
            r.name,
            r.distance_m,
            r.run_type
        FROM vo2max_history h
        LEFT JOIN runs r ON r.id = h.run_id
        ORDER BY h.date ASC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_latest_vo2max() -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            h.smoothed,
            h.vo2max,
            h.date,
            r.name
        FROM vo2max_history h
        LEFT JOIN runs r ON r.id = h.run_id
        ORDER BY h.date DESC
        LIMIT 1
        """
    )

    row = cur.fetchone()
    conn.close()
    return row
