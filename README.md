# VO2max Tracker — Alex Mory

Automatically estimates your VO2max after every run synced to Strava,
using Jack Daniels VDOT + power-based methods calibrated to your data.

---

## Project Structure

```
vo2max-tracker/
├── backend/
│   ├── main.py          # FastAPI server — webhook receiver + Strava API calls
│   ├── vo2max.py        # VO2max estimation engine (VDOT + power + HR methods)
│   ├── database.py      # SQLite database handler
│   └── config.py        # Configuration (reads from .env)
├── dashboard/
│   └── app.py           # Streamlit dashboard — VO2max trend + run history
├── scripts/
│   └── backfill.py      # One-time script to import your Strava history
├── .env.example         # Template for your secrets
├── requirements.txt     # Python dependencies
└── README.md
```

---

## ⚙️ STEPS YOU NEED TO DO YOURSELF

### STEP 1 — Create a Strava API App  *(~15 min)*

1. Go to https://www.strava.com/settings/api
2. Fill in:
   - **Application Name**: VO2max Tracker (or anything)
   - **Category**: Data Importer
   - **Website**: http://localhost (for now)
   - **Authorization Callback Domain**: localhost
3. Note down your **Client ID** and **Client Secret**

### STEP 2 — Get Your Personal Strava Refresh Token  *(~10 min)*

Run this in your browser (replace YOUR_CLIENT_ID):
```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
```
1. Authorize the app → you'll be redirected to a localhost URL
2. Copy the `code=XXXX` value from the URL
3. Run this curl (replace values):
```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=YOUR_CODE \
  -d grant_type=authorization_code
```
4. Save the `refresh_token` from the response

### STEP 3 — Fill in Your .env File  *(~2 min)*

```bash
cp .env.example .env
# Edit .env with your values
```

### STEP 4 — Deploy the Backend  *(~20 min)*

**Option A: Railway (recommended, free tier)**
1. Go to https://railway.app and sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Push this folder to a GitHub repo first
4. Add your `.env` variables in Railway's "Variables" tab
5. Railway will give you a public URL like `https://vo2max-xxx.railway.app`

**Option B: Render (also free)**
1. Go to https://render.com
2. New → Web Service → connect your GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### STEP 5 — Register the Strava Webhook  *(~5 min)*

Once your backend is deployed and running, run this once:
```bash
python scripts/register_webhook.py --callback-url https://YOUR-DEPLOY-URL/webhook
```
Or manually with curl:
```bash
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -F client_id=YOUR_CLIENT_ID \
  -F client_secret=YOUR_CLIENT_SECRET \
  -F callback_url=https://YOUR-DEPLOY-URL/webhook \
  -F verify_token=vo2max_tracker_secret
```

### STEP 6 — Backfill Your History  *(~2 min)*

```bash
pip install -r requirements.txt
python scripts/backfill.py
```
This imports your last 200 activities from Strava and computes VO2max for each.

### STEP 7 — Run the Dashboard  *(~1 min)*

```bash
streamlit run dashboard/app.py
```
Opens at http://localhost:8501

---

## Your Personal Settings (pre-configured)

These are already set in `backend/vo2max.py` based on your races:
- HRmax: 192 bpm
- Resting HR: 60 bpm
- Body weight: 72 kg
- Height: 181 cm
- Age: 26

Calibrated from:
- 10K race: 32:55 → VDOT 65.6
- Half marathon: 1:13:52 → VDOT 64.2
- Consensus VO2max: ~65 ml/kg/min
