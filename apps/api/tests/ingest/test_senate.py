import json
from pathlib import Path

import httpx

from app.ingest.adapters.senate import SenateAdapter, parse_api_response, _parse_date, _extract_salary

FIXTURES = Path(__file__).parent.parent / "fixtures" / "senate"


def test_parse_api_response():
    data = json.loads((FIXTURES / "api_jobs.json").read_text())
    jobs = parse_api_response(data)
    assert len(jobs) > 0

    job = jobs[0]
    assert job["title"]
    assert job["url"].startswith("http")
    assert "company" in job
    assert job["company"]["name"]


def test_parse_api_response_has_metadata():
    data = json.loads((FIXTURES / "api_jobs.json").read_text())
    meta = data.get("meta", {})
    assert "total" in meta
    assert meta["total"] > 0
    assert "last_page" in meta


def test_parse_date():
    dt = _parse_date("October 21, 2025")
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 10
    assert dt.day == 21


def test_parse_date_returns_none_for_invalid():
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("invalid") is None


def test_extract_salary_from_custom_block():
    item = {
        "customBlockList": [
            {"path": "approx_salary_text", "value": "$64,226 Per Year"},
        ]
    }
    sal_min, sal_max, sal_period = _extract_salary(item)
    assert sal_min == 64_226
    assert sal_max == 64_226
    assert sal_period == "yearly"


def test_extract_salary_missing():
    assert _extract_salary({}) == (None, None, None)
    assert _extract_salary({"customBlockList": []}) == (None, None, None)


def test_fetch_jobs_uses_detail_description_from_api(monkeypatch):
    monkeypatch.setattr("app.ingest.adapters.senate.time.sleep", lambda _: None)

    detail_html = (
        "<p>First paragraph.</p>"
        "<p>Second paragraph with <b>details</b>.</p>"
    )

    listing = {
        "data": [
            {
                "id": 306,
                "title": "Law Fellow",
                "url": "https://careers.employment.senate.gov/job/law-fellow",
                "location": "Washington, District of Columbia",
                "shortDescription": "Short summary only",
                "company": {"name": "Senator Adam B. Schiff"},
                "posted_date": "October 21, 2025",
                "customBlockList": [],
            }
        ],
        "meta": {"last_page": 1},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/jobs":
            return httpx.Response(200, json=listing)
        if request.url.path == "/api/v1/jobs/306":
            return httpx.Response(200, json={"data": {"description": detail_html}})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        jobs = SenateAdapter().fetch_jobs(client)
    finally:
        client.close()

    assert len(jobs) == 1
    assert jobs[0].description_html == detail_html
    assert "Second paragraph with details." in jobs[0].description_text
    assert jobs[0].description_text != "Short summary only"


def test_fetch_jobs_retries_on_429_and_403(monkeypatch):
    monkeypatch.setattr("app.ingest.adapters.senate.time.sleep", lambda _: None)

    detail_html = "<p>Full description.</p>"
    call_count = {"value": 0}

    listing = {
        "data": [
            {
                "id": 99,
                "title": "Test Job",
                "url": "https://careers.employment.senate.gov/job/test",
                "location": "Washington, DC",
                "shortDescription": "Short",
                "company": {"name": "Senate Office"},
                "posted_date": "March 1, 2026",
                "customBlockList": [],
            }
        ],
        "meta": {"last_page": 1},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/jobs":
            return httpx.Response(200, json=listing)
        if request.url.path == "/api/v1/jobs/99":
            call_count["value"] += 1
            if call_count["value"] == 1:
                return httpx.Response(429)
            if call_count["value"] == 2:
                return httpx.Response(403)
            return httpx.Response(200, json={"data": {"description": detail_html}})
        raise AssertionError(f"Unexpected: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        jobs = SenateAdapter().fetch_jobs(client)
    finally:
        client.close()

    assert len(jobs) == 1
    assert jobs[0].description_html == detail_html
    assert call_count["value"] == 3
