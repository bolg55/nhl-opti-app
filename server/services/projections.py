import pandas as pd

from server.services.injuries import get_current_injuries
from server.services.nhl_api import (
    calculate_multipliers,
    fetch_all_player_stats,
    fetch_standings,
    fetch_weekly_schedule,
)
from server.services.salary import get_salary_data


def calculate_projections(
    stats_df: pd.DataFrame,
    games_count: dict[str, int],
    multipliers: dict[str, float],
) -> pd.DataFrame:
    df = stats_df.copy()
    df["games_this_week"] = df["team"].map(games_count).fillna(0).astype(int)
    df["multiplier"] = df["team"].map(multipliers).fillna(1.0)
    df["proj_fantasy_pts"] = (
        (df["goals_per_game"] * 2 + df["assists_per_game"] * 1)
        * df["games_this_week"]
        * df["multiplier"]
    )
    df["player_key"] = df["player_name"].str.strip().str.upper()
    df["position_key"] = df["position"]
    return df


def estimate_team_goaltending_points(
    multipliers: dict[str, float],
    games_count: dict[str, int],
    standings_df: pd.DataFrame,
    win_points: float = 2,
    ot_loss_points: float = 1,
    shutout_bonus: float = 2,
    avg_ot_loss_freq: float = 0.1,
    avg_shutout_freq: float = 0.05,
) -> dict[str, tuple[float, int]]:
    pctg_lookup = dict(zip(standings_df["team"], standings_df["point_pctg"]))
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


def _last_name_key(name: str) -> str:
    parts = name.strip().split()
    return parts[-1].upper() if parts else ""


def build_optimizer_input(
    start_date=None,
    force_refresh: bool = False,
    min_gp: int = 10,
) -> pd.DataFrame:
    # 1. Player stats
    stats_df = fetch_all_player_stats(min_gp=min_gp, force_refresh=force_refresh)

    # 2. Standings
    standings_df = fetch_standings(force_refresh=force_refresh)

    # 3. Schedule (always live)
    games_count, opponents = fetch_weekly_schedule(start_date)

    # 4. Multipliers
    multipliers = calculate_multipliers(standings_df, opponents)

    # 5. Projections
    proj_df = calculate_projections(stats_df, games_count, multipliers)

    # 6. Salary data from DB
    salary_df = get_salary_data()
    if salary_df.empty:
        raise ValueError("No salary data loaded. Upload a salary CSV first.")

    # Rename columns for merge compatibility
    salary_df = salary_df.rename(
        columns={"player": "Player", "team": "Team", "position": "Position"}
    )
    salary_df["player_key"] = salary_df["Player"].str.strip().str.upper()

    # 7. Merge stats with salary (match on uppercase name + team + position)
    proj_cols = [
        "player_key",
        "team",
        "position_key",
        "games_this_week",
        "multiplier",
        "proj_fantasy_pts",
        "goals_per_game",
        "assists_per_game",
    ]
    merged = salary_df.merge(
        proj_df[proj_cols],
        left_on=["player_key", "Team", "Position"],
        right_on=["player_key", "team", "position_key"],
        how="left",
    )

    # Fallback: last name + team match for nickname mismatches
    unmatched_idx = merged[merged["proj_fantasy_pts"].isna()].index
    if len(unmatched_idx) > 0:
        merged["last_name_key"] = merged["Player"].apply(_last_name_key)
        proj_df["last_name_key"] = proj_df["player_name"].apply(_last_name_key)

        api_counts = proj_df.groupby(["last_name_key", "team", "position"]).size()
        unique_api = set(api_counts[api_counts == 1].index)

        salary_counts = merged.groupby(["last_name_key", "Team", "Position"]).size()
        unique_salary = set(salary_counts[salary_counts == 1].index)

        fb_lookup = {}
        for _, row in proj_df.iterrows():
            key = (row["last_name_key"], row["team"], row["position"])
            if key in unique_api:
                fb_lookup[key] = row

        for idx in unmatched_idx:
            row = merged.loc[idx]
            key = (row["last_name_key"], row["Team"], row["Position"])
            if key in unique_api and key in unique_salary and key in fb_lookup:
                api_row = fb_lookup[key]
                merged.loc[idx, "games_this_week"] = api_row["games_this_week"]
                merged.loc[idx, "multiplier"] = api_row["multiplier"]
                merged.loc[idx, "proj_fantasy_pts"] = api_row["proj_fantasy_pts"]
                merged.loc[idx, "goals_per_game"] = api_row["goals_per_game"]
                merged.loc[idx, "assists_per_game"] = api_row["assists_per_game"]

        merged.drop(columns=["last_name_key"], inplace=True)

    # Drop extra merge columns
    merged.drop(columns=["team", "position_key"], inplace=True, errors="ignore")

    merged["proj_fantasy_pts"] = merged["proj_fantasy_pts"].fillna(0)
    merged["games_this_week"] = merged["games_this_week"].fillna(0).astype(int)

    # 8. Injuries
    injuries_df = get_current_injuries()
    if not injuries_df.empty:
        injured_keys = set(
            injuries_df["Player"].str.strip().str.upper() + "|" + injuries_df["Team"]
        )
        merged["Injured"] = (
            merged["player_key"] + "|" + merged["Team"]
        ).isin(injured_keys)
        merged.loc[merged["Injured"], "proj_fantasy_pts"] = 0
    else:
        merged["Injured"] = False

    # 9. Goalie rows
    goalie_data = estimate_team_goaltending_points(
        multipliers, games_count, standings_df
    )
    goalie_rows = []
    for team, (pts, games) in goalie_data.items():
        goalie_rows.append(
            {
                "Player": f"{team} Goalie",
                "Team": team,
                "Position": "G",
                "pv": 0,
                "proj_fantasy_pts": pts,
                "games_this_week": games,
                "Injured": False,
                "player_key": f"{team} GOALIE",
            }
        )
    goalie_df = pd.DataFrame(goalie_rows)

    result = pd.concat([merged, goalie_df], ignore_index=True)
    result = result[result["games_this_week"] > 0].copy()

    return result
