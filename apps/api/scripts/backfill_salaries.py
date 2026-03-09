"""Backfill missing salary data using regex, then LLM fallback.

Usage:
    uv run python -m scripts.backfill_salaries [--dry-run]

Finds open jobs with no salary data, tries regex extraction first,
then falls back to Gemini Flash Lite via OpenRouter for unstructured text.
"""

import argparse
import logging
import sys
import time

from dotenv import load_dotenv
from sqlalchemy import select

from app.db import get_engine, get_session
from app.ingest.llm_salary_extractor import extract_salary_with_llm
from app.ingest.salary_parser import parse_salary_from_text
from app.models.jobs import Job

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def backfill(dry_run: bool = False) -> None:
    SessionLocal = get_session()
    session = SessionLocal()

    try:
        jobs = session.execute(
            select(Job).where(
                Job.salary_min.is_(None),
                Job.status == "open",
            )
        ).scalars().all()

        logger.info("Found %d open jobs without salary data", len(jobs))

        stats = {"regex": 0, "llm": 0, "none": 0, "error": 0}

        for job in jobs:
            text = job.description_text or ""
            if not text.strip():
                stats["none"] += 1
                continue

            # Try regex first
            parsed = parse_salary_from_text(text)
            source = "regex"

            # Fall back to LLM
            if parsed is None:
                try:
                    parsed = extract_salary_with_llm(text)
                    source = "llm"
                    # Brief pause to avoid rate limits
                    time.sleep(0.5)
                except Exception:
                    logger.exception("LLM extraction failed for job %s", job.slug)
                    stats["error"] += 1
                    continue

            if parsed is None:
                stats["none"] += 1
                logger.debug("No salary found for: %s", job.slug)
                continue

            stats[source] += 1
            logger.info(
                "%s [%s] %s: $%.2f-$%.2f %s",
                "DRY-RUN" if dry_run else "UPDATE",
                source,
                job.slug,
                parsed.min_value,
                parsed.max_value,
                parsed.period,
            )

            if not dry_run:
                job.salary_min = parsed.min_value
                job.salary_max = parsed.max_value
                job.salary_period = parsed.period

        if not dry_run:
            session.commit()
            logger.info("Committed changes")

        logger.info(
            "Done. regex=%d llm=%d none=%d error=%d",
            stats["regex"],
            stats["llm"],
            stats["none"],
            stats["error"],
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing salary data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would change without writing to DB",
    )
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
