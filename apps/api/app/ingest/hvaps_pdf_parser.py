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


# --- Title extraction ---
#
# Titles come from three places, tried in order: a heading line right after
# the MEM ID, a phrase in the opening prose ("seeks a Staff Assistant"), or
# failing those, the first title-like line near the top.

# Pattern for standalone heading lines: "Title – Member Name (XX-00)" or just "Title"
# These appear on line 2 right after the MEM ID
_HEADING_TITLE_PATTERN = re.compile(
    r"^(.+?)\s*(?:–|—|-)\s*(?:Rep\.|Congresswo?man|U\.S\.\s)", re.IGNORECASE
)

# "POSITION OPENING: DISTRICT DIRECTOR", "JOB POSTING: ..." → keep what follows
_HEADING_PREFIX_RE = re.compile(
    r"^(?:position\s+opening|job\s+(?:posting|opening|announcement|title)|"
    r"now\s+hiring|position|vacancy)\s*:\s*",
    re.IGNORECASE,
)

# Section headers that sometimes sit where a title would ("SUMMARY:",
# "POSITION OVERVIEW", "Requirements:", "Internship Responsibilities")
_HEADER_WORDS = {
    "about", "the", "office", "position", "job", "role", "opening", "posting",
    "announcement", "vacancy", "overview", "summary", "description", "details",
    "requirements", "responsibilities", "qualifications", "duties", "how", "to",
    "apply",
}
_HEADER_LAST_WORDS = {
    "overview", "summary", "description", "requirements", "responsibilities",
    "qualifications", "duties", "benefits", "compensation", "salary", "location",
    "skills", "apply", "instructions", "notice", "eligibility",
}

# Lowercase words allowed inside a Title Case heading
_SMALL_WORDS = {"a", "an", "and", "or", "of", "for", "the", "to", "in", "on", "at", "with"}
# Kept uppercase when title-casing an ALL CAPS heading
_ACRONYMS = {"DC", "HR", "IT", "US", "USA"}
# Words that may join the parts of a title: "Chief of Staff", "Assistant/Secretary"
_CONNECTORS = {"and", "or", "of", "&", "+", "|", "/", "-", "–"}

# Office or member names, which aren't titles: "Office of Rep. ...", "Representative Nancy Mace"
_ORG_RE = re.compile(
    r"\b(?:Congress(?:wo)?man\b|Office\s+of\b|Rep\.|Representative\s+[A-Z][a-z]|Senator\b)"
)

# Job nouns that HVAPS listings often write in lowercase ("seeks press intern",
# "accepting applications for internships", "seeking a fellow")
_LOWERCASE_ROLE_RE = re.compile(r"(?:intern|internship|fellow|fellowship|clerk)s?", re.IGNORECASE)
_INTERN_RE = re.compile(r"\bintern", re.IGNORECASE)
# Job nouns for the low-confidence "The <Title> serves/will ..." pattern
_ROLE_NOUN_RE = re.compile(
    r"\b(?:intern|internship|fellow|fellowship|clerk|aide|assistant|scheduler|"
    r"caseworker|correspondent|secretary|director|manager|counsel|staffer|"
    r"coordinator|analyst|advis[eo]r|representative|specialist|paralegal|writer|"
    r"chief|officer|associate|administrator|liaison|editor|producer|strategist|"
    r"economist|attorney|investigator|designer)s?\b",
    re.IGNORECASE,
)

# Internship terms: "Spring 2027", "Fall of 2026", "2026 Fall term", "fall intern 2026"
_SEASON = r"(spring|summer|fall|autumn|winter)"
_LEADING_TERM_RE = re.compile(
    rf"(?:{_SEASON}(?:\s+(?:of\s+)?(20\d{{2}}))?|(20\d{{2}})\s+{_SEASON})"
    r"(?:\s+(?:semester|term|session))?(?:\s+|$)",
    re.IGNORECASE,
)
_TERM_RE = re.compile(
    rf"\b(?:{_SEASON}\s+(?:\w+\s+)?(20\d{{2}})|(20\d{{2}})\s+{_SEASON})\b",
    re.IGNORECASE,
)
_HAS_TERM_RE = re.compile(r"\b(?:spring|summer|fall|autumn|winter|20\d{2})\b", re.IGNORECASE)

