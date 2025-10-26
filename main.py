import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCOREBAT_API = "https://www.scorebat.com/feed/matches/"


@app.get("/api/matches")
async def get_matches():
    async with aiohttp.ClientSession() as session:
        async with session.get(SCOREBAT_API) as response:
            data = await response.json()

    matches = []
    for m in data:
        matches.append({
            "competition": m["competition"],
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "start_time": m["matchview_url"],  # On ne montre pas d’heure → juste un lien match
            "odds": {
                "home": "-",
                "draw": "-",
                "away": "-"
            }
        })

    return matches
