from unittest.mock import patch
from server.services.projections import build_optimizer_input


MOCK_STATS = [
    {
        "playerId": 8477934,
        "player_name": "Leon Draisaitl",
        "team": "EDM",
        "position": "F",
        "games_played": 50,
        "goals": 30,
        "assists": 40,
        "goals_per_game": 0.6,
        "assists_per_game": 0.8,
    },
]

MOCK_STANDINGS = [
    {"team": "EDM", "point_pctg": 0.6},
    {"team": "CGY", "point_pctg": 0.4},
]

MOCK_SALARY_PLAYERS = [
    {
        "nhlId": 8477934,
        "name": "Leon Draisaitl",
        "team": "EDM",
        "position": "C",
        "salary": 14000000,
        "injury": None,
    },
    {
        "nhlId": 9999999,
        "name": "Unknown Player",
        "team": "EDM",
        "position": "C",
        "salary": 900000,
        "injury": None,
    },
]

MOCK_GAMES_COUNT = {"EDM": 3}
MOCK_OPPONENTS = {"EDM": ["CGY", "CGY", "CGY"]}


@patch("server.services.projections.fetch_all_player_stats", return_value=MOCK_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch("server.services.projections.fetch_weekly_schedule", return_value=(MOCK_GAMES_COUNT, MOCK_OPPONENTS))
@patch("server.services.projections.fetch_players", return_value=MOCK_SALARY_PLAYERS)
def test_build_optimizer_input_joins_on_id(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    # Should have Draisaitl (matched) + goalie rows, but not Unknown Player (no stats)
    skaters = [p for p in result if p["position"] != "G"]
    assert len(skaters) == 1
    assert skaters[0]["name"] == "Leon Draisaitl"
    assert skaters[0]["pv"] == 14.0  # 14000000 / 1_000_000
    assert skaters[0]["proj_fantasy_pts"] > 0


@patch("server.services.projections.fetch_all_player_stats", return_value=MOCK_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch("server.services.projections.fetch_weekly_schedule", return_value=(MOCK_GAMES_COUNT, MOCK_OPPONENTS))
@patch("server.services.projections.fetch_players", return_value=[
    {
        "nhlId": 8477934,
        "name": "Leon Draisaitl",
        "team": "EDM",
        "position": "C",
        "salary": 14000000,
        "injury": {"status": "Week to Week", "description": "Lower Body"},
    },
])
def test_injured_player_zeroed_out(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    skaters = [p for p in result if p["position"] != "G"]
    assert len(skaters) == 1
    assert skaters[0]["injured"] is True
    assert skaters[0]["proj_fantasy_pts"] == 0


@patch("server.services.projections.fetch_all_player_stats", return_value=MOCK_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch("server.services.projections.fetch_weekly_schedule", return_value=(MOCK_GAMES_COUNT, MOCK_OPPONENTS))
@patch("server.services.projections.fetch_players", return_value=MOCK_SALARY_PLAYERS)
def test_goalie_rows_included(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    goalies = [p for p in result if p["position"] == "G"]
    assert len(goalies) >= 1
    edm_goalie = [g for g in goalies if g["team"] == "EDM"]
    assert len(edm_goalie) == 1
    assert edm_goalie[0]["pv"] == 0
    assert edm_goalie[0]["name"] == "EDM Goalie"


@patch("server.services.projections.fetch_all_player_stats", return_value=MOCK_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch("server.services.projections.fetch_weekly_schedule", return_value=(MOCK_GAMES_COUNT, MOCK_OPPONENTS))
@patch("server.services.projections.fetch_players", return_value=MOCK_SALARY_PLAYERS)
def test_position_normalized_to_f(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    skaters = [p for p in result if p["position"] != "G"]
    # Draisaitl is "C" in salary API but should be "F" in output
    assert skaters[0]["position"] == "F"