_LEADING_ARTICLE_RE = re.compile(r"^(?:a|an|the|our|his|her|their)\s+", re.IGNORECASE)
_TRAILING_NOUN_RE = re.compile(
    r"\s+(?:position|role|opportunit(?:y|ies)|program|opening)s?$", re.IGNORECASE
)

# Where a phrase captured by _TITLE_PATTERNS ends: "Staff Assistant to join...",
# "...for her Durham office", "...who can...", end of sentence (but not "D.C. ").
_END = (
    r"(?:\s+(?:to|for|in|who|with|that|during|at|based|starting|beginning)\s"
    r"|(?<!\b[A-Z])\.\s|[;:]|\s*$)"
)

# Sentence patterns, most reliable first. Each entry is (pattern, needs_role_noun).
# Every match is checked by _clean_title_candidate, so a pattern that grabs a
# fragment ("the role of a communications team") falls through to the next match.
_TITLE_PATTERNS = [
    # "... to serve as a Digital Manager ...", "... to join as a fall intern 2026."
    (re.compile(rf"\bto\s+(?:serve|join)\s+as\s+(?:(?:a|an|the)\s+)?(.+?){_END}", re.I), False),
    # "... to fill the Chief of Staff role ..."
    (re.compile(r"\bfill\s+the\s+(.+?)\s+(?:role|position)", re.I), False),
    # "... to hire a Chief of Staff ..."
    (re.compile(rf"\bto\s+hire\s+(?:a|an)\s+(.+?){_END}", re.I), False),
    # "... candidates for the position of Executive Assistant and Scheduler in ..."
    (re.compile(rf"\b(?:position|role)\s+of\s+(?:(?:a|an|the)\s+)?(.+?){_END}", re.I), False),
    # "... has an immediate opening for an Operations Assistant ...",
    # "We are looking for a District Director who ..."
    (re.compile(rf"\b(?:opening|looking)\s+for\s+(?:a|an)\s+(.+?){_END}", re.I), False),
    # "... seeks an organized Staff Assistant ...", "... seeks press intern ...",
    # "... Committee Seeks Legislative/Financial Services Fellow.", "Democrats seek interns"
    (re.compile(rf"\bseeks?\s+(?:(?:a|an)\s+)?(.+?){_END}", re.I), False),
    # "... is hiring a Legislative Assistant ..."
    (re.compile(rf"\bhiring\s+(?:a|an)\s+(.+?){_END}", re.I), False),
    # "... is seeking a Press Secretary ...", "... is seeking interns for ..."
    (re.compile(rf"\bseeking\s+(?:(?:a|an)\s+)?(.+?){_END}", re.I), False),
    # "... is accepting applications for Fall 2026 paid internships in our ..."
    # "... is currently accepting applicants for a paid Fall Legislative Internship ..."
    (re.compile(rf"\baccepting\s+applica(?:tions|nts)\s+for\s+(.+?){_END}", re.I), False),
    # "The Office of Rep. Josh Harder offers paid internships in our Washington office."
    (re.compile(rf"\boffers\s+(.+?){_END}", re.I), False),
    # "... seeks highly motivated candidates for a paid Spring 2027 internship position ..."
    (re.compile(r"\bfor\s+(?:a|an)\s+([^.;:]{3,60}?)\s+(?:position|role|opening)\b", re.I), False),
    # "The Legislative Director serves as ...", "... the Law Clerk will support ...",
    # "A Paralegal for HOLC assists ..." (case-sensitive: the title must be capitalized)
    (
        re.compile(
            r"\b(?:[Tt]he|An?)\s+((?:[A-Z][\w'’/&+-]*\s+(?:(?:and|of|or|&)\s+)?){0,5}[A-Z][\w'’/&+-]*)"
            r"(?:\s+for\s+(?:the\s+)?[A-Z][\w.]*)?"
            r"\s+(?:serves|supports|assists|manages|reports|works|provides|will|is\s+responsible)\b"
        ),
        True,
    ),
    # "... provides seasonal internship opportunities ..."
    (re.compile(r"\bprovides\s+(.+?internship\s+opportunit\w*)", re.I), False),
    # "Summer internships in Rep. Name's office..." (title at start of listing)
    (re.compile(r"^MEM-\d{3}-\d{2}\s+(.+?internship\w*)\s+in\s", re.I), False),
    # "In the Washington, D.C. office, internships run throughout the year..."
    (re.compile(r"\b(internship\w*)\s+(?:run|program|opportunit)", re.I), False),
]


