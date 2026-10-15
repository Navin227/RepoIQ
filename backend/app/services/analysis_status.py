"""Central terminal-status rules for repository analysis.

Completeness is based on useful, grounded core output and required pipeline
stages. Omitted optional files, optional fields, and isolated rejected claims
are diagnostics, not automatic downgrades.
"""
from __future__ import annotations

from typing import Any


def classify_analysis_status(
    analysis: dict[str, Any],
    *,
    pipeline: dict[str, Any] | None = None,
    coverage_gate: dict[str, Any] | None = None,
    insufficient_inputs: bool = False,
) -> dict[str, Any]:
    pipeline = pipeline if isinstance(pipeline, dict) else {}
    gate = coverage_gate if isinstance(coverage_gate, dict) else {}
    reasons: list[dict[str, str]] = []
    failed_stages = [name for name in ("context_preparation", "gemma", "grok", "grok_output")
                     if isinstance(pipeline.get(name), dict)
                     and pipeline[name].get("status") in {"failed", "malformed"}
                     and not (name == "context_preparation" and insufficient_inputs
                              and pipeline[name].get("code") == "insufficient_repository_coverage")]
    if failed_stages:
        reasons.extend({"code": f"{stage}_failed", "stage": stage} for stage in failed_stages)
        return {"status": "failed", "reasons": reasons,
                "required_sections": {"overview": "unknown", "implementation_or_architecture": "unknown"},
                "optional_sections": {"executive_overview": "optional", "investigation_requests": "optional"}}

    overview = bool(str(analysis.get("overview") or "").strip())
    modules = analysis.get("modules") if isinstance(analysis.get("modules"), list) else []
    architecture = analysis.get("architecture") if isinstance(analysis.get("architecture"), dict) else {}
    architecture_summary = str(architecture.get("architecture_summary") or architecture.get("summary") or "").strip()
    unknown_text = {"unknown", "unable to confidently determine from repository evidence."}
    architecture_useful = (bool(architecture_summary) and architecture_summary.casefold() not in unknown_text) or any(
        isinstance(architecture.get(field), list)
        and any(str(item.get("name") or item.get("responsibility") or "").strip().casefold() not in unknown_text
                if isinstance(item, dict) else str(item).strip().casefold() not in unknown_text
                for item in architecture[field])
        for field in ("components", "flow", "request_lifecycle", "communication")
    )
    report = analysis.get("report_sections") if isinstance(analysis.get("report_sections"), dict) else {}
    implementation = bool(modules or architecture_useful or report.get("technical_analysis"))
    claims = analysis.get("claims") if isinstance(analysis.get("claims"), list) else []
    supported_claims = [claim for claim in claims if isinstance(claim, dict)
                        and claim.get("state") in {"confirmed", "inferred"}
                        and isinstance(claim.get("evidence"), list) and claim["evidence"]]
    if not overview and not implementation:
        reasons.append({"code": "no_material_analysis_output", "stage": "analysis"})
        status = "unavailable"
        if insufficient_inputs or gate.get("status") in {"insufficient", "unavailable"}:
            reasons.append({"code": "essential_repository_evidence_unavailable", "stage": "coverage"})
    else:
        status = "complete"
        if not overview:
            status = "partial"
            reasons.append({"code": "overview_missing", "stage": "output"})
        if not implementation:
            status = "partial"
            reasons.append({"code": "implementation_or_architecture_missing", "stage": "output"})
        if gate.get("core_execution_paths_sufficiently_covered") is False or gate.get("status") == "insufficient":
            status = "partial"
            reasons.append({"code": "important_repository_paths_uninspected", "stage": "coverage"})
        if claims and not supported_claims and not (modules or architecture_useful):
            status = "partial"
            reasons.append({"code": "main_claims_not_source_supported", "stage": "evidence_validation"})
    return {
        "status": status,
        "reasons": reasons,
        "required_sections": {"overview": "present" if overview else "missing",
                              "implementation_or_architecture": "present" if implementation else "missing"},
        "optional_sections": {"executive_overview": "optional",
                              "investigation_requests": "optional",
                              "rejected_claims": "diagnostic_only"},
    }
