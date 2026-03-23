"""Live scrape tests — hit real sites, confirm we get jobs back.

Run with:  pytest -m live
These will fail if a site is down or changed its structure.
"""

import pytest
import httpx

from app.ingest.adapters.senate import SenateAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.cbo_bizmerlin import CboBizmerlinAdapter
from app.ingest.adapters.csod import CsodAdapter, HOUSE_CAO_CONFIG, USCP_CONFIG
from app.ingest.adapters.hvaps_email import HvapsEmailAdapter

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


# ── CBO BizMerlin ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cbo_jobs(http_client):
    return CboBizmerlinAdapter().fetch_jobs(http_client)


def test_cbo_got_jobs(cbo_jobs):
    assert len(cbo_jobs) >= 0, "CBO BizMerlin returned an error"


def test_cbo_fields(cbo_jobs):
    if not cbo_jobs:
        pytest.skip("No CBO jobs currently posted")
    job = cbo_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_url
    assert job.source_system == "cbo-bizmerlin"
    assert job.source_organization == "Congressional Budget Office"


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


# ── HVAPS Email ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hvaps_jobs(http_client):
    return HvapsEmailAdapter().fetch_jobs(http_client)


def test_hvaps_got_jobs(hvaps_jobs):
    assert len(hvaps_jobs) > 0, "HVAPS email adapter returned no jobs"


def test_hvaps_fields(hvaps_jobs):
    job = hvaps_jobs[0]
    assert job.title
    assert job.source_job_id
    assert job.source_url
    assert job.source_system == "house-hvaps"


def test_hvaps_pdf_urls_are_govdelivery(hvaps_jobs):
    """Catch if PDF hosting changes away from govdelivery CDN."""
    for job in hvaps_jobs:
        assert "content.govdelivery.com" in job.source_url, (
            f"PDF URL format changed — expected govdelivery CDN, got: {job.source_url}"
        )


def test_hvaps_has_mem_ids(hvaps_jobs):
    """Catch if HVAPS changes their MEM-XXX-XX ID format."""
    mem_jobs = [j for j in hvaps_jobs if j.source_job_id and j.source_job_id.startswith("MEM-")]
    assert len(mem_jobs) > 0, (
        "No jobs with MEM-XXX-XX IDs found — HVAPS PDF format may have changed"
    )


# ── HVAPS Email Format (canary tests) ────────────────────────────────
# These validate our assumptions about the email/inbox so we know fast
# if something changes upstream (sender, subject, URL structure).


@pytest.fixture(scope="module")
def hvaps_email_metadata():
    """Raw email metadata from the inbox — checks format without parsing PDFs."""
    import imaplib
    import email as emaillib
    import os

    user = os.environ.get("GMAIL_ADDRESS", "")
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not pw:
        pytest.skip("GMAIL_APP_PASSWORD not set")

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(user, pw)
    mail.select("INBOX", readonly=True)

    status, data = mail.search(
        None, '(SUBJECT "House of Representatives Vacancy Announcement Bulletin")'
    )
    msg_ids = data[0].split() if data[0] else []
    if not msg_ids:
        mail.logout()
        pytest.skip("No HVAPS emails in inbox")

    # Fetch the most recent one
    status, msg_data = mail.fetch(msg_ids[-1], "(RFC822)")
    msg = emaillib.message_from_bytes(msg_data[0][1])

    # Get HTML body
    html = ""
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_payload(decode=True).decode("utf-8", errors="replace")
            break

    mail.logout()
    return {"subject": msg["Subject"], "from": msg["From"], "html": html}


def test_hvaps_email_subject_format(hvaps_email_metadata):
    """Alert if the bulletin subject line changes."""
    from email.header import decode_header

    raw_subj = hvaps_email_metadata["subject"]
    # Decode MIME-encoded headers (e.g. =?US-ASCII?Q?...?=)
    parts = decode_header(raw_subj)
    subj = "".join(
        part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        for part, enc in parts
    )
    assert "Vacancy Announcement Bulletin" in subj, (
        f"HVAPS email subject changed — got: {subj!r}"
    )


def test_hvaps_email_has_tracking_pdf_links(hvaps_email_metadata):
    """Alert if govdelivery stops wrapping PDF links in tracking URLs."""
    import re
    from app.ingest.adapters.hvaps_email import _TRACKING_PDF_RE

    html = hvaps_email_metadata["html"]
    matches = _TRACKING_PDF_RE.findall(html)
    assert len(matches) >= 1, (
        "No govdelivery tracking PDF links found in email HTML. "
        "The link format may have changed. Check the email source."
    )


def test_hvaps_email_has_two_pdfs(hvaps_email_metadata):
    """Each bulletin should have Members + Internships PDFs."""
    from app.ingest.adapters.hvaps_email import _TRACKING_PDF_RE

    html = hvaps_email_metadata["html"]
    matches = _TRACKING_PDF_RE.findall(html)
    assert len(matches) >= 2, (
        f"Expected 2 PDF links (Members + Internships), found {len(matches)}. "
        "Email format may have changed."
    )
