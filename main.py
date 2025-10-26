import os
import aiohttp
import asyncio
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

API_KEY = "1947393ebfmsh8447824eac2f16dp134efdjsne16437dfdfdf24"

LEAGUES = {
    "🇫🇷 Ligue 1": 61,
    "🇪🇸 LaLiga": 140,
    "🏴 Premier League": 39,
    "🇩🇪 Bundesliga": 78,
    "🏆 Ligue des Champions": 2
}

SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
PROGRAMME_WEBHOOK_URL = "https://discord.com/api/webhooks/1430658587520405604/__2rMnHl2re1Cinw10uuKzCCJnI6NBL30Wh2aCfClQaMrkUHPVWFWODdGcRMaFl6jmrb"

TIMEZONE = pytz.timezone("Europe/Paris")
app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_todays_matches():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    matches = []

    async with aiohttp.ClientSession() as session:
        for name, league_id in LEAGUES.items():
            url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures"
            params = {"date": today, "league": league_id, "season": 2024}
            headers = {
                "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
                "x-rapidapi-key": API_KEY,
            }

            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()

            if not data.get("response"):
                continue

            for item in data["response"]:
                matches.append({
                    "competition": name,
                    "home_team": item["teams"]["home"]["name"],
                    "away_team": item["teams"]["away"]["name"],
                    "start_time": item["fixture"]["date"][11:16],
                    "odds": {
                        item["teams"]["home"]["name"]: 1.50,
                        "Match Nul": 3.20,
                        item["teams"]["away"]["name"]: 2.60
                    }
                })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui.")
    return matches

@app.get("/api/matches")
async def get_matches():
    return await fetch_todays_matches()

scheduler = BackgroundScheduler(timezone=str(TIMEZONE))
scheduler.start()
