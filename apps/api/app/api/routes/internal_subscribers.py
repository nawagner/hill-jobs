"""Protected subscriber maintenance endpoints (x-internal-token)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import verify_internal_token
from app.api.routes.subscribe import send_confirmation_email
from app.config import get_settings
from app.db import get_db
from app.models.subscribers import Subscriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/subscribers")


def _mask(email: str) -> str:
    user, _, domain = email.partition("@")
    return f"{user[:1]}***@{domain}"


@router.post("/resend-confirmations")
def resend_confirmations(
    since: datetime = Query(..., description="Resend to unconfirmed sign-ups made on or after this time (UTC)"),
    dry_run: bool = Query(False, description="List who would get an email without sending"),
    _: None = Depends(verify_internal_token),
    db: Session = Depends(get_db),
):
    """Resend the confirmation email to people whose sign-up never got one.

    For when sending was broken (in November 2026 the Resend key was revoked
    and every confirmation email failed). Each subscriber keeps their current
    confirmation link, so a link that did arrive still works.
    """
    settings = get_settings()
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if not dry_run and not settings.resend_api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not set")

    subscribers = db.execute(
        select(Subscriber)
        .where(
            Subscriber.confirmed.is_(False),
            or_(Subscriber.created_at >= since, Subscriber.updated_at >= since),
        )
        .order_by(Subscriber.created_at)
    ).scalars().all()

    sent, failed = [], []
    for sub in subscribers:
        if dry_run:
            continue
        try:
            send_confirmation_email(settings, sub.email, sub.confirm_token)
            sent.append(_mask(sub.email))
        except Exception:
            logger.exception("Failed to resend confirmation to %s", _mask(sub.email))
            failed.append(_mask(sub.email))

    logger.info(
        "Resend confirmations since %s: matched=%d sent=%d failed=%d dry_run=%s",
        since.isoformat(), len(subscribers), len(sent), len(failed), dry_run,
    )
    return {
        "since": since.isoformat(),
        "dry_run": dry_run,
        "matched": [_mask(s.email) for s in subscribers],
        "sent": sent,
        "failed": failed,
    }
