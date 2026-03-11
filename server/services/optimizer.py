import pulp


def select_best_team(
    players: list[dict],
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

    locked_keys = {p.strip().upper() for p in (locked_players or [])}
    excluded_keys = {p.strip().upper() for p in (excluded_players or [])}

    # Build composite key lookup (without mutating input)
    keys = {i: f"{p['name'].strip().upper()}|{p['team']}|{p['position']}" for i, p in enumerate(players)}

    prob = pulp.LpProblem("FantasyHockeyTeam", pulp.LpMaximize)
    player_vars = {i: pulp.LpVariable(f"player_{i}", cat="Binary") for i in range(len(players))}

    # Objective: maximize projected fantasy points
    prob += pulp.lpSum(players[i]["proj_fantasy_pts"] * player_vars[i] for i in range(len(players)))

    # Salary constraints
    prob += pulp.lpSum(players[i]["pv"] * player_vars[i] for i in range(len(players))) <= max_cost
    prob += pulp.lpSum(players[i]["pv"] * player_vars[i] for i in range(len(players))) >= min_cost

    # Position constraints
    prob += pulp.lpSum(player_vars[i] for i in range(len(players)) if players[i]["position"] == "F") == num_forwards
    prob += pulp.lpSum(player_vars[i] for i in range(len(players)) if players[i]["position"] == "D") == num_defensemen
    prob += pulp.lpSum(player_vars[i] for i in range(len(players)) if players[i]["position"] == "G") == num_goalies

    # Max players per team
    teams = {p["team"] for p in players}
    for team in teams:
        team_idx = [i for i in range(len(players)) if players[i]["team"] == team]
        prob += pulp.lpSum(player_vars[i] for i in team_idx) <= max_per_team

    # Max 1 defenseman per team
    for team in teams:
        d_idx = [i for i in range(len(players)) if players[i]["team"] == team and players[i]["position"] == "D"]
        prob += pulp.lpSum(player_vars[i] for i in d_idx) <= 1

    # Locked players must be selected
    for i in range(len(players)):
        if keys[i] in locked_keys:
            prob += player_vars[i] == 1

    # Excluded players cannot be selected
    for i in range(len(players)):
        if keys[i] in excluded_keys:
            prob += player_vars[i] == 0

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != pulp.constants.LpStatusOptimal:
        return {
            "feasible": False,
            "message": "No feasible solution found. Try relaxing constraints.",
            "players": [],
            "totalPoints": 0,
            "totalSalary": 0,
        }

    selected = [i for i in range(len(players)) if player_vars[i].varValue == 1]
    lineup = [players[i] for i in selected]

    result_players = []
    for p in lineup:
        result_players.append({
            "name": p["name"],
            "team": p["team"],
            "position": p["position"],
            "gamesThisWeek": int(p["games_this_week"]),
            "projFantasyPts": round(float(p["proj_fantasy_pts"]), 2),
            "salary": round(float(p["pv"]), 2),
            "injured": bool(p.get("injured", False)),
        })

    pos_order = {"G": 0, "D": 1, "F": 2}
    result_players.sort(key=lambda p: (pos_order.get(p["position"], 3), -p["projFantasyPts"]))

    total_pts = sum(p["projFantasyPts"] for p in result_players)
    total_sal = sum(p["salary"] for p in result_players)

    return {
        "feasible": True,
        "players": result_players,
        "totalPoints": round(total_pts, 2),
        "totalSalary": round(total_sal, 2),
    }
