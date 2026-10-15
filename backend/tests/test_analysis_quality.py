from types import SimpleNamespace

from app.routes.analyze import _narrative_supported_by_claims


def test_repository_boilerplate_is_not_supported_by_a_product_claim():
    claims = [SimpleNamespace(
        state="confirmed",
        category="overview",
        text="Medusa provides a headless commerce engine for product catalogs and order management.",
    )]

    assert not _narrative_supported_by_claims(
        "It brings the project files, documented purpose, and visible repository "
        "structure together into a usable product or tool for its intended users.",
        claims,
    )


def test_repository_specific_summary_can_match_a_validated_overview_claim():
    claims = [SimpleNamespace(
        state="confirmed",
        category="overview",
        text="Medusa provides a headless commerce engine for product catalogs and order management.",
    )]

    assert _narrative_supported_by_claims(
        "Medusa is an open commerce platform for managing product catalogs and orders.",
        claims,
    )
