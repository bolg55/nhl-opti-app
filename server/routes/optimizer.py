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
