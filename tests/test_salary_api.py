from unittest.mock import patch, MagicMock
from server.services.salary_api import fetch_players, trigger_salary_scrape, trigger_injury_scrape
from server.cache import clear_cache


MOCK_API_RESPONSE = [
    {
        "nhlId": 8477934,
        "name": "Leon Draisaitl",
        "team": "EDM",
        "position": "C",
        "salary": 14000000,
        "injury": None,
    },
    {
        "nhlId": 8478402,
        "name": "Connor McDavid",
        "team": "EDM",
        "position": "C",
        "salary": 12500000,
        "injury": {"status": "Day to Day", "description": "Upper Body"},
    },
]


@patch("server.services.salary_api.requests.get")
def test_fetch_players_returns_list(mock_get):
    clear_cache()
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = fetch_players()
    assert len(result) == 2
    assert result[0]["nhlId"] == 8477934
    assert result[0]["name"] == "Leon Draisaitl"


@patch("server.services.salary_api.requests.get")
def test_fetch_players_uses_cache(mock_get):
    clear_cache()
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    fetch_players()
    fetch_players()
    assert mock_get.call_count == 1  # Second call uses cache


@patch("server.services.salary_api.requests.get")
def test_fetch_players_force_refresh(mock_get):
    clear_cache()
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    fetch_players()
    fetch_players(force_refresh=True)
    assert mock_get.call_count == 2


@patch("server.services.salary_api.requests.post")
def test_trigger_salary_scrape(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": "Scrape complete"}
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = trigger_salary_scrape()
    assert result == {"message": "Scrape complete"}
    mock_post.assert_called_once()


@patch("server.services.salary_api.requests.post")
def test_trigger_injury_scrape(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": "Scrape complete"}
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = trigger_injury_scrape()
    assert result == {"message": "Scrape complete"}
    mock_post.assert_called_once()
