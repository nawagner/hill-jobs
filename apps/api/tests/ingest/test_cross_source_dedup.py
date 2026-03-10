from datetime import datetime, timezone

from app.ingest.upsert_jobs import upsert_jobs, _normalize_for_matching
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


def test_normalize_for_matching():
    assert _normalize_for_matching("Rep. Jane Smith") == "rep jane smith"
    assert _normalize_for_matching("  Rep.  Jane   Smith  ") == "rep jane smith"
    assert _normalize_for_matching("Rep. Jane Smith's Office") == "rep jane smiths office"


def test_hvaps_skipped_when_domewatch_exists(db_session):
    """HVAPS job should be skipped if Domewatch already has the same title+org."""
    now = datetime.now(timezone.utc)

    # Insert a Domewatch job first
    domewatch_job = _make_source_job(
        source_system="house-dems-resumebank",
        source_job_id="DW-123",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    result1 = upsert_jobs(db_session, [domewatch_job], now)
    assert result1.created == 1

    # Now try to insert the same job from HVAPS
    hvaps_job = _make_source_job(
        source_system="house-hvaps",
        source_job_id="MEM-072-26",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    result2 = upsert_jobs(db_session, [hvaps_job], now)
    assert result2.skipped == 1
    assert result2.created == 0

    # Only one job should exist in DB
    jobs = db_session.query(Job).all()
    assert len(jobs) == 1
    assert jobs[0].source_system == "house-dems-resumebank"


def test_domewatch_skipped_when_hvaps_exists(db_session):
    """Domewatch job should be skipped if HVAPS already has the same title+org."""
    now = datetime.now(timezone.utc)

    # Insert HVAPS job first
    hvaps_job = _make_source_job(
        source_system="house-hvaps",
        source_job_id="MEM-072-26",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    result1 = upsert_jobs(db_session, [hvaps_job], now)
    assert result1.created == 1

    # Now try to insert the same job from Domewatch
    domewatch_job = _make_source_job(
        source_system="house-dems-resumebank",
        source_job_id="DW-123",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    result2 = upsert_jobs(db_session, [domewatch_job], now)
    assert result2.skipped == 1
    assert result2.created == 0


def test_no_cross_source_dedup_for_different_title(db_session):
    """Different titles at the same org should NOT be deduplicated."""
    now = datetime.now(timezone.utc)

    domewatch_job = _make_source_job(
        source_system="house-dems-resumebank",
        source_job_id="DW-123",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    upsert_jobs(db_session, [domewatch_job], now)

    hvaps_job = _make_source_job(
        source_system="house-hvaps",
        source_job_id="MEM-072-26",
        source_organization="Rep. Joyce Beatty",
        title="Legislative Assistant",
    )
    result = upsert_jobs(db_session, [hvaps_job], now)
    assert result.created == 1
    assert result.skipped == 0

    jobs = db_session.query(Job).all()
    assert len(jobs) == 2


def test_no_cross_source_dedup_for_unrelated_sources(db_session):
    """Cross-source dedup should NOT fire for unrelated source systems."""
    now = datetime.now(timezone.utc)

    senate_job = _make_source_job(
        source_system="senate-webscribble",
        source_job_id="SEN-100",
        source_organization="Senate Committee on Finance",
        title="Staff Assistant",
    )
    upsert_jobs(db_session, [senate_job], now)

    hvaps_job = _make_source_job(
        source_system="house-hvaps",
        source_job_id="MEM-072-26",
        source_organization="Senate Committee on Finance",
        title="Staff Assistant",
    )
    result = upsert_jobs(db_session, [hvaps_job], now)
    # Senate is not in the cross-source pairs, so no dedup
    assert result.created == 1
    assert result.skipped == 0


def test_closed_domewatch_job_does_not_block_hvaps(db_session):
    """A closed Domewatch job should NOT prevent HVAPS from inserting."""
    now = datetime.now(timezone.utc)

    domewatch_job = _make_source_job(
        source_system="house-dems-resumebank",
        source_job_id="DW-123",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    upsert_jobs(db_session, [domewatch_job], now)

    # Close the Domewatch job
    job = db_session.query(Job).first()
    job.status = "closed"
    db_session.commit()

    # HVAPS should insert since the Domewatch job is closed
    hvaps_job = _make_source_job(
        source_system="house-hvaps",
        source_job_id="MEM-072-26",
        source_organization="Rep. Joyce Beatty",
        title="Communications Director",
    )
    result = upsert_jobs(db_session, [hvaps_job], now)
    assert result.created == 1
    assert result.skipped == 0
