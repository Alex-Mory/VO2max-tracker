"""
main.py — FastAPI server.

Endpoints:
  GET  /             → health check
  GET  /webhook      → Strava subscription validation
  POST /webhook      → Strava activity event receiver
  GET  /runs         → list all processed runs (for dashboard)
  GET  /vo2max       → VO2max history (for dashboard)
  POST /process/{id} → manually trigger processing of one activity
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.config import WEBHOOK_VERIFY_TOKEN
from backend import database as db
from backend.processor import process_activity

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vo2max")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    log.info("Database initialised")
    yield


app = FastAPI(title="VO2max Tracker", version="1.0.0", lifespan=lifespan)


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    latest = db.get_latest_vo2max()
    return {
        "status": "running",
        "latest_vo2max": latest,
    }


# ─── Strava Webhook ───────────────────────────────────────────────────────────

@app.get("/webhook")
async def webhook_validate(request: Request):
    """
    Strava sends a GET to validate the webhook endpoint.
    Must echo back hub.challenge.
    """
    params = dict(request.query_params)
    if params.get("hub.verify_token") != WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    challenge = params.get("hub.challenge", "")
    log.info(f"Webhook validated ✓")
    return JSONResponse({"hub.challenge": challenge})


@app.post("/webhook")
async def webhook_receive(request: Request, background_tasks: BackgroundTasks):
    """
    Strava posts an event when a new activity is created.
    We immediately return 200, then process in the background.
    """
    try:
        event = await request.json()
    except Exception:
        return PlainTextResponse("EVENT_RECEIVED", status_code=200)

    log.info(f"Webhook event: {event}")

    # Only care about activity create events
    if (
        event.get("object_type") == "activity"
        and event.get("aspect_type") == "create"
    ):
        activity_id = event.get("object_id")
        if activity_id:
            background_tasks.add_task(_process_and_log, activity_id)

    # Always return 200 immediately — Strava requires this
    return PlainTextResponse("EVENT_RECEIVED", status_code=200)


async def _process_and_log(activity_id: int):
    try:
        result = await process_activity(activity_id)
        if result:
            log.info(
                f"✓ Processed activity {activity_id}: "
                f"{result['name']} | VO2max={result['vo2max']} | "
                f"method={result['method']} | confidence={result['confidence']}"
            )
        else:
            log.info(f"– Skipped activity {activity_id} (not a run or already exists)")
    except Exception as e:
        log.error(f"✗ Error processing activity {activity_id}: {e}", exc_info=True)


# ─── Dashboard API ────────────────────────────────────────────────────────────

@app.get("/runs")
async def get_runs(limit: int = 200):
    """Return all processed runs for the dashboard."""
    runs = db.get_all_runs(limit=limit)
    return {"runs": runs, "count": len(runs)}


@app.get("/vo2max")
async def get_vo2max_history():
    """Return VO2max history for trend chart."""
    history = db.get_vo2max_history()
    return {"history": history, "count": len(history)}


@app.post("/process/{activity_id}")
async def manual_process(activity_id: int, background_tasks: BackgroundTasks):
    """Manually trigger processing of a specific Strava activity ID."""
    background_tasks.add_task(_process_and_log, activity_id)
    return {"status": "processing", "activity_id": activity_id}
