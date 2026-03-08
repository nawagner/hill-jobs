import re

TITLE_RULES: list[tuple[str, list[str]]] = [
    ("legal", [r"\bcounsel\b", r"\battorney\b", r"\blegal\b", r"\blaw\b", r"\bjudicial\b"]),
    ("communications", [r"\bcommunicat", r"\bpress\b", r"\bwriter\b", r"\beditor\b", r"\bmedia\b", r"\bpublic affairs\b"]),
    ("security", [r"\bsecurity\b", r"\bpolice\b", r"\bthreat\b", r"\bprotect", r"\bcyber"]),
    ("policy", [r"\bpolicy\b", r"\blegislative\b", r"\bresearch specialist\b", r"\banalyst\b"]),
    ("technology", [r"\bengineer", r"\bdeveloper\b", r"\bsystems?\b", r"\bIT\b", r"\bdata\b", r"\bsoftware\b"]),
]

DESCRIPTION_RULES: list[tuple[str, list[str]]] = [
    ("legal", [r"\blegal\b", r"\bcounsel\b", r"\battorney\b"]),
    ("communications", [r"\bcommunications?\b", r"\bmedia relations?\b", r"\bpress\b"]),
    ("security", [r"\bsecurity\b", r"\blaw enforcement\b", r"\bthreat\b"]),
    ("policy", [r"\bpolicy\b", r"\blegislative\b", r"\blegislation\b"]),
    ("technology", [r"\bsoftware\b", r"\bengineering\b", r"\btechnical\b", r"\bcybersecurity\b"]),
]

ORG_DEFAULTS: dict[str, str] = {
    "U.S. Capitol Police": "security",
}


def classify_job(
    title: str,
    description_text: str,
    source_organization: str,
) -> str:
    # Check title rules first — they are the strongest signal
    for role_kind, patterns in TITLE_RULES:
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return role_kind

    # Check description keywords as fallback
    for role_kind, patterns in DESCRIPTION_RULES:
        for pattern in patterns:
            if re.search(pattern, description_text, re.IGNORECASE):
                return role_kind

    # Org-level default when no keywords match at all
    if source_organization in ORG_DEFAULTS:
        return ORG_DEFAULTS[source_organization]

    return "operations"
