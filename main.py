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
async def fetch_todays_matches():
    matches = []
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    leagues = [61, 140, 39, 78, 2]  # Ligue 1, La Liga, Premier League, Bundesliga, LDC
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

    headers = {
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
        "x-rapidapi-key": "1947393ebfmsh8447824eac2f16dp134efdjsne16437dfdf24"
    }

    current_year = datetime.now(TIMEZONE).year

    async with aiohttp.ClientSession() as session:
        for league_id in leagues:
            params = {"date": today, "league": league_id, "season": current_year}

            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
            except Exception as e:
                print(f"❌ Erreur API Football (Ligue {league_id}): {e}")
                continue

            if not data.get("response"):
                continue

            for match in data["response"]:
                home = match["teams"]["home"]["name"]
                away = match["teams"]["away"]["name"]
                time_utc = match["fixture"]["date"]
                local_time = datetime.fromisoformat(time_utc.replace("Z", "+00:00")).astimezone(TIMEZONE)

                matches.append({
                    "competition": match["league"]["name"],
                    "home_team": home,
                    "away_team": away,
                    "start_time": local_time.strftime("%H:%M"),
                    "odds": {
                        home: 1.0,
                        "Match Nul": 1.0,
                        away: 1.0
                    }
                })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui via API-Football ✅")
    return matches

# ----------- API ENDPOINT -----------

@app.get("/api/matches")
async def get_matches():
    return await fetch_matches_today()

