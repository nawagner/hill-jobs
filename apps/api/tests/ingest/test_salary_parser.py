from app.ingest.salary_parser import parse_salary_from_text


def test_yearly_range():
    result = parse_salary_from_text("Salary: $50,000 - $75,000 Per Year")
    assert result is not None
    assert result.min_value == 50_000
    assert result.max_value == 75_000
    assert result.period == "yearly"


def test_hourly_range():
    result = parse_salary_from_text("$40.18 - $46.88 per hour")
    assert result is not None
    assert result.min_value == 40.18
    assert result.max_value == 46.88
    assert result.period == "hourly"


def test_single_yearly_value():
    result = parse_salary_from_text("$64,226 Per Year")
    assert result is not None
    assert result.min_value == 64_226
    assert result.max_value == 64_226
    assert result.period == "yearly"


def test_range_with_to():
    result = parse_salary_from_text("Salary range: $80,000 to $100,000 annually")
    assert result is not None
    assert result.min_value == 80_000
    assert result.max_value == 100_000
    assert result.period == "yearly"


def test_no_salary_returns_none():
    assert parse_salary_from_text("No compensation info here") is None
    assert parse_salary_from_text("") is None
    assert parse_salary_from_text("Competitive salary") is None


def test_range_without_explicit_period_assumes_yearly():
    result = parse_salary_from_text("Compensation: $55,000 - $70,000")
    assert result is not None
    assert result.min_value == 55_000
    assert result.max_value == 70_000
    assert result.period == "yearly"


def test_per_annum():
    result = parse_salary_from_text("$90,000 per annum")
    assert result is not None
    assert result.min_value == 90_000
    assert result.period == "yearly"
