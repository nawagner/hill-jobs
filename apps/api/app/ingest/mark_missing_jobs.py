from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jobs import Job
from app.models.sync_runs import SourceSyncRun


def mark_missing_jobs(
    session: Session,
    source_system: str,
    seen_job_ids: set[int],
    now: datetime,
) -> int:
    # Get the 2 most recent successful sync runs for this source
    recent_runs = (
        session.execute(
            select(SourceSyncRun)
            .where(
                SourceSyncRun.source_system == source_system,
                SourceSyncRun.status == "success",
            )
            .order_by(SourceSyncRun.started_at.desc())
            .limit(2)
        )
        .scalars()
        .all()
    )

    # Need at least 2 successful syncs to close anything
    if len(recent_runs) < 2:
        return 0

    second_most_recent = recent_runs[-1]

    # Find open jobs for this source that were NOT seen in this sync
    open_jobs = (
        session.execute(
            select(Job).where(
                Job.source_system == source_system,
                Job.status == "open",
            )
        )
        .scalars()
        .all()
    )

    closed_count = 0
    for job in open_jobs:
        if job.id in seen_job_ids:
            continue
        # Only close if last_seen_at is older than the 2nd most recent successful sync
        if job.last_seen_at and job.last_seen_at < second_most_recent.started_at:
            job.status = "closed"
            closed_count += 1

    if closed_count:
        session.commit()

    return closed_count
