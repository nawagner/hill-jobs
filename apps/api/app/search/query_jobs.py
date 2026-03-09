from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.jobs import Job


def query_jobs(
    session: Session,
    *,
    q: str | None = None,
    role_kind: str | None = None,
    organization: str | None = None,
    status: str | None = None,
    posted_since_days: int | None = None,
    posted_before_days: int | None = None,
    salary_min: int | None = None,
    party: str | None = None,
    state: str | None = None,
    committee: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Job], int]:
    page_size = min(page_size, 100)
    stmt = select(Job)

    # Default: exclude closed jobs unless explicitly requested
    if status:
        stmt = stmt.where(Job.status == status)
    else:
        stmt = stmt.where(Job.status != "closed")

    if role_kind:
        stmt = stmt.where(Job.role_kind == role_kind)

    if organization:
        stmt = stmt.where(Job.source_organization == organization)

    if posted_since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_since_days)
        stmt = stmt.where(Job.posted_at >= cutoff)

    if posted_before_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_before_days)
        stmt = stmt.where(Job.posted_at < cutoff)

    if salary_min is not None:
        if salary_min == 0:
            stmt = stmt.where(
                or_(Job.salary_min.isnot(None), Job.salary_max.isnot(None))
            )
        else:
            stmt = stmt.where(Job.salary_min >= salary_min)

    if party:
        from app.data.member_parties import MEMBER_PARTIES
        matching = [name for name, p in MEMBER_PARTIES.items() if p == party]
        if matching:
            stmt = stmt.where(Job.source_organization.in_(matching))
        else:
            stmt = stmt.where(False)

    if state:
        from app.data.member_states import MEMBER_STATES
        matching = [name for name, s in MEMBER_STATES.items() if s == state]
        if matching:
            stmt = stmt.where(Job.source_organization.in_(matching))
        else:
            stmt = stmt.where(False)

    if committee:
        from app.data.member_committees import COMMITTEES, MEMBER_COMMITTEES
        committee_ids = {committee}
        for cid, meta in COMMITTEES.items():
            if meta.get("parent") == committee:
                committee_ids.add(cid)
        matching = [name for name, comms in MEMBER_COMMITTEES.items() if committee_ids & set(comms)]
        if matching:
            stmt = stmt.where(Job.source_organization.in_(matching))
        else:
            stmt = stmt.where(False)

    if q:
        dialect = session.bind.dialect.name if session.bind else "sqlite"
        if dialect == "postgresql":
            stmt = stmt.where(
                func.to_tsvector("english", func.coalesce(Job.search_document, "")).op(
                    "@@"
                )(func.plainto_tsquery("english", q))
            )
        else:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(Job.title.ilike(pattern), Job.description_text.ilike(pattern))
            )

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0

    # Apply pagination and ordering
    stmt = stmt.order_by(Job.posted_at.desc().nullslast(), Job.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = list(session.execute(stmt).scalars().all())
    return items, total
