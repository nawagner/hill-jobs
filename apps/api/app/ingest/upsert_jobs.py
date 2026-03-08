from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.categorization.classify_job import classify_job
from app.models.jobs import Job
from app.schemas.ingest import SourceJob
from app.search.slugs import generate_slug


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    seen_ids: list[int] = field(default_factory=list)


def upsert_jobs(
    session: Session,
    jobs: list[SourceJob],
    now: datetime,
) -> UpsertResult:
    result = UpsertResult()

    for src in jobs:
        existing = _find_existing(session, src)

        if existing:
            changed = _update_existing(existing, src, now)
            if changed:
                result.updated += 1
            else:
                result.unchanged += 1
            result.seen_ids.append(existing.id)
        else:
            new_job = _insert_new(session, src, now)
            result.created += 1
            session.flush()
            result.seen_ids.append(new_job.id)

    session.commit()
    return result


def _find_existing(session: Session, src: SourceJob) -> Job | None:
    if src.source_job_id:
        job = session.execute(
            select(Job).where(
                and_(
                    Job.source_system == src.source_system,
                    Job.source_job_id == src.source_job_id,
                )
            )
        ).scalar_one_or_none()
        if job:
            return job

    slug = generate_slug(
        src.source_system,
        src.source_job_id,
        src.title,
        src.source_organization,
        src.source_url,
    )
    return session.execute(
        select(Job).where(Job.slug == slug)
    ).scalar_one_or_none()


def _update_existing(job: Job, src: SourceJob, now: datetime) -> bool:
    changed = False
    for attr in ("title", "description_html", "description_text", "location_text",
                 "employment_type", "source_url", "posted_at", "closing_at"):
        new_val = getattr(src, attr)
        if new_val is not None and getattr(job, attr) != new_val:
            setattr(job, attr, new_val)
            changed = True

    job.last_seen_at = now
    job.last_synced_at = now
    job.raw_payload = src.raw_payload
    job.search_document = f"{src.title} {src.description_text}"

    # Re-open if it was previously closed but now seen again
    if job.status == "closed":
        job.status = "open"
        changed = True

    return changed


def _insert_new(session: Session, src: SourceJob, now: datetime) -> Job:
    slug = generate_slug(
        src.source_system,
        src.source_job_id,
        src.title,
        src.source_organization,
        src.source_url,
    )
    role_kind = classify_job(src.title, src.description_text, src.source_organization)

    job = Job(
        slug=slug,
        title=src.title,
        source_organization=src.source_organization,
        source_system=src.source_system,
        source_job_id=src.source_job_id,
        source_url=src.source_url,
        status="open",
        role_kind=role_kind,
        location_text=src.location_text,
        employment_type=src.employment_type,
        description_html=src.description_html,
        description_text=src.description_text,
        search_document=f"{src.title} {src.description_text}",
        raw_payload=src.raw_payload,
        posted_at=src.posted_at,
        closing_at=src.closing_at,
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add(job)
    return job
