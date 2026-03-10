import pandas as pd
import pulp


def select_best_team(
    df: pd.DataFrame,
    settings: dict,
    locked_players: list[str] | None = None,
    excluded_players: list[str] | None = None,
) -> dict:
    max_cost = settings["max_cost"]
    min_cost = max_cost * (settings["min_cost_pct"] / 100)
    num_forwards = settings["num_forwards"]
    num_defensemen = settings["num_defensemen"]
    num_goalies = settings["num_goalies"]
    max_per_team = settings["max_per_team"]

    locked_players = locked_players or []
    excluded_players = excluded_players or []
    locked_keys = {p.strip().upper() for p in locked_players}
    excluded_keys = {p.strip().upper() for p in excluded_players}

    # Build composite key (name|team|position) for each row
    df["_composite_key"] = (
        df["Player"].str.strip().str.upper()
        + "|"
        + df["Team"]
        + "|"
        + df["Position"]
    )

    prob = pulp.LpProblem("FantasyHockeyTeam", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("player", df.index, cat="Binary")

    # Objective: maximize projected fantasy points
    prob += pulp.lpSum(
        df.loc[i, "proj_fantasy_pts"] * player_vars[i] for i in df.index
    )

    # Salary constraints
    prob += pulp.lpSum(df.loc[i, "pv"] * player_vars[i] for i in df.index) <= max_cost
    prob += pulp.lpSum(df.loc[i, "pv"] * player_vars[i] for i in df.index) >= min_cost

    # Position constraints
    prob += (
        pulp.lpSum(player_vars[i] for i in df[df["Position"] == "F"].index)
        == num_forwards
    )
    prob += (
        pulp.lpSum(player_vars[i] for i in df[df["Position"] == "D"].index)
        == num_defensemen
    )
    prob += (
        pulp.lpSum(player_vars[i] for i in df[df["Position"] == "G"].index)
        == num_goalies
    )

    # Max players per team
    for team in df["Team"].unique():
        team_idx = df[df["Team"] == team].index
        prob += pulp.lpSum(player_vars[i] for i in team_idx) <= max_per_team

    # Max 1 defenseman per team
    for team in df["Team"].unique():
        d_idx = df[(df["Team"] == team) & (df["Position"] == "D")].index
        prob += pulp.lpSum(player_vars[i] for i in d_idx) <= 1

    # Locked players must be selected
    for i in df.index:
        key = df.loc[i, "_composite_key"]
        if key in locked_keys:
            prob += player_vars[i] == 1

    # Excluded players cannot be selected
    for i in df.index:
        key = df.loc[i, "_composite_key"]
        if key in excluded_keys:
            prob += player_vars[i] == 0

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != pulp.constants.LpStatusOptimal:
        return {
            "feasible": False,
            "message": "No feasible solution found. Try relaxing constraints (increase salary cap, reduce roster requirements, or remove locked players).",
            "players": [],
            "totalPoints": 0,
            "totalSalary": 0,
        }

    selected = [i for i in df.index if player_vars[i].varValue == 1]
    lineup = df.loc[selected]

    players = []
    for _, row in lineup.iterrows():
        players.append(
            {
                "name": row["Player"],
                "team": row["Team"],
                "position": row["Position"],
                "gamesThisWeek": int(row["games_this_week"]),
                "projFantasyPts": round(float(row["proj_fantasy_pts"]), 2),
                "salary": round(float(row["pv"]), 2),
                "injured": bool(row.get("Injured", False)),
            }
        )

    # Sort by position order (G, D, F) then by projected points desc
    pos_order = {"G": 0, "D": 1, "F": 2}
    players.sort(key=lambda p: (pos_order.get(p["position"], 3), -p["projFantasyPts"]))

    return {
        "feasible": True,
        "players": players,
        "totalPoints": round(float(lineup["proj_fantasy_pts"].sum()), 2),
        "totalSalary": round(float(lineup["pv"].sum()), 2),
    }
