from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from server.auth import require_auth
from server.database import get_db, get_write_lock
from server.services.optimizer import select_best_team
from server.services.projections import build_optimizer_input

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


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
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT max_cost, min_cost_pct, num_forwards, num_defensemen, num_goalies, max_per_team, min_games_played FROM optimizer_settings WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    return {
        "max_cost": row[0],
        "min_cost_pct": row[1],
        "num_forwards": row[2],
        "num_defensemen": row[3],
        "num_goalies": row[4],
        "max_per_team": row[5],
        "min_games_played": row[6],
    }


@router.post("/optimize")
def optimize(body: OptimizeRequest):
    settings = _get_settings()
    try:
        df = build_optimizer_input(
            start_date=body.start_date,
            min_gp=settings["min_games_played"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data pipeline error: {e}")

    result = select_best_team(
        df,
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

    set_clauses = []
    values = []
    for key, value in updates.items():
        set_clauses.append(f"{key} = ?")
        values.append(value)

    with get_write_lock():
        conn = get_db()
        try:
            conn.execute(
                f"UPDATE optimizer_settings SET {', '.join(set_clauses)} WHERE id = 1",
                values,
            )
            conn.commit()

            # If min_games_played changed, invalidate player stats cache
            new_min_gp = updates.get("min_games_played", old_min_gp)
            if new_min_gp != old_min_gp:
                conn.execute(
                    "DELETE FROM cache_metadata WHERE table_name = 'player_stats'"
                )
                conn.commit()
        finally:
            conn.close()

    return _get_settings()


@router.post("/refresh-data")
def refresh_data():
    _players_cache.clear()
    settings = _get_settings()
    try:
        df = build_optimizer_input(
            force_refresh=True,
            min_gp=settings["min_games_played"],
        )
        skaters = len(df[df["Position"] != "G"])
        goalies = len(df[df["Position"] == "G"])
        return {"message": f"Refreshed: {skaters} skaters + {goalies} goalies"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Simple in-memory cache for /api/players to avoid re-scraping on every call
import time as _time

_players_cache: dict[str, tuple[float, list]] = {}
_PLAYERS_CACHE_TTL = 300  # 5 minutes


def _df_to_players(df) -> list:
    players = []
    for _, row in df.iterrows():
        players.append(
            {
                "name": row["Player"],
                "team": row["Team"],
                "position": row["Position"],
                "gamesThisWeek": int(row["games_this_week"]),
                "projFantasyPts": round(float(row["proj_fantasy_pts"]), 2),
                "salary": round(float(row["pv"]), 2),
                "injured": bool(row.get("Injured", False)),
            }
        )
    return players


@router.get("/players")
def get_players():
    cache_key = "players"
    cached = _players_cache.get(cache_key)
    if cached and (_time.time() - cached[0]) < _PLAYERS_CACHE_TTL:
        return cached[1]

    settings = _get_settings()
    try:
        df = build_optimizer_input(min_gp=settings["min_games_played"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    players = _df_to_players(df)
    _players_cache[cache_key] = (_time.time(), players)
    return players
