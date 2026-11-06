"""Look up the member of Congress (and party) behind a job's employer name.

Sources spell member offices many ways: "Senator Christopher A. Coons",
"Senator Chris Coons", "Rep. Emanuel Cleaver, II", "Senator Richard Blumenthal,
Senate Judiciary Committee". Rather than listing every spelling, names are
normalized (accents, middle initials, suffixes, nicknames) and matched on
chamber + last name, then first name when a last name is shared.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.data.member_data import MEMBERS


@dataclass(frozen=True)
class Member:
    id: str
    chamber: str  # "senate" or "house"
    name: str  # canonical employer name, e.g. "Senator Andy Kim", "Rep. Norma J. Torres"
    party: str  # "D", "R" or "I"
    state: str
    committees: tuple[str, ...]


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Common English diminutives, used only to pick between members who share a
# chamber and last name. Each maps to the formal names it can stand for.
_NICKNAMES: dict[str, set[str]] = {
    "andy": {"andrew"}, "bernie": {"bernard"}, "bill": {"william"}, "billy": {"william"},
    "bob": {"robert"}, "bobby": {"robert"}, "chuck": {"charles"}, "dan": {"daniel"},
    "dave": {"david"}, "dick": {"richard"}, "don": {"donald"}, "ed": {"edward"},
    "jim": {"james"}, "jimmy": {"james"}, "joe": {"joseph"}, "jon": {"jonathan"},
    "ken": {"kenneth"}, "liz": {"elizabeth"}, "maggie": {"margaret"}, "matt": {"matthew"},
    "mike": {"michael"}, "nick": {"nicholas"}, "pat": {"patrick", "patricia"},
    "rick": {"richard", "eric"}, "rob": {"robert"}, "ron": {"ronald"}, "sam": {"samuel"},
    "steve": {"stephen", "steven"}, "ted": {"edward", "theodore"}, "tim": {"timothy"},
    "tom": {"thomas"}, "tony": {"anthony"}, "chris": {"christopher"}, "greg": {"gregory"},
    "hank": {"henry"}, "jeff": {"jeffrey"}, "jerry": {"gerald"}, "kathy": {"kathleen"},
    "chuy": {"jesus"}, "buddy": {"earl"},
}

_CHAMBER_PREFIXES = (
    ("senator ", "senate"),
    ("sen. ", "senate"),
    ("u.s. senator ", "senate"),
    ("us senator ", "senate"),
    ("rep. ", "house"),
    ("rep ", "house"),
    ("representative ", "house"),
    ("congresswoman ", "house"),
    ("congressman ", "house"),
    ("delegate ", "house"),
    ("resident commissioner ", "house"),
)


def _fold(text: str) -> str:
    """Lowercase, strip accents and quotes/periods, keep letters, spaces and hyphens."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("’", "'")
    text = re.sub(r"[\"'.]", "", text)
    text = re.sub(r"[^a-z\- ]", " ", text)
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return [t for t in _fold(text).split() if t not in _SUFFIXES]


def _strip_chamber(name: str) -> tuple[str | None, str]:
    lowered = name.strip().lower()
    if lowered.startswith("office of "):
        name = name.strip()[len("office of "):]
        lowered = name.lower()
    for prefix, chamber in _CHAMBER_PREFIXES:
        if lowered.startswith(prefix):
            return chamber, name.strip()[len(prefix):]
    return None, name


def _display_name(m: dict) -> str:
    full = re.sub(r'\s*"[^"]*"', "", m["official_full"])  # drop quoted nickname
    full = re.sub(r",?\s+(Jr\.?|Sr\.?|II|III|IV)$", "", full)  # drop suffix
    prefix = "Senator " if m["chamber"] == "senate" else "Rep. "
    return prefix + full


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, Member], dict]:
    """Return (canonical name -> Member, (chamber, last-name tokens) -> candidates)."""
    by_name: dict[str, Member] = {}
    by_last: dict[tuple[str, tuple[str, ...]], list[tuple[Member, tuple[frozenset, ...]]]] = {}
    for m in MEMBERS:
        member = Member(
            id=m["id"],
            chamber=m["chamber"],
            name=_display_name(m),
            party=m["party"],
            state=m["state"],
            committees=tuple(m["committees"]),
        )
        by_name[member.name] = member

        # Names the member goes by first (legal first, nickname, the first
        # full word of the official name: "Gregory" for "W. Gregory Steube"),
        # and middle names, used only to tell apart members who share a name.
        firsts = {t for t in _tokens(m["first"]) if len(t) > 1}
        if m.get("nickname"):
            firsts |= set(_tokens(m["nickname"]))
        full_tokens = _tokens(m["official_full"])
        firsts |= {t for t in full_tokens[:1] if len(t) > 1}
        if len(full_tokens) > 1 and len(full_tokens[0]) == 1:
            firsts.add(full_tokens[1])
        middles = set(_tokens(m["middle"])) if m.get("middle") else set()
        legal_first = set(_tokens(m["first"]))
        given = (frozenset(firsts), frozenset(firsts | legal_first), frozenset(middles | legal_first))

        # The legal last name and the one in official_full can differ
        # ("Hernández Rivera" vs "Pablo José Hernández").
        lasts = {tuple(_tokens(m["last"]))}
        for tokens in (_tokens(m["last"]), full_tokens):
            if tokens:
                lasts.add((tokens[-1],))
        for last in lasts:
            by_last.setdefault((member.chamber, last), []).append((member, given))
    return by_name, by_last


