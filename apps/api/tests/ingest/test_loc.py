import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.ingest.adapters.loc import LISTING_URL, LocAdapter, apply_detail, parse_results
from app.schemas.ingest import SourceJob

FIXTURES = Path(__file__).parent.parent / "fixtures" / "loc"


def _listing() -> dict:
    return json.loads((FIXTURES / "careers_listing.json").read_text())


def _detail() -> dict:
    return json.loads((FIXTURES / "career_detail.json").read_text())


def _jobs_by_url() -> dict[str, SourceJob]:
    return {j.source_url: j for j in parse_results(_listing()["results"])}


def test_parse_results_basic_fields():
    jobs = parse_results(_listing()["results"])
    assert len(jobs) == 6

    job = _jobs_by_url()["https://www.loc.gov/item/careers/supervisory-librarian-vacancy-var003371/"]
    assert job.source_system == "loc-careers"
    assert job.source_organization == "Library of Congress"
    assert job.source_job_id == "VAR003371"
    assert job.title == "Supervisory Librarian (GS-14)"
    assert job.posted_at == datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert job.closing_at == datetime(2026, 10, 12, 23, 59, 59, tzinfo=timezone.utc)
    assert job.employment_type == "Permanent"
    assert job.location_text == "Washington, DC"
    assert "Supervisory Librarian" in job.description_text
    assert job.raw_payload["availability"] == "Open to All"


def test_vacancy_number_spellings():
    """Vacancy numbers appear as 'Vacancy#: X', 'Vacancy#:X' and 'Vacancy#X'."""
    by_id = {j.source_job_id: j.title for j in parse_results(_listing()["results"])}
    assert by_id["VAR003371"] == "Supervisory Librarian (GS-14)"
    assert by_id["VAR003462"].startswith("IT Asset Management Specialist (")
    assert by_id["VAR003461"].startswith("Events Coordinator (")
    assert by_id["VAR003455"].startswith("Physical Security Specialist (Locksmith) (")
    assert not any("Vacancy" in title for title in by_id.values())


def test_title_without_vacancy_number():
    jobs = [j for j in parse_results(_listing()["results"]) if j.source_job_id is None]
    titles = {j.title for j in jobs}
    # Matches the HTML scraper's format, so existing rows keep the same slug.
    assert "Work Study Student Program 2026/2027 (GS-01)" in titles


def test_apply_detail_salary_and_location():
    job = _jobs_by_url()["https://www.loc.gov/item/careers/supervisory-librarian-vacancy-var003371/"]
    apply_detail(job, _detail())

    assert job.salary_min == 143_913.00
    assert job.salary_max == 187_093.00
    assert job.salary_period == "yearly"
    assert job.location_text == "Washington, DC"


def test_apply_detail_hourly_wage_grade():
    job = _jobs_by_url()["https://www.loc.gov/item/careers/supervisory-librarian-vacancy-var003371/"]
    apply_detail(job, {"item": {"minimum_salary": "$28.55", "maximum_salary": "$33.31"}})

    assert job.salary_min == 28.55
    assert job.salary_max == 33.31
    assert job.salary_period == "hourly"


def test_apply_detail_without_salary_leaves_job_unchanged():
    job = _jobs_by_url()["https://www.loc.gov/item/careers/supervisory-librarian-vacancy-var003371/"]
    apply_detail(job, {"item": {}})

    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_period is None


def test_fetch_jobs_follows_pages_and_avoids_browser_user_agent():
    listing = _listing()
    first, second = listing["results"][:3], listing["results"][3:]
    page2_url = "https://www.loc.gov/careers/?fo=json&sp=2"
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        url = str(request.url)
        if url == LISTING_URL:
            return httpx.Response(200, json={"results": first, "pagination": {"next": page2_url}})
        if url == page2_url:
            return httpx.Response(200, json={"results": second, "pagination": {"next": None}})
        assert url.endswith("/?fo=json"), url
        return httpx.Response(200, json=_detail())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = LocAdapter(detail_delay=0).fetch_jobs(client)

    assert len(jobs) == 6
    assert all(j.salary_min == 143_913.00 for j in jobs)
    # A browser User-Agent gets the Cloudflare challenge instead of JSON.
    assert not any("Mozilla" in r.headers.get("user-agent", "") for r in requested)


def test_fetch_jobs_retries_rate_limited_detail(monkeypatch):
    """loc.gov answers 429 when requests come too fast; retry instead of dropping salary."""
    sleeps: list[float] = []
    monkeypatch.setattr("app.ingest.adapters.loc.time.sleep", sleeps.append)
    results = _listing()["results"][:1]
    detail_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_calls
        if str(request.url) == LISTING_URL:
            return httpx.Response(200, json={"results": results, "pagination": {"next": None}})
        detail_calls += 1
        if detail_calls == 1:
            return httpx.Response(429, headers={"Retry-After": "5"})
        return httpx.Response(200, json=_detail())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = LocAdapter(detail_delay=0).fetch_jobs(client)

    assert detail_calls == 2
    assert sleeps == [5.0]
    assert jobs[0].salary_min == 143_913.00


def test_fetch_jobs_retries_dropped_connection(monkeypatch):
    """loc.gov sometimes closes the connection mid-body; retry instead of dropping salary."""
    sleeps: list[float] = []
    monkeypatch.setattr("app.ingest.adapters.loc.time.sleep", sleeps.append)
    results = _listing()["results"][:1]
    detail_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_calls
        if str(request.url) == LISTING_URL:
            return httpx.Response(200, json={"results": results, "pagination": {"next": None}})
        detail_calls += 1
        if detail_calls == 1:
            raise httpx.RemoteProtocolError("peer closed connection", request=request)
        return httpx.Response(200, json=_detail())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = LocAdapter(detail_delay=0).fetch_jobs(client)

    assert detail_calls == 2
    assert sleeps == [4.0]
    assert jobs[0].salary_min == 143_913.00
