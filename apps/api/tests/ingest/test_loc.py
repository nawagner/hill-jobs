from pathlib import Path

from app.ingest.adapters.loc import parse_listing

FIXTURES = Path(__file__).parent.parent / "fixtures" / "loc"


def test_parse_listing():
    html = (FIXTURES / "careers_listing.html").read_text()
    jobs = parse_listing(html)
    assert len(jobs) > 0

    # Check first job has expected fields
    job = jobs[0]
    assert job.source_system == "loc-careers"
    assert job.source_organization == "Library of Congress"
    assert job.title
    assert job.source_url
    assert job.source_job_id  # vacancy ID


def test_parse_listing_extracts_dates():
    html = (FIXTURES / "careers_listing.html").read_text()
    jobs = parse_listing(html)

    # At least some jobs should have dates
    jobs_with_dates = [j for j in jobs if j.posted_at is not None]
    assert len(jobs_with_dates) > 0
