import re
from dataclasses import dataclass


@dataclass
class ParsedSalary:
    min_value: float
    max_value: float
    period: str  # "yearly" | "hourly"


# Dollar amount: $55,000 or $55,000.00 or $55k
_DOLLAR = r"\$[\d,]+(?:\.\d{1,2})?k?"
_RANGE_SEP = r"\s*(?:-|–|—|to)\s*"
_PERIOD_YEARLY = r"(?:per\s+year|per\s+annum|annually|annual|/\s*yr|p\.?a\.?|a\s+year)"
_PERIOD_HOURLY = r"(?:per\s+hour|hourly|/\s*hr|p\.?h\.?)"
_PERIOD_MONTHLY = r"(?:per\s+month|monthly|/\s*mo)"

# Standard range: $50,000 - $60,000 [per year]
_RANGE_PATTERN = re.compile(
    rf"({_DOLLAR}){_RANGE_SEP}({_DOLLAR})\s*(?:({_PERIOD_YEARLY})|({_PERIOD_HOURLY})|({_PERIOD_MONTHLY}))?",
    re.IGNORECASE,
)

# Abbreviated range: $60-70,000 or $60-$70,000
_ABBREV_RANGE_PATTERN = re.compile(
    r"\$(\d{2,3})(?:,\d{3})*\s*(?:-|–|—)\s*\$?(\d{2,3},\d{3}(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Single dollar amount with period word: $55,000 annually
_SINGLE_WITH_PERIOD = re.compile(
    rf"({_DOLLAR})\s*(?:({_PERIOD_YEARLY})|({_PERIOD_HOURLY})|({_PERIOD_MONTHLY}))",
    re.IGNORECASE,
)

# Salary-context single amount: "Salary: $55,000" or "starting salary is $65,000"
_SALARY_CONTEXT = re.compile(
    r"(?:salary|compensation|pay|starting\s+salary|annual\s+salary)"
    r"[^$\n]{0,30}"
    rf"({_DOLLAR})",
    re.IGNORECASE,
)


def _parse_dollar(s: str) -> float:
    s = s.replace("$", "").replace(",", "")
    if s.lower().endswith("k"):
        return float(s[:-1]) * 1000
    return float(s)


def _infer_period(value: float) -> str:
    if value < 200:
        return "hourly"
    if value < 10000:
        return "monthly"
    return "yearly"


def parse_salary_from_text(text: str) -> ParsedSalary | None:
    if not text:
        return None

    # 1. Standard range: $50,000 - $60,000
    m = _RANGE_PATTERN.search(text)
    if m:
        min_val = _parse_dollar(m.group(1))
        max_val = _parse_dollar(m.group(2))
        if m.group(3):
            period = "yearly"
        elif m.group(4):
            period = "hourly"
        elif m.group(5):
            period = "monthly"
        else:
            period = _infer_period(min_val)
        return ParsedSalary(min_value=min_val, max_value=max_val, period=period)

    # 2. Abbreviated range: $60-70,000
    m = _ABBREV_RANGE_PATTERN.search(text)
    if m:
        max_val = _parse_dollar("$" + m.group(2))
        # Infer min from abbreviated prefix + max's scale
        # e.g., "60" with max 70,000 -> 60,000
        min_prefix = int(m.group(1).replace(",", ""))
        magnitude = 10 ** (len(str(int(max_val))) - len(str(min_prefix)))
        min_val = float(min_prefix * magnitude)
        period = _infer_period(min_val)
        return ParsedSalary(min_value=min_val, max_value=max_val, period=period)

    # 3. Single amount with explicit period: $55,000 annually
    m = _SINGLE_WITH_PERIOD.search(text)
    if m:
        val = _parse_dollar(m.group(1))
        if m.group(2):
            period = "yearly"
        elif m.group(3):
            period = "hourly"
        elif m.group(4):
            period = "monthly"
        else:
            period = _infer_period(val)
        return ParsedSalary(min_value=val, max_value=val, period=period)

    # 4. Dollar amount near salary-related keyword: "Salary: $55,000"
    m = _SALARY_CONTEXT.search(text)
    if m:
        val = _parse_dollar(m.group(1))
        period = _infer_period(val)
        return ParsedSalary(min_value=val, max_value=val, period=period)

    return None
