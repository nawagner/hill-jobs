import re

# Checked in order; the first match wins. Specific roles come before broad
# ones (e.g. "Counsel/Legislative Assistant" is legal, "Business Systems
# Analyst" is technology).
TITLE_RULES: list[tuple[str, list[str]]] = [
    ("legal", [
        r"\bcounsel\b", r"\battorney\b", r"\blegal\b", r"\bparalegal\b",
        r"\blaw\b(?! enforcement)", r"\bjudicial\b",
    ]),
    ("communications", [
        r"\bcommunicat", r"\bpress\b", r"\bwriter\b", r"\bspeechwriter\b", r"\beditor\b",
        r"\bmedia\b", r"\bpublic affairs\b",
        r"\bdigital (?:director|manager|assistant|strategist|content|intern)",
    ]),
    ("security", [
        r"\bsecurity\b", r"\bpolice\b", r"\bthreat\b", r"\bprotective\b", r"\bcyber",
        r"\bspecial agent\b", r"\blaw enforcement\b", r"\bemergency management\b",
    ]),
    ("technology", [
        # Case-sensitive so the word "it" in a sentence-like title doesn't match.
        r"(?-i:\bIT\b)", r"\binformation technology\b", r"\btechnology\b", r"\bsoftware\b",
        r"\bdeveloper\b", r"\bsystems?\b", r"\bdata\b", r"\bdigital services\b",
    ]),
    ("policy", [
        r"\bpolicy\b", r"\blegislative\b", r"\bresearch specialist\b", r"\banalyst\b",
        r"\beconomist\b", r"\bprofessional staff\b", r"\badvis[eo]r\b", r"\binvestigator\b",
        r"\bfellow(?:ship)?s?\b",
    ]),
]

# Office and facilities roles. Checked after TITLE_RULES ("Press Intern" is
# communications) but before the description, which for these jobs mentions
# press, legislation or security clearances without being about them.
OPERATIONS_TITLE_PATTERNS: list[str] = [
    r"\bintern(?:s|ships?)?\b", r"\bstaff assistant\b", r"\bschedul", r"\bcasework",
    r"\bconstituent\b", r"\bfield (?:representative|assistant|director)\b",
    r"\bdistrict (?:director|representative)\b", r"\bchief of staff\b", r"\boffice manager\b",
    r"\baide\b", r"\badministrative\b", r"\bhuman resources\b", r"\blibrar", r"\btechnician\b",
    r"\bmechanic\b", r"\belectrician\b", r"\bengineer\b", r"\bfacilit",
]

# Fallback for titles that say little ("Senior Advisor", "Investigator").
# Only phrases that describe the job itself: requirements like "strong
# communication skills" or "security clearance" appear in every kind of posting.
DESCRIPTION_RULES: list[tuple[str, list[str]]] = [
    ("legal", [r"\battorneys?\b", r"\blaw clerks?\b", r"\blaw school\b"]),
    ("communications", [r"\bpress releases?\b", r"\bmedia relations\b", r"\bpress secretary\b"]),
    ("security", [r"\blaw enforcement officers?\b"]),
    ("technology", [r"\bsoftware\b", r"\bcybersecurity\b"]),
    ("policy", [r"\blegislative policy\b", r"\bpolicy (?:development|issues|research|analysis)\b",
                r"\bdraft(?:ing)? legislation\b"]),
]

ORG_DEFAULTS: dict[str, str] = {
    "U.S. Capitol Police": "security",
}


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def classify_job(
    title: str,
    description_text: str,
    source_organization: str,
) -> str:
    # Title rules are the strongest signal
    for role_kind, patterns in TITLE_RULES:
        if _matches(patterns, title):
            return role_kind

    # Every Capitol Police job is a security job, whatever its title
    if source_organization in ORG_DEFAULTS:
        return ORG_DEFAULTS[source_organization]

    if _matches(OPERATIONS_TITLE_PATTERNS, title):
        return "operations"

    # Check description phrases as fallback
    for role_kind, patterns in DESCRIPTION_RULES:
        if _matches(patterns, description_text):
            return role_kind

    return "operations"
