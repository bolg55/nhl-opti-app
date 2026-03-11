from server.services.optimizer import select_best_team

MOCK_PLAYERS = [
    {"name": "Player F1", "team": "EDM", "position": "F", "pv": 8.0, "proj_fantasy_pts": 10.0, "games_this_week": 3, "injured": False},
    {"name": "Player F2", "team": "CGY", "position": "F", "pv": 7.0, "proj_fantasy_pts": 9.0, "games_this_week": 3, "injured": False},
    {"name": "Player F3", "team": "TOR", "position": "F", "pv": 6.0, "proj_fantasy_pts": 8.0, "games_this_week": 3, "injured": False},
    {"name": "Player F4", "team": "MTL", "position": "F", "pv": 5.5, "proj_fantasy_pts": 7.0, "games_this_week": 3, "injured": False},
    {"name": "Player F5", "team": "VAN", "position": "F", "pv": 5.0, "proj_fantasy_pts": 6.0, "games_this_week": 3, "injured": False},
    {"name": "Player F6", "team": "WPG", "position": "F", "pv": 4.5, "proj_fantasy_pts": 5.0, "games_this_week": 3, "injured": False},
    {"name": "Player F7", "team": "OTT", "position": "F", "pv": 4.0, "proj_fantasy_pts": 4.0, "games_this_week": 3, "injured": False},
    {"name": "Player D1", "team": "EDM", "position": "D", "pv": 7.0, "proj_fantasy_pts": 6.0, "games_this_week": 3, "injured": False},
    {"name": "Player D2", "team": "CGY", "position": "D", "pv": 6.0, "proj_fantasy_pts": 5.0, "games_this_week": 3, "injured": False},
    {"name": "Player D3", "team": "TOR", "position": "D", "pv": 5.0, "proj_fantasy_pts": 4.0, "games_this_week": 3, "injured": False},
    {"name": "Player D4", "team": "MTL", "position": "D", "pv": 4.0, "proj_fantasy_pts": 3.0, "games_this_week": 3, "injured": False},
    {"name": "EDM Goalie", "team": "EDM", "position": "G", "pv": 0, "proj_fantasy_pts": 5.0, "games_this_week": 3, "injured": False},
    {"name": "CGY Goalie", "team": "CGY", "position": "G", "pv": 0, "proj_fantasy_pts": 4.0, "games_this_week": 3, "injured": False},
]

SETTINGS = {
    "max_cost": 70.5,
    "min_cost_pct": 0,  # Relax for test
    "num_forwards": 6,
    "num_defensemen": 4,
    "num_goalies": 2,
    "max_per_team": 5,
}


def test_select_best_team_feasible():
    result = select_best_team(MOCK_PLAYERS, SETTINGS)
    assert result["feasible"] is True
    assert len(result["players"]) == 12  # 6F + 4D + 2G
    assert result["totalPoints"] > 0
    assert result["totalSalary"] > 0


def test_select_best_team_respects_exclude():
    result = select_best_team(
        MOCK_PLAYERS, SETTINGS,
        excluded_players=["Player F1|EDM|F"]
    )
    assert result["feasible"] is True
    names = {p["name"] for p in result["players"]}
    assert "Player F1" not in names


def test_select_best_team_respects_lock():
    result = select_best_team(
        MOCK_PLAYERS, SETTINGS,
        locked_players=["Player F6|WPG|F"]
    )
    assert result["feasible"] is True
    names = {p["name"] for p in result["players"]}
    assert "Player F6" in names
