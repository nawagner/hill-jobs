"""Parse HVAPS (House Vacancy Announcement and Placement Service) PDF bulletins.

Each bulletin contains multiple job listings separated by MEM-XXX-XX identifiers.
"""

import io
import logging
import re

import pdfplumber

logger = logging.getLogger(__name__)

_MEM_ID_PATTERN = re.compile(r"MEM-\d{3}-\d{2}")
_LOCATION_PATTERN = re.compile(
    r"Location:\s*(.+?)(?:\n|$)", re.IGNORECASE
)
_SALARY_RANGE_PATTERN = re.compile(
    r"Salary\s*(?:Range)?\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE
)

# Patterns to identify the member/office from the introductory sentence
_NAME_END = r"\s*(?:\(|seeks|is\s+(?:seeking|hiring)|has\s)"
_MEMBER_PATTERNS = [
    # "The Office of Congresswoman Jane Doe (CA-10) seeks..."
    re.compile(
        rf"(?:The\s+)?Office\s+of\s+(Congress(?:woman|man)\s+.+?){_NAME_END}",
        re.IGNORECASE,
    ),
    # "Congresswoman Jane Doe (CA-10) seeks..." or "Congressman ..."
    re.compile(
        rf"(Congress(?:woman|man)\s+[\w.\-' ]+?){_NAME_END}",
        re.IGNORECASE,
    ),
    # "The Office of Representative Jane Doe (CA-10)..."
    re.compile(
        rf"(?:The\s+)?Office\s+of\s+(Representative\s+.+?){_NAME_END}",
        re.IGNORECASE,
    ),
    # "The Office of U.S. Representative Jane Doe (CA-10)..."
    re.compile(
        rf"(?:The\s+)?Office\s+of\s+U\.?S\.?\s+(Representative\s+.+?){_NAME_END}",
        re.IGNORECASE,
    ),
    # "Rep. Jane Doe (CA-10) seeks..."
    re.compile(
        rf"(Rep\.\s+[\w.\-' ]+?){_NAME_END}",
        re.IGNORECASE,
    ),
]

