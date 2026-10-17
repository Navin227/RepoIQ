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
        SimpleNamespace(state="confirmed", category="data_flow", text="Checkout submits purchases and writes order records", target_name="Checkout", subject="", evidence=[object()]),
        SimpleNamespace(state="inferred", category="integration", text="Order database stores order records", target_name="Order database", subject="", evidence=[object()]),
    ]
    result = _filter_architecture({
        "summary": "Checkout writes orders and the database stores them.",
        "components": [
            {"name": "Checkout", "responsibility": "Checkout submits purchases and writes order records."},
            {"name": "Order database", "responsibility": "Order database stores order records."},
            {"name": "Unrelated metrics pipeline", "responsibility": "Collects unrelated counters."},
        ],
            "flow": ["Checkout submits purchases and writes order records", "Telemetry samples system latency"],
    }, claims)

    assert [item["name"] for item in result["components"]] == ["Checkout", "Order database"]
    assert result["flow"] == ["Checkout submits purchases and writes order records"]


def test_architecture_edges_require_validated_relationship_and_distinguish_unassessed():
    claims = [SimpleNamespace(
        state="confirmed", category="architecture",
        text="Checkout submits orders and purchases.", target_name="Checkout", subject="",
        evidence=[object()],
    ), SimpleNamespace(
        state="confirmed", category="architecture",
        text="Database stores order records.", target_name="Database", subject="",
        evidence=[object()],
    )]
    result = _filter_architecture({"components": [
        {"name": "Checkout", "responsibility": "Checkout submits orders and purchases.", "connected_to": ["Database"]},
        {"name": "Database", "responsibility": "Database stores order records."},
        {"name": "Response", "responsibility": "Provides a generic runtime responsibility."},
    ]}, claims, module_connection_status={"database": "verified_none"})

    by_name = {item["name"]: item for item in result["components"]}
    assert set(by_name) == {"Checkout", "Database"}
    assert "connected_to" not in by_name["Checkout"]
    assert by_name["Checkout"]["connection_evidence_status"] == "not_fully_assessed"
    assert by_name["Database"]["connection_evidence_status"] == "verified_none"


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
        "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 5}],
    }]})

    assert len(result[0]["evidence"]) == 1
    assert result[0]["validation_reasons"][0]["reason_code"] == "partial_source_coverage"
