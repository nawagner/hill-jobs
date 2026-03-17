import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.lib.email import send_email
from app.lib.email_templates import build_confirmation_html
from app.models.subscribers import Subscriber
from app.schemas.subscribers import (
    PreferencesResponse,
    PreferencesUpdateRequest,
    SubscribeRequest,
    SubscribeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscribe")


@router.post("", response_model=SubscribeResponse, status_code=201)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    existing = db.execute(
        select(Subscriber).where(Subscriber.email == body.email)
    ).scalar_one_or_none()

    if existing and existing.confirmed:
        existing.filters = body.filters
        db.commit()
        return SubscribeResponse(message="Subscription filters updated.")

    if existing and not existing.confirmed:
        existing.confirm_token = str(uuid4())
        existing.filters = body.filters
        db.commit()
    else:
        existing = Subscriber(
            email=body.email,
            filters=body.filters,
            confirm_token=str(uuid4()),
            unsubscribe_token=str(uuid4()),
        )
        db.add(existing)
        db.commit()

    confirm_url = f"{settings.site_base_url}/subscribe/confirm/{existing.confirm_token}"

    if settings.resend_api_key:
        send_email(
            api_key=settings.resend_api_key,
            to=body.email,
            subject="Confirm your Hill Jobs subscription",
            html=build_confirmation_html(confirm_url),
        )
    else:
        logger.warning("RESEND_API_KEY not set; skipping confirmation email")

    return SubscribeResponse(message="Check your email to confirm your subscription.")


@router.get("/confirm/{token}", response_model=SubscribeResponse)
def confirm(token: str, db: Session = Depends(get_db)):
    sub = db.execute(
        select(Subscriber).where(Subscriber.confirm_token == token)
    ).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Invalid or expired token.")
    sub.confirmed = True
    db.commit()
    return SubscribeResponse(message="Subscription confirmed!")


@router.get("/preferences/{token}", response_model=PreferencesResponse)
def get_preferences(token: str, db: Session = Depends(get_db)):
    sub = db.execute(
        select(Subscriber).where(Subscriber.unsubscribe_token == token)
    ).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Invalid token.")
    return PreferencesResponse(email=sub.email, filters=sub.filters)


@router.put("/preferences/{token}", response_model=SubscribeResponse)
def update_preferences(
    token: str, body: PreferencesUpdateRequest, db: Session = Depends(get_db)
):
    sub = db.execute(
        select(Subscriber).where(Subscriber.unsubscribe_token == token)
    ).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Invalid token.")
    sub.filters = body.filters
    db.commit()
    return SubscribeResponse(message="Preferences updated.")


@router.post("/unsubscribe/{token}", response_model=SubscribeResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = db.execute(
        select(Subscriber).where(Subscriber.unsubscribe_token == token)
    ).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Invalid token.")
    db.delete(sub)
    db.commit()
    return SubscribeResponse(message="You have been unsubscribed.")
