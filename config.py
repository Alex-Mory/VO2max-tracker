"""
config.py — Loads settings from .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Strava OAuth
STRAVA_CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")

# Webhook
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "vo2max_tracker_secret")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "vo2max.db")

# Athlete profile — pre-filled from your data
ATHLETE_HRMAX      = int(os.getenv("ATHLETE_HRMAX", 192))
ATHLETE_HR_REST    = int(os.getenv("ATHLETE_HR_REST", 60))
ATHLETE_WEIGHT_KG  = float(os.getenv("ATHLETE_WEIGHT_KG", 72))
ATHLETE_HEIGHT_CM  = float(os.getenv("ATHLETE_HEIGHT_CM", 181))
ATHLETE_AGE        = int(os.getenv("ATHLETE_AGE", 26))
