import json

from app.ingest.adapters.csod import (
    CsodConfig,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    _parse_browser_result,
    parse_listing_page,
    parse_api_response,
)


TEST_CONFIG = CsodConfig(
    source_system="csod-test",
    source_organization="Test Org",
    base_url="https://test.csod.com",
)


def test_parse_listing_page():
    html = """
    <html><body>
        <div data-requisition-id="REQ001" class="job-card">
            <a href="/ux/ats/careersite/1/home/requisition/REQ001">Software Engineer</a>
            <span class="location">Washington, DC</span>
        </div>
        <div data-requisition-id="REQ002" class="job-card">
            <a href="/ux/ats/careersite/1/home/requisition/REQ002">Policy Analyst</a>
            <span class="location">Remote</span>
        </div>
    </body></html>
    """
    jobs = parse_listing_page(html, TEST_CONFIG)
    assert len(jobs) == 2
    assert jobs[0].title == "Software Engineer"
    assert jobs[0].source_job_id == "REQ001"
    assert jobs[0].source_system == "csod-test"
    assert jobs[0].location_text == "Washington, DC"
    assert jobs[1].title == "Policy Analyst"


def test_parse_api_response():
    data = {
        "data": [
            {
                "title": "IT Specialist",
                "requisitionId": 12345,
                "location": "Washington, DC",
                "description": "Manage systems",
            },
            {
                "title": "Clerk",
                "requisitionId": 12346,
                "location": "Capitol Hill",
                "description": "Office support",
            },
        ]
    }
    jobs = parse_api_response(data, TEST_CONFIG)
    assert len(jobs) == 2
    assert jobs[0].title == "IT Specialist"
    assert jobs[0].source_job_id == "12345"
    assert jobs[0].description_text == "Manage systems"


def test_empty_listing_returns_empty():
    html = "<html><body><p>No jobs found</p></body></html>"
    jobs = parse_listing_page(html, TEST_CONFIG)
    assert jobs == []


def test_parse_browser_result():
    items = [
        {"title": "Police Officer", "href": "/ux/ats/careersite/1/home/requisition/718?c=uscp", "reqId": "718"},
        {"title": "Special Agent", "href": "/ux/ats/careersite/1/home/requisition/724?c=uscp", "reqId": "724"},
    ]
    stdout = json.dumps({"success": True, "data": {"result": json.dumps(items)}, "error": None})
    jobs = _parse_browser_result(stdout, TEST_CONFIG)
    assert len(jobs) == 2
    assert jobs[0].title == "Police Officer"
    assert jobs[0].source_job_id == "718"
    assert jobs[0].source_url == "https://test.csod.com/ux/ats/careersite/1/home/requisition/718?c=uscp"
    assert jobs[1].title == "Special Agent"


def test_parse_browser_result_empty():
    stdout = json.dumps({"success": True, "data": {"result": "[]"}, "error": None})
    jobs = _parse_browser_result(stdout, TEST_CONFIG)
    assert jobs == []


def test_parse_browser_result_invalid_json():
    jobs = _parse_browser_result("not json", TEST_CONFIG)
    assert jobs == []


def test_house_csod_configs():
    assert HOUSE_CAO_CONFIG.career_site_id == 1
    assert HOUSE_CAO_CONFIG.listing_path == "/ux/ats/careersite/1/home?c=house"

    assert HOUSE_CLERK_CONFIG.career_site_id == 5
    assert HOUSE_CLERK_CONFIG.listing_path == "/ux/ats/careersite/5/home?c=house"

    assert HOUSE_SAA_CONFIG.career_site_id == 6
    assert HOUSE_SAA_CONFIG.listing_path == "/ux/ats/careersite/6/home?c=house"

    assert HOUSE_GREEN_GOLD_CONFIG.career_site_id == 11
    assert HOUSE_GREEN_GOLD_CONFIG.listing_path == "/ux/ats/careersite/11/home?c=house"
