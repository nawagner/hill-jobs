from app.categorization.role_kinds import ROLE_KINDS


def test_role_kinds_match_product_taxonomy():
    assert ROLE_KINDS == (
        "policy",
        "communications",
        "legal",
        "operations",
        "technology",
        "security",
    )
