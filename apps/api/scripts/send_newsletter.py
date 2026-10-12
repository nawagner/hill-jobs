"""Weekly newsletter sender.

Sends digest emails to confirmed subscribers with jobs matching their filters
posted in the last 7 days. Run weekly by the `newsletter-cron` Railway service.
Pass --dry-run to log what would be sent without sending or recording anything.
"""

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

# Make `app` importable when run as `python scripts/send_newsletter.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import get_engine
from app.lib.email import send_email
from app.lib.email_templates import build_digest_html
from app.models.subscribers import Subscriber
from app.search.query_jobs import query_jobs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Don't send twice in one week, even if the cron is re-run.
MIN_DAYS_BETWEEN_SENDS = 6


@dataclass
class NewsletterResult:
    sent: int = 0
    skipped: int = 0
    errors: int = 0


def send_digests(
    session: Session,
    *,
    api_key: str,
    site_base_url: str,
    now: datetime | None = None,
    send: Callable[..., None] = send_email,
    dry_run: bool = False,
) -> NewsletterResult:
    now = now or datetime.now(timezone.utc)
    result = NewsletterResult()

    subscribers = session.execute(
        select(Subscriber).where(Subscriber.confirmed == True)  # noqa: E712
    ).scalars().all()
    logger.info("Found %d confirmed subscribers", len(subscribers))

    for sub in subscribers:
        last_sent = sub.last_sent_at
        if last_sent and last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if last_sent and (now - last_sent) < timedelta(days=MIN_DAYS_BETWEEN_SENDS):
            result.skipped += 1
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
            result.skipped += 1
            continue

        subject = f"Hill Jobs Weekly: {total} new position{'s' if total != 1 else ''} matching your filters"

        if dry_run:
            logger.info("[dry run] Would send to %s (%d jobs)", _mask(sub.email), total)
            result.sent += 1
            continue

        try:
            send(
                api_key=api_key,
                to=sub.email,
                subject=subject,
                html=build_digest_html(jobs, sub.unsubscribe_token, site_base_url),
            )
            sub.last_sent_at = now
            session.commit()
            result.sent += 1
            logger.info("Sent digest to %s (%d jobs)", _mask(sub.email), total)
        except Exception:
            result.errors += 1
            session.rollback()
            logger.exception("Failed to send to %s", _mask(sub.email))

    return result


def _mask(email: str) -> str:
    """Keep subscriber addresses out of logs: jane.doe@example.com -> j***@example.com."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="log what would be sent; send nothing")
    args = parser.parse_args()

    settings = Settings()
    if not settings.resend_api_key and not args.dry_run:
        logger.error("RESEND_API_KEY not set; aborting")
        sys.exit(1)

    engine = get_engine()
    session = sessionmaker(bind=engine)()
    try:
        result = send_digests(
            session,
            api_key=settings.resend_api_key,
            site_base_url=settings.site_base_url,
            dry_run=args.dry_run,
        )
    finally:
        session.close()
        engine.dispose()

    logger.info(
        "Newsletter complete%s: sent=%d skipped=%d errors=%d",
        " (dry run)" if args.dry_run else "",
        result.sent, result.skipped, result.errors,
    )
    if result.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
