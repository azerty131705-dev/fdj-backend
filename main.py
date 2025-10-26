import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

API_KEY = "69cfb42b44d7624c8ec3730d66a173f1"
FIXTURES_URL = "https://v3.football.api-sports.io/fixtures"
ODDS_URL = "https://v3.football.api-sports.io/odds"

LEAGUES = [61, 39, 140, 78, 2]  # Ligue1, EPL, LaLiga, Bundesliga, UCL

HEADERS = {
    "x-apisports-key": API_KEY
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def fetch_fixtures():
    upcoming_matches = []

    async with aiohttp.ClientSession() as session:
        for league in LEAGUES:
            params = {"league": league, "season": 2024, "next": 5}
            async with session.get(FIXTURES_URL, params=params, headers=HEADERS) as resp:
                data = await resp.json()

                if not data.get("response"):
                    continue

                for match in data["response"]:
                    home = match["teams"]["home"]["name"]
                    away = match["teams"]["away"]["name"]
                    time = match["fixture"]["date"]

                    # Fetch Odds
                    odds_params = {
                        "fixture": match["fixture"]["id"]
                    }
                    async with session.get(ODDS_URL, params=odds_params, headers=HEADERS) as odds_resp:
                        odds_data = await odds_resp.json()

                    home_odd = draw_odd = away_odd = "—"

                    if odds_data.get("response"):
                        try:
                            outcomes = odds_data["response"][0]["bookmakers"][0]["bets"][0]["values"]
                            home_odd = outcomes[0]["odd"]
                            draw_odd = outcomes[1]["odd"]
                            away_odd = outcomes[2]["odd"]
                        except:
                            pass

                    upcoming_matches.append({
                        "league": match["league"]["name"],
                        "home_team": home,
                        "away_team": away,
                        "match_time": time,
                        "odds": {
                            "home": home_odd,
                            "draw": draw_odd,
                            "away": away_odd
                        }
                    })

    return upcoming_matches


@app.get("/api/matches")
async def get_matches():
    matches = await fetch_fixtures()
    return matches
