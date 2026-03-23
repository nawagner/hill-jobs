from app.ingest.adapters.cbo_bizmerlin import _parse_position, SOURCE_SYSTEM, SOURCE_ORG


SAMPLE_POSITION = {
    "positionid": 342528,
    "positionUID": "25-28",
    "name": "Dissertation Fellow ",
    "status": "OPEN",
    "description": "<p>The Congressional Budget Office has positions available.</p>",
    "datePublish": "2025-07-30",
    "applicationDueDate": "2027-06-01",
    "locationModel": {
        "locationId": 3670,
        "locationName": "Ford House Office Building",
        "addressModelList": [
            {
                "city": "Washington D.C",
                "state": "DC",
                "zipCode": "20515",
            }
        ],
    },
    "departmentModel": {
        "departmentId": 46529,
        "name": "Office of the Director",
    },
    "seoUrl": "Dissertation_Fellow_",
}


def test_parse_position():
    job = _parse_position(SAMPLE_POSITION)
    assert job is not None
    assert job.source_system == SOURCE_SYSTEM
    assert job.source_organization == SOURCE_ORG
    assert job.title == "Dissertation Fellow"
    assert job.source_job_id == "342528"
    assert job.source_url == "https://cbo.bizmerlin.net/jobboard/#/position/view/342528/Dissertation_Fellow_"


def test_parse_location():
    job = _parse_position(SAMPLE_POSITION)
    assert job is not None
    assert job.location_text == "Washington D.C, DC"


def test_parse_dates():
    job = _parse_position(SAMPLE_POSITION)
    assert job is not None
    assert job.posted_at is not None
    assert job.posted_at.year == 2025
    assert job.posted_at.month == 7
    assert job.closing_at is not None
    assert job.closing_at.year == 2027


def test_parse_description_includes_dept():
    job = _parse_position(SAMPLE_POSITION)
    assert job is not None
    assert "Office of the Director" in job.description_text


def test_missing_title_returns_none():
    pos = {**SAMPLE_POSITION, "name": ""}
    assert _parse_position(pos) is None


def test_missing_id_returns_none():
    pos = {**SAMPLE_POSITION, "positionid": None}
    assert _parse_position(pos) is None
