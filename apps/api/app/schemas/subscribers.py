from pydantic import BaseModel, EmailStr, field_validator

ALLOWED_FILTER_KEYS = {"q", "role_kind", "organization", "party", "state", "committee", "salary_min"}


class SubscribeRequest(BaseModel):
    email: EmailStr
    filters: dict = {}

    @field_validator("filters")
    @classmethod
    def validate_filter_keys(cls, v: dict) -> dict:
        unknown = set(v.keys()) - ALLOWED_FILTER_KEYS
        if unknown:
            raise ValueError(f"Unknown filter keys: {unknown}")
        return {k: v for k, v in v.items() if v}


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
        unknown = set(v.keys()) - ALLOWED_FILTER_KEYS
        if unknown:
            raise ValueError(f"Unknown filter keys: {unknown}")
        return {k: v for k, v in v.items() if v}
