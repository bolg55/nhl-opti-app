import time
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from server.cache import get_cached, set_cached
from server.constants import (
    ALL_TEAMS, CACHE_HOURS, NHL_API_BASE, OLDER_SHOOTING_SEASONS, PREVIOUS_SEASON_INT, SEASON_INT,
    SHOOTING_PRIOR_SHOTS, STANDINGS_PRIOR_GAMES,
)

_CACHE_TTL = CACHE_HOURS * 3600

# Completed seasons never change, so they're kept for the life of the process instead of
# in the shared cache, which refresh-data and settings changes wipe. Only complete
# fetches (every team answered) are kept, so a rate-limited fetch is retried next time.
_completed_seasons: dict[str, list[dict]] = {}


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")


def _teams_for_season(season: str) -> list[str]:
    # Utah's franchise was Arizona before 2024-25
    if season < "20242025":
        return ["ARI" if t == "UTA" else t for t in ALL_TEAMS]
    return ALL_TEAMS


def _fetch_player_stats_for_season(season: str) -> list[dict]:
    all_players = []

    for team in _teams_for_season(season):
        url = f"{NHL_API_BASE}/club-stats/{team}/{season}/2"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for skater in data.get("skaters", []):
            gp = skater.get("gamesPlayed", 0)
            if gp <= 0:
                continue

            first = skater.get("firstName", {}).get("default", "")
            last = skater.get("lastName", {}).get("default", "")
            name = normalize_name(f"{first} {last}").strip()
            pos_code = skater.get("positionCode", "C")
            position = "D" if pos_code == "D" else "F"
            all_players.append({
                "playerId": skater.get("playerId"),
                "player_name": name,
                "team": team,
                "position": position,
                "games_played": gp,
                "goals": skater.get("goals", 0),
                "assists": skater.get("assists", 0),
                "shots": skater.get("shots", 0),
            })

        time.sleep(0.1)

    return all_players


def fetch_all_player_stats(min_gp: int = 10, force_refresh: bool = False) -> list[dict]:
    cache_key = "player_stats"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    current = _fetch_player_stats_for_season(SEASON_INT)
    previous = _completed_season(PREVIOUS_SEASON_INT)
    older = [row for season in OLDER_SHOOTING_SEASONS for row in _completed_season(season)]
    league_pct = _league_shooting_pct(previous or current)
    all_players = _combine_seasons(current, previous, min_gp, league_pct, older)

    set_cached(cache_key, all_players)
    return all_players


def _completed_season(season: str) -> list[dict]:
    rows = _completed_seasons.get(season)
    if rows is None:
        rows = _fetch_player_stats_for_season(season)
        if {r["team"] for r in rows} >= set(_teams_for_season(season)):
            _completed_seasons[season] = rows
    return rows


def _league_shooting_pct(rows: list[dict]) -> dict[str, float]:
    """Goals per shot by position ("F"/"D") across every skater in rows."""
    totals: dict[str, list[int]] = {}
    for r in rows:
        t = totals.setdefault(r["position"], [0, 0])
        t[0] += r["goals"]
        t[1] += r["shots"]
    return {pos: goals / shots for pos, (goals, shots) in totals.items() if shots > 0}


def _regressed_shooting_pct(rows: list[dict], league_pct: dict[str, float]) -> float:
    """
    A player's goals per shot over every season given, with SHOOTING_PRIOR_SHOTS shots at
    their position's league average mixed in. Shooting % is mostly luck over small
    samples (a 6-for-18 start is 33%), while shot volume settles quickly.
    """
    league = league_pct.get(rows[0]["position"], 0.0)
    goals = sum(r["goals"] for r in rows)
    shots = sum(r["shots"] for r in rows)
    return (goals + league * SHOOTING_PRIOR_SHOTS) / (shots + SHOOTING_PRIOR_SHOTS)


def _combine_seasons(
    current: list[dict],
    previous: list[dict],
    min_gp: int,
    league_pct: dict[str, float],
    older: list[dict] = (),
) -> list[dict]:
    """
    Players with min_gp games this season use this season's rates. Players short of
    it (early season, or back from injury) have last season's rates blended in,
    counted as the games they're missing, so its weight fades out as they play and
    is gone at min_gp. That also covers the pre-season, where everyone has 0 games.
    Last season only counts if it reached min_gp itself, so a call-up's hot first
    few games are still excluded.

    Goals are projected as shots per game times a regressed shooting %, rather
    than from raw goals per game. Shooting % also draws on the older seasons, which
    affect nothing else.
    """
    threshold = max(min_gp, 1)

    current_by_player: dict[int, list[dict]] = {}
    for row in current:
        current_by_player.setdefault(row["playerId"], []).append(row)

    previous_by_player: dict[int, list[dict]] = {}
    for row in previous:
        previous_by_player.setdefault(row["playerId"], []).append(row)

    older_by_player: dict[int, list[dict]] = {}
    for row in older:
        older_by_player.setdefault(row["playerId"], []).append(row)

    result = []
    for player_id in current_by_player.keys() | previous_by_player.keys():
        cur_rows = current_by_player.get(player_id, [])
        prev_rows = previous_by_player.get(player_id, [])
        cur_gp = sum(r["games_played"] for r in cur_rows)
        prev_gp = sum(r["games_played"] for r in prev_rows)
        shooting_rows = cur_rows + prev_rows + older_by_player.get(player_id, [])
        shooting_pct = _regressed_shooting_pct(shooting_rows, league_pct)

        if cur_gp >= threshold:
            # Keep per-team stints; projections picks the current team's one
            for r in cur_rows:
                shots_pg = r["shots"] / r["games_played"]
                result.append({
                    **r,
                    "shots_per_game": shots_pg,
                    "goals_per_game": shots_pg * shooting_pct,
                    "assists_per_game": r["assists"] / r["games_played"],
                })
            continue

        if prev_gp < threshold:
            continue

        prior_games = threshold - cur_gp

        def blended(stat: str) -> float:
            cur = sum(r[stat] for r in cur_rows)
            prev_per_game = sum(r[stat] for r in prev_rows) / prev_gp
            return (cur + prev_per_game * prior_games) / threshold

        shots_pg = blended("shots")
        base = max(cur_rows or prev_rows, key=lambda r: r["games_played"])
        result.append({
            **base,
            "games_played": cur_gp,
            "goals": sum(r["goals"] for r in cur_rows),
            "assists": sum(r["assists"] for r in cur_rows),
            "shots": sum(r["shots"] for r in cur_rows),
            "shots_per_game": shots_pg,
            "goals_per_game": shots_pg * shooting_pct,
            "assists_per_game": blended("assists"),
        })

    return result


def fetch_standings(force_refresh: bool = False) -> list[dict]:
    cache_key = "standings"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    resp = requests.get(f"{NHL_API_BASE}/standings/now", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # point_pctg is regressed toward .500 by STANDINGS_PRIOR_GAMES, so a short-sample
    # record can't dominate opponent multipliers or goalie win odds
    teams = []
    for entry in data.get("standings", []):
        abbrev = entry.get("teamAbbrev", {}).get("default", "")
        gp = entry.get("gamesPlayed", 0)
        pctg = entry.get("pointPctg", 0.5)
        regressed = (pctg * gp + 0.5 * STANDINGS_PRIOR_GAMES) / (gp + STANDINGS_PRIOR_GAMES)
        teams.append({"team": abbrev, "point_pctg": regressed, "games_played": gp})

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
