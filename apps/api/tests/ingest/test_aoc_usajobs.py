import json
from pathlib import Path

from app.ingest.adapters.aoc_usajobs import _parse_result

FIXTURES = Path(__file__).parent.parent / "fixtures" / "usajobs"


def test_parse_result():
    data = json.loads((FIXTURES / "search_response.json").read_text())
    items = data["SearchResult"]["SearchResultItems"]
    assert len(items) > 0

    job = _parse_result(items[0])
    assert job is not None
    assert job.source_system == "aoc-usajobs"
    assert job.source_organization == "Architect of the Capitol"
    assert job.title
    assert job.source_job_id
    assert job.source_url


def test_non_aoc_job_filtered():
    fake_item = {
        "MatchedObjectDescriptor": {
            "OrganizationName": "Department of Defense",
            "PositionTitle": "Analyst",
            "PositionID": "X1",
            "PositionURI": "https://usajobs.gov/x1",
        }
    }
    result = _parse_result(fake_item)
    assert result is None


def test_missing_api_key_returns_empty():
    from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
    import httpx

    adapter = AocUsajobsAdapter(api_key="", user_agent_email="")
    client = httpx.Client()
    jobs = adapter.fetch_jobs(client)
    client.close()
    assert jobs == []
