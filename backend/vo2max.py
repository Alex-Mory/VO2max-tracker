"""
vo2max.py — VO2max estimation engine.

Three methods, automatically selected based on available data:
  1. Jack Daniels VDOT  — uses distance + time (most reliable for races)
  2. Power-based        — uses avg running power + body weight
  3. HR-adjusted VDOT   — uses VDOT corrected with HR/HRmax fraction (Swain 1994)

"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class VO2maxResult:
    vo2max: float               # Final estimate (ml/kg/min)
    method: str                 # Which method(s) used
    vdot: Optional[float]       # Jack Daniels VDOT
    vo2max_power: Optional[float]  # Power-based estimate
    vo2max_hr: Optional[float]  # HR-adjusted estimate
    pct_vo2max: float           # % VO2max this effort represented
    confidence: str             # "high" / "medium" / "low"
    notes: str                  # Human-readable explanation


def _pct_vo2max_at_duration(duration_min: float) -> float:
    """
    Jack Daniels %VO2max fraction for a given race duration.
    From: Daniels & Gilbert (1979) formula.
    """
    return (
        0.8
        + 0.1894393 * math.exp(-0.012778 * duration_min)
        + 0.2989558 * math.exp(-0.1932605 * duration_min)
    )


def _vo2_at_pace(speed_m_per_min: float) -> float:
    """
    VO2 cost at a given pace (ml/kg/min).
    From Jack Daniels' running formula.
    """
    v = speed_m_per_min
    return -4.60 + 0.182258 * v + 0.000104 * v ** 2


def estimate_vdot(
    distance_m: float,
    duration_s: float,
) -> tuple[float, float, float]:
    """
    Returns (vdot, pct_vo2max, vo2_at_pace).
    Requires: distance ≥ 1000m, duration ≥ 3 min.
    """
    if distance_m < 1000 or duration_s < 180:
        raise ValueError("Too short to estimate VDOT reliably")

    speed_mps = distance_m / duration_s
    speed_mpm = speed_mps * 60  # m/min
    duration_min = duration_s / 60

    pct = _pct_vo2max_at_duration(duration_min)
    vo2_pace = _vo2_at_pace(speed_mpm)
    vdot = vo2_pace / pct

    return vdot, pct, vo2_pace


def estimate_power_based(
    avg_power_w: float,
    duration_s: float,
    pct_vo2max: float,
    weight_kg: float,
    efficiency: float = 0.25,
) -> float:
    """
    VO2max from running power using metabolic equivalence.
    1 W = 1 J/s; 1 ml O2 ≈ 20.1 J at RQ ~0.90
    Typical running mechanical efficiency: 23–27%
    """
    vo2_ml_min = avg_power_w * 60 / 20.1 / efficiency
    vo2_ml_kg_min = vo2_ml_min / weight_kg
    return vo2_ml_kg_min / pct_vo2max


def estimate_hr_adjusted(
    vo2_at_pace: float,
    avg_hr: int,
    hrmax: int,
) -> tuple[float, float]:
    """
    HR-adjusted VO2max using Swain (1994):
    %VO2max = 1.12 * (%HRmax) - 0.126
    """
    pct_hrmax = avg_hr / hrmax
    pct_vo2max_hr = 1.12 * pct_hrmax - 0.126
    pct_vo2max_hr = max(0.5, min(1.0, pct_vo2max_hr))  # clamp
    vo2max = vo2_at_pace / pct_vo2max_hr
    return vo2max, pct_vo2max_hr


def classify_run(
    distance_m: float,
    duration_s: float,
    avg_hr: Optional[int],
    hrmax: int,
) -> str:
    """Classify run type for filtering and display."""
    pace_per_km = (duration_s / 60) / (distance_m / 1000)
    hr_frac = (avg_hr / hrmax) if avg_hr else 0

    if distance_m < 3000:
        return "short"
    if duration_s < 600:
        return "short"

    if hr_frac >= 0.88:
        if distance_m >= 18000:
            return "race_hm_plus"
        elif distance_m >= 8000:
            return "race_10k"
        else:
            return "race_5k"

    if hr_frac >= 0.82:
        return "tempo"
    if hr_frac >= 0.72:
        return "moderate"
    return "easy"


def is_usable_for_vo2max(
    distance_m: float,
    duration_s: float,
    avg_hr: Optional[int],
    hrmax: int,
    run_type: str,
) -> tuple[bool, str]:
    """
    Decide whether this run is suitable for VO2max estimation.
    Returns (usable, reason).
    """
    if distance_m < 3000:
        return False, "Too short (< 3km)"
    if duration_s < 600:
        return False, "Too short (< 10 min)"

    hr_frac = (avg_hr / hrmax) if avg_hr else 0

    if run_type in ("race_10k", "race_hm_plus", "race_5k"):
        return True, "Race effort — high confidence"

    if run_type == "tempo" and duration_s >= 1200:
        return True, "Tempo effort — medium confidence"

    if run_type in ("moderate", "easy") and avg_hr:
        if hr_frac >= 0.65:
            return True, "Sub-maximal effort — lower confidence"
        return False, "HR too low for reliable estimation (< 65% HRmax)"

    return False, f"Run type '{run_type}' not suitable"


def estimate(
    distance_m: float,
    duration_s: float,
    avg_hr: Optional[int] = None,
    avg_power_w: Optional[float] = None,
    hrmax: int = 192,
    hr_rest: int = 60,
    weight_kg: float = 72,
) -> VO2maxResult:
    """
    Main entry point. Estimates VO2max from a single activity.

    Selects best method based on available data:
    - Races (>88% HRmax): VDOT is primary, others as validation
    - Tempo/moderate: HR-adjusted VDOT
    - Easy runs: power-based if available, else skip
    """
    run_type = classify_run(distance_m, duration_s, avg_hr, hrmax)
    usable, usable_reason = is_usable_for_vo2max(
        distance_m, duration_s, avg_hr, hrmax, run_type
    )

    if not usable:
        return VO2maxResult(
            vo2max=0.0,
            method="none",
            vdot=None,
            vo2max_power=None,
            vo2max_hr=None,
            pct_vo2max=0.0,
            confidence="none",
            notes=usable_reason,
        )

    # --- VDOT ---
    vdot, pct_vo2max, vo2_pace = estimate_vdot(distance_m, duration_s)

    # --- HR-adjusted ---
    vo2max_hr = None
    if avg_hr:
        vo2max_hr, _ = estimate_hr_adjusted(vo2_pace, avg_hr, hrmax)

    # --- Power-based ---
    vo2max_power = None
    if avg_power_w and avg_power_w > 50:
        vo2max_power = estimate_power_based(
            avg_power_w, duration_s, pct_vo2max, weight_kg
        )

    # --- Combine ---
    hr_frac = (avg_hr / hrmax) if avg_hr else 0
    duration_min = duration_s / 60

    if run_type in ("race_10k", "race_hm_plus", "race_5k"):
        # Race: VDOT is primary, power as secondary if available
        if vo2max_power:
            final = 0.6 * vdot + 0.25 * vo2max_hr + 0.15 * vo2max_power if vo2max_hr else 0.7 * vdot + 0.3 * vo2max_power
            method = "VDOT + Power (race)"
        elif vo2max_hr:
            final = 0.65 * vdot + 0.35 * vo2max_hr
            method = "VDOT + HR-adjusted (race)"
        else:
            final = vdot
            method = "VDOT (race)"
        confidence = "high"

    elif run_type == "tempo":
        # Tempo: HR-adjusted is more appropriate (sub-max effort)
        if vo2max_hr and vo2max_power:
            final = 0.5 * vo2max_hr + 0.3 * vdot + 0.2 * vo2max_power
            method = "HR-adjusted + VDOT + Power (tempo)"
        elif vo2max_hr:
            final = 0.6 * vo2max_hr + 0.4 * vdot
            method = "HR-adjusted + VDOT (tempo)"
        else:
            final = vdot
            method = "VDOT (tempo)"
        confidence = "medium"

    else:
        # Moderate/easy: power if available, else HR-adjusted
        if vo2max_power and vo2max_hr:
            final = 0.5 * vo2max_power + 0.5 * vo2max_hr
            method = "Power + HR-adjusted (sub-max)"
        elif vo2max_power:
            final = vo2max_power
            method = "Power (sub-max)"
        elif vo2max_hr:
            final = vo2max_hr
            method = "HR-adjusted (sub-max)"
        else:
            final = vdot
            method = "VDOT (sub-max)"
        confidence = "low"

    # Sanity clamp: 30–90 ml/kg/min
    final = max(30.0, min(90.0, final))

    pace_per_km = (duration_s / 60) / (distance_m / 1000)
    notes = (
        f"{run_type} | {distance_m/1000:.1f}km in {int(duration_min)}min | "
        f"pace {int(pace_per_km)}:{int((pace_per_km%1)*60):02d}/km | "
        f"{pct_vo2max*100:.0f}% VO2max"
    )
    if avg_hr:
        notes += f" | HR {avg_hr}/{hrmax} ({hr_frac*100:.0f}%)"

    return VO2maxResult(
        vo2max=round(final, 1),
        method=method,
        vdot=round(vdot, 1),
        vo2max_power=round(vo2max_power, 1) if vo2max_power else None,
        vo2max_hr=round(vo2max_hr, 1) if vo2max_hr else None,
        pct_vo2max=round(pct_vo2max, 3),
        confidence=confidence,
        notes=notes,
    )