def _extract_title_from_heading(chunk: str) -> str | None:
    """Extract title from a standalone heading line right after the MEM ID.

    Many HVAPS listings have the format:
        MEM-068-26
        Digital Director | Press Secretary - Congresswoman Nanette Barragán (CA-44)
    or:
        MEM-039-26
        Moderate House Democrat - Legislative Director
    or:
        MEM-216-26
        POSITION OPENING: DISTRICT DIRECTOR
    Section headers in that spot ("SUMMARY:", "POSITION OVERVIEW") are skipped.
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

    line2 = _HEADING_PREFIX_RE.sub("", line2)

    # Skip lines that are long prose descriptions (internship intros etc.)
    if len(line2) > 80:
        return None

    # Format: "Title – Member Name (XX-00)" or "Title - Rep. Name (XX-00)"
    m = _HEADING_TITLE_PATTERN.match(line2)
    if m:
        title = m.group(1).strip().rstrip(".,;:|")
        if 3 <= len(title) <= 100:
            return _fix_all_caps(title)

    # Format: short standalone title line (no member name, e.g., "Digital Manager + Press Secretary")
    # Must be relatively short and not look like a sentence or a section header
    if (
        3 <= len(line2) <= 60
        and not line2.endswith((".", ";"))
        and not re.search(r"\b(?:seeks|hiring|seeking)\b", line2, re.IGNORECASE)
        and _looks_like_title_line(line2)
    ):
        return _fix_all_caps(line2)

    return None


def _extract_title(chunk: str) -> str | None:
    """Try to extract the job title from the listing's opening prose."""
    # Join the first lines so titles that wrap across lines still match
    text = _join_lines(chunk[:1500].split("\n")[:15])[:1000]
    for pattern, needs_role_noun in _TITLE_PATTERNS:
        for m in pattern.finditer(text):
            title = _clean_title_candidate(m.group(1), text)
            if title and (not needs_role_noun or _ROLE_NOUN_RE.search(title)):
                return title
    return None


def _join_lines(lines: list[str]) -> str:
    """Join PDF lines with spaces, re-joining words hyphenated across a line break."""
    text = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.search(r"[A-Za-z]-$", text):  # "service-" + "oriented"
            text += line
        else:
            text = f"{text} {line}" if text else line
    return text


def _clean_title_candidate(phrase: str, text: str) -> str | None:
    """Turn a phrase captured after "seeks a", "position of", etc. into a title.

    Returns None when the phrase isn't a title ("highly motivated candidates",
    "communications team", "the first point of contact").
    """
    phrase = " ".join(phrase.split())
    phrase = re.sub(r"\s+(?:who|that|which)\s.*$", "", phrase, flags=re.IGNORECASE)
    phrase = phrase.strip(" .,;:")

    # Peel off leading articles, adjectives and the internship term:
    # "a paid Spring 2027 internship" → "internship" (term "Spring 2027")
    term = None
    while True:
        before = phrase
        phrase = _LEADING_ARTICLE_RE.sub("", phrase)
        phrase = _strip_leading_qualifiers(phrase)
        m = _LEADING_TERM_RE.match(phrase)
        if m:
            term = term or _format_term(m)
            phrase = phrase[m.end():]
        if phrase == before:
            break
    phrase = re.sub(r"\s+20\d{2}$", "", phrase)  # "fall intern 2026"
    phrase = _TRAILING_NOUN_RE.sub("", phrase)  # "internship opportunity", "... position"

    words = phrase.split()
    first_cap = next((i for i, w in enumerate(words) if w[:1].isupper()), len(words))
    # A lowercase job noun before any capitalized word is the title
    # ("interns serving the House ..."); otherwise take the capitalized run
    # ("organized Staff Assistant to join", "Operations Assistant help manage").
    lower_roles = [i for i, w in enumerate(words[:first_cap]) if _is_lowercase_role(w)]
    if lower_roles:
        role_words = words[: lower_roles[-1] + 1]
        title = _title_case(" ".join(role_words)) if len(role_words) <= 6 else None
    else:
        title = _capitalized_run(words[first_cap:])
    if not title or not _is_plausible_title(title):
        return None

    # Internship titles carry their term: "Fall 2026 Legislative Interns"
    if _INTERN_RE.search(title) and not (term and term[-1].isdigit()):
        m = _TERM_RE.search(text[:600])
        if m:
            term = _format_term(m)
    if term and not _HAS_TERM_RE.search(title):
        title = f"{term} {title}"
    return title


