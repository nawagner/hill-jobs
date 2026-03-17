from app.ingest.hvaps_pdf_parser import (
    _extract_organization,
    _extract_title,
    _extract_title_from_heading,
    _extract_location,
    _extract_salary_text,
    _normalize_org_name,
    _parse_listing,
    _split_into_listings,
    _strip_leading_qualifiers,
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


def test_split_mixed_case_mem_id():
    """MEM IDs with non-standard casing (e.g., 'Mem-071-26') should still be split."""
    text = """MEM-072-26
First job content.
Mem-071-26
Second job content."""
    chunks = _split_into_listings(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("MEM-072-26")
    assert "Mem-071-26" in chunks[1]


def test_parse_listing_mixed_case_mem_id():
    """Mixed-case MEM IDs should be normalized to uppercase."""
    chunk = """Mem-071-26
The Office of Congressman Gilbert R. Cisneros Jr. (CA - 31) seeks a District
Scheduler/Caseworker in Covina, CA."""
    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-071-26"
    assert result["title"] == "District Scheduler/Caseworker"


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


# --- Internship listing parsing ---

def test_extract_org_possessive():
    """Possessive form: Rep. Name\u2019s office (smart apostrophe from PDF)."""
    chunk = "MEM-080-26\nSummer internships in Rep. Angie Craig\u2019s office will be held in-person"
    assert _extract_organization(chunk) == "Rep. Angie Craig"


def test_extract_org_possessive_straight_apostrophe():
    """Possessive form: Rep. Name's office (straight apostrophe)."""
    chunk = "MEM-080-26\nSummer internships in Rep. Angie Craig's office will be held in-person"
    assert _extract_organization(chunk) == "Rep. Angie Craig"


def test_extract_org_is_accepting():
    """'is accepting applications' should match as a name-ending phrase."""
    chunk = "MEM-040-26\nThe Office of Representative Chrissy Houlahan (D-PA-06) is accepting applications"
    assert _extract_organization(chunk) == "Rep. Chrissy Houlahan"


def test_extract_org_provides():
    """'provides seasonal internship' should match as a name-ending phrase."""
    chunk = "The Office of Congresswoman Eleanor Holmes Norton provides seasonal internship opportunities"
    assert _extract_organization(chunk) == "Rep. Eleanor Holmes Norton"


def test_extract_org_committee_staff():
    chunk = "MEM-057-26\nThe Democratic Staff of the House Committee on Veterans\u2019 Affairs seeks a press/digital intern"
    assert _extract_organization(chunk) == "Democratic Staff of the House Committee on Veterans\u2019 Affairs"


def test_extract_org_district_comma():
    """Representative Name, XX-NN district format."""
    chunk = "The District Office of Representative Joseph Morelle, NY-25 in Rochester, NY"
    assert _extract_organization(chunk) == "Rep. Joseph Morelle"


def test_extract_title_seeks_interns():
    chunk = "Congressman Mike Levin (CA-49) seeks press and legislative interns for his Washington, D.C., office."
    assert _extract_title(chunk) == "press and legislative interns"


def test_extract_title_seeking_interns():
    chunk = "The Democratic Staff of the House Committee on Veterans\u2019 Affairs seeks a press/digital intern for the Summer 2026 semester."
    title = _extract_title(chunk)
    assert title is not None
    assert "intern" in title.lower()


def test_extract_title_accepting_internships():
    chunk = "The Office of Representative Chrissy Houlahan (D-PA-06) is accepting applications for Summer 2026 legislative interns in our West Chester office."
    title = _extract_title(chunk)
    assert title is not None
    assert "intern" in title.lower()


def test_extract_title_summer_internships():
    chunk = "MEM-080-26\nSummer internships in Rep. Angie Craig\u2019s office will be held in-person in the Washington, D.C. office."
    title = _extract_title(chunk)
    assert title is not None
    assert "internship" in title.lower()


def test_extract_title_accepting_internship():
    chunk = "The District Office of Representative Joseph Morelle, NY-25 in Rochester, NY, will be accepting applications for an in-person internship during the Summer Semester 2026."
    title = _extract_title(chunk)
    assert title is not None
    assert "internship" in title.lower()


def test_extract_title_provides_internship():
    chunk = "The Office of Congresswoman Eleanor Holmes Norton provides seasonal internship opportunities to undergraduate and graduate students."
    title = _extract_title(chunk)
    assert title is not None
    assert "internship" in title.lower()


def test_extract_title_internship_fallback():
    """Anonymous listing where internships are mentioned but no action verb pattern matches."""
    chunk = "MEM-069-26\nIn the Washington, D.C. office, internships run throughout the year based on the semester calendar."
    title = _extract_title(chunk)
    assert title is not None
    assert "internship" in title.lower()


def test_heading_internship_opportunity():
    """'Internship Opportunity: Office of ...' heading format."""
    chunk = "MEM-052-26\nInternship Opportunity: Office of the Representative Joseph D. Morelle Rochester, NY"
    assert _extract_title_from_heading(chunk) == "Internship Opportunity"


def test_parse_listing_internship_accepting():
    """Full parse of an internship listing using 'is accepting' phrasing (actual PDF text)."""
    chunk = """MEM-048-26
The office of Congressman Juan Ciscomani (AZ-06) is accepting applications for Summer
2026 paid internships in our Washington D.C. Office.
Ideal candidates are motivated, detail-oriented, and possess a strong work ethic."""

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-048-26"
    assert result["organization"] == "Rep. Juan Ciscomani"
    assert "intern" in result["title"].lower()


def test_parse_listing_internship_possessive():
    """Full parse of internship with possessive Rep. Name\u2019s office (actual PDF text)."""
    chunk = "MEM-080-26\nSummer internships in Rep. Angie Craig\u2019s office will be held in-person in the Washington,\nD.C. office. The D.C. internship will run approximately from May 26th, 2026, through Early\nAugust, with some room for flexibility.\nLocation: Washington, D.C."

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-080-26"
    assert result["organization"] == "Rep. Angie Craig"
    assert "internship" in result["title"].lower()


def test_parse_listing_internship_seeks_interns():
    """Full parse of internship with 'seeks interns' phrasing."""
    chunk = """MEM-032-26
Congressman Mike Levin (CA-49) seeks press and legislative interns for his Washington,
D.C., office for the Summer 2026 term.
Location: Washington, D.C."""

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-032-26"
    assert result["organization"] == "Rep. Mike Levin"
    assert "intern" in result["title"].lower()


def test_parse_listing_committee_internship():
    """Committee staff internship listing (actual PDF text)."""
    chunk = "MEM-057-26\nThe Democratic Staff of the House Committee on Veterans\u2019 Affairs seeks a press/digital\nintern for the Summer 2026 semester. Responsibilities include, but are not limited to:\n\u2022 Compiling and distributing morning press clips,"

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-057-26"
    assert "Committee on Veterans" in result["organization"]
    assert "intern" in result["title"].lower()


def test_parse_listing_provides_internship():
    """Listing using 'provides internship opportunities' phrasing (actual PDF text)."""
    chunk = "MEM-077-26\nThe Office of Congresswoman Eleanor Holmes Norton provides seasonal internship\nopportunities to undergraduate and graduate students interested in gaining congressional\nwork experience in her Capitol Hill Office and in her District Office."

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-077-26"
    assert result["organization"] == "Rep. Eleanor Holmes Norton"
    assert "internship" in result["title"].lower()


def test_parse_listing_internship_opportunity_heading():
    """Listing with 'Internship Opportunity:' heading (actual PDF text)."""
    chunk = "MEM-052-26\nInternship Opportunity: Office of the Representative Joseph D. Morelle Rochester, NY\nThe District Office of Representative Joseph Morelle, NY-25 in Rochester, NY, will be\naccepting applications for an in-person internship during the Summer Semester 2026."

    result = _parse_listing(chunk)
    assert result is not None
    assert result["source_job_id"] == "MEM-052-26"
    assert result["organization"] == "Rep. Joseph Morelle"
    assert result["title"] == "Internship Opportunity"


# --- Qualifier stripping ---

def test_strip_comma_separated_qualifiers():
    """Comma-separated adjective lists should be stripped from titles."""
    assert _strip_leading_qualifiers(
        "organized, confident, collaborative, and experienced Legislative Director"
    ) == "Legislative Director"


def test_strip_single_qualifier():
    assert _strip_leading_qualifiers("experienced Legislative Assistant") == "Legislative Assistant"


def test_strip_no_qualifiers():
    assert _strip_leading_qualifiers("Communications Director") == "Communications Director"


def test_strip_qualifiers_preserves_compound_titles():
    """Titles like 'Digital and Communications Director' should not be mangled."""
    assert _strip_leading_qualifiers("Digital and Communications Director") == "Digital and Communications Director"


def test_extract_title_seeks_with_comma_qualifiers():
    """Full title extraction should strip comma-separated qualifiers."""
    chunk = (
        "Rep. David Scott (GA-13) seeks an organized, confident, collaborative, "
        "and experienced Legislative Director for the Washington, DC office."
    )
    assert _extract_title(chunk) == "Legislative Director"
