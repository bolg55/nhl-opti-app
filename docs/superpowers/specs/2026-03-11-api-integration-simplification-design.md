# NHL Optimizer — API Integration Simplification

## Problem

The app currently relies on three separate data sources with fragile integration:
1. **CBS Sports HTML scraping** for injuries (breaks when markup changes)
2. **Manual CSV upload** for salary data (manual, error-prone, requires name-matching fallbacks)
3. **NHL API** for stats/standings/schedule

A new unified salary API (`nhl-salary-api`) has been built that provides players with salary and injury data, keyed by NHL player ID. This enables replacing sources 1 and 2 with a single API call and joining on stable IDs instead of fuzzy name matching.

## Salary API Data Format

Verified from live responses:

```json
{
  "nhlId": 8477934,
  "name": "Leon Draisaitl",
  "team": "EDM",
  "position": "C",
  "salary": 14000000,
  "injury": null
}
```

- **`team`**: 3-letter abbreviations matching NHL API (e.g., `"EDM"`, `"DAL"`)
- **`position`**: NHL-specific codes: `"C"`, `"L"`, `"R"`, `"D"`, `"G"` — must normalize `C/L/R → "F"` for the optimizer
- **`salary`**: Raw dollars (e.g., `14000000`). The current optimizer uses millions (e.g., `14.0`). Convert: `salary / 1_000_000`
- **`injury`**: `null` = healthy. Non-null = `{status, description}` where status is "Day to Day", "Week to Week", "Season", etc. All non-null injuries zero out projected points (same behavior as current CBS scraper, which doesn't distinguish statuses)
- **`GET /injuries` endpoint**: Not used directly. Injury data is consumed via the `injury` field on `GET /players`. The admin `POST /admin/scrape/injuries` triggers the API to update its injury data, which then appears in subsequent `GET /players` responses.

## Design

### Data Flow (Before)

```
CBS Sports (scrape HTML)  →  injury DataFrame
CSV upload → SQLite       →  salary DataFrame
NHL API → SQLite cache    →  stats DataFrame
                                    ↓
                          Name-based merge (uppercase + last-name fallback)
                                    ↓
                          PuLP optimizer → lineup
```

### Data Flow (After)

```
Salary API (GET /players) →  players with salary + injury + nhlId
NHL Stats API             →  player stats with playerId
NHL Standings API         →  team win percentages
NHL Schedule API          →  weekly games
                                    ↓
                          Join on playerId == nhlId
                                    ↓
                          Normalize positions (C/L/R → F), convert salary to millions
                                    ↓
                          Project points, apply schedule multipliers
                                    ↓
                          Append synthetic goalie rows (team-level, salary=0)
                                    ↓
                          PuLP optimizer → lineup
```

### What Gets Removed

| Component | Files | Reason |
|-----------|-------|--------|
| CBS Sports scraper | `server/services/injuries.py` | Replaced by salary API injury data |
| Salary CSV upload | `server/services/salary.py`, `server/routes/salary.py` | Replaced by salary API |
| Salary upload UI | `src/components/salary-upload.tsx` | No longer needed |
| SQLite database | `server/database.py` | Replaced by in-memory cache + JSON settings file |
| Seed data | `server/seed.py`, `seed_data/` | No longer needed |
| Name-matching logic | In `server/services/projections.py` | Replaced by ID-based join |
| BeautifulSoup/lxml deps | `requirements.txt` | No longer scraping HTML |
| Pandas dependency | All service files | Replaced by plain dicts/lists |
| Team name mappings | `FULL_NAME_TO_ABBREV`, `CBS_TEAM_TO_ABBREV` in `constants.py` | No longer needed — both APIs use 3-letter codes |
| numpy dependency | `requirements.txt` | Only used in `nhl_api.py`; PuLP does not depend on it |

### What Gets Added

#### New Service: `server/services/salary_api.py`

Fetches player data from the salary API.

```python
# Single function, in-memory cache with TTL
def fetch_players(force_refresh: bool = False) -> list[dict]:
    """GET /players from salary API. Returns list of:
    {nhlId, name, team, position, salary, injury}
    Cached in-memory for 30 minutes."""

def trigger_salary_scrape() -> dict:
    """POST /admin/scrape/players"""

def trigger_injury_scrape() -> dict:
    """POST /admin/scrape/injuries"""
```

**Auth:** Bearer token from `NHL_SALARY_API_TOKEN` env var.
**Base URL:** From `NHL_SALARY_API_URL` env var.

#### New Module: `server/cache.py`

Simple in-memory cache shared across services. See "In-Memory Cache Design" section.

#### New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/admin/scrape-players` | Proxy to salary API's player scrape |
| POST | `/api/admin/scrape-injuries` | Proxy to salary API's injury scrape |

#### New Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `NHL_SALARY_API_URL` | `https://nhl-salary-api-production.up.railway.app` | Salary API base URL |
| `NHL_SALARY_API_TOKEN` | `<bearer-token>` | Auth token (same one used in Railway) |

#### Admin Buttons (Frontend)

Two buttons added to the UI (settings area or a dedicated admin section):
- **"Refresh Salaries"** → `POST /api/admin/scrape-players`
- **"Refresh Injuries"** → `POST /api/admin/scrape-injuries`
- Each shows loading spinner and success/error toast feedback

### What Gets Modified

#### `server/services/nhl_api.py`

- Remove SQLite read/write, replace with in-memory cache (from `server/cache.py`)
- Remove pandas and numpy — return plain lists of dicts
- Functions stay the same: `fetch_all_player_stats()`, `fetch_standings()`, `fetch_weekly_schedule()`, `calculate_multipliers()`
- `fetch_all_player_stats()` returns list of dicts with `playerId` as a key field for joining

#### `server/services/projections.py`

- Remove CBS injury import and salary import
- Remove all name-matching logic (uppercase normalization, last-name fallback, `_last_name_key()`)
- Fetch salary API data via `salary_api.fetch_players()`
- Build a lookup dict: `{nhlId: {salary, injury, position, ...}}` from salary API
- Join with NHL stats on `nhlId == playerId`
- **Position normalization**: Map `C/L/R → "F"`, keep `D` and `G` as-is
- **Salary conversion**: `salary_api_salary / 1_000_000` to match existing `pv` scale (e.g., `14000000 → 14.0`)
- **Injury handling**: If player's `injury` field is not null, zero out projected points
- **Goalie rows**: Still synthetic team-aggregate rows (e.g., `"EDM Goalie"`) with `pv=0`, appended after the join. These don't exist in the salary API and are generated from standings + schedule data, same as today.
- Use plain dicts/lists instead of DataFrames

#### `server/services/optimizer.py`

- Replace DataFrame operations with plain dict/list operations
- PuLP logic stays the same (variable creation, constraints, solve)
- `pv` field continues to hold salary in millions (no change to constraint logic)

#### `server/constants.py`

- Remove `FULL_NAME_TO_ABBREV` and `CBS_TEAM_TO_ABBREV` dicts
- Keep `ALL_TEAMS` (regenerate as a simple list of 32 team codes)
- Keep `DEFAULT_SETTINGS` — update `max_cost` to stay at `70.5` (millions, matching the converted salary scale)
- Keep `CACHE_HOURS`, `NHL_API_BASE`, `SEASON_INT`

#### `server/routes/optimizer.py`

- Add admin scrape endpoints
- Settings read/write from JSON file instead of SQLite

#### `server/main.py`

- Remove database init, seed data loading
- Remove salary router import
- Add admin router or add admin endpoints to optimizer router
- Startup: just ensure `DATA_DIR` exists for settings JSON

#### `src/lib/api.ts`

- Remove `uploadSalary()`, `getSalaryStatus()`
- Add `triggerSalaryScrape()`, `triggerInjuryScrape()`

#### `src/lib/types.ts`

- Remove `SalaryStatus` interface

#### `src/App.tsx`

- Remove `<SalaryUpload />` component import and rendering
- Add admin buttons component

#### `src/components/salary-upload.tsx`

- Delete entirely

### Settings Storage

Optimizer settings move from SQLite to a JSON file at `{DATA_DIR}/optimizer_settings.json`:

```json
{
  "max_cost": 70.5,
  "min_cost_pct": 90,
  "num_forwards": 6,
  "num_defensemen": 4,
  "num_goalies": 2,
  "max_per_team": 5,
  "min_games_played": 10
}
```

Values match current `DEFAULT_SETTINGS` in `constants.py`. If the file doesn't exist, defaults are used. `GET /api/settings` reads it, `PUT /api/settings` writes it. Single-user app, so no concurrency concerns.

### In-Memory Cache Design

New module `server/cache.py` — simple Python dict with timestamps, replacing SQLite cache:

```python
_cache: dict[str, dict] = {}
# Each entry: {"data": <any>, "fetched_at": <datetime>}

def get_cached(key: str, ttl_seconds: int) -> any | None:
    """Return cached data if within TTL, else None."""

def set_cached(key: str, data: any) -> None:
    """Store data with current timestamp."""

def clear_cache(key: str = None) -> None:
    """Clear specific key or all cache. Used by refresh-data endpoint."""
```

Cache keys and TTLs:
- `player_stats` — 12 hours
- `standings` — 12 hours
- `salary_api_players` — 30 minutes
- Schedule — always live (no cache)

**Tradeoff**: Cache is lost on deploy/restart (unlike SQLite). Acceptable because re-fetching from NHL API and salary API takes only a few seconds, and restarts are infrequent.

### Error Handling

- **Salary API unavailable**: Return a clear error to the frontend ("Salary data unavailable — check API connection"). Do not serve stale data or silently degrade. The optimizer cannot produce meaningful results without salary data.
- **NHL API unavailable**: Same behavior as today — return cached data if within TTL, otherwise error.
- **Admin scrape endpoints fail**: Return the error from the upstream API to the frontend for display.

### Dependencies

**Remove from requirements.txt:**
- `beautifulsoup4`
- `lxml`
- `pandas`
- `numpy`

**Keep:**
- `fastapi`, `uvicorn`
- `pulp`
- `requests` (still used for NHL API + salary API calls)

### Docker/Deployment Changes

- Remove `seed_data/` from Dockerfile COPY
- Remove SQLite volume mount concern (but keep `DATA_DIR` for settings JSON)
- Add `NHL_SALARY_API_URL` and `NHL_SALARY_API_TOKEN` to Railway env vars

## What Stays the Same

- NHL API calls for stats, standings, schedule
- PuLP optimizer logic (constraints, objective function, solver)
- Goalie projection model (synthetic team-aggregate rows with pv=0)
- Schedule strength multiplier calculations
- Frontend: optimizer UI, lock/exclude, player browser, settings panel, theme toggle, auth, date picker, health indicator
- Auth system (HMAC cookie, password login)
- "Refresh Data" button (refreshes NHL API cache)

## Success Criteria

1. Optimizer produces same quality lineups as before
2. No more CBS Sports scraping failures
3. No more manual CSV uploads needed
4. Player matching is 100% reliable (ID-based, no name mismatches)
5. Admin can trigger salary/injury refreshes from the UI
6. App starts faster (no DB init, no seed loading)
7. Fewer dependencies, less code to maintain
