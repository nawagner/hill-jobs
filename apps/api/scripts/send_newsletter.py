"""Weekly newsletter sender.

Sends digest emails to confirmed subscribers with jobs matching their filters
posted in the last 7 days. Intended to run as a Railway cron service weekly.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import get_engine
from app.lib.email import send_email
from app.lib.email_templates import build_digest_html
from app.models.subscribers import Subscriber
from app.search.query_jobs import query_jobs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    settings = Settings()
    if not settings.resend_api_key:
        logger.error("RESEND_API_KEY not set; aborting")
        sys.exit(1)

    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc)
    subscribers = session.execute(
        select(Subscriber).where(Subscriber.confirmed == True)  # noqa: E712
    ).scalars().all()

    logger.info("Found %d confirmed subscribers", len(subscribers))
    sent = 0
    skipped = 0
    errors = 0

    for sub in subscribers:
        # Idempotency: skip if sent within last 6 days
        if sub.last_sent_at and (now - sub.last_sent_at) < timedelta(days=6):
            skipped += 1
            continue

        filters = sub.filters or {}
        try:
            salary_min_val = int(filters["salary_min"]) if filters.get("salary_min") else None
        except (ValueError, TypeError):
            salary_min_val = None

        jobs, total = query_jobs(
            session,
            q=filters.get("q") or None,
            role_kind=filters.get("role_kind") or None,
            organization=filters.get("organization") or None,
            party=filters.get("party") or None,
            state=filters.get("state") or None,
            committee=filters.get("committee") or None,
            salary_min=salary_min_val,
            posted_since_days=7,
            page=1,
            page_size=100,
        )

        if not jobs:
            skipped += 1
            continue

        html = build_digest_html(jobs, sub.unsubscribe_token, settings.site_base_url)
        subject = f"Hill Jobs Weekly: {total} new position{'s' if total != 1 else ''} matching your filters"

        try:
            send_email(
                api_key=settings.resend_api_key,
                to=sub.email,
                subject=subject,
                html=html,
            )
            sub.last_sent_at = now
            session.commit()
            sent += 1
            logger.info("Sent digest to %s (%d jobs)", sub.email, len(jobs))
        except Exception:
            errors += 1
            session.rollback()
            logger.exception("Failed to send to %s", sub.email)

    session.close()
    logger.info("Newsletter complete: sent=%d skipped=%d errors=%d", sent, skipped, errors)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
