"""Parse HVAPS (House Vacancy Announcement and Placement Service) PDF bulletins.

Each bulletin contains multiple job listings separated by MEM-XXX-XX identifiers.
"""

import io
import logging
import re

import pdfplumber

logger = logging.getLogger(__name__)

_MEM_ID_PATTERN = re.compile(r"MEM-\d{3}-\d{2}", re.IGNORECASE)
_LOCATION_PATTERN = re.compile(
    r"Location:\s*(.+?)(?:\n|$)", re.IGNORECASE
)
_SALARY_RANGE_PATTERN = re.compile(
    r"Salary\s*(?:Range)?\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE
)

# Patterns to identify the member/office from the introductory sentence
_NAME_END = r"\s*(?:\(|seeks|is\s+(?:seeking|hiring|accepting|now\s+accepting)|has\s|provides\s)"
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
    # "Rep. Jane Doe (CA-10) seeks..." or "Rep. Jane Doe's office..."
    re.compile(
        rf"(Rep\.\s+[\w.\-' ]+?){_NAME_END}",
        re.IGNORECASE,
    ),
    # Possessive: "Rep. Angie Craig's office..." or "Congressman John Doe's office..."
    # Note: PDFs may use smart apostrophe (U+2019) or straight apostrophe
    re.compile(
        r"((?:Rep\.|Congress(?:woman|man)|Representative)\s+[\w.\-' ]+?)['\u2019]s\s+(?:office|D\.C\.|district)",
        re.IGNORECASE,
    ),
    # "The Office of Representative Jane Doe, NY-25" (comma + district)
    # or "Office of the Representative Joseph D. Morelle Rochester, NY"
    # Use district pattern (XX-NN) after comma for clean extraction
    re.compile(
        r"(?:The\s+)?Office\s+of\s+(?:the\s+)?(?:U\.?S\.?\s+)?(Representative\s+[\w.\-' ]+?)\s*,\s*[A-Z]{2}-\d+",
        re.IGNORECASE,
    ),
    # "The Democratic Staff of the House Committee on Veterans' Affairs seeks..."
    re.compile(
        r"(?:The\s+)?(\w+\s+Staff\s+of\s+the\s+(?:House\s+)?Committee\s+on\s+[\w\s''\u2019]+?)(?:\s+is\s|\s+seeks)",
        re.IGNORECASE,
    ),
]

