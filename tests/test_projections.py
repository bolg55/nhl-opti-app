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


TRADED_PLAYER_STATS = [
    {
        "playerId": 8480800,
        "player_name": "Quinn Hughes",
        "team": "VAN",
        "position": "D",
        "games_played": 26,
        "goals": 2,
        "assists": 21,
        "goals_per_game": 2 / 26,
        "assists_per_game": 21 / 26,
    },
    {
        "playerId": 8480800,
        "player_name": "Quinn Hughes",
        "team": "MIN",
        "position": "D",
        "games_played": 48,
        "goals": 10,
        "assists": 30,
        "goals_per_game": 10 / 48,
        "assists_per_game": 30 / 48,
    },
]

TRADED_PLAYER_SALARY = [
    {
        "nhlId": 8480800,
        "name": "Quinn Hughes",
        "team": "MIN",
        "position": "D",
        "salary": 7850000,
        "injury": None,
    },
]

TRADED_PLAYER_GAMES_COUNT = {"VAN": 3, "MIN": 3}
TRADED_PLAYER_OPPONENTS = {"VAN": ["CGY", "CGY", "CGY"], "MIN": ["CGY", "CGY", "CGY"]}


@patch("server.services.projections.fetch_all_player_stats", return_value=TRADED_PLAYER_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch(
    "server.services.projections.fetch_weekly_schedule",
    return_value=(TRADED_PLAYER_GAMES_COUNT, TRADED_PLAYER_OPPONENTS),
)
@patch("server.services.projections.fetch_players", return_value=TRADED_PLAYER_SALARY)
def test_traded_player_not_duplicated(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    hughes_rows = [p for p in result if p["name"] == "Quinn Hughes"]
    assert len(hughes_rows) == 1
    # Current team (per salary source) should win over the stale stats-team stint
    assert hughes_rows[0]["team"] == "MIN"


OFFSEASON_TRADE_STATS = [
    {
        "playerId": 8480801,
        "player_name": "Brady Tkachuk",
        "team": "OTT",  # last season's team — trade happened over the offseason
        "position": "F",
        "games_played": 60,
        "goals": 25,
        "assists": 30,
        "goals_per_game": 25 / 60,
        "assists_per_game": 30 / 60,
    },
]

OFFSEASON_TRADE_SALARY = [
    {
        "nhlId": 8480801,
        "name": "Brady Tkachuk",
        "team": "FLA",  # current team per the live salary/roster source
        "position": "LW",
        "salary": 9500000,
        "injury": None,
    },
]

# FLA has games this week, OTT does not — the season-stats team (OTT) has no
# games, so a player wrongly attributed to OTT would get filtered out entirely.
OFFSEASON_TRADE_GAMES_COUNT = {"FLA": 4}
OFFSEASON_TRADE_OPPONENTS = {"FLA": ["TBL", "TBL", "CAR", "CAR"]}


@patch("server.services.projections.fetch_all_player_stats", return_value=OFFSEASON_TRADE_STATS)
@patch("server.services.projections.fetch_standings", return_value=MOCK_STANDINGS)
@patch(
    "server.services.projections.fetch_weekly_schedule",
    return_value=(OFFSEASON_TRADE_GAMES_COUNT, OFFSEASON_TRADE_OPPONENTS),
)
@patch("server.services.projections.fetch_players", return_value=OFFSEASON_TRADE_SALARY)
def test_offseason_trade_uses_current_team(mock_salary, mock_sched, mock_stand, mock_stats):
    result = build_optimizer_input()
    tkachuk_rows = [p for p in result if p["name"] == "Brady Tkachuk"]
    assert len(tkachuk_rows) == 1
    # Should be attributed to FLA (current team), not OTT (last season's stats team)
    assert tkachuk_rows[0]["team"] == "FLA"
    assert tkachuk_rows[0]["games_this_week"] == 4
    # His actual production from last season (with OTT) must still drive the projection
    assert tkachuk_rows[0]["goals_per_game"] == 25 / 60
    assert tkachuk_rows[0]["assists_per_game"] == 30 / 60
    assert tkachuk_rows[0]["proj_fantasy_pts"] > 0
