import os
import aiohttp
import json
from datetime import datetime
import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------- CONFIG ----------------
# Webhooks distincts pour éviter tout mélange
SPORTS_WEBHOOK_URL = "https://discord.com/api/webhooks/1430538864941862993/QqxcVkODQN1IGFz7T3JeHV9P_BKRUnxhVK8fV20UhK_akN7IeExI0SQqITB44-uEFN-N"
LOTO_WEBHOOK_URL = "https://discord.com/api/webhooks/1430541861399040130/OqZL0EAgKvCaPWQoiDpwaczzlWkxcIHjLR1XV4s4HNfvfTWCHywSk2yud0jwl-ILrO4h"



API_KEY = "455364ce5710e315f3722a903b97c785"
REGIONS = "eu"
MARKETS = "h2h"
TIMEZONE = pytz.timezone("Europe/Paris")
SCRATCH_FILE = "scratch_entries.json"

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
    allow_origins=["*"],  # Pour ton site React
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
            params = {"apiKey": API_KEY, "regions": REGIONS, "markets": MARKETS}

            try:
                async with session.get(url, params=params, timeout=15) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
            except Exception as e:
                print(f"Erreur {comp_name} : {e}")
                continue

            for ev in data:
                try:
                    start_time = ev.get("commence_time")
                    if not start_time:
                        continue

                    # Convertir en heure locale
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

    return matches


# ----------- ROUTE : MATCHS DU JOUR -----------
@app.get("/api/matches")
async def get_matches():
    """Renvoie uniquement les matchs d'aujourd'hui."""
    data = await fetch_todays_matches()
    return data


# ----------- ROUTE : PARI SPORTIF -----------
@app.post("/api/bet")
async def post_bet(bet: dict):
    """Enregistre un pari virtuel et l'envoie sur Discord."""
    username = bet.get("username", "inconnu")
    selections = bet.get("selections", [])
    stake = float(bet.get("stake", 0))

    # Calcul de la cote totale et du gain potentiel
    total_odds = sum(float(s.get("odd", 1)) for s in selections)
    potential_gain = round(stake * total_odds, 2)

    # 🔹 Message pour Discord
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
        # 🟡 Traduction du mot "Draw"
        if choice.lower() == "draw":
            choice = "Match Nul"
        lines.append(f"• {s['home_team']} 🆚 {s['away_team']} — *{choice}* (cote {s['odd']})")

    content = "\n".join(lines)

    # 🔸 Envoi sur le bon Webhook Discord
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

# ----------- ROUTE : LOTO -----------

LOTO_FILE = "loto_entries.json"
LOTO_WEBHOOK_URL = "https://discord.com/api/webhooks/1430541861399040130/OqZL0EAgKvCaPWQoiDpwaczzlWkxcIHjLR1XV4s4HNfvfTWCHywSk2yud0jwl-ILrO4h"


@app.post("/api/loto")
async def post_loto(entry: dict):
    """Inscrit un joueur au tirage LOTO du jour (1 participation max par jour)."""
    username = entry.get("username", "inconnu")
    numbers = entry.get("numbers", [])
    chance = entry.get("chance", None)

    tz = pytz.timezone("Europe/Paris")
    today = datetime.now(tz).strftime("%Y-%m-%d")

    if not isinstance(numbers, list) or len(numbers) != 5 or not isinstance(chance, int):
        return {"status": "error", "message": "Format invalide. 5 numéros + 1 numéro chance requis."}

    # Charger les participations existantes
    entries = []
    if os.path.exists(LOTO_FILE):
        with open(LOTO_FILE, "r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                entries = []

    # Vérifier si le joueur a déjà joué aujourd’hui
    if any(e["username"].lower() == username.lower() and e["date"] == today for e in entries):
        return {"status": "error", "message": "Tu as déjà joué aujourd’hui !"}

    # Sauvegarder la participation
    new_entry = {
        "username": username,
        "numbers": sorted(numbers),
        "chance": chance,
        "date": today
    }
    entries.append(new_entry)
    with open(LOTO_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # Envoi Discord
    content = (
        f"🎟️ **Nouvelle participation au LOTO** — {username}\n"
        f"🔢 Numéros : {', '.join(map(str, sorted(numbers)))} | 🌟 Chance : {chance}\n"
        f"📅 Date : {today}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(LOTO_WEBHOOK_URL, json={"content": content})
        print(f"✅ LOTO envoyé pour {username}")
    except Exception as e:
        print(f"❌ Erreur webhook LOTO : {e}")

    return {"status": "ok", "message": f"Participation enregistrée pour {username}"}
