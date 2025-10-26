import aiohttp
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
TIMEZONE = pytz.timezone("Europe/Paris")

API_KEY = "1947393ebfmsh8447824eac2f16dp134efdjsne16437dfdf24"
HEADERS = {
    "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

LEAGUES = {
    "Ligue 1": 61,
    "Premier League": 39,
    "LaLiga": 140,
    "Bundesliga": 78,
    "Ligue des Champions": 2
}


@app.get("/api/matches")
async def get_matches():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    matches = []

    async with aiohttp.ClientSession() as session:
        for league_name, league_id in LEAGUES.items():
            url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?date={today}&league={league_id}&season=2024"
            async with session.get(url, headers=HEADERS) as resp:
                data = await resp.json()

            if not data.get("response"):
                continue

            for match in data["response"]:
                matches.append({
                    "competition": league_name,
                    "home_team": match["teams"]["home"]["name"],
                    "away_team": match["teams"]["away"]["name"],
                    "start_time": match["fixture"]["date"][11:16],
                    "odds": {
                        match["teams"]["home"]["name"]: 1.5,
                        "Match Nul": 3.2,
                        match["teams"]["away"]["name"]: 2.6
                    }
                })

    return matches
