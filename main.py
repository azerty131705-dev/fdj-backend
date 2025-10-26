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
    current_year = datetime.now(TIMEZONE).year

    leagues = [61, 140, 39, 78, 2]  # Ligue 1, LaLiga, PL, Bundesliga, LDC

    fixtures_url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    odds_url = "https://api-football-v1.p.rapidapi.com/v3/odds"

    headers = {
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
        "x-rapidapi-key": "1947393ebfmsh8447824eac2f16dp134efdjsne16437dfdf24"
    }

    async with aiohttp.ClientSession() as session:
        for league_id in leagues:
            params = {"date": today, "league": league_id, "season": current_year}

            try:
                async with session.get(fixtures_url, headers=headers, params=params) as resp:
                    data = await resp.json()
            except Exception as e:
                print(f"❌ Erreur API Football (fixtures Ligue {league_id}): {e}")
                continue

            if not data.get("response"):
                continue

            for m in data["response"]:
                fixture_id = m["fixture"]["id"]
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]

                # Conversion heure locale
                time_utc = m["fixture"]["date"]
                local_time = datetime.fromisoformat(time_utc.replace("Z", "+00:00")).astimezone(TIMEZONE)

                # ----------- Récupération des cotes -----------
                odds_params = {"fixture": fixture_id}
                try:
                    async with session.get(odds_url, headers=headers, params=odds_params) as resp_odds:
                        odds_data = await resp_odds.json()
                except:
                    odds_data = {}

                # Valeurs par défaut
                home_odd = away_odd = draw_odd = "—"

                # Lecture bookmakers
                try:
                    bookmakers = odds_data["response"][0]["bookmakers"][0]["bets"][0]["values"]
                    for b in bookmakers:
                        if b["value"] == "Home":
                            home_odd = b["odd"]
                        elif b["value"] == "Away":
                            away_odd = b["odd"]
                        elif b["value"] == "Draw":
                            draw_odd = b["odd"]
                except:
                    pass

                matches.append({
                    "competition": m["league"]["name"],
                    "home_team": home,
                    "away_team": away,
                    "start_time": local_time.strftime("%H:%M"),
                    "odds": {
                        home: float(home_odd) if home_odd != "—" else "—",
                        "Match Nul": float(draw_odd) if draw_odd != "—" else "—",
                        away: float(away_odd) if away_odd != "—" else "—"
                    }
                })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui avec **cotes réelles**")
    return matches

# ----------- API ENDPOINT -----------

@app.get("/api/matches")
async def get_matches():
    return await fetch_matches_today()

