"""
register_webhook.py — Registers your Strava webhook subscription.

Usage:
    python scripts/register_webhook.py --callback-url https://YOUR-DEPLOY-URL/webhook

⚠️  Run this ONCE after deploying your backend.
    Your backend must be live and reachable before running this.
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, WEBHOOK_VERIFY_TOKEN


async def register(callback_url: str):
    print(f"Registering webhook with callback: {callback_url}")
    print(f"Client ID: {STRAVA_CLIENT_ID}")
    print(f"Verify token: {WEBHOOK_VERIFY_TOKEN}\n")

    async with httpx.AsyncClient() as client:
        # Check existing subscription
        resp = await client.get(
            "https://www.strava.com/api/v3/push_subscriptions",
            params={
                "client_id":     STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
            },
        )
        existing = resp.json()
        if existing:
            print(f"⚠️  Existing subscription found: {existing}")
            print("Delete it first if you want to change the callback URL:")
            for sub in existing:
                print(f"   DELETE https://www.strava.com/api/v3/push_subscriptions/{sub['id']}")
            print()

        # Create new subscription
        resp = await client.post(
            "https://www.strava.com/api/v3/push_subscriptions",
            data={
                "client_id":     STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "callback_url":  callback_url,
                "verify_token":  WEBHOOK_VERIFY_TOKEN,
            },
        )

        if resp.status_code == 201:
            data = resp.json()
            print(f"✓ Webhook registered! Subscription ID: {data.get('id')}")
            print("Strava will now POST to your callback on every new run.")
        else:
            print(f"✗ Failed ({resp.status_code}): {resp.text}")
            print("\nMake sure your backend is deployed and reachable first.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--callback-url", required=True)
    args = parser.parse_args()
    asyncio.run(register(args.callback_url))
