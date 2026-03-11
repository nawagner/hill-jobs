"""Unit tests for HVAPS email adapter — URL extraction and parsing logic.

These run without IMAP credentials. They test that we correctly extract
PDF URLs from email HTML, so we catch format changes quickly.
"""

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from app.ingest.adapters.hvaps_email import (
    HvapsEmailAdapter,
    _TRACKING_PDF_RE,
)


# ── Tracking URL regex ────────────────────────────────────────────────


class TestTrackingUrlRegex:
    """Catch changes in govdelivery tracking URL format."""

    def test_extracts_encoded_pdf_url(self):
        """Standard links-2.govdelivery.com/CL0/ wrapper."""
        html = (
            'href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F3578163%2FHVAPS%2520Template_Members.pdf"
            '/1/0101019cd475-abc123/TqtzBo=447"'
        )
        matches = _TRACKING_PDF_RE.findall(html)
        assert len(matches) == 1
        assert "content.govdelivery.com" in matches[0]
        assert matches[0].endswith(".pdf")

    def test_extracts_multiple_pdfs(self):
        """Both Members and Internships PDFs from one email."""
        html = (
            'href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F3578163%2FMembers.pdf"
            '/1/abc/def=123" '
            'href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F3578193%2FInternships.pdf"
            '/1/abc/ghi=456"'
        )
        matches = _TRACKING_PDF_RE.findall(html)
        assert len(matches) == 2

    def test_ignores_non_pdf_tracking_links(self):
        """Don't match govdelivery links that aren't PDFs."""
        html = (
            'href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fwww.house.gov%2Femployment"
            '/1/abc/def=123"'
        )
        matches = _TRACKING_PDF_RE.findall(html)
        assert len(matches) == 0

    def test_handles_links_variant_subdomain(self):
        """govdelivery may use links-1, links-3, etc."""
        html = (
            'href="https://links-5.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F01%2F01%2Ffile_attachments%2F999%2Ftest.pdf"
            '/1/abc/def=1"'
        )
        matches = _TRACKING_PDF_RE.findall(html)
        assert len(matches) == 1

    def test_real_url_from_march_2026_bulletin(self):
        """Regression test with actual URL from a real email."""
        real_url = (
            "https://links-2.govdelivery.com/CL0/"
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F3578163%2FHVAPS%2520Template"
            "_Members_2025_3_09_2026%2520%25284%2529.pdf"
            "/1/0101019cd4751208-fef3dc94-5d89-459b-adbb-b705c4dded27-000000"
            "/TqtzBo3pa9u4a3tPAbr_GitAE0-YgvUoHATir9Jo7tY=447"
        )
        matches = _TRACKING_PDF_RE.findall(real_url)
        assert len(matches) == 1


# ── HTML body extraction ──────────────────────────────────────────────


class TestGetHtmlBody:
    def _adapter(self):
        return HvapsEmailAdapter(gmail_user="x", gmail_app_password="x")

    def test_multipart_email(self):
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("plain text", "plain"))
        msg.attach(MIMEText("<html><body>hello</body></html>", "html"))
        result = self._adapter()._get_html_body(msg)
        assert "<html>" in result

    def test_simple_html_email(self):
        msg = MIMEText("<html><body>hello</body></html>", "html")
        result = self._adapter()._get_html_body(msg)
        assert "hello" in result

    def test_plain_text_only_returns_empty(self):
        msg = MIMEText("just text", "plain")
        result = self._adapter()._get_html_body(msg)
        assert result == ""


# ── Extract PDF URLs from message ─────────────────────────────────────


class TestExtractPdfUrls:
    def _adapter(self):
        return HvapsEmailAdapter(gmail_user="x", gmail_app_password="x")

    def _make_email_bytes(self, html_body: str) -> bytes:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = "House of Representatives Vacancy Announcement Bulletin"
        msg["From"] = "test@example.com"
        return msg.as_bytes()

    def test_extracts_and_decodes_urls(self):
        html = (
            '<a href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F111%2FMembers.pdf"
            '/1/abc/def=1">Members</a>'
        )
        email_bytes = self._make_email_bytes(html)

        mock_mail = MagicMock()
        mock_mail.fetch.return_value = ("OK", [(b"1", email_bytes)])

        urls = self._adapter()._extract_pdf_urls_from_message(mock_mail, b"1")
        assert len(urls) == 1
        assert urls[0].startswith("https://content.govdelivery.com/")
        assert urls[0].endswith(".pdf")
        assert "%2F" not in urls[0]  # should be decoded

    def test_deduplicates_across_emails(self):
        """Same PDF URL in multiple emails should appear once."""
        adapter = self._adapter()
        adapter.max_emails = 5

        html = (
            '<a href="https://links-2.govdelivery.com/CL0/'
            "https:%2F%2Fcontent.govdelivery.com%2F%2Fattachments%2FUSCAOHOUSE"
            "%2F2026%2F03%2F09%2Ffile_attachments%2F111%2FMembers.pdf"
            '/1/abc/def=1">link</a>'
        )
        email_bytes = self._make_email_bytes(html)

        mock_mail = MagicMock()
        mock_mail.login.return_value = ("OK", [])
        mock_mail.select.return_value = ("OK", [])
        mock_mail.search.return_value = ("OK", [b"1 2"])
        mock_mail.fetch.return_value = ("OK", [(b"1", email_bytes)])
        mock_mail.logout.return_value = ("BYE", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
            urls = adapter._get_pdf_urls_from_email()

        assert len(urls) == 1

    def test_no_pdf_links_returns_empty(self):
        html = '<a href="https://www.house.gov/employment">jobs</a>'
        email_bytes = self._make_email_bytes(html)

        mock_mail = MagicMock()
        mock_mail.fetch.return_value = ("OK", [(b"1", email_bytes)])

        urls = self._adapter()._extract_pdf_urls_from_message(mock_mail, b"1")
        assert urls == []


# ── Credential handling ───────────────────────────────────────────────


class TestCredentials:
    def test_strips_spaces_from_password(self):
        adapter = HvapsEmailAdapter(
            gmail_user="x", gmail_app_password="abcd efgh ijkl mnop"
        )
        assert adapter.gmail_app_password == "abcdefghijklmnop"

    def test_skips_when_no_password(self):
        adapter = HvapsEmailAdapter(gmail_user="x", gmail_app_password="")
        jobs = adapter.fetch_jobs(MagicMock())
        assert jobs == []
