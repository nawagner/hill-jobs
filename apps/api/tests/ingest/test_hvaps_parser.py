from app.ingest.hvaps_pdf_parser import (
    _extract_organization,
    _extract_title,
    _extract_title_from_heading,
    _extract_location,
    _extract_salary_text,
    _normalize_org_name,
    _parse_listing,
    _split_into_listings,
)


# --- Organization extraction ---

def test_extract_org_congresswoman():
    chunk = "MEM-072-26\nThe Office of Congresswoman Joyce Beatty (OH-03) seeks an innovative Communications Director"
    assert _extract_organization(chunk) == "Rep. Joyce Beatty"


def test_extract_org_congressman():
    chunk = "MEM-064-26\nThe Office of Congressman Steven Horsford seeks a Director of Communications"
    assert _extract_organization(chunk) == "Rep. Steven Horsford"


def test_extract_org_congresswoman_direct():
    chunk = "MEM-066-26\nCongresswoman Laura Gillen (NY-04) is seeking a Press/ Digital Assistant"
    assert _extract_organization(chunk) == "Rep. Laura Gillen"


def test_extract_org_representative():
    chunk = "MEM-068-26\nThe Office of Representative Jane Smith (CA-10) is hiring"
    assert _extract_organization(chunk) == "Rep. Jane Smith"


def test_extract_org_no_match():
    chunk = "MEM-099-26\nModerate House Democrat - Legislative Director"
    assert _extract_organization(chunk) is None


# --- Organization normalization ---

def test_normalize_congresswoman():
    assert _normalize_org_name("Congresswoman Joyce Beatty") == "Rep. Joyce Beatty"


def test_normalize_congressman():
    assert _normalize_org_name("Congressman Steven Horsford") == "Rep. Steven Horsford"


def test_normalize_representative():
    assert _normalize_org_name("Representative Jane Smith") == "Rep. Jane Smith"


def test_normalize_already_rep():
    assert _normalize_org_name("Rep. Jane Smith") == "Rep. Jane Smith"


def test_normalize_committee():
    assert _normalize_org_name("House Rules Committee") == "House Rules Committee"


# --- Heading title extraction (standalone title line after MEM ID) ---

def test_heading_title_with_member_dash():
    """Format: 'Title – Member Name (XX-00)'"""
    chunk = "MEM-068-26\nDigital Director | Press Secretary - Congresswoman Nanette Barragán (CA-44)\nLocation: Washington, DC"
    assert _extract_title_from_heading(chunk) == "Digital Director | Press Secretary"


def test_heading_title_with_rep_dash():
    """Format: 'Title – Rep. Name (XX-00)'"""
    chunk = "MEM-053-26\nCommunications Director – Rep. Jimmy Panetta (CA-19)\nUnited States Representative..."
    assert _extract_title_from_heading(chunk) == "Communications Director"


def test_heading_title_with_scheduler():
    chunk = "MEM-067-26\nScheduler|Executive Assistant – Rep. Nanette Barragán (CA-44)\nLocation: Washington, DC"
    assert _extract_title_from_heading(chunk) == "Scheduler|Executive Assistant"


def test_heading_title_standalone_short():
    """Format: short title with no member name"""
    chunk = "MEM-060-26\nDigital Manager + Press Secretary\nU.S. House of Representatives"
    assert _extract_title_from_heading(chunk) == "Digital Manager + Press Secretary"


def test_heading_title_anonymous_member():
    """Format: 'Moderate House Democrat - Legislative Director'"""
    chunk = "MEM-039-26\nModerate House Democrat - Legislative Director\nModerate House Democrat seeks..."
    assert _extract_title_from_heading(chunk) == "Moderate House Democrat - Legislative Director"


def test_heading_skips_prose_intro():
    """Lines starting with member intro should be skipped (handled by _extract_title)"""
    chunk = "MEM-072-26\nCongresswoman Joyce Beatty (OH-03) seeks an innovative Communications Director"
    assert _extract_title_from_heading(chunk) is None


def test_heading_skips_office_intro():
    chunk = "MEM-064-26\nThe Office of Congressman Steven Horsford seeks a Director of Communications"
    assert _extract_title_from_heading(chunk) is None


# --- Sentence-based title extraction ---

