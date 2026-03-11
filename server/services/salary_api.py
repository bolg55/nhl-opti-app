import os

import requests

from server.cache import get_cached, set_cached, clear_cache

_BASE_URL = os.environ.get("NHL_SALARY_API_URL", "https://nhl-salary-api-production.up.railway.app")
_TOKEN = os.environ.get("NHL_SALARY_API_TOKEN", "")

_CACHE_KEY = "salary_api_players"
_CACHE_TTL = 1800  # 30 minutes


def _headers() -> dict:
    return {"Authorization": f"Bearer {_TOKEN}"}


def fetch_players(force_refresh: bool = False) -> list[dict]:
    if not force_refresh:
        cached = get_cached(_CACHE_KEY, _CACHE_TTL)
        if cached is not None:
            return cached

    resp = requests.get(f"{_BASE_URL}/players", headers=_headers(), timeout=15)
    resp.raise_for_status()
    players = resp.json()
    set_cached(_CACHE_KEY, players)
    return players


def trigger_salary_scrape() -> dict:
    resp = requests.post(f"{_BASE_URL}/admin/scrape/players", headers=_headers(), timeout=60)
    resp.raise_for_status()
    clear_cache(_CACHE_KEY)
    return resp.json()


def trigger_injury_scrape() -> dict:
    resp = requests.post(f"{_BASE_URL}/admin/scrape/injuries", headers=_headers(), timeout=60)
    resp.raise_for_status()
    clear_cache(_CACHE_KEY)
    return resp.json()
