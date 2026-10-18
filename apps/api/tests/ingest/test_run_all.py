from datetime import datetime, timezone

import httpx

from app.ingest.run_all import run_all_sources
from app.ingest.upsert_jobs import upsert_jobs
from app.models.jobs import Job
from app.models.sync_runs import SourceSyncRun
from app.schemas.ingest import SourceJob


class _SuccessAdapter:
    source_system = "good-source"

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        return [
            SourceJob(
                source_system="good-source",
                source_organization="Good Org",
                source_job_id="G1",
                source_url="https://example.com/g1",
                title="Good Job",
                description_html="<p>Good</p>",
                description_text="Good",
                raw_payload={},
            )
        ]


class _EmptyAdapter:
    source_system = "empty-source"

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        return []


class _ConfirmedEmptyAdapter:
    """Like CsodAdapter: returns [] only when the site confirmed zero openings."""

    source_system = "confirmed-empty"
    empty_is_authoritative = True

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        return []


class _NotAuthoritativeEmptyAdapter:
    source_system = "unconfirmed-empty"
    empty_is_authoritative = False

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        return []


class _FailAdapter:
    source_system = "bad-source"

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        raise RuntimeError("scrape failed")


def test_one_failure_does_not_abort_others(db_session):
    registry = {
        "good-source": _SuccessAdapter(),
        "bad-source": _FailAdapter(),
    }
    client = httpx.Client()
    results = run_all_sources(db_session, registry, client)
    client.close()

    assert results["good-source"].status == "success"
    assert results["good-source"].created == 1
    assert results["bad-source"].status == "error"
    assert "scrape failed" in results["bad-source"].error

    # Verify sync runs were recorded
    runs = db_session.query(SourceSyncRun).all()
    assert len(runs) == 2
    statuses = {r.source_system: r.status for r in runs}
    assert statuses["good-source"] == "success"
    assert statuses["bad-source"] == "error"


def test_empty_fetch_does_not_close_existing_jobs(db_session):
    """An adapter returning [] (e.g. a swallowed scrape failure) must not
    count as a successful sync, so repeated empty runs never close jobs."""
    client = httpx.Client()
    for _ in range(3):
        run_all_sources(db_session, {"good-source": _SuccessAdapter()}, client)

    for _ in range(3):
        results = run_all_sources(db_session, {"good-source": _EmptyAdapter()}, client)
    client.close()

    assert results["good-source"].status == "empty"
    job = db_session.query(Job).one()
    assert job.status == "open"

    statuses = [r.status for r in db_session.query(SourceSyncRun).all()]
    assert statuses.count("success") == 3
    assert statuses.count("empty") == 3


def test_authoritative_empty_fetch_is_a_successful_sync(db_session):
    client = httpx.Client()
    results = run_all_sources(db_session, {"confirmed-empty": _ConfirmedEmptyAdapter()}, client)
    client.close()

    result = results["confirmed-empty"]
    assert result.status == "success"
    assert result.jobs_found == 0
    assert result.closed == 0

    run = db_session.query(SourceSyncRun).one()
    assert run.source_system == "confirmed-empty"
    assert run.status == "success"
    assert run.jobs_found == 0
    assert run.jobs_closed == 0
    assert run.finished_at is not None


def test_authoritative_empty_is_per_adapter(db_session):
    registry = {
        "confirmed-empty": _ConfirmedEmptyAdapter(),
        "empty-source": _EmptyAdapter(),
        "unconfirmed-empty": _NotAuthoritativeEmptyAdapter(),
    }
    client = httpx.Client()
    results = run_all_sources(db_session, registry, client)
    client.close()

    assert {name: r.status for name, r in results.items()} == {
        "confirmed-empty": "success",
        "empty-source": "empty",
        "unconfirmed-empty": "empty",
    }
    statuses = {r.source_system: r.status for r in db_session.query(SourceSyncRun).all()}
    assert statuses == {
        "confirmed-empty": "success",
        "empty-source": "empty",
        "unconfirmed-empty": "empty",
    }


def test_authoritative_empty_fetches_close_stale_jobs(db_session):
    """A site that confirms it has no openings closes its stale open jobs
    under mark_missing_jobs' usual two-successful-runs rule."""
    upsert_jobs(
        db_session,
        [
            SourceJob(
                source_system="confirmed-empty",
                source_organization="Clerk of the House",
                source_job_id="R1",
                source_url="https://example.com/r1",
                title="Stale Clerk Job",
                description_html="",
                description_text="",
                raw_payload={},
            )
        ],
        datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    # An earlier successful sync that no longer saw the job.
    earlier = datetime(2026, 9, 2, tzinfo=timezone.utc)
    db_session.add(
        SourceSyncRun(
            source_system="confirmed-empty",
            started_at=earlier,
            finished_at=earlier,
            status="success",
        )
    )
    db_session.commit()

    client = httpx.Client()
    registry = {"confirmed-empty": _ConfirmedEmptyAdapter()}

    first = run_all_sources(db_session, registry, client)["confirmed-empty"]
    assert first.status == "success"
    assert first.closed == 0
    assert db_session.query(Job).one().status == "open"

    second = run_all_sources(db_session, registry, client)["confirmed-empty"]
    client.close()

    assert second.status == "success"
    assert second.jobs_found == 0
    assert second.closed == 1
    assert db_session.query(Job).one().status == "closed"

    latest = (
        db_session.query(SourceSyncRun)
        .filter(SourceSyncRun.source_system == "confirmed-empty")
        .order_by(SourceSyncRun.id.desc())
        .first()
    )
    assert latest.status == "success"
    assert latest.jobs_found == 0
    assert latest.jobs_closed == 1
