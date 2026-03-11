# API Integration Simplification — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CBS Sports scraping and CSV salary upload with the unified nhl-salary-api, drop SQLite for in-memory cache + JSON settings, and join player data on NHL IDs instead of fuzzy name matching.

**Architecture:** Single salary API call replaces injury scraping + CSV upload. In-memory TTL cache replaces SQLite for NHL API data. JSON file on persistent volume replaces SQLite for optimizer settings. All player matching uses numeric `playerId == nhlId` instead of name strings.

**Tech Stack:** FastAPI, PuLP, requests, React/TypeScript/Tailwind/shadcn

**Spec:** `docs/superpowers/specs/2026-03-11-api-integration-simplification-design.md`

---

## File Structure

### New Files
- `server/cache.py` — In-memory TTL cache module (replaces SQLite caching)
- `server/services/salary_api.py` — Client for nhl-salary-api (replaces `injuries.py` + `salary.py`)
- `server/routes/admin.py` — Admin scrape endpoints
- `src/components/admin-controls.tsx` — Admin buttons UI (replaces `salary-upload.tsx`)
- `tests/test_cache.py` — Tests for cache module
- `tests/test_salary_api.py` — Tests for salary API client
- `tests/test_projections.py` — Tests for projection pipeline
- `tests/test_optimizer.py` — Tests for optimizer (dict-based)
- `tests/test_settings.py` — Tests for JSON settings

### Files to Delete
- `server/database.py`
- `server/seed.py`
- `server/services/injuries.py`
- `server/services/salary.py`
- `server/routes/salary.py`
- `src/components/salary-upload.tsx`
- `seed_data/nhl_players_2025_26.csv`
- `seed_data/` (directory)

### Files to Modify
- `server/constants.py` — Remove team name mappings, keep defaults/config
- `server/services/nhl_api.py` — Replace SQLite + pandas with in-memory cache + dicts
- `server/services/projections.py` — Rewrite: ID-based join, no pandas, salary API integration
- `server/services/optimizer.py` — Replace pandas with plain dicts, keep PuLP logic
- `server/routes/optimizer.py` — JSON settings, remove SQLite, add admin routes
- `server/main.py` — Remove DB/seed, add admin router
- `requirements.txt` — Remove pandas/numpy/bs4/lxml
- `Dockerfile` — Remove seed_data COPY
- `src/lib/api.ts` — Remove salary functions, add admin functions
- `src/lib/types.ts` — Remove SalaryStatus
- `src/App.tsx` — Replace SalaryUpload with AdminControls

---

## Chunk 1: Backend Infrastructure

### Task 1: In-Memory Cache Module

**Files:**
- Create: `server/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 0: Create tests directory**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 1: Write failing tests for cache module**

Create `tests/test_cache.py`:

```python
from datetime import datetime, timedelta, timezone
from server.cache import get_cached, set_cached, clear_cache, _cache


def test_set_and_get_within_ttl():
    clear_cache()
    set_cached("test_key", {"foo": "bar"})
    result = get_cached("test_key", ttl_seconds=60)
    assert result == {"foo": "bar"}


def test_get_returns_none_when_expired():
    clear_cache()
    set_cached("test_key", {"foo": "bar"})
    # Manually backdate the cache entry
    _cache["test_key"]["fetched_at"] = datetime.now(timezone.utc) - timedelta(seconds=120)
    result = get_cached("test_key", ttl_seconds=60)
    assert result is None


def test_get_returns_none_for_missing_key():
    clear_cache()
    result = get_cached("nonexistent", ttl_seconds=60)
    assert result is None


def test_clear_specific_key():
    clear_cache()
    set_cached("a", 1)
    set_cached("b", 2)
    clear_cache("a")
    assert get_cached("a", ttl_seconds=60) is None
    assert get_cached("b", ttl_seconds=60) == 2


def test_clear_all():
    clear_cache()
    set_cached("a", 1)
    set_cached("b", 2)
    clear_cache()
    assert get_cached("a", ttl_seconds=60) is None
    assert get_cached("b", ttl_seconds=60) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.cache'`

- [ ] **Step 3: Implement cache module**

Create `server/cache.py`:

