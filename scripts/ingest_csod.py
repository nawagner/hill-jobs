#!/usr/bin/env python3
"""CSOD ingest script.

Runs the CSOD adapters (House CAO and USCP) using Playwright,
then upserts the jobs into the Railway Postgres database.

Requires:
  - playwright installed (pip) with browsers: playwright install chromium
  - DATABASE_URL env var pointing to Railway Postgres

Usage:
  DATABASE_URL="postgresql+psycopg://..." python scripts/ingest_csod.py
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add the API app to the path so we can import its modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.config import Settings
from app.ingest.adapters.csod import HOUSE_CAO_CONFIG, USCP_CONFIG, CsodAdapter
from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.upsert_jobs import upsert_jobs
from app.models.sync_runs import SourceSyncRun

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)

    adapters = [
        CsodAdapter(HOUSE_CAO_CONFIG),
        CsodAdapter(USCP_CONFIG),
    ]

    with httpx.Client(timeout=60.0) as client, Session(engine) as session:
        for adapter in adapters:
            name = adapter.source_system
            now = datetime.now(timezone.utc)
            sync_run = SourceSyncRun(
                source_system=name, started_at=now, status="running"
            )
            session.add(sync_run)
            session.commit()

            try:
                source_jobs = adapter.fetch_jobs(client)
                result = upsert_jobs(session, source_jobs, now)
                closed = mark_missing_jobs(
                    session, name, set(result.seen_ids), now
                )

                sync_run.status = "success"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.jobs_found = len(source_jobs)
                sync_run.jobs_created = result.created
                sync_run.jobs_updated = result.updated
                sync_run.jobs_closed = closed
                session.commit()

                logger.info(
                    "%s: found=%d created=%d updated=%d closed=%d",
                    name, len(source_jobs), result.created,
                    result.updated, closed,
                )
            except Exception as e:
                logger.exception("%s failed: %s", name, e)
                sync_run.status = "error"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.error_message = str(e)
                session.commit()


if __name__ == "__main__":
    main()
