import json
from pathlib import Path

import pytest

from app.ingest.hvaps_pdf_parser import (
    _extract_organization,
    _extract_title,
    _extract_title_from_heading,
    _extract_title_from_lines,
    _extract_location,
    _extract_salary_text,
    _normalize_org_name,
    _parse_listing,
    _split_into_listings,
    _strip_leading_qualifiers,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "hvaps"


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
    assert _extract_title(chunk) == "Press and Legislative Interns"


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


# --- Titles from real listings that used to get fragments or headers ---
# Opening lines of listings from the 2026 bulletins. Each one used to be titled
# with a section header ("SUMMARY:"), "Unknown Position" or a sentence fragment.

@pytest.mark.parametrize(
    "chunk, expected",
    [
    # section header "SUMMARY:"
    pytest.param(
        (
            "MEM-189-26\n"
            "SUMMARY:\n"
            "Congresswoman Valerie P. Foushee (NC-04) seeks an organized, motivated, and service-\n"
            "oriented Staff Assistant to join her Durham office. This entry-level, full-time, on-site"
        ),
        "Staff Assistant",
        id="MEM-189-26",
    ),
    # "The <Title> serves" (was "Requirements:")
    pytest.param(
        (
            "MEM-200-26\n"
            "The Legislative Director serves as the Member’s chief policy advisor and leader of the\n"
            "office’s Legislative Team. The Legislative Director’s primary responsibilities are to manage\n"
            "the Legislative Team, advise the Member on legislation, and direct the development of\n"
            "policy positions and legislative initiatives."
        ),
        "Legislative Director",
        id="MEM-200-26",
    ),
    # "position of <Title>" (was "POSITION OVERVIEW")
    pytest.param(
        (
            "MEM-179-26\n"
            "POSITION OVERVIEW\n"
            "Representative Raul Ruiz, M.D. is a Senior Member of the Energy and Commerce\n"
            "Committee and former Chair of the Congressional Hispanic Caucus. Interested and\n"
            "qualified candidates for the position of Executive Assistant and Scheduler in his"
        ),
        "Executive Assistant and Scheduler",
        id="MEM-179-26",
    ),
    # "serve as <Title>" (was "self- starter")
    pytest.param(
        (
            "MEM-226-26\n"
            "Congresswoman Debbie Wasserman Schultz seeks an organized and motivated self-\n"
            "starter to serve as Scheduler in her fast-paced Washington, D.C. office. Candidates are"
        ),
        "Scheduler",
        id="MEM-226-26",
    ),
    # "for a paid Spring 2027 internship position" (was "Unknown Position")
    pytest.param(
        (
            "MEM-293-26\n"
            "The office of Congresswoman Dina Titus (NV-01) seeks highly motivated candidates for a\n"
            "paid Spring 2027 internship position in our Las Vegas office."
        ),
        "Spring 2027 Internship",
        id="MEM-293-26",
    ),
    # "seeks ... interns" (was "Unknown Position")
    pytest.param(
        (
            "MEM-118-26\n"
            "The Office of U.S. Representative Pramila Jayapal (WA-07) seeks highly motivated,\n"
            "organized, and dedicated interns to serve for the Fall of 2026 in the Representative’s"
        ),
        "Fall 2026 Interns",
        id="MEM-118-26",
    ),
    # "join as a fall intern 2026" (was "All applicants can submit ...")
    pytest.param(
        (
            "MEM-223-26\n"
            "Congresswoman Nancy Mace's District Office (Daniel Island) is seeking students with a\n"
            "strong interest in political science, public service, and communication to join as a fall\n"
            "intern 2026.\n"
            "The internship can be full-time or part-time and will run from mid-August through\n"
            "November.\n"
            "All applicants can submit their information using this link:"
        ),
        "Fall 2026 Intern",
        id="MEM-223-26",
    ),
    # "opening for an <Title>" (was "Congressman Ro Khanna’s office ...")
    pytest.param(
        (
            "MEM-196-26\n"
            "Congressman Ro Khanna’s office in Washington, DC has an immediate opening for an\n"
            "Operations Assistant help manage office operations, help drive and staff the member in"
        ),
        "Operations Assistant",
        id="MEM-196-26",
    ),
    # "The <Title> supports" (was "communicate and liaise ...")
    pytest.param(
        (
            "MEM-238-26\n"
            "The Communications and Correspondence Assistant supports district-based efforts to\n"
            "communicate and liaise with stakeholders and key audiences in person and across\n"
            "platforms. The Communications and Correspondence Assistant manages the"
        ),
        "Communications and Correspondence Assistant",
        id="MEM-238-26",
    ),
    # "A <Title> for HOLC assists" (was "debated in Congress, ...")
    pytest.param(
        (
            "MEM-281-26\n"
            "The Office of the Legislative Counsel of the U.S. House of Representatives (HOLC)\n"
            "transforms the policy goals of Members and committees of the House into clear, concise,\n"
            "and legally effective legislative language to help ensure that the legislation introduced and\n"
            "debated in Congress, and the enacted laws of the United States, clearly express\n"
            "congressional intent. HOLC carries out this mission by providing expert legislative drafting\n"
            "services and related legal services on a non-partisan, impartial, and confidential basis.\n"
            "Position Description:\n"
            "A Paralegal for HOLC assists the attorneys and teams of the Office to meet the legislative"
        ),
        "Paralegal",
        id="MEM-281-26",
    ),
    # "organized and detail-oriented <Title>"
    pytest.param(
        (
            "MEM-227-26\n"
            "Rep. Dina Titus seeks an organized and detail-oriented Staff Assistant for her Las Vegas\n"
            "office. Primary responsibilities include managing the front office, answering and logging"
        ),
        "Staff Assistant",
        id="MEM-227-26",
    ),
    # "an internship during the 2026 Fall term" (was "an internship")
    pytest.param(
        (
            "MEM-199-26\n"
            "The Washington, D.C. Office of Representative Joe Morelle is now accepting applications for\n"
            "an internship during the 2026 Fall term. Applicants must be based in Washington, D.C. for"
        ),
        "Fall 2026 Internship",
        id="MEM-199-26",
    ),
    # "Fall 2026 paid internships" (was "paid internships")
    pytest.param(
        (
            "MEM-221-26\n"
            "The office of Congressman Juan Ciscomani (AZ-06) is accepting applications for Fall\n"
            "2026 paid internships in our Washington D.C. Office."
        ),
        "Fall 2026 Internships",
        id="MEM-221-26",
    ),
    # "seeks press intern" (was "communications team")
    pytest.param(
        (
            "MEM-233-26\n"
            "Congressman Mike Levin (CA-49) seeks press intern for his Washington, D.C., office for\n"
            "the Fall 2026 term.\n"
            "This internship provide an opportunity for undergraduate students, graduate students, and\n"
            "recent graduates to learn more about the workings of a Congressional office, the legislative"
        ),
        "Fall 2026 Press Intern",
        id="MEM-233-26",
    ),
    # "POSITION OPENING: DISTRICT DIRECTOR"
    pytest.param(
        (
            "MEM-216-26\n"
            "POSITION OPENING: DISTRICT DIRECTOR\n"
            "District Office | Reports to the Chief of Staff | Full-Time, Exempt\n"
            "About the Office\n"
            "A New Jersey Congressman is seeking a motivated District Director to run his multiple"
        ),
        "District Director",
        id="MEM-216-26",
    ),
    # "JOB POSTING: DISTRICT PRESS/DIGITAL ASSISTANT"
    pytest.param(
        (
            "MEM-182-26\n"
            "JOB POSTING: DISTRICT PRESS/DIGITAL ASSISTANT\n"
            "Congresswoman Luz Rivas (CA-29) is seeking a motivated, creative, and"
        ),
        "District Press/Digital Assistant",
        id="MEM-182-26",
    ),
    # "COMMUNICATIONS INTERNSHIP"
    pytest.param(
        (
            "MEM-231-26\n"
            "COMMUNICATIONS INTERNSHIP\n"
            "The DC office of Representative Marilyn Strickland (WA-10) is currently accepting"
        ),
        "Communications Internship",
        id="MEM-231-26",
    ),
    # "Seeks <Title>." with no article (was "fellow")
    pytest.param(
        (
            "MEM-186-26\n"
            "Senior Republican Member of House Financial Services Committee Seeks\n"
            "Legislative/Financial Services Fellow.\n"
            "A senior Republican member serving on the House Financial Services Committee is"
        ),
        "Legislative/Financial Services Fellow",
        id="MEM-186-26",
    ),
    # "<Title> with excellent writing skills"
    pytest.param(
        (
            "MEM-214-26\n"
            "Western Conservative Member seeks an energetic and proactive Press\n"
            "Assistant/Secretary with excellent writing skills to serve in the Member's Washington,"
        ),
        "Press Assistant/Secretary",
        id="MEM-214-26",
    ),
    # "accepting applicants for a paid Fall Legislative Internship"
    pytest.param(
        (
            "MEM-241-26\n"
            "The DC office of Representative Marilyn Strickland (WA-10) is currently\n"
            "accepting applicants for a paid Fall Legislative Internship with a start date\n"
            "of Monday, August 24, 2026, until December 2026, with the potential to"
        ),
        "Fall Legislative Internship",
        id="MEM-241-26",
    ),
    # "is seeking interns" (was "The Washington, D.C. office of ...")
    pytest.param(
        (
            "MEM-201-26\n"
            "The Washington, D.C. office of Congresswoman Gwen Moore (WI-04) is seeking\n"
            "interns for the upcoming Fall 2026 term."
        ),
        "Fall 2026 Interns",
        id="MEM-201-26",
    ),
    # "seeks legislative and communications interns"
    pytest.param(
        (
            "MEM-164-26\n"
            "The Office of U.S. Representative Mark Takano (CA-39) seeks legislative and\n"
            "communications interns to serve for the Fall of 2026 in the Representative’s Washington,"
        ),
        "Fall 2026 Legislative and Communications Interns",
        id="MEM-164-26",
    ),
    # "the <Title> will support" (was "recommendations, and ...")
    pytest.param(
        (
            "MEM-193-26\n"
            "Under the supervision of the office’s Legislative Counsel, the Law Clerk will support the\n"
            "Congresswoman’s legislative and oversight work by conducting legal and policy research,\n"
            "preparing for and staffing Judiciary Committee hearings and markups, developing vote"
        ),
        "Law Clerk",
        id="MEM-193-26",
    ),
    # "has an opening for a <Title>" (was "answering telephones; ...")
    pytest.param(
        (
            "MEM-207-26\n"
            "The Committee on Ethics has an opening for a Staff Assistant. Duties include assisting the\n"
            "technology needs of Committee staff; editing and maintaining the Committee’s website;\n"
            "answering telephones; assisting with the tracking and processing of committee"
        ),
        "Staff Assistant",
        id="MEM-207-26",
    ),
    # "part-time or full-time, energetic interns"
    pytest.param(
        (
            "MEM-183-26\n"
            "The Democratic Staff of the Committee on Rules is seeking part-time or full-time, energetic\n"
            "interns for the fall (September/October – mid-December). Our interns work closely with"
        ),
        "Interns",
        id="MEM-183-26",
    ),
    # "offers paid internships" (was "The Office of Rep. Josh Harder offers ...")
    pytest.param(
        (
            "MEM-198-26\n"
            "The Office of Rep. Josh Harder offers paid internships in our Washington office. Our\n"
            "hands-on internship program offers highly motivated undergraduates, graduate students,"
        ),
        "Internships",
        id="MEM-198-26",
    ),
    # "a short-term internship opportunity"
    pytest.param(
        (
            "MEM-289-26\n"
            "The Committee on House Administration (Democratic Staff) is now accepting applications\n"
            "for a short-term internship opportunity during the late fall 2026 term. Applicants should"
        ),
        "Fall 2026 Internship",
        id="MEM-289-26",
    ),
    ],
)
def test_parse_listing_title_from_real_listing(chunk, expected):
    assert _parse_listing(chunk)["title"] == expected


def test_titles_for_listings_open_on_2026_10_12():
    """Every HVAPS listing open on 2026-10-12, so parser changes show up as title diffs.

    `text` is the first 1500 characters of each listing, which is all that title
    extraction reads. When a change improves a title, update `expected_title`.
    """
    listings = json.loads((FIXTURES / "listings_2026-10-12.json").read_text())
    titles = {item["source_job_id"]: _parse_listing(item["text"])["title"] for item in listings}
    assert titles == {item["source_job_id"]: item["expected_title"] for item in listings}


@pytest.mark.parametrize(
    "header", ["SUMMARY:", "POSITION OVERVIEW", "Requirements:", "About the Office"]
)
def test_heading_skips_section_header(header):
    chunk = f"MEM-001-26\n{header}\nThe office seeks a Staff Assistant."
    assert _extract_title_from_heading(chunk) is None


def test_heading_strips_posting_prefix_and_all_caps():
    chunk = "MEM-216-26\nPOSITION OPENING: DISTRICT DIRECTOR\nDistrict Office | Reports to the Chief of Staff"
    assert _extract_title_from_heading(chunk) == "District Director"


def test_extract_title_rejects_lowercase_fragment():
    """A lowercase phrase that doesn't name a job isn't a title."""
    chunk = "MEM-001-26\nThe office seeks an organized and motivated self-\nstarter to join our team."
    assert _extract_title(chunk) is None


def test_extract_title_skips_member_possessive():
    chunk = "MEM-001-26\nThe office seeks someone to serve as the Member\u2019s chief policy advisor."
    assert _extract_title(chunk) is None


def test_extract_title_keeps_parenthesized_acronym():
    chunk = (
        "MEM-291-26\nThe Democratic staff of the House Natural Resources Committee (HNRC) Subcommittee\n"
        "on Energy and Mineral Resources seeks a Professional Staff Member (PSM) or Counsel to\n"
        "play a lead role in planning, coordinating, and executing the legislative and oversight"
    )
    assert _extract_title(chunk) == "Professional Staff Member (PSM) or Counsel"


def test_lines_fallback_skips_fragments_and_office_names():
    chunk = (
        "MEM-001-26\n"
        "communicate and liaise with stakeholders and key audiences in person and across\n"
        "All applicants can submit their information using this link:\n"
        "Internships | Representative Nancy Mace\n"
        "Washington, D.C. Internship Responsibilities"
    )
    assert _extract_title_from_lines(chunk, "MEM-001-26") is None
