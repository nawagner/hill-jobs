import json
from pathlib import Path

from app.ingest.adapters.senate import parse_api_response, _parse_date, _extract_salary

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
