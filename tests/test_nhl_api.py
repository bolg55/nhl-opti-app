from unittest.mock import MagicMock, patch

from server.cache import clear_cache
from server.constants import ALL_TEAMS, PREVIOUS_SEASON_INT, SEASON_INT
from server.services.nhl_api import fetch_all_player_stats

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
