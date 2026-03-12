from datetime import datetime, timezone

from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.upsert_jobs import upsert_jobs
from app.models.sync_runs import SourceSyncRun
from app.schemas.ingest import SourceJob


def _make_source_job(job_id: str = "J100") -> SourceJob:
    return SourceJob(
        source_system="test-source",
        source_organization="Test Org",
        source_job_id=job_id,
        source_url=f"https://example.com/{job_id}",
        title="Test Job",
        description_html="<p>Test</p>",
        description_text="Test",
        raw_payload={},
    )


def _add_sync_run(session, source_system: str, started_at: datetime, status: str = "success"):
    run = SourceSyncRun(
        source_system=source_system,
        started_at=started_at,
        finished_at=started_at,
        status=status,
    )
    session.add(run)
    session.commit()
    return run


def test_no_closure_with_one_sync(db_session):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    src = _make_source_job()
    upsert_jobs(db_session, [src], t1)
    _add_sync_run(db_session, "test-source", t1)

    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    result = mark_missing_jobs(db_session, "test-source", set(), t2)
    assert result.closed_count == 0


def test_closure_after_two_missed_syncs(db_session):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    src = _make_source_job()
    upsert_jobs(db_session, [src], t1)

    # Two successful syncs where the job was NOT seen
    _add_sync_run(db_session, "test-source", datetime(2026, 1, 2, tzinfo=timezone.utc))
    _add_sync_run(db_session, "test-source", datetime(2026, 1, 3, tzinfo=timezone.utc))

    t3 = datetime(2026, 1, 4, tzinfo=timezone.utc)
    result = mark_missing_jobs(db_session, "test-source", set(), t3)
    assert result.closed_count == 1
    assert result.closed_titles == ["Test Job"]

    from app.models.jobs import Job
    job = db_session.query(Job).first()
    assert job.status == "closed"


def test_job_not_closed_if_seen_in_current_sync(db_session):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    src = _make_source_job()
    result = upsert_jobs(db_session, [src], t1)

    _add_sync_run(db_session, "test-source", datetime(2026, 1, 2, tzinfo=timezone.utc))
    _add_sync_run(db_session, "test-source", datetime(2026, 1, 3, tzinfo=timezone.utc))

    missing_result = mark_missing_jobs(db_session, "test-source", set(result.seen_ids), t1)
    assert missing_result.closed_count == 0
