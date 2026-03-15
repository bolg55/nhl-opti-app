from server.services.nhl_api import (
    calculate_multipliers,
    fetch_all_player_stats,
    fetch_standings,
    fetch_weekly_schedule,
)
from server.services.salary_api import fetch_players


def _normalize_position(pos: str) -> str:
    if pos in ("C", "L", "R", "LW", "RW"):
        return "F"
    return pos  # "D" and "G" stay as-is


def calculate_projections(
    stats: list[dict],
    games_count: dict[str, int],
    multipliers: dict[str, float],
) -> list[dict]:
    result = []
    for p in stats:
        games = games_count.get(p["team"], 0)
        mult = multipliers.get(p["team"], 1.0)
        proj = (p["goals_per_game"] * 2 + p["assists_per_game"] * 1) * games * mult
        result.append({
            **p,
            "games_this_week": games,
            "multiplier": mult,
            "proj_fantasy_pts": proj,
        })
    return result


def estimate_team_goaltending_points(
    multipliers: dict[str, float],
    games_count: dict[str, int],
    standings: list[dict],
    win_points: float = 2,
    ot_loss_points: float = 1,
    shutout_bonus: float = 2,
    avg_ot_loss_freq: float = 0.1,
    avg_shutout_freq: float = 0.05,
) -> dict[str, tuple[float, int]]:
    pctg_lookup = {s["team"]: s["point_pctg"] for s in standings}
    goaltending_data = {}

    for team, multiplier in multipliers.items():
        games = games_count.get(team, 0)
        own_pctg = pctg_lookup.get(team, 0.5)
        win_prob = min(own_pctg * multiplier, 0.9)

        projected_wins = games * win_prob
        projected_ot_losses = games * avg_ot_loss_freq
        projected_shutouts = games * avg_shutout_freq

        total_points = (
            projected_wins * win_points
            + projected_ot_losses * ot_loss_points
            + projected_shutouts * shutout_bonus
        )
        goaltending_data[team] = (total_points, games)

    return goaltending_data


def build_optimizer_input(
    start_date=None,
    force_refresh: bool = False,
    min_gp: int = 10,
) -> list[dict]:
    # 1. Fetch data from all sources
    stats = fetch_all_player_stats(min_gp=min_gp, force_refresh=force_refresh)
    standings = fetch_standings(force_refresh=force_refresh)
    games_count, opponents = fetch_weekly_schedule(start_date)
    multipliers = calculate_multipliers(standings, opponents)
    salary_players = fetch_players(force_refresh=force_refresh)

    # 2. Build salary lookup by nhlId
    salary_lookup = {p["nhlId"]: p for p in salary_players}

    # 3. Calculate projections for stats players
    projected = calculate_projections(stats, games_count, multipliers)

    # 4. Join stats with salary on playerId == nhlId
    result = []
    for p in projected:
        if p["games_this_week"] <= 0:
            continue
        salary_info = salary_lookup.get(p["playerId"])
        if salary_info is None or salary_info["salary"] is None:
            continue  # No salary data — skip player

        injury = salary_info["injury"]
        injured = injury is not None
        position = _normalize_position(salary_info["position"])

        result.append({
            "name": salary_info["name"],
            "team": p["team"],
            "position": position,
            "pv": salary_info["salary"] / 1_000_000,
            "games_this_week": p["games_this_week"],
            "multiplier": p["multiplier"],
            "proj_fantasy_pts": 0 if injured else p["proj_fantasy_pts"],
            "goals_per_game": p["goals_per_game"],
            "assists_per_game": p["assists_per_game"],
            "injured": injured,
            "injury_description": injury["description"] if injured else None,
        })

    # 5. Add goalie rows
    goalie_data = estimate_team_goaltending_points(multipliers, games_count, standings)
    for team, (pts, games) in goalie_data.items():
        if games <= 0:
            continue
        result.append({
            "name": f"{team} Goalie",
            "team": team,
            "position": "G",
            "pv": 0,
            "games_this_week": games,
            "multiplier": multipliers.get(team, 1.0),
            "proj_fantasy_pts": pts,
            "goals_per_game": 0,
            "assists_per_game": 0,
            "injured": False,
        })

    return result
