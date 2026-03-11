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