# Title patterns - the job title typically appears as a bold line
# right after or near the MEM ID, often with the member name
_TITLE_PATTERNS = [
    # Try specific structural patterns first (higher confidence)
    # "... to serve as a Digital Manager ..."
    re.compile(
        r"to\s+serve\s+as\s+(?:a|an)\s+(?:full[- ]time\s+|part[- ]time\s+)?(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... to fill the Chief of Staff role ..."
    re.compile(
        r"(?:to\s+fill|fill)\s+the\s+(.+?)\s+(?:role|position)",
        re.IGNORECASE,
    ),
    # "... to hire a Chief of Staff ..."
    re.compile(
        r"to\s+hire\s+(?:a|an)\s+(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... seeks qualified candidates for the position of Legislative Director"
    re.compile(
        r"(?:position|role)\s+of\s+(?:a\s+)?(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # Then try general "seeks/hiring/seeking" patterns
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
        r"is\s+seeking\s+(?:a|an)\s+(.+?)(?:\s+to\s|\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... seeks press and legislative interns for ..."
    # "... is seeking full-time, energetic interns for ..."
    re.compile(
        r"(?:seeks|is\s+seeking)\s+(.+?intern\w*)(?:\s+for\s|\s+in\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... is accepting applications for Summer 2026 legislative interns ..."
    # "... is accepting applications for summer internships ..."
    re.compile(
        r"(?:is\s+)?(?:now\s+)?accepting\s+applications\s+for\s+(?:\w+\s+\d{4}\s+)?(.+?)(?:\s+in\s+(?:our|the|his|her|their)\s|\s+during\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "Summer internships in Rep. Name's office..." (title at start of listing)
    re.compile(
        r"^MEM-\d{3}-\d{2}\s+(.+?internship\w*)\s+in\s",
        re.IGNORECASE,
    ),
    # "... will be accepting applications for an in-person internship ..."
    re.compile(
        r"(?:will\s+be\s+)?accepting\s+applications\s+for\s+(?:a|an)\s+(.+?)(?:\s+during\s|\.\s|\s*$)",
        re.IGNORECASE,
    ),
    # "... provides seasonal internship opportunities ..."
    re.compile(
        r"provides\s+(.+?internship\s+opportunit\w*)",
        re.IGNORECASE,
    ),
    # Broad fallback: if text mentions "internship" prominently, use "Internship"
    # "In the Washington, D.C. office, internships run throughout the year..."
    re.compile(
        r"\b(internship\w*)\s+(?:run|program|opportunit)",
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
    source_job_id = mem_match.group(0).upper()

    # Extract organization (member/office name)
    organization = _extract_organization(chunk)

    # Extract title — try heading line first, then sentence patterns, then fallback
    title = _extract_title_from_heading(chunk)
    if not title:
        title = _extract_title(chunk)
    if not title:
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


# Pattern for standalone heading lines: "Title – Member Name (XX-00)" or just "Title"
# These appear on line 2 right after the MEM ID
_HEADING_TITLE_PATTERN = re.compile(
    r"^(.+?)\s*(?:–|—|-)\s*(?:Rep\.|Congresswo?man|U\.S\.\s)", re.IGNORECASE
)


def _extract_title_from_heading(chunk: str) -> str | None:
    """Extract title from a standalone heading line right after the MEM ID.

    Many HVAPS listings have the format:
        MEM-068-26
        Digital Director | Press Secretary - Congresswoman Nanette Barragán (CA-44)
    or:
        MEM-039-26
        Moderate House Democrat - Legislative Director
    """
    lines = chunk.split("\n")
    if len(lines) < 2:
        return None

    line2 = lines[1].strip()

    # Skip lines that start with a member/office intro (these embed the title
    # in prose, handled by _extract_title instead)
    if re.match(
        r"(?:The\s+)?(?:Office\s+of\s+)?(?:Congress(?:wo)?man|Rep(?:resentative)?\.?\s|United\s+States)",
        line2,
        re.IGNORECASE,
    ):
        return None

    # "Internship Opportunity: Office of ..." — extract "Internship Opportunity" as title
    m_intern_heading = re.match(r"(Internship\s+Opportunity)\s*:", line2, re.IGNORECASE)
    if m_intern_heading:
        return m_intern_heading.group(1)

    # Skip lines that are long prose descriptions (internship intros etc.)
    if len(line2) > 80:
        return None

    # Format: "Title – Member Name (XX-00)" or "Title - Rep. Name (XX-00)"
    m = _HEADING_TITLE_PATTERN.match(line2)
    if m:
        title = m.group(1).strip().rstrip(".,;:|")
        if 3 <= len(title) <= 100:
            return title

    # Format: short standalone title line (no member name, e.g., "Digital Manager + Press Secretary")
    # Must be relatively short and not look like a sentence
    if len(line2) <= 60 and not line2.endswith((".", ";")) and not re.search(r"\b(?:seeks|hiring|seeking)\b", line2, re.IGNORECASE):
        return line2

    return None


def _extract_title(chunk: str) -> str | None:
    """Try to extract the job title from the listing text using patterns."""
    # Join lines in the first ~1000 chars to handle titles that wrap across lines
    lines = chunk[:1500].split("\n")
    joined = " ".join(line.strip() for line in lines[:15] if line.strip())
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(joined[:1000])
        if m:
            title = m.group(1).strip()
            # Clean up common trailing artifacts
            title = re.sub(r"\s+(?:who|that|which)\s.*$", "", title, flags=re.IGNORECASE)
            title = _strip_leading_qualifiers(title)
            # Remove trailing punctuation
            title = title.rstrip(".,;:")
            if 3 <= len(title) <= 100:
                return title
    return None


_ADJ_RE = re.compile(
    r"^(?:experienced|innovative|creative|dynamic|motivated|dedicated|"
    r"detail[\s-]oriented|organized|strategic|seasoned|talented|qualified|"
    r"highly\s+\w+|full[\s-]time|part[\s-]time|and\s+\w+)[,;\s]+",
    re.IGNORECASE,
)


def _strip_leading_qualifiers(title: str) -> str:
    """Strip leading adjective lists from an extracted title.

    Handles both space-separated ("experienced Legislative Director") and
    comma-separated ("organized, confident, and experienced Legislative Director").
    """
    # First, strip comma-separated lowercase qualifier lists that precede
    # a capitalized title, e.g. "organized, confident, collaborative, and
    # experienced Legislative Director" → "Legislative Director"
    title = re.sub(
        r"^(?:[a-z][\w-]*(?:\s+[a-z][\w-]*)?,\s+)+(?:and\s+)?[a-z][\w-]*(?:\s+[a-z][\w-]*)?\s+",
        "", title,
    )
    # Then strip any remaining individual leading adjectives
    while _ADJ_RE.match(title):
        title = _ADJ_RE.sub("", title, count=1)
    return title


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
