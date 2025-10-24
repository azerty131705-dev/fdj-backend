import os
import aiohttp
import asyncio
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# =========================
# CONFIG
# =========================
# → Mets ta clé The Odds API dans la variable d'environnement THE_ODDS_API_KEY sur Render
API_KEY = os.getenv("455364ce5710e315f3722a903b97c785", "").strip()
REGIONS = "eu"
MARKETS = "h2h"
TIMEZONE = pytz.timezone("Europe/Paris")

# Webhooks Discord
SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
PROGRAMME_WEBHOOK_URL = "https://discord.com/api/webhooks/1430658587520405604/__2rMnHl2re1Cinw10uuKzCCJnI6NBL30Wh2aCfClQaMrkUHPVWFWODdGcRMaFl6jmrb"

# Les compétitions demandées (clés officielles The Odds API)
SPORTS = {
    "🏆 Ligue des Champions": "soccer_uefa_champs_league",
    "🇫🇷 Ligue 1": "soccer_france_ligue_one",
    "🇪🇸 LaLiga": "soccer_spain_la_liga",
    "🏴 Premier League": "soccer_epl",
    "🇩🇪 Bundesliga": "soccer_germany_bundesliga",
}

# =========================
# FASTAPI
# =========================
app = FastAPI(title="FDJ Virtuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # garde simple pour Vercel/Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# HELPERS
# =========================
def _today_paris_date():
    return datetime.now(TIMEZONE).date()

def _to_paris_time(iso_str: str) -> datetime:
    # commence_time ex: "2025-10-23T18:45:00Z"
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(TIMEZONE)

# =========================
# FETCH MATCHES (The Odds API)
# =========================
async def fetch_todays_matches():
    """
    Récupère les matchs d'AUJOURD'HUI uniquement, pour les compétitions listées,
    avec les cotes H2H (1/N/2) si disponibles.
    """
    matches = []
    today = _today_paris_date()

    if not API_KEY:
        print("⚠️ THE_ODDS_API_KEY manquante (aucun match renvoyé).")
        return []

    async with aiohttp.ClientSession() as session:
        for comp_name, sport_key in SPORTS.items():
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": API_KEY,
                "regions": REGIONS,
                "markets": MARKETS,
            }

            try:
                async with session.get(url, params=params, timeout=20) as resp:
                    if resp.status != 200:
                        txt = await resp.text()
                        print(f"❌ {comp_name} ({sport_key}) status={resp.status} body={txt[:300]}")
                        continue
                    data = await resp.json()
            except Exception as e:
                print(f"❌ Erreur réseau {comp_name}: {e}")
                continue

            # Parcours des événements
            for ev in data:
                try:
                    start_iso = ev.get("commence_time")
                    if not start_iso:
                        continue

                    dt_local = _to_paris_time(start_iso)
                    if dt_local.date() != today:
                        continue  # on garde uniquement les matchs du jour

                    home = ev.get("home_team") or "Domicile"
                    away = ev.get("away_team") or "Extérieur"

                    # On prend le premier bookmaker (simple) → marche très bien pour un affichage
                    bm = (ev.get("bookmakers") or [])
                    if not bm:
                        # pas de bookmaker → pas de cotes, on affiche quand même le match
                        odds_map = {home: "—", "Match Nul": "—", away: "—"}
                    else:
                        market = (bm[0].get("markets") or [])
                        h2h = None
                        for m in market:
                            if m.get("key") == "h2h":
                                h2h = m
                                break
                        if not h2h:
                            odds_map = {home: "—", "Match Nul": "—", away: "—"}
                        else:
                            outcomes = h2h.get("outcomes") or []
                            # outcomes: [{name:"TeamA"/"TeamB"/"Draw", price:1.8}, ...]
                            odds_map = {home: "—", "Match Nul": "—", away: "—"}
                            for o in outcomes:
                                name = o.get("name", "")
                                price = o.get("price", "—")
                                if name.lower() == "draw":
                                    odds_map["Match Nul"] = price
                                elif name == home:
                                    odds_map[home] = price
                                elif name == away:
                                    odds_map[away] = price

                    matches.append({
                        "competition": comp_name,
                        "home_team": home,
                        "away_team": away,
                        "start_time": dt_local.strftime("%H:%M"),
                        "odds": odds_map,
                    })
                except Exception:
                    # on ignore l'event foireux
                    continue

    print(f"✅ {len(matches)} matchs trouvés aujourd’hui.")
    return matches

# =========================
# ROUTES
# =========================
@app.get("/api/matches")
async def get_matches():
    return await fetch_todays_matches()

@app.post("/api/bet")
async def post_bet(bet: dict):
    username = bet.get("username", "inconnu")
    selections = bet.get("selections", [])
    try:
        stake = float(bet.get("stake", 0))
    except Exception:
        stake = 0.0

    total_odds = 0.0
    for s in selections:
        try:
            total_odds += float(s.get("odd", 0))
        except Exception:
            pass

    potential_gain = round(stake * total_odds, 2)

    lines = [
        f"🎟️ **NOUVEAU PARI** — {username}",
        f"💶 Mise : {stake:.2f} €",
        f"🔢 Cote totale : {total_odds:.2f}",
        f"💰 Gain potentiel : {potential_gain:.2f} €",
        "",
        "**Sélections :**",
    ]
    for s in selections:
        choice = s.get("choice", "")
        if choice.lower() == "draw":
            choice = "Match Nul"
        lines.append(
            f"• {s.get('home_team','?')} 🆚 {s.get('away_team','?')} — *{choice}* (cote {s.get('odd','—')})"
        )

    content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(SPORTS_WEBHOOK_URL, json={"content": content})
    except Exception as e:
        print(f"⚠️ Envoi Discord échoué: {e}")

    return {
        "status": "ok",
        "message": f"Pari envoyé sur Discord pour {username}",
        "total_odds": round(total_odds, 2),
        "potential_gain": potential_gain,
    }

# =========================
# ENVOI QUOTIDIEN DU PROGRAMME (10h)
# =========================
async def send_daily_matches_to_discord():
    matches = await fetch_todays_matches()
    if not matches:
        content = "⚽ Aucun match prévu aujourd’hui."
    else:
        lines = ["📅 **Programme du jour :**\n"]
        current = None
        for m in matches:
            if m["competition"] != current:
                current = m["competition"]
                lines.append(f"\n🏆 **{current}**")
            odds = m["odds"]
            home = m["home_team"]
            away = m["away_team"]
            draw = odds.get("Match Nul", "—")
            lines.append(
                f"• {home} 🆚 {away} — 🕒 {m['start_time']}\n"
                f"  💰 Cotes : 🏠 {odds.get(home,'—')} | 🤝 {draw} | 🚗 {odds.get(away,'—')}"
            )
        content = "\n".join(lines)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(PROGRAMME_WEBHOOK_URL, json={"content": content})
        print("✅ Programme du jour envoyé sur Discord.")
    except Exception as e:
        print(f"❌ Erreur envoi Discord programme : {e}")

# Planif auto à 10:00 Europe/Paris
scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(lambda: asyncio.run(send_daily_matches_to_discord()), "cron", hour=10, minute=0)
scheduler.start()

print("🕒 Scheduler OK — envoi du programme chaque jour à 10h.")
