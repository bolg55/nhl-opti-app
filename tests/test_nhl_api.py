from unittest.mock import MagicMock, patch

import pytest

from server.cache import clear_cache
from server.constants import (
    ALL_TEAMS, PREVIOUS_SEASON_INT, SEASON_INT, SHOOTING_PRIOR_SHOTS, STANDINGS_PRIOR_GAMES,
)
from server.services.nhl_api import fetch_all_player_stats, fetch_standings

EMPTY_RESPONSE = {"skaters": [], "goalies": []}

PREVIOUS_SEASON_SKATER = {
    "playerId": 8477934,
    "firstName": {"default": "Leon"},
    "lastName": {"default": "Draisaitl"},
    "positionCode": "C",
    "gamesPlayed": 82,
    "goals": 40,
    "assists": 50,
}


def _mock_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_falls_back_to_previous_season_when_current_season_has_no_stats():
    clear_cache()

    def fake_get(url, timeout=10):
        if f"/{SEASON_INT}/" in url:
            return _mock_response(EMPTY_RESPONSE)
        if f"/{PREVIOUS_SEASON_INT}/" in url and url.endswith(f"/EDM/{PREVIOUS_SEASON_INT}/2"):
            return _mock_response({"skaters": [PREVIOUS_SEASON_SKATER], "goalies": []})
        return _mock_response(EMPTY_RESPONSE)

    with patch("server.services.nhl_api.requests.get", side_effect=fake_get):
        players = fetch_all_player_stats(min_gp=10, force_refresh=True)

    assert len(players) == 1
    assert players[0]["player_name"] == "Leon Draisaitl"
    assert players[0]["team"] == "EDM"


def _skater(player_id, gp, goals=0, assists=0, shots=0, pos="C"):
    return {
        "playerId": player_id,
        "firstName": {"default": "Test"},
        "lastName": {"default": f"Player{player_id}"},
        "positionCode": pos,
        "gamesPlayed": gp,
        "goals": goals,
        "assists": assists,
        "shots": shots,
    }


def _fetch_with(current: dict, previous: dict, min_gp=10):
    """current/previous map team abbrev -> list of skater payloads for that season."""
    clear_cache()

    def fake_get(url, timeout=10):
        for season, by_team in ((SEASON_INT, current), (PREVIOUS_SEASON_INT, previous)):
            for team, skaters in by_team.items():
                if url.endswith(f"/{team}/{season}/2"):
                    return _mock_response({"skaters": skaters, "goalies": []})
        return _mock_response(EMPTY_RESPONSE)

    with patch("server.services.nhl_api.requests.get", side_effect=fake_get), \
            patch("server.services.nhl_api.time.sleep"):
        return {p["playerId"]: p for p in fetch_all_player_stats(min_gp=min_gp, force_refresh=True)}


def test_early_season_player_blends_in_previous_season_rates():
    # 4 games this season, so last season fills the other 6 of the 10-game minimum
    players = _fetch_with(
        current={"EDM": [_skater(1, gp=4, assists=2, shots=12)]},
        previous={"EDM": [_skater(1, gp=80, assists=80, shots=160)]},
    )

    assert list(players) == [1]
    assert players[1]["shots_per_game"] == pytest.approx((12 + 2.0 * 6) / 10)
    assert players[1]["assists_per_game"] == pytest.approx((2 + 1.0 * 6) / 10)
    assert players[1]["games_played"] == 4


@pytest.mark.parametrize("previous", [{}, {"EDM": [_skater(1, gp=5, goals=5, assists=5, shots=10)]}])
def test_hot_start_without_a_full_previous_season_is_excluded(previous):
    # A call-up's big first few games shouldn't count on their own
    players = _fetch_with(
        current={"EDM": [_skater(1, gp=3, goals=4, assists=3, shots=8)]},
        previous=previous,
    )

    assert players == {}


