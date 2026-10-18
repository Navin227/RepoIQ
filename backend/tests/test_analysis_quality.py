from types import SimpleNamespace

from app.routes.analyze import (
    _filter_architecture,
    _filter_claims_by_coverage,
    _filter_narrative_sentences,
    _narrative_supported_by_claims,
)


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


def test_supported_overview_with_different_wording_is_retained():
    claims = [SimpleNamespace(
        state="confirmed", category="overview",
        text="Buyers use checkout to submit product orders.",
    )]
    assert _narrative_supported_by_claims(
        "Customers can purchase items through the checkout flow.", claims
    )


def test_narrative_filter_keeps_a_supported_sentence_and_drops_only_the_unsupported_one():
    claims = [SimpleNamespace(
        state="confirmed", category="overview",
        text="Buyers use checkout to submit product orders.",
    )]
    kept = _filter_narrative_sentences(
        "Customers can purchase items through checkout. The service streams satellite telemetry.",
        claims,
    )
    assert kept == "Customers can purchase items through checkout."


def test_architecture_keeps_verified_claims_across_categories_and_generic_names():
    claims = [
        SimpleNamespace(state="confirmed", category="data_flow", text="Checkout writes order records", target_name="Checkout", subject="", evidence=[object()]),
        SimpleNamespace(state="inferred", category="integration", text="Order persistence uses the database adapter", target_name="Order database", subject="", evidence=[object()]),
    ]
    result = _filter_architecture({
        "summary": "Checkout writes orders and the database stores them.",
        "components": [
            {"name": "Checkout", "responsibility": "Submits purchases."},
            {"name": "Order database", "responsibility": "Persists orders."},
            {"name": "Unrelated metrics pipeline", "responsibility": "Collects unrelated counters."},
        ],
        "flow": ["Checkout submits an order", "Telemetry samples system latency"],
    }, claims)

    assert [item["name"] for item in result["components"]] == ["Checkout", "Order database"]
    assert result["flow"] == ["Checkout submits an order"]


def test_architecture_omits_placeholders_and_unverified_connections():
    claims = [SimpleNamespace(
        state="confirmed", category="architecture",
        text="The React UI renders repository results.", target_name="React UI",
        subject="", evidence=[object()],
    )]
    result = _filter_architecture({
        "architecture_summary": "Unable to confidently determine from repository evidence.",
        "components": [
            {"name": "React UI", "responsibility": "Renders repository results.", "connected_to": ["API Gateway"]},
            {"name": "Response", "responsibility": "Performs a specific runtime responsibility inferred from repository architecture evidence."},
        ],
    }, claims)

    assert [item["name"] for item in result["components"]] == ["React UI"]
    assert result["components"][0]["connected_to"] == []
    assert result["architecture_summary"] == ""


def test_architecture_without_supported_claims_uses_empty_optional_values():
    result = _filter_architecture({
        "summary": "Unable to confidently determine from repository evidence.",
        "components": [{"name": "Response", "responsibility": "Unknown"}],
    }, [])

    assert result["architecture_summary"] == ""
    assert result["architecture_type"] == ""
    assert result["components"] == []
    assert result["deployment"] == ""


def test_coverage_filter_distinguishes_partial_ranges_and_keeps_valid_reference():
    claims = [{
        "text": "Creates orders", "confidence": 0.8,
        "evidence": [
            {"path": "src/orders.py", "start_line": 2, "end_line": 3},
            {"path": "src/orders.py", "start_line": 20, "end_line": 21},
        ],
    }]
    result = _filter_claims_by_coverage(claims, {"files": [{
        "path": "SRC/ORDERS.PY", "status": "partially_inspected",
        "gemini_supplied_line_ranges": [{"start_line": 1, "end_line": 5}],
    }]})

    assert len(result[0]["evidence"]) == 1
    assert result[0]["validation_reasons"][0]["reason_code"] == "partial_source_coverage"
