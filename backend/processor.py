"""
processor.py — Processes a Strava activity into a VO2max estimate.
Bridges the Strava API response and the vo2max estimation engine.
"""

import statistics
from typing import Optional
import vo2max as engine
import database as db
import strava
from config import (
    ATHLETE_HRMAX,
    ATHLETE_HR_REST,
    ATHLETE_WEIGHT_KG,
)


def _avg(lst: list) -> Optional[float]:
    if not lst:
        return None
    clean = [x for x in lst if x is not None and x > 0]
    return statistics.mean(clean) if clean else None


async def process_activity(activity_id: int) -> Optional[dict]:
    """
    Full pipeline for one activity:
      1. Fetch activity summary from Strava
      2. Fetch streams (HR, speed, power)
      3. Estimate VO2max
      4. Save to database
    Returns a summary dict or None if skipped.
    """
    # Skip if already processed
    if db.run_exists(activity_id):
        return None

    # 1. Fetch activity
    activity = await strava.get_activity(activity_id)

    sport = activity.get("sport_type", activity.get("type", ""))
    if sport not in ("Run", "TrailRun", "VirtualRun", "Treadmill"):
        return None

    distance_m = activity.get("distance", 0)
    duration_s = activity.get("moving_time", 0)

    if distance_m < 1000 or duration_s < 180:
        return None

    # 2. Fetch streams for better HR/power data
    streams = await strava.get_activity_streams(activity_id)

    # Use stream averages when available (more accurate than activity summary)
    hr_stream    = streams.get("heartrate", [])
    power_stream = streams.get("watts", [])

    avg_hr    = int(_avg(hr_stream))    if hr_stream    else activity.get("average_heartrate")
    max_hr    = max(hr_stream)          if hr_stream    else activity.get("max_heartrate")
    avg_power = _avg(power_stream)      if power_stream else activity.get("average_watts")

    avg_hr    = int(avg_hr)    if avg_hr    else None
    max_hr    = int(max_hr)    if max_hr    else None
    avg_power = float(avg_power) if avg_power else None

    avg_cadence  = activity.get("average_cadence")
    total_ascent = activity.get("total_elevation_gain")
    name         = activity.get("name", "Run")
    date         = activity.get("start_date_local", "")[:10]

    # 3. Classify + estimate
    run_type = engine.classify_run(distance_m, duration_s, avg_hr, ATHLETE_HRMAX)

    result = engine.estimate(
        distance_m  = distance_m,
        duration_s  = duration_s,
        avg_hr      = avg_hr,
        avg_power_w = avg_power,
        hrmax       = ATHLETE_HRMAX,
        hr_rest     = ATHLETE_HR_REST,
        weight_kg   = ATHLETE_WEIGHT_KG,
    )

    # 4. Save run
    row_id = db.upsert_run(
        strava_id    = activity_id,
        name         = name,
        date         = date,
        distance_m   = distance_m,
        duration_s   = duration_s,
        avg_hr       = avg_hr,
        max_hr       = max_hr,
        avg_power    = avg_power,
        avg_cadence  = avg_cadence,
        total_ascent = total_ascent,
        sport_type   = sport,
        vo2max_result = result,
        run_type     = run_type,
        raw_json     = activity,
    )

    # 5. Add to VO2max trend (only if we got a real estimate)
    if result.vo2max > 0 and result.confidence != "none":
        db.insert_vo2max_history(
            date       = date,
            vo2max     = result.vo2max,
            confidence = result.confidence,
            run_id     = row_id,
        )

    return {
        "activity_id": activity_id,
        "name":        name,
        "date":        date,
        "distance_km": round(distance_m / 1000, 2),
        "vo2max":      result.vo2max,
        "method":      result.method,
        "confidence":  result.confidence,
        "run_type":    run_type,
    }
