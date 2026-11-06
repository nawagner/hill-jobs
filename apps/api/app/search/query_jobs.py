from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session

from app.data.member_committees import COMMITTEES
from app.data.members import employer_party, find_member
from app.data.organizations import TOP_ORGANIZATIONS, employer_organization, staff_committee
from app.models.jobs import Job


def _employer_condition(session: Session, keep: Callable[[str, str], bool]):
    """SQL condition matching jobs whose (source_system, source_organization) passes keep.

    Party, state and committee come from matching employer names in Python
    (spellings vary by source), so this checks each distinct employer once.
    """
    pairs = session.execute(
        select(Job.source_system, Job.source_organization).distinct()
    ).all()
    by_system: dict[str, list[str]] = {}
    for system, org in pairs:
        if keep(system, org):
            by_system.setdefault(system, []).append(org)
    if not by_system:
        return false()
    return or_(
        *(
            and_(Job.source_system == system, Job.source_organization.in_(orgs))
            for system, orgs in by_system.items()
        )
    )


def query_jobs(
    session: Session,
    *,
    q: str | None = None,
    role_kind: str | None = None,
    organization: str | None = None,
    member: str | None = None,
    status: str | None = None,
    posted_since_days: int | None = None,
    posted_before_days: int | None = None,
    new_since: datetime | None = None,
    order_undated_by_first_seen: bool = False,
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

    if organization in TOP_ORGANIZATIONS:
        stmt = stmt.where(
            _employer_condition(
                session, lambda system, org: employer_organization(system, org) == organization
            )
        )
    elif organization:
        # Links and alert subscriptions from before organizations were grouped
        # name a single office ("Clerk of the House").
        stmt = stmt.where(Job.source_organization == organization)

    if member:
        wanted = find_member(member)
        if wanted:
            stmt = stmt.where(
                _employer_condition(
                    session,
                    lambda system, org: (m := find_member(org)) is not None and m.id == wanted.id,
                )
            )
        else:
            stmt = stmt.where(Job.source_organization == member)

    # HVAPS and CSOD listings have no posting date; date them by when we first
    # saw them, or every date filter (and the newsletter) would hide them.
    posted_on = func.coalesce(Job.posted_at, Job.first_seen_at)

    if posted_since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_since_days)
        stmt = stmt.where(posted_on >= cutoff)

    if posted_before_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_before_days)
        stmt = stmt.where(posted_on < cutoff)

    if new_since is not None:
        # New to Hill Jobs since then (covers undated and late-ingested
        # listings), or (re)posted since then.
        stmt = stmt.where(
            or_(Job.first_seen_at >= new_since, Job.posted_at >= new_since)
        )

    if salary_min is not None:
        if salary_min == 0:
            stmt = stmt.where(
                or_(Job.salary_min.isnot(None), Job.salary_max.isnot(None))
            )
        else:
            stmt = stmt.where(Job.salary_min >= salary_min)

    if party:
        stmt = stmt.where(
            _employer_condition(
                session, lambda system, org: employer_party(system, org) == party
            )
        )

    if state:
        stmt = stmt.where(
            _employer_condition(
                session,
                lambda system, org: (m := find_member(org)) is not None and m.state == state,
            )
        )

    if committee:
        committee_ids = {committee}
        for cid, meta in COMMITTEES.items():
            if meta.get("parent") == committee:
                committee_ids.add(cid)
        # The committee's own staff, plus the offices of members who sit on it.
        stmt = stmt.where(
            _employer_condition(
                session,
                lambda system, org: staff_committee(system, org) in committee_ids
                or (
                    (m := find_member(org)) is not None
                    and bool(committee_ids & set(m.committees))
                ),
            )
        )

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
                or_(
                    Job.title.ilike(pattern),
                    Job.source_organization.ilike(pattern),
                    Job.location_text.ilike(pattern),
                    Job.description_text.ilike(pattern),
                )
            )

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0

    # Apply pagination and ordering. The site lists undated jobs last; the
    # newsletter dates them by first_seen_at so its 100-job cap doesn't drop them first.
    newest = posted_on if order_undated_by_first_seen else Job.posted_at
    stmt = stmt.order_by(newest.desc().nullslast(), Job.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = list(session.execute(stmt).scalars().all())
    return items, total
