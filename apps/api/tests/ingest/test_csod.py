from app.ingest.adapters.csod import (
    CsodConfig,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    _apply_detail,
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
