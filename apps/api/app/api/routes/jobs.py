from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.categorization.role_kinds import ROLE_KINDS
from app.data.member_committees import COMMITTEES
from app.data.member_data import MEMBERS
from app.data.members import find_member
from app.data.organizations import TOP_ORGANIZATIONS, employer_organization
from app.db import get_db
from app.models.jobs import Job
from app.schemas.jobs import (
    CommitteeItem,
    JobDetail,
    JobListItem,
    JobSearchResponse,
    MemberItem,
    OrganizationItem,
    StateItem,
)
from app.search.query_jobs import query_jobs

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands",
    "PR": "Puerto Rico", "VI": "U.S. Virgin Islands",
}

router = APIRouter(prefix="/api")


def _get_member_committee_names(org_name: str) -> list[str] | None:
    """Resolve a member's committee codes to unique parent committee names."""
    member = find_member(org_name)
    codes = member.committees if member else None
    if not codes:
        return None
    # Collect unique parent committee names (skip subcommittees to keep it concise)
    names: list[str] = []
    seen: set[str] = set()
    for code in codes:
        meta = COMMITTEES.get(code)
        if not meta:
            continue
        # If it's a subcommittee, use the parent name instead
        parent_code = meta.get("parent") or code
        parent_meta = COMMITTEES.get(parent_code, meta)
        name = parent_meta["name"]
        if name not in seen:
            seen.add(name)
            names.append(name)
    return sorted(names) if names else None


@router.get("/jobs", response_model=JobSearchResponse)
def list_jobs(
    q: str | None = None,
    role_kind: str | None = None,
    organization: str | None = None,
    member: str | None = None,
    status: str | None = None,
    posted_since_days: int | None = None,
    posted_before_days: int | None = None,
    salary_min: int | None = None,
    party: str | None = None,
    state: str | None = None,
    committee: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    items, total = query_jobs(
        db,
        q=q,
        role_kind=role_kind,
        organization=organization,
        member=member,
        status=status,
        posted_since_days=posted_since_days,
        posted_before_days=posted_before_days,
        salary_min=salary_min,
        party=party,
        state=state,
        committee=committee,
        page=page,
    )
    job_items = []
    for j in items:
        item = JobListItem.model_validate(j, from_attributes=True)
        item.organization = employer_organization(j.source_system, j.source_organization)
        item.member_committees = _get_member_committee_names(j.source_organization)
        job_items.append(item)
    return JobSearchResponse(
        items=job_items,
        total=total,
        page=page,
    )


@router.get("/jobs/{slug}", response_model=JobDetail)
def get_job(slug: str, db: Session = Depends(get_db)):
    job = db.execute(select(Job).where(Job.slug == slug)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    detail = JobDetail.model_validate(job, from_attributes=True)
    detail.organization = employer_organization(job.source_system, job.source_organization)
    detail.member_committees = _get_member_committee_names(job.source_organization)
    return detail


def _open_employers(db: Session) -> list[tuple[str, str]]:
    stmt = (
        select(Job.source_system, Job.source_organization)
        .where(Job.status != "closed")
        .distinct()
    )
    return [(system, org) for system, org in db.execute(stmt).all()]


@router.get("/organizations", response_model=list[OrganizationItem])
def list_organizations(db: Session = Depends(get_db)) -> list[OrganizationItem]:
    """Top-level organizations with open jobs, e.g. "U.S. Senate", "Library of Congress"."""
    present = {employer_organization(system, org) for system, org in _open_employers(db)}
    return [OrganizationItem(name=name) for name in TOP_ORGANIZATIONS if name in present]


@router.get("/members", response_model=list[MemberItem])
def list_members(db: Session = Depends(get_db)) -> list[MemberItem]:
    """Members of Congress whose offices have open jobs, senators first."""
    members = {}
    for _, org in _open_employers(db):
        m = find_member(org)
        if m:
            members[m.id] = m
    ordered = sorted(
        members.values(),
        key=lambda m: (m.chamber != "senate", m.name.split(" ", 1)[1]),
    )
    return [
        MemberItem(name=m.name, chamber=m.chamber, party=m.party, state=m.state)
        for m in ordered
    ]


@router.get("/role-kinds")
def list_role_kinds() -> list[str]:
    return list(ROLE_KINDS)


@router.get("/states", response_model=list[StateItem])
def list_states() -> list[StateItem]:
    codes = sorted({m["state"] for m in MEMBERS})
    return [
        StateItem(code=code, name=STATE_NAMES.get(code, code))
        for code in codes
        if code in STATE_NAMES
    ]


@router.get("/committees", response_model=list[CommitteeItem])
def list_committees() -> list[CommitteeItem]:
    # Build parent committees with nested subcommittees
    parents: dict[str, CommitteeItem] = {}
    children: dict[str, list[CommitteeItem]] = {}

    for cid, meta in COMMITTEES.items():
        item = CommitteeItem(
            id=cid,
            name=meta["name"],
            chamber=meta["chamber"],
        )
        if meta.get("parent") is None:
            parents[cid] = item
        else:
            children.setdefault(meta["parent"], []).append(item)

    # Nest subcommittees into their parents
    for parent_id, subs in children.items():
        if parent_id in parents:
            parents[parent_id].subcommittees = sorted(subs, key=lambda s: s.name)

    return sorted(parents.values(), key=lambda c: (c.chamber, c.name))
