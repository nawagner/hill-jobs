import json
from pathlib import Path

from app.ingest.adapters.house_dems_resumebank import (
    parse_jobs,
    _normalize_employment_type,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "house_dems_resumebank"


def _load_fixture():
    data = json.loads((FIXTURES / "api_jobs.json").read_text())
    return parse_jobs(data)


def test_parse_jobs():
    jobs = _load_fixture()
    assert len(jobs) == 4

    for job in jobs:
        assert job.source_system == "house-dems-resumebank"
        assert job.source_organization == "House Democrats"


def test_field_mapping():
    jobs = _load_fixture()
    intern = jobs[0]  # Summer 2026 Internship

    assert intern.source_job_id == "994766"
    assert intern.title == "Summer 2026 Internship"
    assert intern.source_url == "https://resumebank.domewatch.us/jobs/994766"
    assert intern.posted_at is not None
    assert intern.closing_at is not None
    assert intern.description_html.startswith("<p>")
    assert "<" not in intern.description_text  # no HTML tags in plain text
    assert "Cleaver" in intern.description_text
    assert intern.raw_payload["id"] == 994766


def test_closing_date_parsed():
    jobs = _load_fixture()
    # First job has validThrough = "2026-03-19T00:00:00.000Z"
    assert jobs[0].closing_at is not None
    assert jobs[0].closing_at.year == 2026
    assert jobs[0].closing_at.month == 3
    assert jobs[0].closing_at.day == 19


def test_closing_date_null():
    jobs = _load_fixture()
    # Fourth job (Dingell) has validThrough = null
    dingell = jobs[3]
    assert dingell.closing_at is None


def test_normalize_employment_type():
    assert _normalize_employment_type("FULL_TIME") == "Full Time"
    assert _normalize_employment_type("Full Time") == "Full Time"
    assert _normalize_employment_type("Intern") == "Intern"
    assert _normalize_employment_type("Volunteer") == "Volunteer"
    assert _normalize_employment_type("") is None
    assert _normalize_employment_type(None) is None


def test_employment_type_in_jobs():
    jobs = _load_fixture()
    assert jobs[0].employment_type == "Intern"
    assert jobs[1].employment_type is None  # empty string -> None
    assert jobs[2].employment_type == "Full Time"
    assert jobs[3].employment_type == "Full Time"  # FULL_TIME -> Full Time


def test_location_from_job_location():
    jobs = _load_fixture()
    # First 3 have empty jobLocation {}
    assert jobs[0].location_text is None
    assert jobs[1].location_text is None
    # Fourth has addressLocality/addressRegion
    assert jobs[3].location_text == "Washington, DC"


def test_empty_input():
    jobs = parse_jobs([])
    assert jobs == []