# Title patterns - the job title typically appears as a bold line
# right after or near the MEM ID, often with the member name
_TITLE_PATTERNS = [
    # "... seeks a Communications Director ..."
    re.compile(
        r"seeks\s+(?:a|an)\s+(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\s+who\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... is hiring a Legislative Assistant ..."
    re.compile(
        r"(?:is\s+)?hiring\s+(?:a|an)\s+(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... is seeking a Press Secretary ..."
    re.compile(
        r"is\s+seeking\s+(?:a|an)\s+(?:motivated\s+|detail[- ]oriented\s+)?(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... seeks qualified candidates for the position of Legislative Director"
    re.compile(
        r"(?:for|of)\s+(?:the\s+)?(?:position\s+of\s+)?(?:a\s+)?(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
]


def parse_hvaps_pdf(pdf_bytes: bytes) -> list[dict]:
    """Parse an HVAPS PDF bulletin into individual job listing dicts.

    Returns a list of dicts with keys:
        source_job_id, title, organization, location, salary_text,
        description_text
    """
    text = _extract_text(pdf_bytes)
    chunks = _split_into_listings(text)
    jobs = []
    for chunk in chunks:
        try:
            job = _parse_listing(chunk)
            if job:
                jobs.append(job)
        except Exception:
            logger.exception("Failed to parse HVAPS listing chunk")
    logger.info("Parsed %d job listings from HVAPS PDF", len(jobs))
    return jobs


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF."""
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _split_into_listings(text: str) -> list[str]:
    """Split the full PDF text into individual listing chunks by MEM-XXX-XX IDs."""
    # Find all MEM ID positions
    matches = list(_MEM_ID_PATTERN.finditer(text))
    if not matches:
        return []

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _parse_listing(chunk: str) -> dict | None:
    """Parse a single listing chunk into a structured dict."""
    # Extract MEM ID
    mem_match = _MEM_ID_PATTERN.match(chunk)
    if not mem_match:
        return None
    source_job_id = mem_match.group(0)

    # Extract organization (member/office name)
    organization = _extract_organization(chunk)

    # Extract title
    title = _extract_title(chunk)
    if not title:
        # Fallback: use the first non-MEM line that looks like a title
        title = _extract_title_from_lines(chunk, source_job_id)

    # Extract location
    location = _extract_location(chunk)

    # Extract salary text (raw, will be parsed by salary_parser later)
    salary_text = _extract_salary_text(chunk)

    return {
        "source_job_id": source_job_id,
        "title": title or "Unknown Position",
        "organization": organization or "U.S. House of Representatives",
        "location": location or "Washington, DC",
        "salary_text": salary_text,
        "description_text": chunk,
    }


def _extract_organization(chunk: str) -> str | None:
    """Extract the member/office name from the listing text."""
    for pattern in _MEMBER_PATTERNS:
        m = pattern.search(chunk)
        if m:
            return _normalize_org_name(m.group(1).strip())
    return None


def _normalize_org_name(name: str) -> str:
    """Normalize organization names to align with Domewatch format.

    Converts "Congresswoman Jane Doe" / "Congressman John Doe" to "Rep. Jane Doe".
    """
    for prefix in ("Congresswoman ", "Congressman "):
        if name.startswith(prefix):
            return f"Rep. {name[len(prefix):]}"
    for prefix in ("Representative ",):
        if name.startswith(prefix):
            return f"Rep. {name[len(prefix):]}"
    return name


def _extract_title(chunk: str) -> str | None:
    """Try to extract the job title from the listing text using patterns."""
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(chunk[:1000])  # Only search first ~1000 chars
        if m:
            title = m.group(1).strip()
            # Clean up common trailing artifacts
            title = re.sub(r"\s+(?:who|that|which)\s.*$", "", title, flags=re.IGNORECASE)
            # Strip leading adjectives/qualifiers that aren't part of the title
            _ADJ_RE = re.compile(
                r"^(?:experienced|innovative|creative|dynamic|motivated|dedicated|"
                r"detail[\s-]oriented|organized|strategic|seasoned|talented|qualified|"
                r"highly\s+\w+|full[\s-]time|part[\s-]time|and\s+\w+)\s+",
                re.IGNORECASE,
            )
            while _ADJ_RE.match(title):
                title = _ADJ_RE.sub("", title, count=1)
            # Remove trailing punctuation
            title = title.rstrip(".,;:")
            if 3 <= len(title) <= 100:
                return title
    return None


def _extract_title_from_lines(chunk: str, mem_id: str) -> str | None:
    """Fallback title extraction from prominent lines near the MEM ID."""
    lines = chunk.split("\n")
    # Skip the MEM ID line, look at subsequent lines for a short title-like line
    for line in lines[1:10]:
        line = line.strip()
        # Skip empty lines, long lines (descriptions), and common non-title lines
        if not line or len(line) > 80 or len(line) < 5:
            continue
        # Skip lines that look like sections
        if line.upper().startswith(("ESSENTIAL", "EDUCATION", "SALARY", "QUALIFICATIONS",
                                    "SKILLS", "WORKING", "BENEFITS", "HOW TO", "TO APPLY",
                                    "NOTICE", "APPLICANT")):
            continue
        # A short line near the top that isn't a paragraph is likely a title
        if not line.endswith((".",";")):
            return line
    return None


def _extract_location(chunk: str) -> str | None:
    """Extract location from the listing text."""
    m = _LOCATION_PATTERN.search(chunk)
    if m:
        loc = m.group(1).strip().rstrip(".,;")
        return loc
    return None


def _extract_salary_text(chunk: str) -> str | None:
    """Extract raw salary text for later parsing."""
    m = _SALARY_RANGE_PATTERN.search(chunk)
    if m:
        return m.group(1).strip()
    return None
