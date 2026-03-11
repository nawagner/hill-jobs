"""Live scrape tests — hit real sites, confirm we get jobs back.

Run with:  pytest -m live
These will fail if a site is down or changed its structure.
"""

import pytest
import httpx

from app.ingest.adapters.senate import SenateAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.csod import CsodAdapter, HOUSE_CAO_CONFIG, USCP_CONFIG

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def http_client():
    with httpx.Client(timeout=60.0) as client:
        yield client


@pytest.fixture(scope="module")
def senate_jobs(http_client):
    return SenateAdapter().fetch_jobs(http_client)


@pytest.fixture(scope="module")
def loc_jobs(http_client):
    return LocAdapter().fetch_jobs(http_client)


@pytest.fixture(scope="module")
def house_dems_jobs(http_client):
    return HouseDemsResumebankAdapter().fetch_jobs(http_client)


@pytest.fixture(scope="module")
def csod_house_cao_jobs(http_client):
    return CsodAdapter(HOUSE_CAO_CONFIG).fetch_jobs(http_client)


@pytest.fixture(scope="module")
def csod_uscp_jobs(http_client):
    return CsodAdapter(USCP_CONFIG).fetch_jobs(http_client)


# ── Senate ──────────────────────────────────────────────────────────────


def test_senate_got_jobs(senate_jobs):
    assert len(senate_jobs) > 0, "Senate returned no jobs"


def test_senate_fields(senate_jobs):
    job = senate_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_url
    assert job.source_system == "senate-webscribble"


# ── Library of Congress ─────────────────────────────────────────────────


def test_loc_got_jobs(loc_jobs):
    assert len(loc_jobs) > 0, "LoC returned no jobs"


def test_loc_fields(loc_jobs):
    job = loc_jobs[0]
    assert job.title
    assert job.source_url
    assert job.source_system == "loc-careers"


# ── House Dems Resume Bank ──────────────────────────────────────────────


def test_house_dems_got_jobs(house_dems_jobs):
    assert len(house_dems_jobs) > 0, "House Dems Resume Bank returned no jobs"


def test_house_dems_fields(house_dems_jobs):
    job = house_dems_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_system == "house-dems-resumebank"


# ── CSOD House CAO ─────────────────────────────────────────────────────


def test_csod_house_cao_got_jobs(csod_house_cao_jobs):
    assert len(csod_house_cao_jobs) > 0, "CSOD House CAO returned no jobs"


def test_csod_house_cao_fields(csod_house_cao_jobs):
    job = csod_house_cao_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_url
    assert job.source_system == "csod-house-cao"


def test_csod_house_cao_enriched(csod_house_cao_jobs):
    """At least one job should have description from the detail page."""
    enriched = [j for j in csod_house_cao_jobs if j.description_text]
    assert len(enriched) > 0, "No CAO jobs got detail enrichment"


# ── CSOD USCP ──────────────────────────────────────────────────────────


def test_csod_uscp_got_jobs(csod_uscp_jobs):
    assert len(csod_uscp_jobs) > 0, "CSOD USCP returned no jobs"


def test_csod_uscp_fields(csod_uscp_jobs):
    job = csod_uscp_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_system == "csod-uscp"
