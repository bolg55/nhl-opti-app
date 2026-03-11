import time
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from server.cache import get_cached, set_cached
from server.constants import ALL_TEAMS, CACHE_HOURS, NHL_API_BASE, SEASON_INT

_CACHE_TTL = CACHE_HOURS * 3600


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")


def fetch_all_player_stats(min_gp: int = 10, force_refresh: bool = False) -> list[dict]:
    cache_key = "player_stats"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    all_players = []

    for team in ALL_TEAMS:
        url = f"{NHL_API_BASE}/club-stats/{team}/{SEASON_INT}/2"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for skater in data.get("skaters", []):
            gp = skater.get("gamesPlayed", 0)
            if gp < min_gp:
                continue

            first = skater.get("firstName", {}).get("default", "")
            last = skater.get("lastName", {}).get("default", "")
            name = normalize_name(f"{first} {last}").strip()
            pos_code = skater.get("positionCode", "C")
            position = "D" if pos_code == "D" else "F"
            goals = skater.get("goals", 0)
            assists = skater.get("assists", 0)

            all_players.append({
                "playerId": skater.get("playerId"),
                "player_name": name,
                "team": team,
                "position": position,
                "games_played": gp,
                "goals": goals,
                "assists": assists,
                "goals_per_game": goals / gp,
                "assists_per_game": assists / gp,
            })

        time.sleep(0.1)

    set_cached(cache_key, all_players)
    return all_players


def fetch_standings(force_refresh: bool = False) -> list[dict]:
    cache_key = "standings"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    resp = requests.get(f"{NHL_API_BASE}/standings/now", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    teams = []
    for entry in data.get("standings", []):
        abbrev = entry.get("teamAbbrev", {}).get("default", "")
        pctg = entry.get("pointPctg", 0.5)
        teams.append({"team": abbrev, "point_pctg": pctg})

    set_cached(cache_key, teams)
    return teams


def fetch_weekly_schedule(start_date=None):
    if start_date is None:
        start_date = datetime.now(ZoneInfo("America/New_York")).date()
    elif isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    resp = requests.get(
        f"{NHL_API_BASE}/schedule/{start_date.isoformat()}", timeout=10
    )
    resp.raise_for_status()
    data = resp.json()

    games_count: dict[str, int] = {}
    opponents: dict[str, list[str]] = {}

    for day in data.get("gameWeek", []):
        game_date = date.fromisoformat(day["date"])
        if game_date < start_date:
            continue
        for game in day.get("games", []):
            away = game.get("awayTeam", {}).get("abbrev", "")
            home = game.get("homeTeam", {}).get("abbrev", "")
            if not away or not home:
                continue
            games_count[away] = games_count.get(away, 0) + 1
            games_count[home] = games_count.get(home, 0) + 1
            opponents.setdefault(away, []).append(home)
            opponents.setdefault(home, []).append(away)

    return games_count, opponents


def calculate_multipliers(
    standings: list[dict], opponents: dict[str, list[str]]
) -> dict[str, float]:
    pctg_lookup = {s["team"]: s["point_pctg"] for s in standings}
    multipliers = {}

    for team, opps in opponents.items():
        opp_mults = []
        for opp in opps:
            pctg = pctg_lookup.get(opp, 0.5)
            opp_mults.append(0.5 / pctg if pctg > 0 else 1.8)
        multipliers[team] = sum(opp_mults) / len(opp_mults) if opp_mults else 1.0

    return multipliers
