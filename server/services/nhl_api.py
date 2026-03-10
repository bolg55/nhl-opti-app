import time
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from server.constants import ALL_TEAMS, CACHE_HOURS, NHL_API_BASE, SEASON_INT
from server.database import get_db, get_write_lock


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")


def is_cache_fresh(table_name: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT updated_at FROM cache_metadata WHERE table_name = ?",
            (table_name,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False
    updated = datetime.fromisoformat(row[0])
    return (datetime.now() - updated).total_seconds() < CACHE_HOURS * 3600


def set_cache_timestamp(conn, table_name: str):
    conn.execute(
        "INSERT OR REPLACE INTO cache_metadata (table_name, updated_at) VALUES (?, ?)",
        (table_name, datetime.now().isoformat()),
    )
    conn.commit()


def fetch_all_player_stats(min_gp: int = 10, force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and is_cache_fresh("player_stats"):
        conn = get_db()
        try:
            return pd.read_sql("SELECT * FROM player_stats", conn)
        finally:
            conn.close()

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
            shots = skater.get("shots", 0)
            toi = skater.get("avgTimeOnIcePerGame", 0)

            all_players.append(
                {
                    "player_name": name,
                    "team": team,
                    "position": position,
                    "games_played": gp,
                    "goals": goals,
                    "assists": assists,
                    "shots": shots,
                    "avg_toi_seconds": toi,
                    "goals_per_game": goals / gp,
                    "assists_per_game": assists / gp,
                }
            )

        time.sleep(0.1)

    df = pd.DataFrame(all_players)

    with get_write_lock():
        conn = get_db()
        try:
            conn.execute("DELETE FROM player_stats")
            df.to_sql("player_stats", conn, if_exists="append", index=False)
            set_cache_timestamp(conn, "player_stats")
        finally:
            conn.close()

    return df


def fetch_standings(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and is_cache_fresh("standings"):
        conn = get_db()
        try:
            return pd.read_sql("SELECT * FROM standings", conn)
        finally:
            conn.close()

    resp = requests.get(f"{NHL_API_BASE}/standings/now", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    teams = []
    for entry in data.get("standings", []):
        abbrev = entry.get("teamAbbrev", {}).get("default", "")
        name = entry.get("teamName", {}).get("default", "")
        pctg = entry.get("pointPctg", 0.5)
        teams.append({"team": abbrev, "team_name": name, "point_pctg": pctg})

    df = pd.DataFrame(teams)

    with get_write_lock():
        conn = get_db()
        try:
            conn.execute("DELETE FROM standings")
            df.to_sql("standings", conn, if_exists="append", index=False)
            set_cache_timestamp(conn, "standings")
        finally:
            conn.close()

    return df


def fetch_weekly_schedule(start_date=None):
    if start_date is None:
        # Use Eastern Time to align with NHL schedule dates
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
    standings_df: pd.DataFrame, opponents: dict[str, list[str]]
) -> dict[str, float]:
    pctg_lookup = dict(zip(standings_df["team"], standings_df["point_pctg"]))
    multipliers = {}

    for team, opps in opponents.items():
        opp_mults = []
        for opp in opps:
            pctg = pctg_lookup.get(opp, 0.5)
            opp_mults.append(0.5 / pctg if pctg > 0 else 1.8)
        multipliers[team] = float(np.mean(opp_mults)) if opp_mults else 1.0

    return multipliers
