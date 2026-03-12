import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.source_registry import SourceAdapter
from app.ingest.upsert_jobs import upsert_jobs
from app.models.sync_runs import SourceSyncRun

logger = logging.getLogger(__name__)


@dataclass
class SyncRunResult:
    status: str
    jobs_found: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    closed: int = 0
    error: str | None = None


def run_all_sources(
    session: Session,
    registry: dict[str, SourceAdapter],
    http_client: httpx.Client,
) -> dict[str, SyncRunResult]:
    results: dict[str, SyncRunResult] = {}

    for name, adapter in registry.items():
        now = datetime.now(timezone.utc)
        sync_run = SourceSyncRun(
            source_system=name,
            started_at=now,
            status="running",
        )
        session.add(sync_run)
        session.commit()

        try:
            source_jobs = adapter.fetch_jobs(http_client)
            upsert_result = upsert_jobs(session, source_jobs, now)
            missing_result = mark_missing_jobs(
                session, name, set(upsert_result.seen_ids), now
            )

            sync_run.status = "success"
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.jobs_found = len(source_jobs)
            sync_run.jobs_created = upsert_result.created
            sync_run.jobs_updated = upsert_result.updated
            sync_run.jobs_closed = missing_result.closed_count
            session.commit()

            results[name] = SyncRunResult(
                status="success",
                jobs_found=len(source_jobs),
                created=upsert_result.created,
                updated=upsert_result.updated,
                skipped=upsert_result.skipped,
                closed=missing_result.closed_count,
            )
            logger.info(
                "Source %s: found=%d created=%d updated=%d skipped=%d closed=%d",
                name, len(source_jobs), upsert_result.created,
                upsert_result.updated, upsert_result.skipped,
                missing_result.closed_count,
            )
        except Exception as e:
            logger.exception("Source %s failed: %s", name, e)
            sync_run.status = "error"
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.error_message = str(e)
            session.commit()

            results[name] = SyncRunResult(status="error", error=str(e))

    return results
