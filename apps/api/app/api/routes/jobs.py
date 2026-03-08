from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.categorization.role_kinds import ROLE_KINDS
from app.db import get_db
from app.models.jobs import Job
from app.schemas.jobs import JobDetail, JobListItem, JobSearchResponse
from app.search.query_jobs import query_jobs

router = APIRouter(prefix="/api")


@router.get("/jobs", response_model=JobSearchResponse)
def list_jobs(
    q: str | None = None,
    role_kind: str | None = None,
    organization: str | None = None,
    status: str | None = None,
    posted_since_days: int | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    items, total = query_jobs(
        db,
        q=q,
        role_kind=role_kind,
        organization=organization,
        status=status,
        posted_since_days=posted_since_days,
        page=page,
    )
    return JobSearchResponse(
        items=[JobListItem.model_validate(j, from_attributes=True) for j in items],
        total=total,
        page=page,
    )


@router.get("/jobs/{slug}", response_model=JobDetail)
def get_job(slug: str, db: Session = Depends(get_db)):
    job = db.execute(select(Job).where(Job.slug == slug)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobDetail.model_validate(job, from_attributes=True)


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db)) -> list[str]:
    stmt = (
        select(Job.source_organization)
        .where(Job.status != "closed")
        .distinct()
        .order_by(Job.source_organization)
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/role-kinds")
def list_role_kinds() -> list[str]:
    return list(ROLE_KINDS)
