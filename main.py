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
    today_str = _now_paris().strftime("%Y-%m-%d")
    url = "https://www.scorebat.com/video-api/v3/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    print(f"❌ ScoreBat status {resp.status}")
                    return []
                data = await resp.json()
    except Exception as e:
        print(f"❌ Erreur API ScoreBat : {e}")
        return []

    if "response" not in data:
        print("⚠️ ScoreBat: pas de clé 'response'")
        return []

    matches = []
    for m in data["response"]:
        # Competition
        comp_name = ""
        try:
            comp_name = m["competition"]["name"] or ""
        except Exception:
            comp_name = ""

        comp_upper = comp_name.upper()
        if not any(k in comp_upper for k in COMP_FILTERS):
            # saute les compétitions qui ne nous intéressent pas
            continue

        # Date match (UTC)
        raw_date = m.get("date") or ""
        if "T" not in raw_date:
            continue
        try:
            dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except Exception:
            continue

        # On ne garde que les matchs du jour (Paris)
        if dt_utc.astimezone(TIMEZONE).strftime("%Y-%m-%d") != today_str:
            continue

        title = m.get("title") or ""
        if " - " not in title:
            continue

        home, away = title.split(" - ", 1)

        matches.append({
            "competition": comp_name,
            "home_team": home.strip(),
            "away_team": away.strip(),
            "start_time": _fmt_hhmm(dt_utc),
            "odds": {
                home.strip(): 1.50,
                "Match Nul": 3.20,
                away.strip(): 2.60,
            }
        })

    # Tri: par compétition puis par heure
    matches.sort(key=lambda x: (x["competition"], x["start_time"]))
    print(f"✅ {len(matches)} match(s) trouvés pour aujourd’hui.")
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
