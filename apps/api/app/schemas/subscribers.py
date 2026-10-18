from pydantic import BaseModel, EmailStr, field_validator

ALLOWED_FILTER_KEYS = {
    "q", "role_kind", "organization", "party", "state", "committee", "salary_min", "freshness",
}

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
    return {k: v for k, v in v.items() if v}


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