def test_previous_season_stints_are_combined_for_traded_players():
    players = _fetch_with(
        current={"TOR": [_skater(1, gp=2, shots=2)]},
        previous={
            "EDM": [_skater(1, gp=40, shots=40)],
            "TOR": [_skater(1, gp=40, shots=120)],
        },
    )

    assert list(players) == [1]
    assert players[1]["team"] == "TOR"
    assert players[1]["shots_per_game"] == pytest.approx((2 + 2.0 * 8) / 10)


def test_player_at_minimum_games_uses_only_current_season():
    players = _fetch_with(
        current={"EDM": [_skater(1, gp=10, assists=10, shots=30)]},
        previous={"EDM": [_skater(1, gp=82, shots=82)]},
    )

    assert players[1]["shots_per_game"] == pytest.approx(3.0)
    assert players[1]["assists_per_game"] == pytest.approx(1.0)


def test_zero_minimum_still_falls_back_before_the_season_starts():
    players = _fetch_with(
        current={},
        previous={"EDM": [_skater(1, gp=82, shots=164)]},
        min_gp=0,
    )

    assert players[1]["shots_per_game"] == pytest.approx(2.0)


def test_goals_come_from_shot_rate_times_regressed_shooting_pct():
    # League forwards shot 12% last season (player 2 sets the average with player 1);
    # player 1's hot 33% start is pulled back toward it
    k = SHOOTING_PRIOR_SHOTS
    players = _fetch_with(
        current={"EDM": [_skater(1, gp=10, goals=10, shots=30)]},
        previous={"EDM": [_skater(1, gp=80, goals=20, shots=200), _skater(2, gp=80, goals=100, shots=800)]},
    )

    shooting_pct = (10 + 20 + 0.12 * k) / (30 + 200 + k)
    assert players[1]["goals_per_game"] == pytest.approx(3.0 * shooting_pct)


def test_defensemen_regress_toward_the_defenseman_average():
    # Forwards shoot 15%, defensemen 5%; a defenseman with no track record gets the D average
    players = _fetch_with(
        current={"EDM": [_skater(1, gp=10, shots=20, pos="D")]},
        previous={"EDM": [_skater(2, gp=80, goals=30, shots=200), _skater(3, gp=80, goals=5, shots=100, pos="D")]},
    )

    assert players[1]["goals_per_game"] == pytest.approx(2.0 * (0.05 * SHOOTING_PRIOR_SHOTS) / (20 + SHOOTING_PRIOR_SHOTS))


def test_uses_current_season_stats_when_available():
    clear_cache()
    current_season_skater = {**PREVIOUS_SEASON_SKATER, "gamesPlayed": 5}

    def fake_get(url, timeout=10):
        if url.endswith(f"/EDM/{SEASON_INT}/2"):
            return _mock_response({"skaters": [current_season_skater], "goalies": []})
        return _mock_response(EMPTY_RESPONSE)

    with patch("server.services.nhl_api.requests.get", side_effect=fake_get):
        players = fetch_all_player_stats(min_gp=1, force_refresh=True)

    assert len(players) == 1
    assert players[0]["games_played"] == 5


def _standings_with(*teams):
    clear_cache()
    payload = {"standings": [
        {"teamAbbrev": {"default": t}, "gamesPlayed": gp, "pointPctg": pctg} for t, gp, pctg in teams
    ]}
    with patch("server.services.nhl_api.requests.get", return_value=_mock_response(payload)):
        return {s["team"]: s["point_pctg"] for s in fetch_standings(force_refresh=True)}


def test_early_season_points_pct_is_pulled_toward_500():
    k = STANDINGS_PRIOR_GAMES
    pctg = _standings_with(("LAK", 6, 1 / 6))
    assert pctg["LAK"] == pytest.approx((1 / 6 * 6 + 0.5 * k) / (6 + k))


def test_points_pct_is_500_before_a_team_has_played():
    assert _standings_with(("LAK", 0, 0.0))["LAK"] == pytest.approx(0.5)


def test_bigger_samples_keep_more_of_their_record():
    pctg = _standings_with(("EARLY", 6, 0.25), ("LATE", 70, 0.25))
    assert pctg["EARLY"] > pctg["LATE"] > 0.25
