# NHL Optimizer — API Integration Simplification

## Problem

The app currently relies on three separate data sources with fragile integration:
1. **CBS Sports HTML scraping** for injuries (breaks when markup changes)
2. **Manual CSV upload** for salary data (manual, error-prone, requires name-matching fallbacks)
3. **NHL API** for stats/standings/schedule

A new unified salary API (`nhl-salary-api`) has been built that provides players with salary and injury data, keyed by NHL player ID. This enables replacing sources 1 and 2 with a single API call and joining on stable IDs instead of fuzzy name matching.

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
                          Project points, apply schedule multipliers
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

- Remove SQLite read/write, replace with in-memory dict cache + TTL
- Remove pandas — return plain dicts/lists
- Functions stay the same: `fetch_all_player_stats()`, `fetch_standings()`, `fetch_weekly_schedule()`, `calculate_multipliers()`
- Stats keyed by `playerId` for easy join

#### `server/services/projections.py`

- Remove CBS injury import
- Remove name-matching logic (uppercase normalization, last-name fallback)
- Join salary API data with NHL stats on `nhlId == playerId`
- If player has `injury` field set (not null), zero out projected points
- Use plain dicts instead of DataFrames

#### `server/services/optimizer.py`

- Replace DataFrame operations with plain dict/list operations
- PuLP logic stays the same (variable creation, constraints, solve)

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
  "max_cost": 70500000,
  "min_cost_pct": 0.90,
  "num_forwards": 6,
  "num_defensemen": 4,
  "num_goalies": 2,
  "max_per_team": 5,
  "min_games_played": 10
}
```

If the file doesn't exist, defaults are used. `GET /api/settings` reads it, `PUT /api/settings` writes it.

### In-Memory Cache Design

Simple Python dict with timestamps, replacing SQLite cache:

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

### Dependencies

**Remove from requirements.txt:**
- `beautifulsoup4`
- `lxml`
- `pandas`
- `numpy` (check if PuLP needs it — if not, remove)

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
- Goalie projection model
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
