import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api")

APP_PASSWORD = os.environ.get("APP_PASSWORD") or "dev"
SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "development") == "production"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days
COOKIE_NAME = "session"


def _sign(timestamp: str) -> str:
    return hmac.new(
        SECRET_KEY.encode(), timestamp.encode(), hashlib.sha256
    ).hexdigest()


def _make_cookie_value() -> str:
    ts = str(int(time.time()))
    return f"{ts}:{_sign(ts)}"


def _validate_cookie(value: str | None) -> bool:
    if not value:
        return False
    parts = value.split(":", 1)
    if len(parts) != 2:
        return False
    ts, sig = parts
    if not hmac.compare_digest(sig, _sign(ts)):
        return False
    try:
        age = time.time() - int(ts)
        return age < COOKIE_MAX_AGE
    except ValueError:
        return False


def require_auth(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not _validate_cookie(cookie):
        raise HTTPException(status_code=401, detail="Not authenticated")


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if not hmac.compare_digest(body.password, APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    response.set_cookie(
        key=COOKIE_NAME,
        value=_make_cookie_value(),
        httponly=True,
        samesite="lax",
        secure=IS_PRODUCTION,
        max_age=COOKIE_MAX_AGE,
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"authenticated": False}


@router.get("/auth/check")
def auth_check(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not _validate_cookie(cookie):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True}


@router.get("/health")
def health():
    return {"status": "ok"}