```python
from datetime import datetime, timezone
from typing import Any

_cache: dict[str, dict] = {}


def get_cached(key: str, ttl_seconds: int) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    if age >= ttl_seconds:
        return None
    return entry["data"]


def set_cached(key: str, data: Any) -> None:
    _cache[key] = {"data": data, "fetched_at": datetime.now(timezone.utc)}


def clear_cache(key: str | None = None) -> None:
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cache.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/cache.py tests/test_cache.py
git commit -m "feat: add in-memory TTL cache module"
```

---

### Task 2: Salary API Client

**Files:**
- Create: `server/services/salary_api.py`
- Create: `tests/test_salary_api.py`

- [ ] **Step 1: Write failing tests for salary API client**

Create `tests/test_salary_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_salary_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.salary_api'`

- [ ] **Step 3: Implement salary API client**

Create `server/services/salary_api.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_salary_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/salary_api.py tests/test_salary_api.py
git commit -m "feat: add salary API client with caching"
```

---

### Task 3: Update Constants

**Files:**
- Modify: `server/constants.py`

- [ ] **Step 1: Rewrite constants.py**

Replace the entire file. Remove `FULL_NAME_TO_ABBREV` and `CBS_TEAM_TO_ABBREV`. Keep `ALL_TEAMS` as a plain sorted list. Keep `DEFAULT_SETTINGS`, `CACHE_HOURS`, `NHL_API_BASE`, `SEASON_INT`.

```python
from datetime import date

# Auto-detect season: if month >= September, use current year; else prior year
today = date.today()
SEASON_START_YEAR = today.year if today.month >= 9 else today.year - 1
SEASON_INT = f"{SEASON_START_YEAR}{SEASON_START_YEAR + 1}"

# All 32 NHL API team codes
ALL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]

# Default optimizer constraints
DEFAULT_SETTINGS = {
    "max_cost": 70.5,
    "min_cost_pct": 90,
    "num_forwards": 6,
    "num_defensemen": 4,
    "num_goalies": 2,
    "max_per_team": 5,
    "min_games_played": 10,
}

# Cache TTL in hours
CACHE_HOURS = 12

# NHL API base URL
NHL_API_BASE = "https://api-web.nhle.com/v1"
```

- [ ] **Step 2: Verify no import errors**

Run: `python -c "from server.constants import ALL_TEAMS, DEFAULT_SETTINGS, CACHE_HOURS, NHL_API_BASE, SEASON_INT; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/constants.py
git commit -m "refactor: simplify constants, remove team name mappings"
```

---

### Task 4: Rewrite NHL API Service (Remove SQLite + Pandas)

**Files:**
- Modify: `server/services/nhl_api.py`

- [ ] **Step 1: Rewrite nhl_api.py**

Replace entire file. Remove all SQLite imports, pandas, numpy. Use `server.cache` for caching. Return plain dicts/lists. Keep the same public function signatures but return dicts instead of DataFrames. Add `playerId` to stats output.

