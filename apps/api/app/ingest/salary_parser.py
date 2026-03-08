import re
from dataclasses import dataclass


@dataclass
class ParsedSalary:
    min_value: float
    max_value: float
    period: str  # "yearly" | "hourly"


_DOLLAR = r"\$[\d,]+(?:\.\d{1,2})?"
_RANGE_SEP = r"\s*(?:-|–|—|to)\s*"
_PERIOD_YEARLY = r"(?:per\s+year|per\s+annum|annually|annual|/\s*yr|p\.?a\.?)"
_PERIOD_HOURLY = r"(?:per\s+hour|hourly|/\s*hr|p\.?h\.?)"

_RANGE_PATTERN = re.compile(
    rf"({_DOLLAR}){_RANGE_SEP}({_DOLLAR})\s*(?:({_PERIOD_YEARLY})|({_PERIOD_HOURLY}))?",
    re.IGNORECASE,
)
_SINGLE_PATTERN = re.compile(
    rf"({_DOLLAR})\s*(?:({_PERIOD_YEARLY})|({_PERIOD_HOURLY}))",
    re.IGNORECASE,
)


def _parse_dollar(s: str) -> float:
    return float(s.replace("$", "").replace(",", ""))


def _infer_period(value: float) -> str:
    return "hourly" if value < 200 else "yearly"


def parse_salary_from_text(text: str) -> ParsedSalary | None:
    if not text:
        return None

    m = _RANGE_PATTERN.search(text)
    if m:
        min_val = _parse_dollar(m.group(1))
        max_val = _parse_dollar(m.group(2))
        if m.group(3):
            period = "yearly"
        elif m.group(4):
            period = "hourly"
        else:
            period = _infer_period(min_val)
        return ParsedSalary(min_value=min_val, max_value=max_val, period=period)

    m = _SINGLE_PATTERN.search(text)
    if m:
        val = _parse_dollar(m.group(1))
        if m.group(2):
            period = "yearly"
        elif m.group(3):
            period = "hourly"
        else:
            period = _infer_period(val)
        return ParsedSalary(min_value=val, max_value=val, period=period)

    return None
