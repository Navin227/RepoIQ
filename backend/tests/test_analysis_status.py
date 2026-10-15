from app.services.analysis_status import classify_analysis_status


def useful_analysis():
    return {
        "overview": "A source-grounded repository summary.",
        "modules": [{"name": "API", "purpose": "Provides API routes."}],
        "architecture": {},
    }


def test_complete_result_does_not_require_optional_fields_or_every_claim():
    result = useful_analysis()
    result["claims"] = [
        {"text": "Supported", "state": "confirmed", "evidence": [{"path": "src/api.py"}]},
        {"text": "Rejected", "state": "rejected", "evidence": []},
    ]
    result["analysis_evidence"] = {"coverage_manifest": {"omitted_count": 20}}
    classification = classify_analysis_status(result, coverage_gate={"status": "sufficient", "core_execution_paths_sufficiently_covered": True})
    assert classification["status"] == "complete"
    assert classification["required_sections"]["overview"] == "present"
    assert classification["optional_sections"]["executive_overview"] == "optional"


def test_missing_material_section_is_partial_with_reason():
    classification = classify_analysis_status({"overview": "Useful overview", "modules": [], "architecture": {}})
    assert classification["status"] == "partial"
    assert "implementation_or_architecture_missing" in {reason["code"] for reason in classification["reasons"]}


def test_weak_main_claims_are_partial_but_rejected_optional_claim_is_not():
    result = useful_analysis()
    result["modules"] = []
    result["claims"] = [{"text": "Unsupported", "state": "rejected", "evidence": []}]
    classification = classify_analysis_status(result)
    assert classification["status"] == "partial"
    assert "main_claims_not_source_supported" in {reason["code"] for reason in classification["reasons"]}


def test_provider_failure_is_failed_and_low_source_evidence_is_unavailable():
    failed = classify_analysis_status(useful_analysis(), pipeline={"gemini": {"status": "failed"}})
    unavailable = classify_analysis_status({}, coverage_gate={"status": "insufficient"}, insufficient_inputs=True)
    assert failed["status"] == "failed"
    assert failed["reasons"][0]["code"] == "gemini_failed"
    assert unavailable["status"] == "unavailable"


def test_insufficient_repository_coverage_is_unavailable_not_pipeline_failure():
    classification = classify_analysis_status(
        {},
        pipeline={"context_preparation": {"status": "failed", "code": "insufficient_repository_coverage"}},
        coverage_gate={"status": "insufficient"},
        insufficient_inputs=True,
    )
    assert classification["status"] == "unavailable"
    assert "essential_repository_evidence_unavailable" in {reason["code"] for reason in classification["reasons"]}


def test_bounded_large_repository_can_be_complete_when_critical_paths_are_covered():
    result = useful_analysis()
    result["coverage_manifest"] = {"omitted_count": 100, "partially_inspected_count": 20}
    classification = classify_analysis_status(result, coverage_gate={"status": "partial", "core_execution_paths_sufficiently_covered": True})
    assert classification["status"] == "complete"
