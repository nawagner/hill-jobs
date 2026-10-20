from datetime import datetime, timedelta, timezone

from app.data.manual_jobs import MANUAL_JOBS
from app.data.member_parties import MEMBER_PARTIES
from app.ingest.adapters.manual import ManualAdapter
from app.ingest.run_all import run_all_sources
from app.ingest.upsert_jobs import upsert_jobs
from app.models.jobs import Job
from app.schemas.ingest import SourceJob


def _entry(**overrides) -> dict:
    entry = dict(
        source_job_id="smith-ai-fellow",
        source_organization="Rep. Jane Smith",
        title="AI Policy Fellow",
        source_url="https://smith.house.gov/news/1",
        location_text="Washington, DC",
        posted_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        closing_at=None,
        description=["Research AI & track bills.", "Email a resume."],
    )
    entry.update(overrides)
    return entry


def test_fetch_jobs_builds_source_jobs():
    jobs = ManualAdapter([_entry()]).fetch_jobs(None)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_system == "manual"
    assert job.source_job_id == "smith-ai-fellow"
    assert job.source_organization == "Rep. Jane Smith"
    assert job.description_text == "Research AI & track bills.\nEmail a resume."
    assert job.description_html == "<p>Research AI &amp; track bills.</p>\n<p>Email a resume.</p>"


def test_fetch_jobs_drops_listings_past_their_closing_date():
    now = datetime.now(timezone.utc)
    adapter = ManualAdapter([
        _entry(source_job_id="closed", closing_at=now - timedelta(days=1)),
        _entry(source_job_id="open", closing_at=now + timedelta(days=1)),
    ])

    assert [j.source_job_id for j in adapter.fetch_jobs(None)] == ["open"]


def test_empty_list_is_a_successful_sync(db_session):
    """Removing every entry syncs as success, so mark_missing_jobs closes
    the old rows instead of the run being skipped as empty."""
    results = run_all_sources(db_session, {"manual": ManualAdapter([])}, None)

    assert results["manual"].status == "success"


def test_hvaps_copy_of_a_manual_listing_is_skipped(db_session):
    now = datetime.now(timezone.utc)
    upsert_jobs(db_session, ManualAdapter([_entry()]).fetch_jobs(None), now)

    hvaps = SourceJob(
        source_system="house-hvaps",
        source_job_id="MEM-300-26",
        source_organization="Rep. Jane Smith",
        source_url="https://example.com/bulletin.pdf",
        title="AI Policy Fellow",
        description_html="",
        description_text="",
    )
    result = upsert_jobs(db_session, [hvaps], now)

    assert result.skipped == 1
    assert db_session.query(Job).one().source_system == "manual"


def test_manual_entries_are_well_formed():
    ids = [e["source_job_id"] for e in MANUAL_JOBS]
    assert len(ids) == len(set(ids))
    for entry in MANUAL_JOBS:
        # Matches a member name, so the party/state/committee filters apply
        if entry["source_organization"].startswith(("Rep. ", "Senator ")):
            assert entry["source_organization"] in MEMBER_PARTIES
        assert entry["description"]
        assert entry["source_url"].startswith("https://")