```python
import time
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from server.cache import get_cached, set_cached
from server.constants import ALL_TEAMS, CACHE_HOURS, NHL_API_BASE, SEASON_INT

_CACHE_TTL = CACHE_HOURS * 3600


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")


def fetch_all_player_stats(min_gp: int = 10, force_refresh: bool = False) -> list[dict]:
    cache_key = "player_stats"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    all_players = []

    for team in ALL_TEAMS:
        url = f"{NHL_API_BASE}/club-stats/{team}/{SEASON_INT}/2"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for skater in data.get("skaters", []):
            gp = skater.get("gamesPlayed", 0)
            if gp < min_gp:
                continue

            first = skater.get("firstName", {}).get("default", "")
            last = skater.get("lastName", {}).get("default", "")
            name = normalize_name(f"{first} {last}").strip()
            pos_code = skater.get("positionCode", "C")
            position = "D" if pos_code == "D" else "F"
            goals = skater.get("goals", 0)
            assists = skater.get("assists", 0)

            all_players.append({
                "playerId": skater.get("playerId"),
                "player_name": name,
                "team": team,
                "position": position,
                "games_played": gp,
                "goals": goals,
                "assists": assists,
                "goals_per_game": goals / gp,
                "assists_per_game": assists / gp,
            })

        time.sleep(0.1)

    set_cached(cache_key, all_players)
    return all_players


def fetch_standings(force_refresh: bool = False) -> list[dict]:
    cache_key = "standings"
    if not force_refresh:
        cached = get_cached(cache_key, _CACHE_TTL)
        if cached is not None:
            return cached

    resp = requests.get(f"{NHL_API_BASE}/standings/now", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    teams = []
    for entry in data.get("standings", []):
        abbrev = entry.get("teamAbbrev", {}).get("default", "")
        pctg = entry.get("pointPctg", 0.5)
        teams.append({"team": abbrev, "point_pctg": pctg})

    set_cached(cache_key, teams)
    return teams


def fetch_weekly_schedule(start_date=None):
    if start_date is None:
        start_date = datetime.now(ZoneInfo("America/New_York")).date()
    elif isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    resp = requests.get(
        f"{NHL_API_BASE}/schedule/{start_date.isoformat()}", timeout=10
    )
    resp.raise_for_status()
    data = resp.json()

    games_count: dict[str, int] = {}
    opponents: dict[str, list[str]] = {}

    for day in data.get("gameWeek", []):
        game_date = date.fromisoformat(day["date"])
        if game_date < start_date:
            continue
        for game in day.get("games", []):
            away = game.get("awayTeam", {}).get("abbrev", "")
            home = game.get("homeTeam", {}).get("abbrev", "")
            if not away or not home:
                continue
            games_count[away] = games_count.get(away, 0) + 1
            games_count[home] = games_count.get(home, 0) + 1
            opponents.setdefault(away, []).append(home)
            opponents.setdefault(home, []).append(away)

    return games_count, opponents


def calculate_multipliers(
    standings: list[dict], opponents: dict[str, list[str]]
) -> dict[str, float]:
    pctg_lookup = {s["team"]: s["point_pctg"] for s in standings}
    multipliers = {}

    for team, opps in opponents.items():
        opp_mults = []
        for opp in opps:
            pctg = pctg_lookup.get(opp, 0.5)
            opp_mults.append(0.5 / pctg if pctg > 0 else 1.8)
        multipliers[team] = sum(opp_mults) / len(opp_mults) if opp_mults else 1.0

    return multipliers
```

- [ ] **Step 2: Verify no import errors**

Run: `python -c "from server.services.nhl_api import fetch_all_player_stats, fetch_standings, fetch_weekly_schedule, calculate_multipliers; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/services/nhl_api.py
git commit -m "refactor: nhl_api uses in-memory cache, returns plain dicts"
```

---

### Task 5: Rewrite Projections Service

**Files:**
- Modify: `server/services/projections.py`
- Create: `tests/test_projections.py`

- [ ] **Step 1: Write failing tests for projections**

Create `tests/test_projections.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_projections.py -v`
Expected: FAIL — current projections.py has different imports/signatures

- [ ] **Step 3: Rewrite projections.py**

Replace `server/services/projections.py` entirely:

