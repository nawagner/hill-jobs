from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jobs import Job
from app.models.sync_runs import SourceSyncRun


@dataclass
class MarkMissingResult:
    closed_count: int = 0
    closed_titles: list[str] = field(default_factory=list)


def mark_missing_jobs(
    session: Session,
    source_system: str,
    seen_job_ids: set[int],
    now: datetime,
) -> MarkMissingResult:
    result = MarkMissingResult()

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
        return result

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

    for job in open_jobs:
        if job.id in seen_job_ids:
            continue
        # Only close if last_seen_at is older than the 2nd most recent successful sync
        if job.last_seen_at and job.last_seen_at < second_most_recent.started_at:
            job.status = "closed"
            result.closed_count += 1
            result.closed_titles.append(job.title)

    if result.closed_count:
        session.commit()

    return result
