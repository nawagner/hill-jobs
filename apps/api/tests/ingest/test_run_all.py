from datetime import datetime, timezone

import httpx

from app.ingest.run_all import run_all_sources
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
