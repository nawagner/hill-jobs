import json
from pathlib import Path

from app.ingest.adapters.usajobs import _parse_result, AOC_CONFIG, GAO_CONFIG, GPO_CONFIG

FIXTURES = Path(__file__).parent.parent / "fixtures" / "usajobs"


def test_parse_result():
    data = json.loads((FIXTURES / "search_response.json").read_text())
    items = data["SearchResult"]["SearchResultItems"]
    assert len(items) > 0

    job = _parse_result(items[0], AOC_CONFIG)
    assert job is not None
    assert job.source_system == "aoc-usajobs"
    assert job.source_organization == "Architect of the Capitol"
    assert job.title
    assert job.source_job_id
    assert job.source_url


def test_salary_yearly():
    data = json.loads((FIXTURES / "search_response.json").read_text())
    items = data["SearchResult"]["SearchResultItems"]
    # First item: Purchasing Agent, PA (per annum)
    job = _parse_result(items[0], AOC_CONFIG)
    assert job is not None
    assert job.salary_min == 57_736
    assert job.salary_max == 75_059
    assert job.salary_period == "yearly"


def test_salary_hourly():
    data = json.loads((FIXTURES / "search_response.json").read_text())
    items = data["SearchResult"]["SearchResultItems"]
    # Second item: Mason Leader, PH (per hour)
    job = _parse_result(items[1], AOC_CONFIG)
    assert job is not None
    assert job.salary_min == 40.18
    assert job.salary_max == 46.88
    assert job.salary_period == "hourly"


def test_non_aoc_job_filtered():
    fake_item = {
        "MatchedObjectDescriptor": {
            "OrganizationName": "Department of Defense",
            "PositionTitle": "Analyst",
            "PositionID": "X1",
            "PositionURI": "https://usajobs.gov/x1",
        }
    }
    result = _parse_result(fake_item, AOC_CONFIG)
    assert result is None


def test_non_aoc_job_passes_for_gao_config():
    """When using org-code config (no keyword), no org filtering is applied."""
    fake_item = {
        "MatchedObjectDescriptor": {
            "OrganizationName": "Government Accountability Office",
            "PositionTitle": "Analyst",
            "PositionID": "GAO-1",
            "PositionURI": "https://usajobs.gov/gao1",
        }
    }
    result = _parse_result(fake_item, GAO_CONFIG)
    assert result is not None
    assert result.source_system == "gao-usajobs"
    assert result.source_organization == "Government Accountability Office"


def test_gpo_config():
    assert GPO_CONFIG.source_system == "gpo-usajobs"
    assert GPO_CONFIG.organization_code == "LP00"


def test_missing_api_key_returns_empty():
    from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
    import httpx

    adapter = AocUsajobsAdapter(api_key="", user_agent_email="")
    client = httpx.Client()
    jobs = adapter.fetch_jobs(client)
    client.close()
    assert jobs == []
