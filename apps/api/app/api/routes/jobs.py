import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.categorization.role_kinds import ROLE_KINDS
from app.db import get_db
from app.models.jobs import Job
from app.schemas.jobs import JobDetail, JobListItem, JobSearchResponse, OrganizationItem
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


_PARTY_RE = re.compile(r"\(([RD])-[A-Z]{2}\)")


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db)) -> list[OrganizationItem]:
    stmt = (
        select(Job.source_organization, Job.source_system)
        .where(Job.status != "closed")
        .distinct()
        .order_by(Job.source_organization)
    )
    rows = db.execute(stmt).all()

    # For Senator entries, look up party from raw_payload
    senator_parties: dict[str, str] = {}
    senator_orgs = [name for name, sys in rows if name.startswith("Senator ")]
    if senator_orgs:
        party_stmt = (
            select(Job.source_organization, Job.raw_payload)
            .where(Job.source_organization.in_(senator_orgs))
            .where(Job.raw_payload.isnot(None))
            .distinct(Job.source_organization)
        )
        for org, payload in db.execute(party_stmt).all():
            if org in senator_parties:
                continue
            desc = (payload or {}).get("shortDescription", "")
            m = _PARTY_RE.search(desc)
            if m:
                senator_parties[org] = m.group(1)

    result: list[OrganizationItem] = []
    for name, source_system in rows:
        party = senator_parties.get(name)
        result.append(OrganizationItem(
            name=name,
            source_system=source_system,
            party=party,
        ))
    return result


@router.get("/role-kinds")
def list_role_kinds() -> list[str]:
    return list(ROLE_KINDS)
