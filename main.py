import os
import aiohttp
import json
import asyncio
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# ---------------- CONFIG ----------------
SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
PROGRAMME_WEBHOOK_URL = "https://discord.com/api/webhooks/1430658587520405604/__2rMnHl2re1Cinw10uuKzCCJnI6NBL30Wh2aCfClQaMrkUHPVWFWODdGcRMaFl6jmrb"

TIMEZONE = pytz.timezone("Europe/Paris")
SCOREBAT_URL = "https://www.scorebat.com/video-api/v3/"

# ---------------- FASTAPI ----------------
app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- FETCH MATCHES FROM SCOREBAT -----------
async def fetch_todays_matches():
    matches = []
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SCOREBAT_URL) as resp:
                data = await resp.json()
    except Exception as e:
        print(f"❌ Erreur API ScoreBat : {e}")
        return []

    if "response" not in data:
        return []

    for match in data["response"]:
        match_date = match.get("date", "").split("T")[0]
        if match_date != today:
            continue

        competition = match["competition"]["name"]

        if " - " not in match["title"]:
            continue
        home, away = match["title"].split(" - ")

        matches.append({
            "competition": competition,
            "home_team": home,
            "away_team": away,
            "start_time": "À venir",
            "odds": {
                home: 1.50,
                "Match Nul": 3.20,
                away: 2.60,
            }
        })

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui.")
    return matches


# ----------- API ENDPOINT -----------
@app.get("/api/matches")
async def get_matches():
    return await fetch_todays_matches()


# ----------- PARIS SPORTIFS -----------
@app.post("/api/bet")
async def post_bet(bet: dict):
    username = bet.get("username", "inconnu")
    selections = bet.get("selections", [])
    stake = float(bet.get("stake", 0))

    total_odds = sum(float(s.get("odd", 1)) for s in selections)
    potential_gain = round(stake * total_odds, 2)

    lines = [
        f"🎟️ **NOUVEAU PARI** — {username}",
        f"💶 Mise : {stake:.2f} €",
        f"🔢 Cote totale : {total_odds:.2f}",
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


# ----------- AUTO PROGRAMME (10H) -----------
async def send_daily_matches_to_discord():
    matches = await fetch_todays_matches()

    if not matches:
        content = "⚽ Aucun match prévu aujourd’hui."
    else:
        lines = ["📅 **Programme du jour :**\n"]
        current_comp = ""
        for m in matches:
            if m["competition"] != current_comp:
                current_comp = m["competition"]
                lines.append(f"\n🏆 **{current_comp}**")
            lines.append(f"• {m['home_team']} vs {m['away_team']} — 🕒 {m['start_time']}")
        content = "\n".join(lines)

    async with aiohttp.ClientSession() as session:
        await session.post(PROGRAMME_WEBHOOK_URL, json={"content": content})


scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(lambda: asyncio.run(send_daily_matches_to_discord()), "cron", hour=10, minute=0)
scheduler.start()

print("🕒 Scheduler OK — envoi chaque jour à 10h")