def _same_name(token: str, names: frozenset) -> bool:
    if token in names:
        return True
    if any(n.startswith(token) or token.startswith(n) for n in names if len(n) > 2 and len(token) > 2):
        return True  # Chris / Christopher
    return bool(_NICKNAMES.get(token, set()) & names)


def _pick(candidates: list[tuple[Member, tuple[frozenset, ...]]], given: list[str]) -> Member | None:
    """Pick the member a name's given names (everything before the last name) mean.

    The first full given name must be a name the member goes by first; a middle
    initial never stands in for it ("Susan M. Collins" is not Mike Collins).
    Initials only break a tie between members who both fit.
    """
    full = [t for t in given if len(t) > 1]
    initials = [t for t in given if len(t) == 1]
    if full:
        matches = [(c, g) for c, g in candidates if _same_name(full[0], g[0])]
    else:
        # "M. Collins": only initials, the first one is the first name's.
        matches = [(c, g) for c, g in candidates if any(n.startswith(initials[0]) for n in g[1])]
        initials = initials[1:]
    if len(matches) > 1 and initials:
        matches = [
            (c, g) for c, g in matches
            if all(any(n.startswith(i) for n in g[1] | g[2]) for i in initials)
        ]
    # No fit, or still more than one: a miss, not a guess.
    return matches[0][0] if len(matches) == 1 else None


@lru_cache(maxsize=4096)
def find_member(source_organization: str | None) -> Member | None:
    """Return the member whose office posted the job, or None if it isn't one."""
    if not source_organization:
        return None
    by_name, by_last = _index()
    if source_organization in by_name:
        return by_name[source_organization]

    chamber, rest = _strip_chamber(source_organization)
    if chamber is None:
        return None
    # Suffixes go first, wherever a source put them: "Emanuel Cleaver, II",
    # "Emanuel, II Cleaver" (Domewatch's "Cleaver, Emanuel, II - Rep.").
    rest = re.sub(r",?\s*\b(?:Jr|Sr|II|III|IV)\b\.?,?", " ", rest)
    # "Richard Blumenthal, Senate Judiciary Committee" -> "Richard Blumenthal"
    rest = rest.split(",")[0]
    rest = re.sub(r"\([^)]*\)", " ", rest)  # "(CA-10)"
    tokens = _tokens(rest)
    if len(tokens) < 2:
        return None

    # Try the longest last name first, so "Cortez Masto" wins over "Masto".
    for size in (3, 2, 1):
        if len(tokens) <= size:
            continue
        last = tuple(tokens[-size:])
        candidates = by_last.get((chamber, last), [])
        unique = {c.id: (c, g) for c, g in candidates}
        if not unique:
            continue
        # A first name that fits nobody (e.g. "Rep. Andy Kim" when only Young
        # Kim is in the House) is a miss, not a guess.
        return _pick(list(unique.values()), tokens[:-size])
    return None


_DEMOCRATIC = re.compile(r"\bdemocrat(?:s|ic)?\b", re.IGNORECASE)
_REPUBLICAN = re.compile(r"\brepublicans?\b", re.IGNORECASE)

# Sources that only carry one party's offices.
_SOURCE_PARTY = {"house-dems-resumebank": "D"}


def employer_party(source_system: str | None, source_organization: str | None) -> str | None:
    """Party of the office that posted a job, or None if it's nonpartisan or unknown.

    Uses, in order: the member of Congress named in the employer, the words
    "Democrats"/"Republicans" in a committee staff name ("Finance - Democrats"),
    and sources that only list one party's jobs (the House Democrats' resume bank).
    """
    member = find_member(source_organization)
    if member:
        return member.party
    name = source_organization or ""
    dem = bool(_DEMOCRATIC.search(name))
    rep = bool(_REPUBLICAN.search(name))
    if dem != rep:
        return "D" if dem else "R"
    return _SOURCE_PARTY.get(source_system or "")
