import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.categorization.classify_job import classify_job
from app.ingest.llm_salary_extractor import extract_salary_with_llm
from app.ingest.salary_parser import parse_salary_from_text
from app.models.jobs import Job
from app.schemas.ingest import SourceJob
from app.search.slugs import generate_slug

logger = logging.getLogger(__name__)

# Source systems known to overlap — checked for cross-source duplicates
_CROSS_SOURCE_PAIRS: dict[str, list[str]] = {
    "house-hvaps": ["house-dems-resumebank"],
    "house-dems-resumebank": ["house-hvaps"],
}


@dataclass
class JobChange:
    title: str
    organization: str
    changed_fields: list[str]


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    seen_ids: list[int] = field(default_factory=list)
    created_details: list[str] = field(default_factory=list)
    updated_details: list[JobChange] = field(default_factory=list)
    reopened_details: list[str] = field(default_factory=list)


def upsert_jobs(
    session: Session,
    jobs: list[SourceJob],
    now: datetime,
) -> UpsertResult:
    result = UpsertResult()

    for src in jobs:
        existing = _find_existing(session, src)

        # Enrich salary via regex then LLM if adapter provided none
        if src.salary_min is None and src.description_text:
            _enrich_salary(src, existing)

        if existing:
            changed_fields = _update_existing(existing, src, now)
            if changed_fields:
                result.updated += 1
                result.updated_details.append(JobChange(
                    title=src.title,
                    organization=src.source_organization,
                    changed_fields=changed_fields,
                ))
                if "status (reopened)" in changed_fields:
                    result.reopened_details.append(src.title)
            else:
                result.unchanged += 1
            result.seen_ids.append(existing.id)
        else:
            # Check for cross-source duplicates before inserting
            cross_dup = _find_cross_source_duplicate(session, src)
            if cross_dup:
                logger.info(
                    "Skipping cross-source duplicate: %s '%s' at '%s' "
                    "(matches %s job id=%d)",
                    src.source_system, src.title, src.source_organization,
                    cross_dup.source_system, cross_dup.id,
                )
                result.skipped += 1
                continue

            new_job = _insert_new(session, src, now)
            result.created += 1
            result.created_details.append(src.title)
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


def _update_existing(job: Job, src: SourceJob, now: datetime) -> list[str]:
    """Update an existing job. Returns list of field names that changed."""
    changed_fields: list[str] = []
    for attr in ("title", "description_html", "description_text", "location_text",
                 "employment_type", "source_organization", "source_url",
                 "posted_at", "closing_at",
                 "salary_min", "salary_max", "salary_period"):
        new_val = getattr(src, attr)
        if new_val is not None and getattr(job, attr) != new_val:
            setattr(job, attr, new_val)
            changed_fields.append(attr)

    job.last_seen_at = now
    job.last_synced_at = now
    job.raw_payload = src.raw_payload
    job.search_document = f"{src.title} {src.source_organization} {src.location_text or ''} {src.description_text}"

    # Re-open if it was previously closed but now seen again
    if job.status == "closed":
        job.status = "open"
        changed_fields.append("status (reopened)")

    return changed_fields


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
        search_document=f"{src.title} {src.source_organization} {src.location_text or ''} {src.description_text}",
        salary_min=src.salary_min,
        salary_max=src.salary_max,
        salary_period=src.salary_period,
        raw_payload=src.raw_payload,
        posted_at=src.posted_at,
        closing_at=src.closing_at,
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add(job)
    return job


def _enrich_salary(src: SourceJob, existing: Job | None) -> None:
    """Try regex then LLM to fill in missing salary data on a SourceJob.

    For existing jobs, only tries regex — LLM is skipped since we already
    attempted extraction on a previous ingestion and the description text
    is unlikely to have changed to include salary info.
    For new jobs, tries regex then LLM.
    """
    # Existing job already has salary — nothing to do
    if existing and existing.salary_min is not None:
        return

    parsed = parse_salary_from_text(src.description_text)
    if parsed is None and existing is None:
        # Only call LLM for new jobs — existing jobs without salary have
        # already been processed and their descriptions likely don't contain it
        try:
            parsed = extract_salary_with_llm(src.description_text)
        except Exception:
            logger.exception("LLM salary extraction failed for %s", src.source_job_id)
            return

    if parsed is None:
        return

    src.salary_min = parsed.min_value
    src.salary_max = parsed.max_value
    src.salary_period = parsed.period


def _find_cross_source_duplicate(session: Session, src: SourceJob) -> Job | None:
    """Check if a job from one source already exists from another overlapping source."""
    partner_sources = _CROSS_SOURCE_PAIRS.get(src.source_system)
    if not partner_sources:
        return None

    normalized_title = _normalize_for_matching(src.title)
    normalized_org = _normalize_for_matching(src.source_organization)

    candidates = (
        session.execute(
            select(Job).where(
                Job.source_system.in_(partner_sources),
                Job.status == "open",
            )
        )
        .scalars()
        .all()
    )

    for job in candidates:
        if (
            _normalize_for_matching(job.title) == normalized_title
            and _normalize_for_matching(job.source_organization) == normalized_org
        ):
            return job
    return None


def _normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy cross-source matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
