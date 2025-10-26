import aiohttp
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

API_KEY = "69cfb42b44d7624c8ec3730d66a173f1"
TIMEZONE = pytz.timezone("Europe/Paris")

LEAGUES = {
    "🇫🇷 Ligue 1": 61,
    "🏴 Premier League": 39,
    "🇪🇸 La Liga": 140,
    "🇩🇪 Bundesliga": 78,
    "🏆 Ligue des Champions": 2
}


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_matches():
    # Prend la vraie date du jour à Paris
    now = datetime.now(TIMEZONE)
    today = now.strftime("%Y-%m-%d")

    # Saison = année en cours si après juillet, sinon année précédente
    season = now.year if now.month >= 7 else now.year - 1

    matches = []

    async with aiohttp.ClientSession() as session:
        headers = {"x-apisports-key": API_KEY}

        for league_name, league_id in LEAGUES.items():
            url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={league_id}&season={season}"

            async with session.get(url, headers=headers) as resp:
                data = await resp.json()

                # ✅ Debug visible dans logs Render
                print(f"[DEBUG] {league_name}: {data.get('results', 0)} resultats")

                if "response" not in data:
                    continue

                for m in data["response"]:
                    home = m["teams"]["home"]["name"]
                    away = m["teams"]["away"]["name"]

                    # Heure format FR
                    dt = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00")).astimezone(TIMEZONE)
                    time = dt.strftime("%H:%M")

                    matches.append({
                        "competition": league_name,
                        "home_team": home,
                        "away_team": away,
                        "start_time": time,
                        "odds": {
                            home: "-", 
                            "Match Nul": "-", 
                            away: "-"
                        }
                    })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui ({today})")
    return matches

@app.get("/api/matches")
async def get_matches():
    return await fetch_matches()
