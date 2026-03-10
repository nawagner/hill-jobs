from app.ingest.adapters.hvaps import _resolve_canonical_name


def test_resolve_exact_match():
    """Name already in MEMBER_PARTIES should be returned as-is."""
    assert _resolve_canonical_name("Rep. Gilbert Ray Cisneros") == "Rep. Gilbert Ray Cisneros"


def test_resolve_name_variant():
    """HVAPS variant 'Gilbert R. Cisneros Jr.' should map to canonical."""
    result = _resolve_canonical_name("Rep. Gilbert R. Cisneros Jr.")
    assert result == "Rep. Gilbert Ray Cisneros"


def test_resolve_non_rep():
    """Non-Rep names should pass through unchanged."""
    assert _resolve_canonical_name("House Rules Committee") == "House Rules Committee"


def test_resolve_unknown_name():
    """Unknown names should pass through unchanged."""
    assert _resolve_canonical_name("Rep. Nonexistent Person") == "Rep. Nonexistent Person"
