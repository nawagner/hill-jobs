from datetime import datetime, timezone

import httpx

from app.ingest.run_all import run_all_sources
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


class _ConfirmedEmptyAdapter(_EmptyAdapter):
    """Like CSOD: returns [] only when the site itself reports no openings."""

    confirms_empty = True


def test_confirmed_empty_fetch_closes_taken_down_jobs(db_session):
    """A career site that confirms it has no openings isn't a failure, and the
    job it took down gets closed like any other missing job."""
    client = httpx.Client()
    for _ in range(2):
        run_all_sources(db_session, {"good-source": _SuccessAdapter()}, client)

    # Closed on the third empty run, the same grace period as any missing job.
    for _ in range(3):
        results = run_all_sources(db_session, {"good-source": _ConfirmedEmptyAdapter()}, client)
    client.close()

    assert results["good-source"].status == "success"
    assert results["good-source"].closed == 1
    assert db_session.query(Job).one().status == "closed"
