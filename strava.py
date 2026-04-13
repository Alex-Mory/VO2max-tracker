"""
strava.py — Strava API client with automatic token refresh.
"""

import httpx
from datetime import datetime
from backend.config import (
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REFRESH_TOKEN,
)

_cached_token: dict = {}


async def get_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    global _cached_token

    now = datetime.utcnow().timestamp()
    if _cached_token.get("expires_at", 0) > now + 60:
        return _cached_token["access_token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "refresh_token": STRAVA_REFRESH_TOKEN,
                "grant_type":    "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _cached_token = {
        "access_token": data["access_token"],
        "expires_at":   data["expires_at"],
    }
    return _cached_token["access_token"]


async def get_activity(activity_id: int) -> dict:
    """Fetch a single activity's full detail from Strava."""
    token = await get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_activity_streams(activity_id: int) -> dict:
    """
    Fetch HR + speed + power streams for an activity.
    Returns dict of {stream_type: [values]} or empty dict if unavailable.
    """
    token = await get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "keys": "heartrate,velocity_smooth,watts,cadence,altitude",
                "key_by_type": "true",
            },
        )
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        data = resp.json()

    # Flatten to {type: [data]}
    return {k: v.get("data", []) for k, v in data.items()}


async def list_activities(page: int = 1, per_page: int = 50) -> list[dict]:
    """List recent activities (runs only)."""
    token = await get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {token}"},
            params={"page": page, "per_page": per_page},
        )
        resp.raise_for_status()
        activities = resp.json()

    return [a for a in activities if a.get("type") in ("Run", "TrailRun", "VirtualRun")]
