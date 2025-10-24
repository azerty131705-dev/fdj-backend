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
# Webhooks distincts pour éviter tout mélange
SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
PROGRAMME_WEBHOOK_URL = "https://discord.com/api/webhooks/1430658587520405604/__2rMnHl2re1Cinw10uuKzCCJnI6NBL30Wh2aCfClQaMrkUHPVWFWODdGcRMaFl6jmrb"
LOTO_WEBHOOK_URL = "https://discord.com/api/webhooks/1430541861399040130/OqZL0EAgKvCaPWQoiDpwaczzlWkxcIHjLR1XV4s4HNfvfTWCHywSk2yud0jwl-ILrO4h"

API_KEY = "455364ce5710e315f3722a903b97c785"
REGIONS = "eu"
MARKETS = "h2h"
TIMEZONE = pytz.timezone("Europe/Paris")

SPORTS = {
    "🇫🇷 Ligue 1": "soccer_france_ligue_one",
    "🇪🇸 LaLiga": "soccer_spain_la_liga",
    "🏴 Premier League": "soccer_epl",
    "🏆 Ligue des Champions": "soccer_uefa_champs_league",
    "🇩🇪 Bundesliga": "soccer_germany_bundesliga"
}

# --------------- FASTAPI INIT ---------------
app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fdj-frontend-3hhi48lwk-wesleys-projects-950691c3.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------- FETCH MATCHES FROM API -----------
async def fetch_todays_matches():
    matches = []
    today = datetime.now(TIMEZONE).date()

    async with aiohttp.ClientSession() as session:
        for comp_name, sport_key in SPORTS.items():
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": API_KEY,
                "regions": "eu",
                "markets": "h2h",
                "bookmakers": "bet365",
                "dateFormat": "iso"
            }

            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        print(f"❌ API {comp_name}: HTTP {resp.status}")
                        continue
                    data = await resp.json()
            except Exception as e:
                print(f"❌ Erreur API {comp_name}: {e}")
                continue

            for ev in data:
                try:
                    start_time = ev.get("commence_time")
                    if not start_time:
                        continue

                    dt_local = datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(TIMEZONE)

                    if dt_local.date() != today:
                        continue

                    outcomes = ev["bookmakers"][0]["markets"][0]["outcomes"]
                    odds = {o["name"]: o["price"] for o in outcomes}

                    matches.append({
                        "competition": comp_name,
                        "home_team": ev["home_team"],
                        "away_team": ev["away_team"],
                        "start_time": dt_local.strftime("%H:%M"),
                        "odds": odds
                    })

                except Exception:
                    continue

    print(f"✅ {len(matches)} match(s) trouvés aujourd’hui.")
    return matches


# ----------- ROUTE : MATCHS DU JOUR -----------
@app.get("/api/matches")
async def get_matches():
    data = await fetch_todays_matches()
    return data


# ----------- ROUTE : PARI SPORTIF -----------
@app.post("/api/bet")
async def post_bet(bet: dict):
    username = bet.get("username", "inconnu")
    selections = bet.get("selections", [])
    stake = float(bet.get("stake", 0))

    total_odds = sum(float(s.get("odd", 1)) for s in selections)
    potential_gain = round(stake * total_odds, 2)

    lines = [
        f"🎟️ **NOUVEAU PARI** — {username}",
        f"💶 **Mise** : {stake:.2f} €",
        f"🔢 **Cote totale** : {total_odds:.2f}",
        f"💰 **Gain potentiel** : {potential_gain:.2f} €",
        "",
        "**Sélections :**"
    ]

    for s in selections:
        choice = s["choice"]
        if choice.lower() == "draw":
            choice = "Match Nul"
        lines.append(f"• {s['home_team']} 🆚 {s['away_team']} — *{choice}* (cote {s['odd']})")

    content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(SPORTS_WEBHOOK_URL, json={"content": content})
        print("✅ Message pari envoyé sur Discord.")
    except Exception as e:
        print(f"❌ Erreur Discord Webhook (pari) : {e}")

    return {
        "status": "ok",
        "message": f"Pari envoyé sur Discord pour {username}",
        "total_odds": round(total_odds, 2),
        "potential_gain": potential_gain
    }


# ==========================================================
# AUTO-ENVOI QUOTIDIEN DU PROGRAMME DANS DISCORD (10H)
# ==========================================================
async def send_daily_matches_to_discord():
    print("🕙 Envoi automatique du programme du jour...")

    matches = await fetch_todays_matches()

    if not matches:
        content = "⚽ Aucun match prévu aujourd’hui."
    else:
        lines = ["📅 **Programme du jour :**\n"]
        current_competition = None
        for m in matches:
            if m["competition"] != current_competition:
                current_competition = m["competition"]
                lines.append(f"\n🏆 **{current_competition}**")
            odds = m["odds"]
            home = odds.get(m["home_team"], "—")
            draw = odds.get("Draw", "—")
            away = odds.get(m["away_team"], "—")
            lines.append(
                f"• {m['home_team']} 🆚 {m['away_team']} — 🕒 {m['start_time']}\n"
                f"  💰 Cotes : 🏠 {home} | 🤝 {draw} | 🚗 {away}"
            )
        content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(PROGRAMME_WEBHOOK_URL, json={"content": content})
        print("✅ Programme du jour envoyé sur Discord.")
    except Exception as e:
        print(f"❌ Erreur envoi Discord programme : {e}")


# ==========================================================
# PLANIFICATION AUTOMATIQUE À 10H
# ==========================================================
scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(lambda: asyncio.run(send_daily_matches_to_discord()), "cron", hour=10, minute=0)
scheduler.start()

print("🕒 Scheduler lancé — le programme sera envoyé chaque jour à 10h.")
