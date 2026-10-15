import pytest

from app.ingest.adapters.csod import (
    CsodConfig,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    _apply_detail,
    _job_search_total,
)
from app.schemas.ingest import SourceJob


TEST_CONFIG = CsodConfig(
    source_system="csod-test",
    source_organization="Test Org",
    base_url="https://test.csod.com",
)


def test_house_csod_configs():
    assert HOUSE_CAO_CONFIG.career_site_id == 1
    assert HOUSE_CAO_CONFIG.listing_path == "/ux/ats/careersite/1/home?c=house"

    assert HOUSE_CLERK_CONFIG.career_site_id == 5
    assert HOUSE_CLERK_CONFIG.listing_path == "/ux/ats/careersite/5/home?c=house"

    assert HOUSE_SAA_CONFIG.career_site_id == 6
    assert HOUSE_SAA_CONFIG.listing_path == "/ux/ats/careersite/6/home?c=house"

    assert HOUSE_GREEN_GOLD_CONFIG.career_site_id == 11
    assert HOUSE_GREEN_GOLD_CONFIG.listing_path == "/ux/ats/careersite/11/home?c=house"


def test_apply_detail_enriches_job():
    job = SourceJob(
        source_system="csod-test",
        source_organization="Test Org",
        source_job_id="123",
        source_url="https://test.csod.com/requisition/123",
        title="Test Job",
        description_html="",
        description_text="",
        raw_payload={},
    )
    detail = {
        "location": "WASHINGTON, DC, United States",
        "descHtml": "<p><strong>Salary Range:</strong> 73,712.00 - 84,271.00</p><p>Closing Date: 3/23/2026</p><p>Job description here</p>",
        "descText": "Salary Range: 73,712.00 - 84,271.00\nClosing Date: 3/23/2026\nJob description here",
    }
    enriched = _apply_detail(job, detail)
    assert enriched.location_text == "WASHINGTON, DC, United States"
    assert enriched.description_text == detail["descText"]
    assert enriched.description_html == detail["descHtml"]
    assert enriched.salary_min == 73712.0
    assert enriched.salary_max == 84271.0
    assert enriched.salary_period == "yearly"
    assert enriched.closing_at is not None
    assert enriched.closing_at.month == 3
    assert enriched.closing_at.day == 23


def test_job_search_total_reads_confirmed_count():
    body = {"status": "Success", "data": {"totalCount": 0, "requisitions": []}}
    assert _job_search_total(200, body) == 0
    body = {"status": "Success", "data": {"totalCount": 2, "requisitions": [{}, {}]}}
    assert _job_search_total(200, body) == 2


@pytest.mark.parametrize(
    "http_status,body",
    [
        (500, {"status": "Success", "data": {"totalCount": 0}}),
        (200, {"status": "Error", "data": {"totalCount": 0}}),
        (200, {"status": "Success", "data": {}}),
        (200, {"status": "Success"}),
        (200, []),
    ],
)
def test_job_search_total_rejects_anything_but_a_clean_answer(http_status, body):
    """Only an explicit successful count may be read as "no openings"."""
    with pytest.raises(RuntimeError):
        _job_search_total(http_status, body)
