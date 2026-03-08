from fastapi import Header, HTTPException

from app.config import get_settings


def verify_internal_token(x_internal_token: str = Header(...)) -> None:
    settings = get_settings()
    if not settings.internal_ingest_token:
        raise HTTPException(status_code=500, detail="Ingest token not configured")
    if x_internal_token != settings.internal_ingest_token:
        raise HTTPException(status_code=401, detail="Invalid token")
