from pydantic import BaseModel, EmailStr, field_validator

from app.data.members import find_member
from app.data.organizations import TOP_ORGANIZATIONS

ALLOWED_FILTER_KEYS = {
    "q", "role_kind", "organization", "member", "party", "state", "committee", "salary_min",
    "freshness",
}


def upgrade_legacy_filters(filters: dict | None) -> dict:
    """Move a member saved as "organization" (before members had their own filter) to "member".

    Other single offices saved as "organization" ("Clerk of the House") stay as
    they are: the search still matches them exactly, and widening them to a
    whole chamber would change what the subscriber gets.
    """
    filters = dict(filters or {})
    organization = filters.get("organization")
    if not organization or organization in TOP_ORGANIZATIONS:
        return filters
    member = find_member(organization)
    if member:
        filters.pop("organization")
        filters.setdefault("member", member.name)
    return filters
    member = find_member(organization)
    if member and not filters.get("member"):
        filters["member"] = member.name
    committee = staff_committee(None, organization)
    if committee and not filters.get("committee"):
        filters["committee"] = committee
    top = employer_organization(None, organization)
    if member or top:
        filters.pop("organization")
        if top and not member:
            filters["organization"] = top
    return filters

# The "Date posted" choices the alert forms offer. The site's search also has
# "older_30", which makes no sense for alerts about new jobs.
FRESHNESS_VALUES = {"7", "30"}


def _clean_filters(v: dict) -> dict:
    unknown = set(v.keys()) - ALLOWED_FILTER_KEYS
    if unknown:
        raise ValueError(f"Unknown filter keys: {unknown}")
    freshness = v.get("freshness")
    if freshness and (not isinstance(freshness, str) or freshness not in FRESHNESS_VALUES):
        raise ValueError(f"freshness must be one of {sorted(FRESHNESS_VALUES)}")
    return upgrade_legacy_filters({k: val for k, val in v.items() if val})


class SubscribeRequest(BaseModel):
    email: EmailStr
    filters: dict = {}

    @field_validator("filters")
    @classmethod
    def validate_filter_keys(cls, v: dict) -> dict:
        return _clean_filters(v)


class SubscribeResponse(BaseModel):
    message: str


class PreferencesResponse(BaseModel):
    email: str
    filters: dict


class PreferencesUpdateRequest(BaseModel):
    filters: dict = {}

    @field_validator("filters")
    @classmethod
    def validate_filter_keys(cls, v: dict) -> dict:
        return _clean_filters(v)
