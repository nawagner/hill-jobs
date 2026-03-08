from app.ingest.adapters.csod import (
    CsodConfig,
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
