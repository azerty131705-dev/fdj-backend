import aiohttp
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

API_KEY = "69cfb42b44d7624c8ec3730d66a173f1"
TIMEZONE = pytz.timezone("Europe/Paris")

LEAGUES = {
    "🇫🇷 Ligue 1": 61,
    "🇪🇸 La Liga": 140,
    "🏴 Premier League": 39,
    "🇩🇪 Bundesliga": 78,
    "🏆 Ligue des Champions": 2,
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_matches():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    season = 2025  # ✅ car la date est 26/10/2025

    matches = []

    async with aiohttp.ClientSession() as session:
        for league_name, league_id in LEAGUES.items():
            url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={league_id}&season={season}"
            headers = {"x-apisports-key": API_KEY}

            async with session.get(url, headers=headers) as resp:
                data = await resp.json()

                if "response" not in data:
                    continue

                for m in data["response"]:
                    home = m["teams"]["home"]["name"]
                    away = m["teams"]["away"]["name"]
                    time = m["fixture"]["date"][11:16]  # Heure locale

                    # --- Cotes (si disponibles)
                    odds = {
                        home: "-",
                        "Match Nul": "-",
                        away: "-"
                    }

                    matches.append({
                        "competition": league_name,
                        "home_team": home,
                        "away_team": away,
                        "start_time": time,
                        "odds": odds
                    })

    return matches

@app.get("/api/matches")
async def get_matches():
    return await fetch_matches()
