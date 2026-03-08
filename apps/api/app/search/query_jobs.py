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
