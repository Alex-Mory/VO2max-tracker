"""
backfill.py — One-time script to import your Strava run history.

Usage:
    python scripts/backfill.py              # import last 200 runs
    python scripts/backfill.py --pages 10   # import last 500 runs (50/page)

⚠️  YOU NEED TO RUN THIS ONCE after setup to populate your history.
"""

import asyncio
import argparse
import sys
import os

# Add parent dir to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database as db
from backend import strava
from backend.processor import process_activity


async def backfill(pages: int = 4):
    db.init_db()
    print(f"🔄 Fetching up to {pages * 50} activities from Strava...\n")

    total_fetched = 0
    total_processed = 0
    total_skipped = 0

    for page in range(1, pages + 1):
        activities = await strava.list_activities(page=page, per_page=50)
        if not activities:
            print(f"  Page {page}: no more activities")
            break

        print(f"  Page {page}: {len(activities)} runs found")

        for act in activities:
            activity_id = act["id"]
            name = act.get("name", "Run")
            distance_km = act.get("distance", 0) / 1000
            date = act.get("start_date_local", "")[:10]
            total_fetched += 1

            try:
                result = await process_activity(activity_id)
                if result:
                    vo2 = result["vo2max"]
                    conf = result["confidence"]
                    rt = result["run_type"]
                    print(
                        f"    ✓ {date} | {name[:30]:<30} | "
                        f"{distance_km:.1f}km | VO2max={vo2} [{conf}] ({rt})"
                    )
                    total_processed += 1
                else:
                    print(f"    – {date} | {name[:30]:<30} | {distance_km:.1f}km | skipped")
                    total_skipped += 1

                # Respect Strava rate limits (200 req / 15 min)
                await asyncio.sleep(0.4)

            except Exception as e:
                print(f"    ✗ {date} | {name} | ERROR: {e}")

    print(f"\n{'─'*60}")
    print(f"Done. Fetched: {total_fetched} | Processed: {total_processed} | Skipped: {total_skipped}")
    print(f"Database: {os.path.abspath('vo2max.db')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=4, help="Number of pages (50 runs/page)")
    args = parser.parse_args()
    asyncio.run(backfill(pages=args.pages))
