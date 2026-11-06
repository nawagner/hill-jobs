"""Group job employers into a few top-level legislative branch organizations.

Sources name employers at very different levels: a member's office, a committee's
minority staff, a support office (Clerk of the House) or a whole agency. The
Organization filter uses only the top level; members and committees have their
own filters, and staff_committee() ties committee staff jobs to the Committee filter.
"""

import re
import unicodedata

from app.data.member_committees import COMMITTEES
from app.data.members import find_member

SENATE = "U.S. Senate"
HOUSE = "U.S. House of Representatives"
COMMISSIONS = "Congressional Commissions"

# In the order the Organization filter lists them.
TOP_ORGANIZATIONS: tuple[str, ...] = (
    SENATE,
    HOUSE,
    "Architect of the Capitol",
    "Congressional Budget Office",
    "Government Accountability Office",
    "Government Publishing Office",
    "Library of Congress",
    "U.S. Capitol Police",
    COMMISSIONS,
)

_SOURCE_ORGANIZATIONS: dict[str, str] = {
    "senate-webscribble": SENATE,
    "house-dems-resumebank": HOUSE,
    "house-hvaps": HOUSE,
    "house-bulletin": HOUSE,
    "csod-house-cao": HOUSE,
    "csod-house-clerk": HOUSE,
    "csod-house-saa": HOUSE,
    "csod-house-green-gold": HOUSE,
    "aoc-usajobs": "Architect of the Capitol",
    "cbo-bizmerlin": "Congressional Budget Office",
    "gao-usajobs": "Government Accountability Office",
    "gpo-usajobs": "Government Publishing Office",
    "loc-careers": "Library of Congress",
    "csod-uscp": "U.S. Capitol Police",
}

# Employer names that identify an organization whatever the source (the
# Senate Employment Office also posts for commissions; manual entries have no
# source of their own).
_NAME_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\barchitect of the capitol\b", re.I), "Architect of the Capitol"),
    (re.compile(r"\bcongressional budget office\b", re.I), "Congressional Budget Office"),
    (re.compile(r"\bgovernment accountability office\b", re.I), "Government Accountability Office"),
    (re.compile(r"\bgovernment publishing office\b", re.I), "Government Publishing Office"),
    (re.compile(r"\blibrary of congress\b", re.I), "Library of Congress"),
    (re.compile(r"\bcapitol police\b", re.I), "U.S. Capitol Police"),
    (re.compile(r"\bsenat(e|or)\b", re.I), SENATE),
    (re.compile(r"\bhouse\b|\bcongress(wo)?man\b|^rep\.", re.I), HOUSE),
)

_CHAMBER_ORGANIZATIONS = {"senate": SENATE, "house": HOUSE}


def employer_organization(source_system: str | None, source_organization: str | None) -> str | None:
    """The top-level organization a job belongs to, e.g. "U.S. Senate"."""
    name = source_organization or ""
    member = find_member(name)
    if member:
        return _CHAMBER_ORGANIZATIONS[member.chamber]
    if re.search(r"\bcommission\b", name, re.I):
        # Commissions are posted through the Senate Employment Office but
        # aren't Senate offices. A committee named "Commission" (the Helsinki
        # Commission) is a joint committee and lands here too.
        return COMMISSIONS
    if source_system in _SOURCE_ORGANIZATIONS:
        return _SOURCE_ORGANIZATIONS[source_system]
    for pattern, organization in _NAME_PATTERNS:
        if pattern.search(name):
            return organization
    return None


# Words that say whose staff it is, not which committee.
_STAFF_WORDS = {
    "the", "of", "on", "and", "for", "committee", "committees", "staff", "house",
    "senate", "us", "united", "states", "democrats", "democratic", "republicans",
    "republican", "majority", "minority", "nondesignated", "non", "designated",
    "select", "special", "permanent",
}


def _committee_words(name: str) -> frozenset[str]:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"['’]", "", text).replace("&", " and ")
    words = re.findall(r"[a-z]+", text)
    return frozenset(w for w in words if w not in _STAFF_WORDS)


def _build_committee_index() -> dict[tuple[str, frozenset[str]], str]:
    index: dict[tuple[str, frozenset[str]], str] = {}
    for cid, meta in COMMITTEES.items():
        if meta["parent"] is None:
            index[(meta["chamber"], _committee_words(meta["name"]))] = cid
    return index


_COMMITTEE_INDEX = _build_committee_index()
_CHAMBER_SOURCES = {SENATE: "senate", HOUSE: "house"}


def staff_committee(source_system: str | None, source_organization: str | None) -> str | None:
    """The committee whose own staff posted a job ("Finance - Democrats" -> SSFI)."""
    name = source_organization or ""
    member = find_member(name)
    if member:
        # "Senator Richard Blumenthal, Senate Judiciary Committee": staff of a
        # committee the member leads.
        if "," not in name:
            return None
        name = name.split(",", 1)[1]
        chamber = member.chamber
    else:
        chamber = _CHAMBER_SOURCES.get(employer_organization(source_system, name) or "")
    # A name that says its chamber outranks the source ("Senate Judiciary
    # Committee" is never the House Judiciary Committee).
    says_senate = bool(re.search(r"\bsenate\b", name, re.I))
    says_house = bool(re.search(r"\bhouse\b", name, re.I))
    if says_senate != says_house:
        chamber = "senate" if says_senate else "house"
    if not re.search(
        r"\bcommittee\b|\s-\s(democrats|republicans|non-?designated|majority|minority)\b",
        name,
        re.I,
    ):
        return None
    words = _committee_words(name)
    if not words:
        return None
    chambers = [chamber] if chamber else ["senate", "house", "joint"]
    matches = {_COMMITTEE_INDEX.get((c, words)) for c in chambers} - {None}
    if not matches:
        matches = {_COMMITTEE_INDEX.get(("joint", words))} - {None}
    return matches.pop() if len(matches) == 1 else None