```python
from server.services.nhl_api import (
    calculate_multipliers,
    fetch_all_player_stats,
    fetch_standings,
    fetch_weekly_schedule,
)
from server.services.salary_api import fetch_players


def _normalize_position(pos: str) -> str:
    if pos in ("C", "L", "R", "LW", "RW"):
        return "F"
    return pos  # "D" and "G" stay as-is


def calculate_projections(
    stats: list[dict],
    games_count: dict[str, int],
    multipliers: dict[str, float],
) -> list[dict]:
    result = []
    for p in stats:
        games = games_count.get(p["team"], 0)
        mult = multipliers.get(p["team"], 1.0)
        proj = (p["goals_per_game"] * 2 + p["assists_per_game"] * 1) * games * mult
        result.append({
            **p,
            "games_this_week": games,
            "multiplier": mult,
            "proj_fantasy_pts": proj,
        })
    return result


def estimate_team_goaltending_points(
    multipliers: dict[str, float],
    games_count: dict[str, int],
    standings: list[dict],
    win_points: float = 2,
    ot_loss_points: float = 1,
    shutout_bonus: float = 2,
    avg_ot_loss_freq: float = 0.1,
    avg_shutout_freq: float = 0.05,
) -> dict[str, tuple[float, int]]:
    pctg_lookup = {s["team"]: s["point_pctg"] for s in standings}
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


def build_optimizer_input(
    start_date=None,
    force_refresh: bool = False,
    min_gp: int = 10,
) -> list[dict]:
    # 1. Fetch data from all sources
    stats = fetch_all_player_stats(min_gp=min_gp, force_refresh=force_refresh)
    standings = fetch_standings(force_refresh=force_refresh)
    games_count, opponents = fetch_weekly_schedule(start_date)
    multipliers = calculate_multipliers(standings, opponents)
    salary_players = fetch_players(force_refresh=force_refresh)

    # 2. Build salary lookup by nhlId
    salary_lookup = {p["nhlId"]: p for p in salary_players}

    # 3. Calculate projections for stats players
    projected = calculate_projections(stats, games_count, multipliers)

    # 4. Join stats with salary on playerId == nhlId
    result = []
    for p in projected:
        if p["games_this_week"] <= 0:
            continue
        salary_info = salary_lookup.get(p["playerId"])
        if salary_info is None:
            continue  # No salary data — skip player

        injured = salary_info["injury"] is not None
        position = _normalize_position(salary_info["position"])

        result.append({
            "name": salary_info["name"],
            "team": p["team"],
            "position": position,
            "pv": salary_info["salary"] / 1_000_000,
            "games_this_week": p["games_this_week"],
            "multiplier": p["multiplier"],
            "proj_fantasy_pts": 0 if injured else p["proj_fantasy_pts"],
            "goals_per_game": p["goals_per_game"],
            "assists_per_game": p["assists_per_game"],
            "injured": injured,
        })

    # 5. Add goalie rows
    goalie_data = estimate_team_goaltending_points(multipliers, games_count, standings)
    for team, (pts, games) in goalie_data.items():
        if games <= 0:
            continue
        result.append({
            "name": f"{team} Goalie",
            "team": team,
            "position": "G",
            "pv": 0,
            "games_this_week": games,
            "multiplier": multipliers.get(team, 1.0),
            "proj_fantasy_pts": pts,
            "goals_per_game": 0,
            "assists_per_game": 0,
            "injured": False,
        })

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_projections.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/projections.py tests/test_projections.py
git commit -m "refactor: projections uses salary API with ID-based join"
```

---

### Task 6: Rewrite Optimizer Service (Remove Pandas)

**Files:**
- Modify: `server/services/optimizer.py`
- Create: `tests/test_optimizer.py`

- [ ] **Step 1: Write failing tests for optimizer**

Create `tests/test_optimizer.py`:

```python
from server.services.optimizer import select_best_team

MOCK_PLAYERS = [
    {"name": "Player F1", "team": "EDM", "position": "F", "pv": 8.0, "proj_fantasy_pts": 10.0, "games_this_week": 3, "injured": False},
    {"name": "Player F2", "team": "CGY", "position": "F", "pv": 7.0, "proj_fantasy_pts": 9.0, "games_this_week": 3, "injured": False},
    {"name": "Player F3", "team": "TOR", "position": "F", "pv": 6.0, "proj_fantasy_pts": 8.0, "games_this_week": 3, "injured": False},
    {"name": "Player F4", "team": "MTL", "position": "F", "pv": 5.5, "proj_fantasy_pts": 7.0, "games_this_week": 3, "injured": False},
    {"name": "Player F5", "team": "VAN", "position": "F", "pv": 5.0, "proj_fantasy_pts": 6.0, "games_this_week": 3, "injured": False},
    {"name": "Player F6", "team": "WPG", "position": "F", "pv": 4.5, "proj_fantasy_pts": 5.0, "games_this_week": 3, "injured": False},
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_optimizer.py -v`
Expected: FAIL — current optimizer.py expects a DataFrame

- [ ] **Step 3: Rewrite optimizer.py**

Replace `server/services/optimizer.py` entirely:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_optimizer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/optimizer.py tests/test_optimizer.py
git commit -m "refactor: optimizer uses plain dicts instead of pandas DataFrames"
```

---

## Chunk 2: Routes, Wiring, and Cleanup

### Task 7: Rewrite Routes and Settings (JSON File)

**Files:**
- Modify: `server/routes/optimizer.py`
- Create: `server/routes/admin.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests for JSON settings**