def _format_term(m: re.Match) -> str:
    """ "fall of 2026" / "2026 Fall" → "Fall 2026" (groups as in _LEADING_TERM_RE/_TERM_RE)."""
    season = (m.group(1) or m.group(4)).capitalize()
    year = m.group(2) or m.group(3)
    return f"{season} {year}" if year else season


def _is_lowercase_role(word: str) -> bool:
    # The word or its last part: "interns", "press/intern", but not "self-starter"
    return bool(_LOWERCASE_ROLE_RE.fullmatch(re.split(r"[/-]", word.rstrip(",;"))[-1]))


def _capitalized_run(words: list[str]) -> str | None:
    """Take capitalized words from the start: "Staff Assistant to join" → "Staff Assistant"."""
    run: list[str] = []
    for word in words:
        bare = word.rstrip(",;")
        if not (
            bare[:1].isupper()
            or bare[:1].isdigit()
            or bare.lower() in _CONNECTORS
            or _is_lowercase_role(bare)  # "Legislative intern"
            or re.fullmatch(r"\([A-Z]{2,6}\)", bare)  # "Professional Staff Member (PSM)"
        ):
            break
        run.append(_title_case(bare) if _is_lowercase_role(bare) else bare)
        if bare != word:  # a comma ends the title
            break
    while run and run[-1].lower() in _CONNECTORS:
        run.pop()
    return " ".join(run) or None


def _is_plausible_title(title: str) -> bool:
    return (
        3 <= len(title) <= 100
        and len(title.split()) <= 10
        and not _ORG_RE.search(title)
        and not re.search(r"\b(?:Member|Office|Committee)['’]s\b", title)  # "Member’s chief policy advisor"
        and not _is_section_header(title)
    )


def _is_section_header(line: str) -> bool:
    if line.rstrip().endswith(":"):
        return True
    words = re.findall(r"[a-z]+", line.lower())
    return bool(words) and (
        words[-1] in _HEADER_LAST_WORDS or all(w in _HEADER_WORDS for w in words)
    )


def _looks_like_title_line(line: str) -> bool:
    """Title Case, no colon, not a section header: "Fall 2026 Interns", "Digital Director"."""
    if ":" in line or _is_section_header(line):
        return False
    for word in line.split():
        first_letter = next((c for c in word if c.isalpha()), "")
        if first_letter.islower() and word.strip("(),").lower() not in _SMALL_WORDS:
            return False
    return True


def _fix_all_caps(title: str) -> str:
    return _title_case(title) if title.isupper() else title


def _title_case(text: str) -> str:
    """ "DISTRICT PRESS/DIGITAL ASSISTANT" → "District Press/Digital Assistant"."""
    words = []
    for i, word in enumerate(text.split()):
        if word.strip("(),") in _ACRONYMS or "." in word.rstrip("."):  # "IT", "D.C."
            words.append(word)
        elif i and word.lower() in _SMALL_WORDS:
            words.append(word.lower())
        else:
            words.append(
                re.sub(r"(^|[/(-])([a-z])", lambda m: m.group(1) + m.group(2).upper(), word.lower())
            )
    return " ".join(words)


_ADJ_RE = re.compile(
    r"^(?:experienced|innovative|creative|dynamic|motivated|dedicated|"
    r"detail[\s-]oriented|organized|strategic|seasoned|talented|qualified|"
    r"energetic|proactive|enthusiastic|driven|paid|unpaid|seasonal|"
    r"short[\s-]term|long[\s-]term|in[\s-]person|entry[\s-]level|"
    r"highly\s+\w+|full[\s-]time|part[\s-]time|(?:and|or)\s+[\w-]+)[,;\s]+",
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
        # A short Title Case line near the top that isn't a sentence fragment
        # ("communicate and liaise with ...") or an office name is likely a title
        if (
            not line.endswith((".", ";"))
            and _looks_like_title_line(line)
            and not _ORG_RE.search(line)
        ):
            return _fix_all_caps(line)
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
