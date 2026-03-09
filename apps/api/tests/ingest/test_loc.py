from pathlib import Path
from unittest.mock import patch

from app.ingest.adapters.loc import _enrich_from_detail, parse_listing
from app.schemas.ingest import SourceJob

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


def _make_job(**kwargs) -> SourceJob:
    defaults = dict(
        source_system="loc-careers",
        source_organization="Library of Congress",
        source_job_id="VAR003279",
        source_url="https://www.loc.gov/item/careers/test/",
        title="Test Job",
        description_html="<p>Short</p>",
        description_text="Short",
    )
    defaults.update(kwargs)
    return SourceJob(**defaults)


def test_enrich_from_detail_extracts_salary():
    detail_html = (FIXTURES / "career_detail.html").read_text()
    job = _make_job()

    with patch("app.ingest.adapters.loc.fetch_page", return_value=detail_html):
        _enrich_from_detail(None, job)

    assert job.salary_min == 169_279.00
    assert job.salary_max == 197_200.00
    assert job.salary_period == "yearly"


def test_enrich_from_detail_extracts_description():
    detail_html = (FIXTURES / "career_detail.html").read_text()
    job = _make_job()

    with patch("app.ingest.adapters.loc.fetch_page", return_value=detail_html):
        _enrich_from_detail(None, job)

    assert "Congressional Research Service" in job.description_text
    assert len(job.description_text) > len("Short")


def test_enrich_from_detail_no_salary():
    """Detail page without salary fields should leave job unchanged."""
    html = "<html><body><div id='content'><p>No salary here</p></div></body></html>"
    job = _make_job()

    with patch("app.ingest.adapters.loc.fetch_page", return_value=html):
        _enrich_from_detail(None, job)

    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_period is None
