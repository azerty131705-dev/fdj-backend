import os
import aiohttp
import random
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------- CONFIG ----------------
TIMEZONE = pytz.timezone("Europe/Paris")

# ⚠️ Mets ta clé API ici, sans la montrer
RAPID_API_KEY = "1947393ebfmsh8447824eac2f16dp134efdjsne16437dfdf24"

LEAGUES = [61, 39, 140, 78, 2]  # Ligue 1, EPL, LaLiga, Bundesliga, UCL

app = FastAPI(title="Bar du Centre - API FDJ Virtuelle")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- FETCH MATCHES FROM API-FOOTBALL -----------
async def fetch_matches_today():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

    matches = []

    async with aiohttp.ClientSession() as session:
        for league_id in LEAGUES:
            params = {"date": today, "league": league_id, "season": "2024"}
            headers = {
                "x-rapidapi-key": RAPID_API_KEY,
                "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
            }

            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
            except Exception:
                continue

            if "response" not in data:
                continue

            for m in data["response"]:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]
                league = m["league"]["name"]

                # Génération de cotes réalistes
                home_odd = round(random.uniform(1.40, 2.80), 2)
                draw_odd = round(random.uniform(2.80, 4.20), 2)
                away_odd = round(random.uniform(1.40, 2.80), 2)

                matches.append({
                    "competition": league,
                    "home_team": home,
                    "away_team": away,
                    "start_time": m["fixture"]["date"][11:16],  # HH:MM
                    "odds": {
                        home: home_odd,
                        "Match Nul": draw_odd,
                        away: away_odd,
                    }
                })

    return matches

# ----------- API ENDPOINT -----------

@app.get("/api/matches")
async def get_matches():
    return await fetch_matches_today()