Create `tests/test_settings.py`:

```python
import json
import os
import tempfile
from unittest.mock import patch

from server.routes.optimizer import _get_settings, _save_settings


def test_get_settings_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "optimizer_settings.json")
        with patch("server.routes.optimizer._SETTINGS_PATH", path):
            settings = _get_settings()
            assert settings["max_cost"] == 70.5
            assert settings["num_forwards"] == 6


def test_save_and_get_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "optimizer_settings.json")
        with patch("server.routes.optimizer._SETTINGS_PATH", path):
            _save_settings({"max_cost": 80.0, "num_forwards": 7})
            settings = _get_settings()
            assert settings["max_cost"] == 80.0
            assert settings["num_forwards"] == 7
            # Other fields should still be defaults
            assert settings["num_defensemen"] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_settings.py -v`
Expected: FAIL — `_get_settings` and `_save_settings` don't exist yet in new form

- [ ] **Step 3: Rewrite optimizer routes**

Replace `server/routes/optimizer.py` entirely:

```python
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from server.auth import require_auth
from server.cache import clear_cache, get_cached, set_cached
from server.constants import DEFAULT_SETTINGS
from server.services.optimizer import select_best_team
from server.services.projections import build_optimizer_input

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

_DATA_DIR = os.environ.get("DATA_DIR", "data")
_SETTINGS_PATH = os.path.join(_DATA_DIR, "optimizer_settings.json")


class OptimizeRequest(BaseModel):
    start_date: str | None = None
    locked_players: list[str] = []
    excluded_players: list[str] = []


class SettingsUpdate(BaseModel):
    max_cost: float | None = None
    min_cost_pct: float | None = None
    num_forwards: int | None = None
    num_defensemen: int | None = None
    num_goalies: int | None = None
    max_per_team: int | None = None
    min_games_played: int | None = None

    @field_validator("max_cost")
    @classmethod
    def max_cost_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("max_cost must be positive")
        return v

    @field_validator("min_cost_pct")
    @classmethod
    def min_cost_pct_range(cls, v: float | None) -> float | None:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("min_cost_pct must be between 0 and 100")
        return v

    @field_validator("num_forwards", "num_defensemen", "num_goalies", "max_per_team", "min_games_played")
    @classmethod
    def non_negative_int(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v


def _get_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(_SETTINGS_PATH):
        with open(_SETTINGS_PATH) as f:
            saved = json.load(f)
        settings.update(saved)
    return settings


def _save_settings(updates: dict) -> dict:
    settings = _get_settings()
    settings.update(updates)
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    return settings


@router.post("/optimize")
def optimize(body: OptimizeRequest):
    settings = _get_settings()
    try:
        players = build_optimizer_input(
            start_date=body.start_date,
            min_gp=settings["min_games_played"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data pipeline error: {e}")

    result = select_best_team(
        players,
        settings=settings,
        locked_players=body.locked_players,
        excluded_players=body.excluded_players,
    )
    return result


@router.get("/settings")
def get_settings():
    return _get_settings()


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    settings = _get_settings()
    old_min_gp = settings["min_games_played"]

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return settings

    new_settings = _save_settings(updates)

    # If min_games_played changed, invalidate all caches (stats need re-filtering)
    new_min_gp = updates.get("min_games_played", old_min_gp)
    if new_min_gp != old_min_gp:
        clear_cache()

    return new_settings


@router.post("/refresh-data")
def refresh_data():
    clear_cache()
    settings = _get_settings()
    try:
        players = build_optimizer_input(
            force_refresh=True,
            min_gp=settings["min_games_played"],
        )
        skaters = sum(1 for p in players if p["position"] != "G")
        goalies = sum(1 for p in players if p["position"] == "G")
        return {"message": f"Refreshed: {skaters} skaters + {goalies} goalies"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_PLAYERS_ENDPOINT_TTL = 300  # 5 minutes


@router.get("/players")
def get_players():
    cached = get_cached("api_players_formatted", _PLAYERS_ENDPOINT_TTL)
    if cached is not None:
        return cached

    settings = _get_settings()
    try:
        players = build_optimizer_input(min_gp=settings["min_games_played"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Format for frontend
    formatted = []
    for p in players:
        formatted.append({
            "name": p["name"],
            "team": p["team"],
            "position": p["position"],
            "gamesThisWeek": int(p["games_this_week"]),
            "projFantasyPts": round(float(p["proj_fantasy_pts"]), 2),
            "salary": round(float(p["pv"]), 2),
            "injured": bool(p.get("injured", False)),
        })

    set_cached("api_players_formatted", formatted)
    return formatted
```