def test_extract_title_seeks():
    chunk = "The Office of Congresswoman Joyce Beatty (OH-03) seeks an innovative Communications Director who can design, produce, and turn around products."
    assert _extract_title(chunk) == "Communications Director"


def test_extract_title_hiring():
    chunk = "Rep. Jane Smith (CA-10) is hiring a Legislative Assistant to manage the portfolio."
    assert _extract_title(chunk) == "Legislative Assistant"


def test_extract_title_seeking():
    chunk = "Congressman John Doe (TX-05) is seeking a Staff Assistant for the Washington, D.C. office."
    assert _extract_title(chunk) == "Staff Assistant"


def test_extract_title_seeks_experienced():
    chunk = "The Office seeks an experienced full-time Legislative Assistant for his Washington, D.C. office."
    assert _extract_title(chunk) == "Legislative Assistant"


# --- Location extraction ---

def test_extract_location_with_prefix():
    chunk = "Location: Washington, DC\nSalary Range: $50,000"
    assert _extract_location(chunk) == "Washington, DC"


def test_extract_location_city_state():
    chunk = "Location: Covina, CA - 31, in person"
    assert _extract_location(chunk) == "Covina, CA - 31, in person"


def test_extract_location_none():
    chunk = "This is a full-time position based in Washington."
    assert _extract_location(chunk) is None


# --- Salary text extraction ---

def test_extract_salary_range():
    chunk = "Salary Range: $45,000 - 50,000 a year depending on the experience"
    assert _extract_salary_text(chunk) is not None
    assert "$45,000" in _extract_salary_text(chunk)


def test_extract_salary_with_label():
    chunk = "Salary: $60,000 - $80,000 annually"
    result = _extract_salary_text(chunk)
    assert result is not None


def test_extract_salary_none():
    chunk = "Compensation is commensurate with experience."
    assert _extract_salary_text(chunk) is None


# --- Listing splitting ---

def test_split_into_listings():
    text = """Header text
MEM-072-26
First job content here.
MEM-071-26
Second job content here.
MEM-070-26
Third job content here."""
    chunks = _split_into_listings(text)
    assert len(chunks) == 3
    assert chunks[0].startswith("MEM-072-26")
    assert chunks[1].startswith("MEM-071-26")
    assert chunks[2].startswith("MEM-070-26")


def test_split_no_listings():
    text = "This is just a header with no MEM IDs."
    assert _split_into_listings(text) == []


# --- Full listing parse ---

def test_parse_listing_full():
    chunk = """MEM-072-26
Congresswoman Joyce Beatty (OH-03) seeks an innovative Communications Director
who can design, produce, and turn around products that respond to the moment.
Location: Washington, DC
Salary Range: $60,000 - $80,000 annually
ESSENTIAL JOB FUNCTIONS:
Develops and implements media, communications, public relations strategies."""

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-072-26"
    assert result["organization"] == "Rep. Joyce Beatty"
    assert result["title"] == "Communications Director"
    assert result["location"] == "Washington, DC"
    assert "$60,000" in result["salary_text"]


def test_parse_listing_minimal():
    chunk = """MEM-099-26
Some office seeks a Staff Assistant."""
    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-099-26"
    assert result["title"] == "Staff Assistant"


def test_parse_listing_heading_format():
    """Listings where title is a standalone heading line."""
    chunk = """MEM-068-26
Digital Director | Press Secretary - Congresswoman Nanette Barragán (CA-44)
Location: Washington, DC
Salary Range: $60-70,000 based on experience
Congresswoman Nanette Barragán (CA-44) is seeking a Press Secretary|Digital Director
to join our communications team."""

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-068-26"
    assert result["title"] == "Digital Director | Press Secretary"
    assert result["organization"] == "Rep. Nanette Barragán"
    assert result["location"] == "Washington, DC"


def test_parse_listing_anonymous_member():
    """Listings with anonymous member (no Congresswoman/man/Rep pattern)."""
    chunk = """MEM-039-26
Moderate House Democrat - Legislative Director
Moderate House Democrat seeks qualified candidates for the position of Legislative
Director for their Washington, D.C. office."""

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-039-26"
    assert result["title"] == "Moderate House Democrat - Legislative Director"


def test_parse_listing_no_mem_id():
    chunk = "This is not a valid listing"
    assert _parse_listing(chunk) is None
