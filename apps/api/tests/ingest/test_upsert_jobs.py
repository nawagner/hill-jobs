from datetime import datetime, timezone

from app.ingest.upsert_jobs import upsert_jobs
from app.models.jobs import Job
from app.schemas.ingest import SourceJob


def _make_source_job(**overrides) -> SourceJob:
    defaults = dict(
        source_system="test-source",
        source_organization="Test Org",
        source_job_id="J100",
        source_url="https://example.com/j100",
        title="Software Engineer",
        description_html="<p>Build things</p>",
        description_text="Build things",
        raw_payload={"id": "J100"},
    )
    defaults.update(overrides)
    return SourceJob(**defaults)


def test_new_job_inserts(db_session):
    now = datetime.now(timezone.utc)
    src = _make_source_job()
    result = upsert_jobs(db_session, [src], now)

    assert result.created == 1
    assert result.updated == 0
    assert len(result.seen_ids) == 1

    job = db_session.query(Job).first()
    assert job.title == "Software Engineer"
    assert job.role_kind == "technology"
    assert job.status == "open"
    # SQLite strips tzinfo, so compare without tz
    assert job.first_seen_at.replace(tzinfo=None) == now.replace(tzinfo=None)
    assert job.last_seen_at.replace(tzinfo=None) == now.replace(tzinfo=None)
    assert job.search_document == "Software Engineer Test Org  Build things"


def test_re_upsert_updates_last_seen(db_session):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    src = _make_source_job()

    upsert_jobs(db_session, [src], t1)
    result = upsert_jobs(db_session, [src], t2)

    assert result.unchanged == 1
    assert result.created == 0

    job = db_session.query(Job).first()
    assert job.first_seen_at.replace(tzinfo=None) == t1.replace(tzinfo=None)
    assert job.last_seen_at.replace(tzinfo=None) == t2.replace(tzinfo=None)


def test_changed_fields_update(db_session):
    now = datetime.now(timezone.utc)
    src1 = _make_source_job(title="Software Engineer")
    upsert_jobs(db_session, [src1], now)

    src2 = _make_source_job(title="Senior Software Engineer")
    result = upsert_jobs(db_session, [src2], now)

    assert result.updated == 1
    job = db_session.query(Job).first()
    assert job.title == "Senior Software Engineer"


def test_closed_job_reopens_when_seen(db_session):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    src = _make_source_job()
    upsert_jobs(db_session, [src], t1)

    job = db_session.query(Job).first()
    job.status = "closed"
    db_session.commit()

    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    result = upsert_jobs(db_session, [src], t2)
    assert result.updated == 1

    db_session.refresh(job)
    assert job.status == "open"


def test_salary_fields_inserted(db_session):
    now = datetime.now(timezone.utc)
    src = _make_source_job(salary_min=50000, salary_max=75000, salary_period="yearly")
    upsert_jobs(db_session, [src], now)

    job = db_session.query(Job).first()
    assert float(job.salary_min) == 50000
    assert float(job.salary_max) == 75000
    assert job.salary_period == "yearly"


def test_salary_fields_updated(db_session):
    now = datetime.now(timezone.utc)
    src1 = _make_source_job()
    upsert_jobs(db_session, [src1], now)

    job = db_session.query(Job).first()
    assert job.salary_min is None

    src2 = _make_source_job(salary_min=60000, salary_max=80000, salary_period="yearly")
    result = upsert_jobs(db_session, [src2], now)
    assert result.updated == 1

    db_session.refresh(job)
    assert float(job.salary_min) == 60000
    assert float(job.salary_max) == 80000
    assert job.salary_period == "yearly"


def test_source_organization_updated(db_session):
    now = datetime.now(timezone.utc)
    src1 = _make_source_job(source_organization="House Democrats")
    upsert_jobs(db_session, [src1], now)

    src2 = _make_source_job(source_organization="Rep. Jane Smith")
    result = upsert_jobs(db_session, [src2], now)
    assert result.updated == 1

    job = db_session.query(Job).first()
    assert job.source_organization == "Rep. Jane Smith"


def test_hash_based_slug_for_no_job_id(db_session):
    now = datetime.now(timezone.utc)
    src = _make_source_job(source_job_id=None)
    upsert_jobs(db_session, [src], now)

    job = db_session.query(Job).first()
    assert job.slug.startswith("test-source-")
    assert len(job.slug) > 12
