"""HVAPS email adapter — fetches PDF bulletins from Gmail via IMAP.

Connects to the hilljobs.ingest@gmail.com inbox, finds HVAPS bulletin
emails, extracts PDF links, downloads them, and parses job listings
using the existing HVAPS PDF parser.
"""

import email
import imaplib
import logging
import os
import re
from email.message import Message
from urllib.parse import unquote

import httpx

from app.ingest.adapters.hvaps import parse_hvaps_source_jobs
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"
HVAPS_SUBJECT = "House of Representatives Vacancy Announcement Bulletin"

# Govdelivery tracking URLs that wrap real PDF links:
# https://links-2.govdelivery.com/CL0/https:%2F%2Fcontent.govdelivery.com%2F...pdf/1/...
_TRACKING_PDF_RE = re.compile(
    r"https://links[-\w]*\.govdelivery\.com/CL0/(https:%2F%2Fcontent\.govdelivery\.com"
    r"%2F[^/]*\.pdf)/",
)


class HvapsEmailAdapter:
    source_system = "house-hvaps"

    def __init__(
        self,
        gmail_user: str | None = None,
        gmail_app_password: str | None = None,
        max_emails: int = 5,
    ):
        self.gmail_user = gmail_user or os.environ.get(
            "GMAIL_ADDRESS", "hilljobs.ingest@gmail.com"
        )
        raw_pw = gmail_app_password or os.environ.get("GMAIL_APP_PASSWORD", "")
        self.gmail_app_password = raw_pw.replace(" ", "")
        self.max_emails = max_emails

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        if not self.gmail_app_password:
            logger.warning("GMAIL_APP_PASSWORD not set — skipping HVAPS email adapter")
            return []

        pdf_urls = self._get_pdf_urls_from_email()
        if not pdf_urls:
            logger.info("No HVAPS PDF URLs found in recent emails")
            return []

        logger.info("Found %d HVAPS PDF URLs", len(pdf_urls))

        all_jobs: list[SourceJob] = []
        for url in pdf_urls:
            try:
                resp = client.get(url, follow_redirects=True, timeout=30.0)
                resp.raise_for_status()
                jobs = parse_hvaps_source_jobs(resp.content, url)
                all_jobs.extend(jobs)
                logger.info("Parsed %d jobs from %s", len(jobs), url)
            except Exception:
                logger.exception("Failed to download/parse HVAPS PDF: %s", url)

        return all_jobs

    def _get_pdf_urls_from_email(self) -> list[str]:
        """Connect to Gmail IMAP and extract PDF URLs from HVAPS emails."""
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        try:
            mail.login(self.gmail_user, self.gmail_app_password)
            mail.select("INBOX", readonly=True)

            status, data = mail.search(
                None, f'(SUBJECT "{HVAPS_SUBJECT}")'
            )
            if status != "OK" or not data[0]:
                logger.info("No HVAPS emails found")
                return []

            msg_ids = data[0].split()
            recent_ids = msg_ids[-self.max_emails :]

            pdf_urls: list[str] = []
            for msg_id in reversed(recent_ids):  # newest first
                urls = self._extract_pdf_urls_from_message(mail, msg_id)
                pdf_urls.extend(urls)

            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for url in pdf_urls:
                if url not in seen:
                    seen.add(url)
                    unique.append(url)

            return unique
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def _extract_pdf_urls_from_message(
        self, mail: imaplib.IMAP4_SSL, msg_id: bytes
    ) -> list[str]:
        """Extract PDF URLs from a single email message."""
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK" or not msg_data[0]:
            return []

        msg = email.message_from_bytes(msg_data[0][1])
        html_body = self._get_html_body(msg)
        if not html_body:
            return []

        # Extract real PDF URLs from govdelivery tracking wrappers
        encoded_urls = _TRACKING_PDF_RE.findall(html_body)
        return [unquote(u) for u in encoded_urls]

    def _get_html_body(self, msg: Message) -> str:
        """Extract HTML body from an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            if msg.get_content_type() == "text/html":
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