- [ ] **Step 4: Create admin routes**

Create `server/routes/admin.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from server.auth import require_auth
from server.services.salary_api import trigger_injury_scrape, trigger_salary_scrape

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_auth)])


@router.post("/scrape-players")
def scrape_players():
    try:
        return trigger_salary_scrape()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Salary API error: {e}")


@router.post("/scrape-injuries")
def scrape_injuries():
    try:
        return trigger_injury_scrape()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Salary API error: {e}")
```

- [ ] **Step 5: Run settings tests**

Run: `python -m pytest tests/test_settings.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/routes/optimizer.py server/routes/admin.py tests/test_settings.py
git commit -m "refactor: routes use JSON settings, add admin scrape endpoints"
```

---

### Task 8: Update main.py and Delete Old Files

**Files:**
- Modify: `server/main.py`
- Delete: `server/database.py`, `server/seed.py`, `server/services/injuries.py`, `server/services/salary.py`, `server/routes/salary.py`, `src/components/salary-upload.tsx`, `seed_data/`

- [ ] **Step 1: Rewrite main.py**

Replace `server/main.py`:

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.auth import router as auth_router
from server.routes.admin import router as admin_router
from server.routes.optimizer import router as optimizer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.environ.get("DATA_DIR", "data"), exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth_router)
app.include_router(optimizer_router)
app.include_router(admin_router)

