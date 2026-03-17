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


def test_fetch_jobs_uses_detail_description_from_wrapped_response(monkeypatch):
    monkeypatch.setattr("app.ingest.adapters.senate.time.sleep", lambda _: None)

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
    detail = {
        "data": {
            "id": 306,
            "description": (
                "<p>First paragraph.</p>"
                "<p>Second paragraph with <b>details</b>.</p>"
            ),
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/jobs":
            return httpx.Response(200, json=listing)
        if request.url.path == "/api/v1/jobs/306":
            return httpx.Response(200, json=detail)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        jobs = SenateAdapter().fetch_jobs(client)
    finally:
        client.close()

    assert len(jobs) == 1
    assert jobs[0].description_html == detail["data"]["description"]
    assert "Second paragraph with details." in jobs[0].description_text
    assert jobs[0].description_text != "Short summary only"
