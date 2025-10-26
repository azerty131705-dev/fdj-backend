import aiohttp
import asyncio
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# ---------------- CONFIG ----------------
API_KEY = "69cfb42b44d7624c8ec3730d66a173f1"
API_FIXTURES = "https://v3.football.api-sports.io/fixtures"
API_ODDS = "https://v3.football.api-sports.io/odds"

SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"

TIMEZONE = pytz.timezone("Europe/Paris")

LEAGUES = {
    "🇫🇷 Ligue 1": 61,
    "🇪🇸 LaLiga": 140,
    "🏴 Premier League": 39,
    "🇩🇪 Bundesliga": 78,
    "🏆 Ligue des Champions": 2
}

app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# RÉCUPÉRATION DES MATCHS + COTES RÉELLES
# -------------------------------------------------
async def fetch_todays_matches():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    headers = {"x-apisports-key": API_KEY}

    matches = []

    async with aiohttp.ClientSession() as session:
        for league_name, league_id in LEAGUES.items():
            params = {"date": today, "league": league_id, "season": "2024"}

            async with session.get(API_FIXTURES, params=params, headers=headers) as resp:
                data = await resp.json()

            for m in data.get("response", []):
                fixture_id = m["fixture"]["id"]
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]
                start = m["fixture"]["date"][11:16]

                # ---- Récupération des vraies cotes ----
                odds_home, odds_draw, odds_away = "—", "—", "—"

                async with session.get(API_ODDS, params={"fixture": fixture_id}, headers=headers) as resp2:
                    odds_data = await resp2.json()

                try:
                    book = odds_data["response"][0]["bookmakers"][0]["bets"][0]["values"]
                    odds_home = float(book[0]["odd"])
                    odds_draw = float(book[1]["odd"])
                    odds_away = float(book[2]["odd"])
                except:
                    pass  # Si pas de cotes, on laisse "—"

                matches.append({
                    "competition": league_name,
                    "home_team": home,
                    "away_team": away,
                    "start_time": start,
                    "odds": {
                        home: odds_home,
                        "Match Nul": odds_draw,
                        away: odds_away,
                    }
                })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui.")
    return matches

# -------------------------------------------------
# ROUTE API MATCHS
# -------------------------------------------------
@app.get("/api/matches")
async def get_matches():
    return await fetch_todays_matches()

# -------------------------------------------------
# PARIS SPORTIFS
# -------------------------------------------------
@app.post("/api/bet")
async def post_bet(bet: dict):
    import aiohttp

    username = bet.get("username", "inconnu")
    selections = bet.get("selections", [])
    stake = float(bet.get("stake", 0))

    total_odds = sum(float(s.get("odd", 1)) for s in selections if s.get("odd") != "—")
    potential_gain = round(stake * total_odds, 2)

    lines = [
        f"🎟️ **PARI** — {username}",
        f"💶 Mise : {stake:.2f} €",
        f"📊 Cote totale : {total_odds:.2f}",
        f"💰 Gain potentiel : {potential_gain:.2f} €",
        "",
        "**Sélections :**"
    ]

    for s in selections:
        lines.append(f"• {s['home_team']} vs {s['away_team']} — *{s['choice']}* (cote {s['odd']})")

    content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(SPORTS_WEBHOOK_URL, json={"content": content})
    except:
        pass

    return {"status": "ok"}

# -------------------------------------------------
# ENVOI AUTO DU PROGRAMME À 10H
# -------------------------------------------------
async def send_daily_matches():
    matches = await fetch_todays_matches()
    if not matches:
        msg = "⚽ Aucun match aujourd’hui."
    else:
        msg = "📅 **Programme du jour :**\n"
        comp = ""
        for m in matches:
            if m["competition"] != comp:
                comp = m["competition"]
                msg += f"\n{comp}\n"
            msg += f"• {m['home_team']} vs {m['away_team']} — {m['start_time']}\n"

    async with aiohttp.ClientSession() as session:
        await session.post(SPORTS_WEBHOOK_URL, json={"content": msg})

scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(lambda: asyncio.run(send_daily_matches()), "cron", hour=10, minute=0)
scheduler.start()

print("✅ Backend démarré avec vraies cotes.")
