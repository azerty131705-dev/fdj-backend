import os
import aiohttp
import json
import asyncio
from datetime import datetime
import pytz
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# ---------------- CONFIG ----------------
SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
PROGRAMME_WEBHOOK_URL = "https://discord.com/api/webhooks/1430658587520405604/__2rMnHl2re1Cinw10uuKzCCJnI6NBL30Wh2aCfClQaMrkUHPVWFWODdGcRMaFl6jmrb"

TIMEZONE = pytz.timezone("Europe/Paris")
CRON_TOKEN = os.environ.get("CRON_TOKEN", "change-me")  # mets une valeur secrète en prod

# Keywords pour filtrer les compétitions ScoreBat
COMP_FILTERS = [
    "LIGUE 1", "LA LIGA", "PRIMEIRA LIGA",  # on garde LA LIGA
    "PREMIER LEAGUE",
    "CHAMPIONS LEAGUE", "UEFA CHAMPIONS",
    "BUNDESLIGA",
]

# ---------------- FASTAPI ----------------
app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # mets ton domaine si tu veux restreindre
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _now_paris():
    return datetime.now(TIMEZONE)

def _fmt_hhmm(dt: datetime) -> str:
    return dt.astimezone(TIMEZONE).strftime("%H:%M")

# ----------- FETCH MATCHES (ScoreBat) -----------
async def fetch_todays_matches():
    matches = []
    today = datetime.now(TIMEZONE).date()

    async with aiohttp.ClientSession() as session:
        for comp_name, sport_key in SPORTS.items():
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {"apiKey": API_KEY, "regions": "eu", "markets": "h2h"}

            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
            except:
                continue

            for ev in data:
                start_time = ev.get("commence_time")
                if not start_time:
                    continue

                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(TIMEZONE)

                # On garde seulement les matchs d'aujourd'hui
                if dt.date() != today:
                    continue

                odds = {"Match Nul": "—"}
                try:
                    market = ev["bookmakers"][0]["markets"][0]["outcomes"]
                    for o in market:
                        odds[o["name"]] = o["price"]
                except:
                    pass

                matches.append({
                    "competition": comp_name,
                    "home_team": ev["home_team"],
                    "away_team": ev["away_team"],
                    "start_time": dt.strftime("%H:%M"),
                    "odds": odds
                })

    print(f"✅ {len(matches)} matchs trouvés pour aujourd’hui.")
    return matches

# ----------- API GET MATCHES -----------
@app.get("/api/matches")
async def get_matches():
    matches = await fetch_todays_matches()
    # message de fallback explicite si vide
    if not matches:
        return []
    return matches

# ----------- PARIS SPORTIFS -----------
@app.post("/api/bet")
async def post_bet(bet: dict):
    username = (bet.get("username") or "inconnu").strip()[:64]
    selections = bet.get("selections", [])
    try:
        stake = float(bet.get("stake", 0))
    except Exception:
        raise HTTPException(status_code=400, detail="Stake invalide")

    if not selections:
        raise HTTPException(status_code=400, detail="Aucune sélection")

    # Somme (comme voulu)
    try:
        total_odds = sum(float(s.get("odd", 1)) for s in selections)
    except Exception:
        raise HTTPException(status_code=400, detail="Cote invalide")
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
        choice = s.get("choice", "")
        if str(choice).lower() == "draw":
            choice = "Match Nul"
        lines.append(
            f"• {s.get('home_team','?')} 🆚 {s.get('away_team','?')} — *{choice}* (cote {s.get('odd','?')})"
        )

    content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            r = await session.post(SPORTS_WEBHOOK_URL, json={"content": content}, timeout=15)
            if r.status >= 300:
                txt = await r.text()
                print(f"⚠️ Webhook pari status {r.status}: {txt}")
    except Exception as e:
        print(f"❌ Erreur webhook pari : {e}")

    return {
        "status": "ok",
        "message": f"Pari envoyé sur Discord pour {username}",
        "total_odds": round(total_odds, 2),
        "potential_gain": potential_gain
    }

# ----------- ENVOI AUTOMATIQUE DU PROGRAMME -----------
async def send_daily_matches_to_discord():
    matches = await fetch_todays_matches()

    if not matches:
        content = "⚽ Aucun match prévu aujourd’hui. Revenez demain."
    else:
        lines = ["📅 **Programme du jour**"]
        current_comp = None
        for m in matches:
            if m["competition"] != current_comp:
                current_comp = m["competition"]
                lines.append(f"\n🏆 **{current_comp}**")
            odds = m["odds"]
            home = odds.get(m["home_team"], "—")
            draw = odds.get("Match Nul", "—")
            away = odds.get(m["away_team"], "—")
            lines.append(
                f"• {m['home_team']} 🆚 {m['away_team']} — 🕒 {m['start_time']}\n"
                f"  💰 Cotes : 🏠 {home} | 🤝 {draw} | 🚗 {away}"
            )
        content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            r = await session.post(PROGRAMME_WEBHOOK_URL, json={"content": content}, timeout=15)
            if r.status >= 300:
                txt = await r.text()
                print(f"⚠️ Webhook programme status {r.status}: {txt}")
            else:
                print("✅ Programme du jour envoyé sur Discord.")
    except Exception as e:
        print(f"❌ Erreur envoi programme : {e}")

# ----------- CRON ENDPOINT (fallback si scheduler ne tourne pas) -----------
@app.get("/cron/send_programme")
async def cron_send_programme(token: str = Query(..., description="Token de sécurité")):
    if token != CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Token invalide")
    await send_daily_matches_to_discord()
    return {"status": "ok", "sent": True}

# ----------- HEALTHCHECK -----------
@app.get("/")
def root():
    return {"ok": True, "time": _now_paris().isoformat()}

# ----------- PLANNING AUTO 10H -----------
# Évite double démarrage sur certains hébergeurs (gunicorn/uvicorn workers)
if not os.environ.get("DISABLE_SCHEDULER", "").lower() in ("1", "true", "yes"):
    scheduler = BackgroundScheduler(timezone="Europe/Paris")
    # Appel asynchrone propre
    scheduler.add_job(lambda: asyncio.run(send_daily_matches_to_discord()),
                      "cron", hour=10, minute=0)
    scheduler.start()
    print("🕒 Scheduler OK : Envoi automatique tous les jours à 10h.")