# Static files (production: serve Vite build output)
dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist")
if os.path.isdir(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        file_path = os.path.realpath(os.path.join(dist_dir, path))
        if not file_path.startswith(os.path.realpath(dist_dir)):
            return FileResponse(os.path.join(dist_dir, "index.html"))
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
```

- [ ] **Step 2: Delete old backend files**

```bash
rm server/database.py server/seed.py server/services/injuries.py server/services/salary.py server/routes/salary.py
rm -r seed_data/
```

- [ ] **Step 3: Verify the app imports cleanly**

Run: `python -c "from server.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run all backend tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove SQLite, CBS scraper, CSV upload, and seed data"
```

---

### Task 9: Update Dependencies and Dockerfile

**Files:**
- Modify: `requirements.txt`
- Modify: `Dockerfile`

- [ ] **Step 1: Update requirements.txt**

Replace contents of `requirements.txt`:

```
fastapi
uvicorn[standard]
python-multipart
pulp
requests
```

Note: `pytest` is a dev dependency — install it locally with `pip install pytest` but don't include in production deps.

- [ ] **Step 2: Update Dockerfile**

Replace `Dockerfile`:

```dockerfile
# Stage 1: Build frontend
FROM node:22-slim AS frontend
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.13-slim-bookworm
WORKDIR /app

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY --from=frontend /app/dist dist/

RUN useradd -r -s /bin/false appuser
USER appuser

ENV PORT=8000
ENV DATA_DIR=/app/data
EXPOSE $PORT

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Verify pip install works**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 4: Run all tests one more time**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt Dockerfile
git commit -m "chore: remove unused deps, update Dockerfile"
```

---

## Chunk 3: Frontend Changes

### Task 10: Update Frontend API Client and Types

**Files:**
- Modify: `src/lib/api.ts`
- Modify: `src/lib/types.ts`

- [ ] **Step 1: Update types.ts**

Remove `SalaryStatus` interface from `src/lib/types.ts`. Keep everything else.

New contents:

```typescript
export interface Player {
  name: string
  team: string
  position: string
  gamesThisWeek: number
  projFantasyPts: number
  salary: number
  injured: boolean
}

export function playerKey(p: { name: string; team: string; position: string }): string {
  return `${p.name}|${p.team}|${p.position}`
}

export interface LineupResult {
  players: Player[]
  totalPoints: number
  totalSalary: number
  feasible: boolean
  message?: string
}

export interface Settings {
  max_cost: number
  min_cost_pct: number
  num_forwards: number
  num_defensemen: number
  num_goalies: number
  max_per_team: number
  min_games_played: number
}

export interface AuthResponse {
  authenticated: boolean
}
```

- [ ] **Step 2: Update api.ts**

Remove `uploadSalary()` and `getSalaryStatus()`. Remove `SalaryStatus` from import. Add `triggerSalaryScrape()` and `triggerInjuryScrape()`.

New contents:

```typescript
import type {
  AuthResponse,
  LineupResult,
  Player,
  Settings,
} from "./types"

async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    credentials: "include",
    ...options,
  })
  if (res.status === 401) {
    throw new AuthError()
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export class AuthError extends Error {
  constructor() {
    super("Not authenticated")
    this.name = "AuthError"
  }
}

export async function login(password: string): Promise<AuthResponse> {
  return request("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  })
}

export async function logout(): Promise<void> {
  await request("/api/logout", { method: "POST" })
}

export async function checkAuth(): Promise<AuthResponse> {
  return request("/api/auth/check")
}

export async function optimize(params: {
  start_date?: string
  locked_players?: string[]
  excluded_players?: string[]
}): Promise<LineupResult> {
  return request("/api/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
}

export async function getSettings(): Promise<Settings> {
  return request("/api/settings")
}

export async function updateSettings(
  settings: Partial<Settings>
): Promise<Settings> {
  return request("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  })
}

export async function refreshData(): Promise<{ message: string }> {
  return request("/api/refresh-data", { method: "POST" })
}

export async function getPlayers(): Promise<Player[]> {
  return request("/api/players")
}

export async function triggerSalaryScrape(): Promise<{ message: string }> {
  return request("/api/admin/scrape-players", { method: "POST" })
}

export async function triggerInjuryScrape(): Promise<{ message: string }> {
  return request("/api/admin/scrape-injuries", { method: "POST" })
}
```

- [ ] **Step 3: Commit**

```bash
git add src/lib/api.ts src/lib/types.ts
git commit -m "refactor: update frontend API client, remove salary upload functions"
```

---

### Task 11: Create Admin Controls Component and Update App

**Files:**
- Create: `src/components/admin-controls.tsx`
- Modify: `src/App.tsx`
- Delete: `src/components/salary-upload.tsx`

- [ ] **Step 1: Create admin controls component**

Create `src/components/admin-controls.tsx`:

```tsx
import { useState } from "react"
import { Database, Stethoscope } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { triggerInjuryScrape, triggerSalaryScrape } from "@/lib/api"

export function AdminControls({ onRefreshed }: { onRefreshed?: () => void }) {
  const [salaryLoading, setSalaryLoading] = useState(false)
  const [injuryLoading, setInjuryLoading] = useState(false)
  const [message, setMessage] = useState("")

  async function handleSalaryScrape() {
    setSalaryLoading(true)
    setMessage("")
    try {
      const result = await triggerSalaryScrape()
      setMessage(result.message || "Salary scrape complete")
      onRefreshed?.()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Salary scrape failed")
    } finally {
      setSalaryLoading(false)
    }
  }

  async function handleInjuryScrape() {
    setInjuryLoading(true)
    setMessage("")
    try {
      const result = await triggerInjuryScrape()
      setMessage(result.message || "Injury scrape complete")
      onRefreshed?.()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Injury scrape failed")
    } finally {
      setInjuryLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Admin</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleSalaryScrape}
            disabled={salaryLoading}
          >
            <Database className="mr-1.5 h-3.5 w-3.5" />
            {salaryLoading ? "Scraping..." : "Refresh Salaries"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleInjuryScrape}
            disabled={injuryLoading}
          >
            <Stethoscope className="mr-1.5 h-3.5 w-3.5" />
            {injuryLoading ? "Scraping..." : "Refresh Injuries"}
          </Button>
        </div>
        {message && (
          <p className="text-xs font-medium text-muted-foreground">
            {message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: Update App.tsx**

Replace `src/App.tsx`. Remove `SalaryUpload` import/usage and `salaryKey` state. Add `AdminControls`.

```tsx
import { useCallback, useEffect, useState } from "react"
import { LogOut, Moon, RefreshCw, Sun } from "lucide-react"

import { AdminControls } from "@/components/admin-controls"
import { ConstraintsPanel } from "@/components/constraints-panel"
import { LineupDisplay } from "@/components/lineup-display"
import { LoginForm } from "@/components/login-form"
import { PlayerBrowser } from "@/components/player-browser"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { checkAuth, logout, refreshData } from "@/lib/api"

export function App() {
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [lockedPlayers, setLockedPlayers] = useState<Set<string>>(new Set())
  const [excludedPlayers, setExcludedPlayers] = useState<Set<string>>(new Set())
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
  })
  const [dataVersion, setDataVersion] = useState(0)
  const [apiStatus, setApiStatus] = useState<"ok" | "error" | "checking">("checking")
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    checkAuth()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false))
  }, [])

  useEffect(() => {
    if (!authed) return
    function ping() {
      fetch("/api/health")
        .then((r) => setApiStatus(r.ok ? "ok" : "error"))
        .catch(() => setApiStatus("error"))
    }
    ping()
    const id = setInterval(ping, 30_000)
    return () => clearInterval(id)
  }, [authed])

  const toggleLock = useCallback((key: string) => {
    setLockedPlayers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    setExcludedPlayers((prev) => {
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  const toggleExclude = useCallback((key: string) => {
    setExcludedPlayers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    setLockedPlayers((prev) => {
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await refreshData()
      setDataVersion((v) => v + 1)
    } catch (e) {
      console.error(e)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleLogout() {
    await logout()
    setAuthed(false)
  }

  if (authed === null) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  if (!authed) {
    return <LoginForm onSuccess={() => setAuthed(true)} />
  }

  return (
    <div className="mx-auto flex min-h-svh max-w-5xl flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              apiStatus === "ok"
                ? "bg-green-500"
                : apiStatus === "error"
                  ? "bg-red-500"
                  : "bg-yellow-500"
            }`}
            title={`API ${apiStatus}`}
          />
          <h1 className="text-sm font-medium">NHL Fantasy Optimizer</h1>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh data"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title="Toggle theme"
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <ConstraintsPanel
        startDate={startDate}
        onStartDateChange={setStartDate}
        onSettingsSaved={() => {}}
      />

      <main className="flex flex-col gap-6 p-4">
        <AdminControls onRefreshed={() => setDataVersion((v) => v + 1)} />

        <LineupDisplay
          lockedPlayers={lockedPlayers}
          excludedPlayers={excludedPlayers}
          onToggleLock={toggleLock}
          onToggleExclude={toggleExclude}
          startDate={startDate}
        />

        <PlayerBrowser
          lockedPlayers={lockedPlayers}
          excludedPlayers={excludedPlayers}
          onToggleLock={toggleLock}
          onToggleExclude={toggleExclude}
          dataVersion={dataVersion}
        />
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 3: Delete salary-upload.tsx**

```bash
rm src/components/salary-upload.tsx
```

- [ ] **Step 4: Verify frontend builds**

Run: `pnpm build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: replace salary upload with admin controls, update App layout"
```

---

### Task 12: Verify Full Stack

- [ ] **Step 1: Run all backend tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (cache: 5, salary_api: 5, projections: 4, optimizer: 3, settings: 2 = 19 total)

- [ ] **Step 2: Verify frontend builds**

Run: `pnpm build`
Expected: Build succeeds

- [ ] **Step 3: Verify backend starts**

Run: `timeout 5 uvicorn server.main:app --host 0.0.0.0 --port 8000 || true`
Expected: Server starts without import errors (will timeout after 5s, that's fine)

- [ ] **Step 4: Final commit with any remaining cleanup**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```

---

## Post-Implementation

After all tasks complete:
1. Set `NHL_SALARY_API_URL` and `NHL_SALARY_API_TOKEN` environment variables locally for testing
2. Start both dev servers (`pnpm dev` + `pnpm dev:api`) and verify the optimizer works end-to-end
3. Add `NHL_SALARY_API_URL` and `NHL_SALARY_API_TOKEN` to Railway environment variables
4. Deploy and verify on Railway
