import json
import logging
import re
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from app.config import settings
from app.services.repository_discovery import build_analysis_evidence
from app.services.semantic_profile_builder import build_semantic_repository_profile
from app.services.source_evidence_extractor import redact_secrets
from app.services.analysis_diagnostics import emit
from app.services.analysis_context import ContextPreparationError, prepare_context
from app.services.analysis_status import classify_analysis_status

logger = logging.getLogger(__name__)
UNKNOWN = "Unable to confidently determine from repository evidence."


def _fit_gemini_input(payload: Dict[str, Any], instructions: str, count_tokens, budget: int) -> tuple[Dict[str, Any], str, dict[str, Any]]:
    """Fit the actual final prompt and account for every context omission."""
    provider_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    omissions: list[dict[str, Any]] = []
    removed_fields: list[dict[str, str]] = []
    context_bundle = provider_payload.get("context_bundle")
    context_bundle = context_bundle if isinstance(context_bundle, dict) else {}
    if context_bundle and "file_tree" in provider_payload:
        provider_payload.pop("file_tree")
        removed_fields.append({"field": "file_tree", "reason": "duplicated_by_coverage_manifest"})
    excerpts = context_bundle.get("source_excerpts")
    excerpts = excerpts if isinstance(excerpts, list) else []
    coverage_files = {
        item.get("path"): item
        for item in (context_bundle.get("coverage_manifest", {}).get("files", []))
        if isinstance(item, dict) and item.get("path")
    }
    for entry in coverage_files.values():
        entry["gemini_supplied_line_ranges"] = []
        entry["gemini_omitted_line_ranges"] = []
    for excerpt in excerpts:
        if isinstance(excerpt, dict) and excerpt.get("path") in coverage_files:
            coverage_files[excerpt["path"]]["gemini_supplied_line_ranges"].append({"start_line": excerpt.get("start_line"), "end_line": excerpt.get("end_line")})
    manifest: dict[str, Any] = {"budget_tokens": budget, "estimated_tokens": None, "estimated": False, "omitted_source_ranges": omissions, "omitted_fields": removed_fields}

    def build_prompt() -> str:
        provider_payload["gemini_input_manifest"] = manifest
        return instructions + "\n\nRepository input:\n" + json.dumps(provider_payload, ensure_ascii=False, indent=2)

    def measure(prompt: str) -> int:
        try:
            measured = count_tokens(prompt)
            if not isinstance(measured, int) or measured < 1:
                raise ValueError("Gemini token counter returned no token count")
            return measured
        except Exception:
            manifest["estimated"] = True
            return max(1, (len(prompt) + 1) // 2)

    prompt = build_prompt()
    token_count = measure(prompt)
    while token_count > budget and excerpts:
        paths = sorted(
            {item.get("path") for item in excerpts if isinstance(item, dict) and item.get("path")},
            key=lambda path: (
                bool(coverage_files.get(path, {}).get("important_to_execution_path")),
                0 if "entry_point" not in coverage_files.get(path, {}).get("roles", []) else 1,
                -(coverage_files.get(path, {}).get("execution_path_distance") or 0),
                str(path).casefold(),
            ),
        )
        if not paths:
            break
        # Remove lower-priority paths in deterministic groups to bound calls to
        # Gemini's token counter while preserving execution-path evidence first.
        drop_paths = paths[:max(1, (len(paths) + 7) // 8)]
        keep = []
        for item in excerpts:
            if not isinstance(item, dict) or item.get("path") not in drop_paths:
                keep.append(item)
                continue
            omissions.append({"path": item["path"], "start_line": item.get("start_line"), "end_line": item.get("end_line"), "reason": "gemini_input_token_budget"})
            if item.get("path") in coverage_files:
                entry = coverage_files[item["path"]]
                entry["gemini_supplied_line_ranges"] = [r for r in entry["gemini_supplied_line_ranges"] if r != {"start_line": item.get("start_line"), "end_line": item.get("end_line")}]
                entry["gemini_omitted_line_ranges"].append({"start_line": item.get("start_line"), "end_line": item.get("end_line"), "reason": "gemini_input_token_budget"})
        excerpts = keep
        context_bundle["source_excerpts"] = excerpts
        prompt = build_prompt()
        token_count = measure(prompt)

    # The inventory in the manifest replaces this shallow duplicate tree.
    for field in ("file_tree", "repository_structure"):
        if token_count <= budget:
            break
        if field in provider_payload:
            provider_payload.pop(field)
            removed_fields.append({"field": field, "reason": "gemini_input_token_budget_duplicate_inventory"})
            prompt = build_prompt()
            token_count = measure(prompt)

    # For requests without a clone path, retain scan findings but remove only
    # old inline previews if those are the remaining oversized context.
    details = (provider_payload.get("source_evidence") or {}).get("selected_source_file_details", [])
    details = details if isinstance(details, list) else []
    while token_count > budget:
        candidates = sorted(
            (item for item in details if isinstance(item, dict) and item.get("content")),
            key=lambda item: (int(item.get("priority", 0)), str(item.get("path", "")).casefold()),
        )
        if not candidates:
            break
        drop_count = max(1, (len(candidates) + 7) // 8)
        for item in candidates[:drop_count]:
            item["content"] = ""
            item["content_omitted_reason"] = "Gemini input token budget"
            omissions.append({"path": item.get("path"), "start_line": item.get("start_line"), "end_line": item.get("end_line"), "reason": "Gemini input token budget"})
        prompt = build_prompt()
        token_count = measure(prompt)

    manifest["estimated_tokens"] = token_count
    dropped_critical = sorted({item["path"] for item in omissions if coverage_files.get(item["path"], {}).get("important_to_execution_path")})
    if dropped_critical:
        gate = provider_payload.get("coverage_gate") or context_bundle.get("coverage_gate")
        if isinstance(gate, dict):
            gate["status"] = "partial"
            gate["core_execution_paths_sufficiently_covered"] = False
            gate["known_critical_dependencies_not_inspected"] = sorted(set(gate.get("known_critical_dependencies_not_inspected", [])) | set(dropped_critical))
            gate["reason"] = "Gemini input budget omitted evidence from critical execution paths"
            context_bundle["coverage_gate"] = gate
            coverage_manifest = context_bundle.get("coverage_manifest")
            if isinstance(coverage_manifest, dict):
                coverage_manifest["coverage"] = gate
    for _ in range(2):
        prompt = build_prompt()
        measured = measure(prompt)
        if measured == manifest["estimated_tokens"]:
            break
        manifest["estimated_tokens"] = measured
    prompt = build_prompt()
    return provider_payload, prompt, manifest


class LLMService:
    def __init__(self, provider: str = "gemini") -> None:
        self.provider = provider

    @staticmethod
    def _validate_gemini_output(value: Dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise RuntimeError("Gemini returned malformed output: expected a JSON object")
        if not any(value.get(key) for key in ("overview", "executive_overview", "claims", "modules", "architecture", "report_sections")):
            raise RuntimeError("Gemini returned malformed output: no report content")
        expected = {"overview": str, "executive_overview": dict, "claims": list, "modules": list,
                    "architecture": dict, "report_sections": dict, "investigation_requests": list}
        missing = sorted(set(expected) - set(value))
        wrong_types = sorted(key for key, kind in expected.items() if key in value and not isinstance(value[key], kind))
        incomplete = bool(missing or wrong_types)
        return {"status": "partial" if incomplete else "complete",
                "code": "gemini_partial_output" if incomplete else "ok",
                "missing_fields": missing, "invalid_type_fields": wrong_types}

    @staticmethod
    def _complete_partial_output_shape(value: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "overview": "", "executive_overview": {}, "claims": [], "modules": [],
            "architecture": {}, "report_sections": {}, "investigation_requests": [],
        }
        for key, default in defaults.items():
            if not isinstance(value.get(key), type(default)):
                value[key] = default
        return value

    def generate_repository_analysis(
        self,
        metadata: Dict[str, Any],
        readme: str,
        stack: Dict[str, Any],
        repository_structure: List[Dict[str, Any]],
        scan: Dict[str, Any],
        repo_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        analysis_id = str(metadata.get("analysis_run_id") or uuid.uuid4().hex)
        started = time.perf_counter()
        emit(logger, "llm_analysis_started", stage="llm_analysis", analysis_run_id=analysis_id,
             repository=metadata.get("full_name") or metadata.get("name"), commit_sha=metadata.get("commit_sha"))
        try:
            payload = self._build_input_payload(
                metadata, readme, stack, repository_structure, scan, repo_path=repo_path
            )
        except Exception as exc:
            emit(logger, "llm_input_build_failed", level=logging.ERROR, stage="llm_input_build",
                 analysis_run_id=analysis_id, exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
            raise
        payload["analysis_id"] = analysis_id
        payload["analysis_run_id"] = analysis_id

        context_bundle = None
        context_error = None
        context_diagnostic = {"status": "skipped", "code": "no_repository_path"}
        gemini_output_diagnostic = {"status": "not_received", "code": "not_run"}
        if repo_path:
            context_diagnostic = {"status": "failed", "code": "context_preparation_failure"}
            try:
                context_bundle = prepare_context(
                    metadata, scan, repo_path, str(metadata.get("commit_sha") or ""), payload
                )
                payload["context_bundle"] = context_bundle
                context_diagnostic = {"status": "prepared", "code": "ok"}
            except Exception as exc:
                context_error = exc if isinstance(exc, ContextPreparationError) else ContextPreparationError(
                    f"Context preparation failed: {type(exc).__name__}", "context_preparation_failure"
                )
                context_diagnostic = {"status": "failed", "code": context_error.diagnostic_code}

        emit(logger, "analysis_request_start", stage="llm_analysis", analysis_run_id=analysis_id,
             repository=metadata.get("full_name") or metadata.get("name") or "unknown",
             commit_sha=metadata.get("commit_sha"), readme_chars=len(str(readme or "")))

        try:
            if context_error:
                raise context_error
            self._log_gemini_input(
                analysis_id,
                self.provider,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
            llm_started = time.perf_counter()
            emit(logger, "llm_request_started", stage="llm_request", analysis_run_id=analysis_id,
                 repository=metadata.get("full_name") or metadata.get("name"), commit_sha=metadata.get("commit_sha"),
                 purpose="final_repository_analysis", context_preparation=context_diagnostic)
            emit(logger, "llm_request_context_snapshot", stage="llm_request", analysis_run_id=analysis_id,
                 repository=metadata.get("full_name") or metadata.get("name"), commit_sha=metadata.get("commit_sha"),
                 context={"context_bundle_present": bool(payload.get("context_bundle")),
                          "source_excerpt_count": len((payload.get("context_bundle") or {}).get("source_excerpts", [])),
                          "coverage_gate": (payload.get("context_bundle") or {}).get("coverage_gate"),
                          "deterministic_evidence_present": bool(payload.get("analysis_evidence"))})
            response_text = self._generate_with_gemini(payload)
            self._log_gemini_output(analysis_id, self.provider, response_text)
            emit(logger, "llm_response_received", stage="llm_request", analysis_run_id=analysis_id,
                 duration_ms=round((time.perf_counter() - llm_started) * 1000),
                 response_chars=len(response_text), response_status="received", response_preview=response_text[:2400])
            try:
                generated = self._parse_json_response(response_text)
            except Exception as exc:
                emit(logger, "llm_response_parse_failed", level=logging.ERROR, stage="llm_response_parse",
                     analysis_run_id=analysis_id, exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
                raise RuntimeError("Gemini returned malformed output: invalid JSON response") from exc
            gemini_output_diagnostic = self._validate_gemini_output(generated)
            payload["gemini_output_diagnostic"] = gemini_output_diagnostic
            if gemini_output_diagnostic["status"] == "partial":
                generated = self._complete_partial_output_shape(generated)
            requests = generated.get("investigation_requests", [])
            emit(logger, "llm_response_parsed", stage="llm_response_parse", analysis_run_id=analysis_id,
                 claim_count=len(generated.get("claims", [])) if isinstance(generated.get("claims"), list) else 0,
                 module_count=len(generated.get("modules", [])) if isinstance(generated.get("modules"), list) else 0,
                 investigation_request_count=len(requests) if isinstance(requests, list) else 0)
            coverage_unresolved = list(requests) if isinstance(requests, list) else []
            if context_bundle:
                coverage_unresolved.extend(context_bundle["limitations"]["unresolved_files"])
                coverage_unresolved.extend(context_bundle["limitations"]["unresolved_questions"])
                coverage_unresolved.extend(context_bundle["limitations"]["conflicting_findings"])
            payload["investigation_coverage"] = {"unresolved": coverage_unresolved}
            analysis = self._normalize_analysis(generated, payload)
            raw_architecture = generated.get("architecture") if isinstance(generated.get("architecture"), dict) else {}
            normalized_architecture = analysis.get("architecture") or {}
            raw_executive = generated.get("executive_overview") if isinstance(generated.get("executive_overview"), dict) else {}
            normalized_executive = analysis.get("executive_overview") or {}
            normalization_diagnostic = {
                "status": "filtered" if any((
                    len(generated.get("modules", [])) > len(analysis.get("modules", [])) if isinstance(generated.get("modules"), list) else False,
                    len(raw_architecture.get("components", [])) > len(normalized_architecture.get("components", [])) if isinstance(raw_architecture.get("components"), list) else False,
                    len(raw_executive.get("user_features", [])) > len(normalized_executive.get("user_features", [])) if isinstance(raw_executive.get("user_features"), list) else False,
                )) else "passed",
                "counts": {
                    "modules": {"before": len(generated.get("modules", [])) if isinstance(generated.get("modules"), list) else 0, "after": len(analysis.get("modules", []))},
                    "features": {"before": len(raw_executive.get("user_features", [])) if isinstance(raw_executive.get("user_features"), list) else 0, "after": len(normalized_executive.get("user_features", []))},
                    "architecture_components": {"before": len(raw_architecture.get("components", [])) if isinstance(raw_architecture.get("components"), list) else 0, "after": len(normalized_architecture.get("components", []))},
                    "claims": {"before": len(generated.get("claims", [])) if isinstance(generated.get("claims"), list) else 0, "after": len(analysis.get("claims", []))},
                },
                "reason_counts": {},
            }
            module_removals = normalization_diagnostic["counts"]["modules"]["before"] - normalization_diagnostic["counts"]["modules"]["after"]
            feature_removals = normalization_diagnostic["counts"]["features"]["before"] - normalization_diagnostic["counts"]["features"]["after"]
            component_removals = normalization_diagnostic["counts"]["architecture_components"]["before"] - normalization_diagnostic["counts"]["architecture_components"]["after"]
            if module_removals:
                normalization_diagnostic["reason_counts"]["path_not_in_manifest_or_invalid_module_evidence"] = module_removals
            if feature_removals:
                normalization_diagnostic["reason_counts"]["path_not_in_manifest"] = feature_removals
            if component_removals:
                normalization_diagnostic["reason_counts"]["invalid_schema_or_unknown_component_path"] = component_removals
            analysis["analysis_evidence"] = payload["analysis_evidence"]
            analysis["analysis_evidence"]["semantic_repository_profile"] = payload.get("semantic_repository_profile", {})
            effective_gate = payload.get("gemini_coverage_gate") or (context_bundle or {}).get("coverage_gate")
            if context_bundle:
                final_manifest = payload.get("gemini_coverage_manifest") or context_bundle["coverage_manifest"]
                analysis["analysis_evidence"]["coverage_manifest"] = final_manifest
                analysis["coverage_manifest"] = final_manifest
                analysis["analysis_evidence"]["context_preparation"] = {
                    "status": "complete" if effective_gate.get("status") == "sufficient" and not context_bundle["limitations"]["unresolved_files"] and not final_manifest.get("partially_inspected_count") else "partial",
                    "coverage_gate": effective_gate,
                    "provider": settings.openrouter_model,
                }
            if payload.get("gemini_input_manifest"):
                analysis["analysis_evidence"]["gemini_input_manifest"] = payload["gemini_input_manifest"]
            analysis["analysis_evidence"]["pipeline_diagnostics"] = {
                "context_preparation": context_diagnostic,
                "gemma": {"status": "completed" if context_bundle else "skipped", "code": "ok" if context_bundle else "no_repository_path"},
                "gemini": {"status": "completed", "code": "ok"},
                "gemini_output": gemini_output_diagnostic,
                "normalization": normalization_diagnostic,
                "gemini_generation": payload.get("gemini_generation_diagnostic", {"status": "complete"}),
                "coverage": effective_gate or {"status": "not_assessed"},
                "evidence_validation": {"status": "pending_route_validation"},
                "output_filtering": {"status": "pending_route_filtering"},
            }
            analysis["ai_insights"] = []
            coverage = payload.get("investigation_coverage") or {}
            if coverage:
                payload["analysis_evidence"]["investigation_coverage"] = coverage
            manifest = (payload.get("gemini_coverage_manifest") or context_bundle.get("coverage_manifest", {})) if context_bundle else {}
            classification = classify_analysis_status(
                analysis,
                pipeline=analysis["analysis_evidence"]["pipeline_diagnostics"],
                coverage_gate=effective_gate,
            )
            analysis["analysis_status"] = classification["status"]
            analysis["analysis_evidence"]["pipeline_diagnostics"]["status_classification"] = classification
            emit(logger, "llm_analysis_completed", stage="llm_analysis", analysis_run_id=analysis_id,
                 duration_ms=round((time.perf_counter() - started) * 1000), status=analysis["analysis_status"],
                 claim_count=len(analysis.get("claims", [])), module_count=len(analysis.get("modules", [])))
            self._log_analysis_sections(analysis, degraded=False)
            emit(logger, "analysis_request_end", stage="llm_analysis", analysis_run_id=analysis_id,
                 status=analysis["analysis_status"])
            return analysis
        except Exception as exc:
            failure_code = self._failure_reason(exc)
            failure_stage = (
                "context_preparation" if failure_code in {"context_preparation_failure", "insufficient_repository_coverage"}
                else "gemma" if failure_code.startswith("gemma_")
                else "gemini_output" if failure_code == "gemini_malformed_output"
                else "gemini"
            )
            emit(logger, "llm_analysis_failed", level=logging.ERROR, stage="llm_analysis",
                 analysis_run_id=analysis_id, duration_ms=round((time.perf_counter() - started) * 1000),
                 exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
            emit(logger, "analysis_degraded", level=logging.WARNING, stage="llm_analysis",
                 analysis_run_id=analysis_id, error_code=failure_code)
            # Provider failure is a degraded result. Never turn metadata or filenames
            # into a fabricated successful architecture.
            analysis = {
                "overview": "",
                "executive_overview": None,
                "modules": [],
                "architecture": {"architecture_summary": "", "summary": "", "architecture_type": "unknown", "flow": [], "request_lifecycle": [], "components": [], "communication": [], "deployment": "unknown"},
                "analysis_evidence": payload["analysis_evidence"],
                "ai_insights": [],
                "analysis_status": "unavailable" if failure_code == "insufficient_repository_coverage" else "failed",
                "analysis_error": failure_code,
            }
            if payload.get("gemini_input_manifest"):
                analysis["analysis_evidence"]["gemini_input_manifest"] = payload["gemini_input_manifest"]
            if context_bundle:
                final_manifest = payload.get("gemini_coverage_manifest") or context_bundle["coverage_manifest"]
                analysis["coverage_manifest"] = final_manifest
                analysis["analysis_evidence"]["coverage_manifest"] = final_manifest
                analysis["analysis_evidence"]["semantic_repository_profile"] = payload.get("semantic_repository_profile", {})
            analysis["analysis_evidence"]["pipeline_diagnostics"] = {
                "context_preparation": context_diagnostic,
                "gemma": {"status": "failed" if failure_stage == "gemma" else "completed" if context_bundle else "not_run", "code": failure_code if failure_stage == "gemma" else "ok" if context_bundle else "not_applicable"},
                "gemini": {"status": "failed" if failure_stage == "gemini" else "completed" if failure_stage == "gemini_output" else "not_run", "code": failure_code if failure_stage == "gemini" else "ok" if failure_stage == "gemini_output" else "not_applicable"},
                "gemini_output": {"status": "malformed" if failure_stage == "gemini_output" else "not_received", "code": failure_code},
                "coverage": context_bundle.get("coverage_gate", {"status": "insufficient" if failure_code == "insufficient_repository_coverage" else "unknown"}) if context_bundle else {"status": "insufficient" if failure_code == "insufficient_repository_coverage" else "unknown"},
                "failure_stage": failure_stage,
                "failure_code": failure_code,
            }
            classification = classify_analysis_status(
                analysis,
                pipeline=analysis["analysis_evidence"]["pipeline_diagnostics"],
                coverage_gate=(context_bundle or {}).get("coverage_gate"),
                insufficient_inputs=failure_code == "insufficient_repository_coverage",
            )
            analysis["analysis_status"] = classification["status"]
            analysis["analysis_evidence"]["pipeline_diagnostics"]["status_classification"] = classification
            analysis["analysis_evidence"]["investigation_coverage"] = {"status": "degraded", "unresolved": [failure_code]}
            emit(logger, "analysis_request_end", stage="llm_analysis", analysis_run_id=analysis_id,
                 status=analysis["analysis_status"], error_code=failure_code)
            return analysis

    def _generate_with_gemini(self, payload: Dict[str, Any]) -> str:
        if self.provider != "gemini":
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("google-generativeai is not installed") from exc

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        provider_payload = json.loads(json.dumps(payload))

        def redact_payload(value: Any) -> Any:
            if isinstance(value, str):
                return redact_secrets(value)
            if isinstance(value, list):
                return [redact_payload(item) for item in value]
            if isinstance(value, dict):
                return {key: ("[REDACTED]" if re.search(r"api.?key|authorization|secret|password|credential", str(key), re.I) else redact_payload(item)) for key, item in value.items()}
            return value

        provider_payload = redact_payload(provider_payload)
        analysis_id = str(provider_payload.get("analysis_id") or uuid.uuid4().hex[:12])
        provider_payload["analysis_id"] = analysis_id

        instructions = (Path(__file__).parent / "prompts" / "repo_analysis_system.txt").read_text(encoding="utf-8")

        genai.configure(api_key=settings.gemini_api_key)
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=16_384,
            response_mime_type="application/json",
        )

        errors = []
        for model_name in (settings.gemini_model,):
            request_started = time.perf_counter()
            provider_started = None

            try:
                model = genai.GenerativeModel(model_name)
                def count_tokens(text: str) -> int:
                    result = model.count_tokens(text)
                    value = getattr(result, "total_tokens", None)
                    if not isinstance(value, int):
                        raise ValueError("Gemini token counter returned no token count")
                    return value

                input_budget = max(256, int(settings.gemini_input_token_budget))
                provider_payload, prompt, input_manifest = _fit_gemini_input(
                    provider_payload, instructions, count_tokens, input_budget
                )
                payload["gemini_input_manifest"] = input_manifest
                payload["gemini_coverage_gate"] = (provider_payload.get("context_bundle") or {}).get("coverage_gate") or provider_payload.get("coverage_gate")
                if isinstance((provider_payload.get("context_bundle") or {}).get("coverage_manifest"), dict):
                    payload["gemini_coverage_manifest"] = provider_payload["context_bundle"]["coverage_manifest"]
                token_count = input_manifest["estimated_tokens"]
                if input_manifest.get("estimated"):
                    emit(logger, "gemini_token_count_unavailable", level=logging.WARNING, stage="gemini_prepare",
                         analysis_run_id=analysis_id, model=model_name, estimated_tokens=token_count)
                if token_count > input_budget:
                    raise RuntimeError(f"Gemini input exceeds configured token budget ({token_count}>{input_budget})")

                selected_excerpts = ((provider_payload.get("context_bundle") or {}).get("source_excerpts") or [])
                selected_chars = sum(len(item.get("content") or "") for item in selected_excerpts if isinstance(item, dict))
                selected_files = len({item.get("path") for item in selected_excerpts if isinstance(item, dict)})
                omitted_files = len({item.get("path") for item in input_manifest["omitted_source_ranges"]})

                emit(logger, "gemini_request_prepared", stage="gemini_prepare", analysis_run_id=analysis_id,
                     model=model_name, payload_chars=len(prompt), source_chars_selected=selected_chars,
                     selected_file_count=selected_files, excluded_file_count=omitted_files,
                     omitted_field_count=len(input_manifest["omitted_fields"]), input_tokens=token_count,
                     input_budget=input_budget)
                self._log_gemini_input(analysis_id, model_name, prompt)
                provider_started = time.perf_counter()
                response = model.generate_content(
                    prompt, generation_config=generation_config
                )
                usage = getattr(response, "usage_metadata", None)
                emit(logger, "gemini_request_completed", stage="gemini_request", analysis_run_id=analysis_id,
                     model=model_name, status="success", duration_ms=round((time.perf_counter() - provider_started) * 1000),
                     input_tokens=token_count, prompt_tokens=getattr(usage, "prompt_token_count", None),
                     output_tokens=getattr(usage, "candidates_token_count", None))

                response_text = getattr(response, "text", "") or ""
                finish_reason = None
                try:
                    finish_reason = response.candidates[0].finish_reason
                except (AttributeError, IndexError, TypeError):
                    pass
                finish_text = str(finish_reason or "").casefold()
                payload["gemini_generation_diagnostic"] = {
                    "status": "partial" if "max_tokens" in finish_text or finish_text in {"2", "finishreason.max_tokens"} else "complete",
                    "finish_reason": finish_text or None,
                }
                emit(logger, "gemini_response_metadata", stage="gemini_response", analysis_run_id=analysis_id,
                     model=model_name, finish_reason=str(finish_reason), response_chars=len(response_text))
                if not response_text.strip():
                    raise RuntimeError("Gemini returned an empty response")
                return response_text

            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
                rate_limited = any(term in str(exc).lower() for term in ("429", "rate limit", "resource_exhausted"))
                emit(logger, "gemini_request_failed", level=logging.WARNING, stage="gemini_request",
                     analysis_run_id=analysis_id, model=model_name,
                     duration_ms=round((time.perf_counter() - (provider_started or request_started)) * 1000),
                     exception_type=type(exc).__name__, reason=str(exc), rate_limited=rate_limited,
                     retrying=bool(model_name != "gemini-1.5-flash"), exc_info=True)
                if rate_limited:
                    emit(logger, "gemini_rate_limited", level=logging.WARNING, stage="gemini_request", analysis_run_id=analysis_id, model=model_name)

        raise RuntimeError("; ".join(errors))

    @staticmethod
    def _debug_preview(text: str, limit: int = 12_000) -> str:
        safe_text = redact_secrets(str(text or ""))
        if len(safe_text) <= limit:
            return safe_text
        return safe_text[:limit] + (
            f"\n... [truncated {len(safe_text) - limit} characters]"
        )

    @staticmethod
    def _log_gemini_input(analysis_id: str, model_name: str, prompt: str) -> None:
        if not settings.analysis_debug_logging:
            return
        preview_limit = max(
            1, int(getattr(settings, "analysis_debug_preview_chars", 12_000) or 12_000)
        )
        emit(logger, "gemini_input_summary", stage="gemini_prepare", analysis_run_id=analysis_id,
             model=model_name, prompt_chars=len(prompt))
        emit(logger, "gemini_input_debug_preview", level=logging.DEBUG, stage="gemini_prepare",
             analysis_run_id=analysis_id, preview=LLMService._debug_preview(prompt, preview_limit))

    @staticmethod
    def _log_gemini_output(
        analysis_id: str, model_name: str, response_text: str
    ) -> None:
        if not settings.analysis_debug_logging:
            return
        preview_limit = max(
            1, int(getattr(settings, "analysis_debug_preview_chars", 12_000) or 12_000)
        )
        emit(logger, "gemini_output_summary", stage="gemini_response", analysis_run_id=analysis_id,
             model=model_name, response_chars=len(str(response_text or "")))
        emit(logger, "gemini_output_debug_preview", level=logging.DEBUG, stage="gemini_response",
             analysis_run_id=analysis_id, preview=LLMService._debug_preview(response_text, preview_limit))

    @staticmethod
    def _failure_reason(exc: Exception) -> str:
        diagnostic_code = getattr(exc, "diagnostic_code", None)
        if diagnostic_code:
            return str(diagnostic_code)
        message = str(exc).lower()
        if any(term in message for term in ("malformed output", "no report content", "valid json", "json object", "empty response")):
            return "gemini_malformed_output"
        if "context token budget" in message:
            return "gemini_input_token_budget_exceeded"
        if "not configured" in message:
            return "gemini_credentials_not_configured" if "gemini" in message else "gemma_credentials_not_configured"
        if "not installed" in message:
            return "gemini_dependency_missing"
        if "token budget" in message:
            return "gemini_input_token_budget_exceeded"
        return "gemini_provider_failure"

    @staticmethod
    def _log_analysis_sections(
        analysis: Dict[str, Any], degraded: bool
    ) -> None:
        executive = analysis.get("executive_overview")
        architecture = analysis.get("architecture")
        logger.info(
            "Analysis sections complete: degraded=%s overview=%s "
            "executive_features=%s modules=%s architecture_components=%s",
            degraded,
            bool(analysis.get("overview")),
            len(executive.get("user_features", []))
            if isinstance(executive, dict)
            else 0,
            len(analysis.get("modules", []))
            if isinstance(analysis.get("modules"), list)
            else 0,
            len(architecture.get("components", []))
            if isinstance(architecture, dict)
            else 0,
        )

    def _build_input_payload(
        self,
        metadata: Dict[str, Any],
        readme: str,
        stack: Dict[str, Any],
        repository_structure: List[Dict[str, Any]],
        scan: Dict[str, Any],
        repo_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
        cloud = categories.get("cloud", [])
        infrastructure = categories.get("infrastructure", [])
        devops = categories.get("devops", [])

        code_signals = self._extract_code_signals(scan)
        analysis_evidence = build_analysis_evidence(
            scan, stack, readme, code_signals
        )
        source_evidence = self._build_source_evidence_payload(scan)
        if repo_path:
            # The pinned, inventory-verified excerpts are carried only in context_bundle.
            source_evidence["selected_source_file_details"] = []
        semantic_profile = build_semantic_repository_profile(
            metadata, readme, stack, scan, code_signals
        )
        scan_evidence = scan.get("source_evidence") or {}
        functional_evidence = (
            scan_evidence.get("capability_signals", [])
            if isinstance(scan_evidence, dict)
            else []
        )

        readme_text = redact_secrets(str(readme or ""))
        payload = {
            "analysis_id": str(metadata.get("analysis_id") or uuid.uuid4().hex[:12]),
            "metadata": {
                "name": (
                    metadata.get("name")
                    or metadata.get("repo_name")
                    or metadata.get("full_name")
                ),
                "full_name": metadata.get("full_name"),
                "description": metadata.get("description", ""),
                "primary_language": (
                    metadata.get("language") or metadata.get("primary_language")
                ),
                "topics": metadata.get("topics", []),
                "readme_source": metadata.get("readme_source") or "repository_scan",
            },
            "readme_text": readme_text,
            "detected_technology_stack": stack,
            "repository_structure": self._trim_structure(repository_structure),
            # This preview supports post-generation evidence-path normalization.
            # The Gemini request uses Gemma's manifest as the complete inventory.
            "file_tree": scan.get("files", [])[:500],
            "inventory_file_count": len(scan.get("files", [])),
            "code_signals": code_signals,
            "api_routes": code_signals.get("api_routes", []),
            "api_routes_enriched": code_signals.get("api_routes_enriched", []),
            "services": code_signals.get("service_names", []),
            "controllers": code_signals.get("controller_names", []),
            "top_level_modules": scan.get("top_level_dirs", []),
            "detected_cloud_infrastructure": {
                "cloud": cloud,
                "infrastructure": infrastructure,
                "devops": devops,
            },
            "source_evidence": source_evidence,
            "semantic_repository_profile": semantic_profile,
            "domain_signals": analysis_evidence.get("domain_signals", []),
            "functional_evidence": functional_evidence,
            "analysis_evidence": analysis_evidence,
        }

        stats = scan_evidence.get("stats", {}) if isinstance(scan_evidence, dict) else {}
        emit(logger, "analysis_payload_assembled", stage="llm_input_build",
             analysis_run_id=metadata.get("analysis_run_id"), repository=metadata.get("full_name"),
             commit_sha=metadata.get("commit_sha"), payload_chars=len(json.dumps(payload, ensure_ascii=False)),
             source_chars_selected=stats.get("source_chars_selected", 0),
             selected_source_files=semantic_profile.get("confidence_signals", {}).get("source_files_selected"),
             routes=stats.get("routes_detected", 0), symbols=stats.get("symbols_detected", 0),
             models=stats.get("models_detected", 0),
             semantic_profile_item_counts={key: len(value) if isinstance(value, (list, dict)) else 0
                                           for key, value in semantic_profile.items()})
        return payload

    def _build_source_evidence_payload(self, scan: Dict[str, Any]) -> Dict[str, Any]:
        raw = scan.get("source_evidence") or {}
        details = scan.get("_selected_source_file_objects") or []
        if not isinstance(raw, dict):
            raw = {}
        payload = dict(raw)
        payload["selected_source_file_details"] = details if isinstance(details, list) else []
        return payload


    def _trim_structure(
        self, structure: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        def trim_node(node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            trimmed = {"name": node.get("name"), "type": node.get("type")}
            children = node.get("children", [])
            if depth < 2 and isinstance(children, list):
                trimmed["children"] = [
                    trim_node(child, depth + 1)
                    for child in children[:20]
                    if isinstance(child, dict)
                ]
            return trimmed

        return [
            trim_node(node)
            for node in structure[:3]
            if isinstance(node, dict)
        ]

    def _extract_code_signals(self, scan: Dict[str, Any]) -> Dict[str, Any]:
        files = [str(path) for path in scan.get("files", [])]
        dependencies = scan.get("dependencies", {})
        source_previews = scan.get("source_previews", {})
        source_evidence = scan.get("source_evidence") or {}

        enriched_routes = []
        if isinstance(source_evidence, dict):
            enriched_routes = [
                item
                for item in (source_evidence.get("routes") or [])
                if isinstance(item, dict) and item.get("path")
            ]

        route_patterns = [
            re.compile(r"""["'](/api/[^"']+)["']"""),
            re.compile(r"""@\w+\.(?:get|post|put|delete|patch)\(["']([^"']+)["']"""),
            re.compile(r"""router\.(?:get|post|put|delete|patch)\(["']([^"']+)["']"""),
        ]
        function_patterns = [
            re.compile(r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
            re.compile(r"\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
            re.compile(
                r"\b(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*="
                r"\s*(?:async\s*)?\("
            ),
        ]

        api_routes = [
            str(item.get("path"))
            for item in enriched_routes
            if item.get("path")
        ]
        function_names = []
        for detail in scan.get("_selected_source_file_objects") or []:
            if isinstance(detail, dict):
                function_names.extend(detail.get("symbols") or [])

        evidence_blobs = [
            str(data.get("content", ""))
            for data in dependencies.values()
            if isinstance(data, dict)
        ]
        evidence_blobs.extend(str(content) for content in source_previews.values())

        for content in evidence_blobs:
            for pattern in route_patterns:
                api_routes.extend(pattern.findall(content))
            for pattern in function_patterns:
                function_names.extend(pattern.findall(content))

        service_names = []
        controller_names = []
        model_names = []

        for path in files:
            name = path.rsplit("/", 1)[-1]
            stem = name.rsplit(".", 1)[0]
            lower = path.lower()
            if re.search(r"services?/", lower) or stem.endswith("Service"):
                service_names.append(stem)
            if re.search(r"controllers?/", lower) or stem.endswith("Controller"):
                controller_names.append(stem)
            if re.search(r"(models?|entities?|schemas?)/", lower):
                model_names.append(stem)

        if isinstance(source_evidence, dict):
            for path in source_evidence.get("services", [])[:40]:
                service_names.append(Path(path).stem)
            for path in source_evidence.get("controllers", [])[:40]:
                controller_names.append(Path(path).stem)
            for path in source_evidence.get("models", [])[:40]:
                model_names.append(Path(path).stem)

        business_names = [
            path
            for path in files
            if re.search(
                r"(auth|upload|download|file|document|compress|convert|merge|split|"
                r"summar|payment|checkout|cart|product|order|inventory|notification|"
                r"chat|message|analytics|storage|worker|queue|pdf)",
                path,
                re.IGNORECASE,
            )
        ][:80]

        if isinstance(source_evidence, dict):
            for key in (
                "auth_files",
                "storage_files",
                "worker_files",
                "frontend_pages",
            ):
                business_names.extend(source_evidence.get(key, [])[:20])

        return {
            "api_routes": list(dict.fromkeys(api_routes))[:80],
            "api_routes_enriched": enriched_routes[:80],
            "service_names": list(dict.fromkeys(service_names))[:80],
            "controller_names": list(dict.fromkeys(controller_names))[:80],
            "model_names": list(dict.fromkeys(model_names))[:80],
            "function_names": list(dict.fromkeys(function_names))[:120],
            "business_file_names": list(dict.fromkeys(business_names))[:80],
            "infrastructure_files": [
                path
                for path in files
                if re.search(
                    r"(dockerfile|docker-compose|compose\.ya?ml|\.tf$|k8s|"
                    r"kubernetes|helm|chart\.yaml|values\.yaml|\.github/workflows|"
                    r"gitlab-ci|jenkinsfile)",
                    path,
                    re.IGNORECASE,
                )
            ][:80],
        }

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise ValueError("Gemini response did not contain a valid JSON object")
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object")
        return parsed

    @staticmethod
    def _normalize_evidence_path(value: Any, route: bool = False) -> str:
        """Normalize a repository path or API route without stripping leading dots."""
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            return ""

        if route:
            if not text.startswith("/"):
                return ""
            return re.sub(r"/+", "/", text).rstrip("/") or "/"

        if text.startswith("/") or re.match(r"^[a-zA-Z]:/", text):
            return ""

        parts = text.split("/")
        if any(part == ".." for part in parts):
            return ""

        # Remove only explicit leading "./" segments. Do not use lstrip("./"),
        # because it corrupts names such as ".github/workflows/deploy.yml".
        while text.startswith("./"):
            text = text[2:]

        return text.lower()

    @staticmethod
    def _looks_like_repo_path(token: str) -> bool:
        text = str(token or "").strip().strip(".,;:()[]{}'")
        if not text:
            return False
        if "/" in text:
            return True
        return bool(re.search(r"(?:^|/)[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}$", text))

    def _normalize_analysis(
        self, analysis: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        overview = str(analysis.get("overview") or "").strip()
        if not overview:
            raise ValueError("Gemini response missing overview")

        modules = analysis.get("modules")
        architecture = analysis.get("architecture")
        if not isinstance(modules, list):
            raise ValueError("Gemini response missing modules")
        if not isinstance(architecture, dict):
            raise ValueError("Gemini response missing architecture")

        executive = self._normalize_executive_overview(
            analysis.get("executive_overview"), payload
        )
        evidence_paths = []
        evidence = payload.get("analysis_evidence", {})
        if isinstance(evidence, dict):
            for key in (
                "source_files",
                "infrastructure_files",
                "business_file_names",
                "selected_evidence_files",
            ):
                values = evidence.get(key, [])
                if isinstance(values, list):
                    evidence_paths.extend(values)

        source_evidence = payload.get("source_evidence") or {}
        if isinstance(source_evidence, dict):
            for detail in source_evidence.get("selected_source_file_details") or []:
                if isinstance(detail, dict) and detail.get("path"):
                    evidence_paths.append(detail["path"])

        bundle_files = ((payload.get("context_bundle") or {}).get("coverage_manifest") or {}).get("files", [])
        if isinstance(payload.get("context_bundle"), dict):
            raw_paths = [
                item.get("path") for item in bundle_files
                if isinstance(item, dict) and item.get("path") and item.get("gemini_supplied_line_ranges")
            ]
        else:
            raw_paths = list(payload.get("file_tree", [])) + evidence_paths
        known_paths = {
            normalized.casefold()
            for normalized in (
                self._normalize_evidence_path(path) for path in raw_paths
            )
            if normalized
        }

        known_routes = {
            normalized.casefold()
            for normalized in (
                self._normalize_evidence_path(route, route=True)
                for route in payload.get("api_routes", [])
            )
            if normalized
        }
        for item in payload.get("api_routes_enriched") or []:
            if isinstance(item, dict) and item.get("path"):
                normalized = self._normalize_evidence_path(
                    item["path"], route=True
                )
                if normalized:
                    known_routes.add(normalized.casefold())

        normalized_modules = []
        seen_module_names = set()

        for item in modules:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            purpose = str(
                item.get("purpose")
                or item.get("description")
                or item.get("summary")
                or ""
            ).strip()
            model_confidence = self._coerce_confidence(item.get("confidence", 80))

            if (
                not name
                or not purpose
            ):
                continue

            module_key = re.sub(r"\s+", " ", name).casefold()
            if module_key in seen_module_names:
                continue

            raw_components = self._normalize_string_list(
                self._normalize_string_list(item.get("components"))
                + self._normalize_string_list(item.get("evidence"))
            )[:12]
            supported_components = []

            for component in raw_components:
                normalized_path = self._normalize_evidence_path(component)
                normalized_route = self._normalize_evidence_path(
                    component, route=True
                )

                # Only exact known file paths and exact known API routes count.
                # Basename matches and README substring matches are deliberately
                # excluded because they can validate unrelated repository evidence.
                if (
                    normalized_path.casefold() in known_paths
                    or normalized_route.casefold() in known_routes
                ):
                    supported_components.append(component.strip())

            supported_components = list(dict.fromkeys(supported_components))
            if not supported_components:
                continue

            seen_module_names.add(module_key)
            evidence_items = self._normalize_string_list(item.get("evidence"))[:8]
            supported_evidence = [
                reference
                for reference in evidence_items
                if reference in supported_components
            ]

            normalized_modules.append(
                {
                    "name": name,
                    "purpose": purpose,
                    "description": purpose,
                    "capabilities": self._normalize_string_list(
                        item.get("capabilities")
                    )[:8],
                    "components": supported_components,
                    "evidence": supported_evidence or supported_components,
                    "connected_modules": self._normalize_string_list(
                        item.get("connected_modules")
                    )[:8],
                    "confidence": model_confidence,
                    "model_confidence": model_confidence,
                }
            )

        # Invalid module candidates should not invalidate otherwise valid
        # overview and architecture sections. An empty module list is valid.
        normalized_architecture = self._normalize_architecture(architecture, payload)

        return {
            "overview": overview,
            "executive_overview": executive,
            "modules": normalized_modules[:10],
            "architecture": normalized_architecture,
            "claims": self._normalize_claims(analysis.get("claims")),
            "report_sections": self._normalize_report_sections(
                analysis.get("report_sections")
            ),
        }

    @staticmethod
    def _normalize_report_sections(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        sections: Dict[str, Any] = {}
        technical = value.get("technical_analysis")
        if isinstance(technical, str):
            sections["technical_analysis"] = technical[:12_000]
        for key in ("data_flow", "technology_stack_analysis", "repository_structure_analysis", "limitations"):
            items = value.get(key)
            if isinstance(items, list):
                sections[key] = [item for item in items[:30] if isinstance(item, (str, dict))]
        recommendations = value.get("recommendations")
        if isinstance(recommendations, list):
            sections["recommendations"] = [item for item in recommendations[:12] if isinstance(item, dict)]
        return sections

    @staticmethod
    def _normalize_claims(value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        claims = []
        seen = set()
        for item in value:
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                continue
            text = str(item["text"]).strip()
            key = re.sub(r"\W+", " ", text.casefold()).strip()
            if key in seen:
                continue
            seen.add(key)
            evidence = []
            validation_reasons = []
            for ref in item.get("evidence", []) if isinstance(item.get("evidence"), list) else []:
                if not isinstance(ref, dict):
                    validation_reasons.append({"reason_code": "invalid_schema", "stage": "normalization"})
                    continue
                path = str(ref.get("path") or "").strip()
                start = ref.get("start_line")
                end = ref.get("end_line")
                if path and isinstance(start, int) and isinstance(end, int) and start >= 1 and end >= start:
                    evidence.append({"path": path, "start_line": start, "end_line": end, "excerpt": str(ref.get("excerpt") or "")})
                else:
                    validation_reasons.append({"reason_code": "invalid_line_range" if path else "path_not_in_manifest", "stage": "normalization", "path": path})
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            claims.append({"text": text, "subject": str(item.get("subject") or ""), "category": str(item.get("category") or "claim"), "target_name": str(item.get("target_name") or ""), "confidence": confidence, "model_confidence": confidence, "evidence": evidence, "validation_reasons": validation_reasons})
        return claims

    def _normalize_architecture(
        self, architecture: Dict[str, Any], payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        summary = str(
            architecture.get("architecture_summary")
            or architecture.get("summary")
            or ""
        ).strip()
        architecture_type = str(
            architecture.get("architecture_type") or ""
        ).strip()
        flow = self._normalize_string_list(architecture.get("flow"))
        lifecycle = self._normalize_string_list(
            architecture.get("request_lifecycle")
        )

        components = []
        known_repo_paths: set[str] = set()
        if isinstance(payload, dict):
            context_bundle = payload.get("context_bundle")
            if isinstance(context_bundle, dict):
                manifest = context_bundle.get("coverage_manifest") or {}
                known_repo_paths.update(
                    self._normalize_evidence_path(item.get("path"))
                    for item in manifest.get("files", [])
                    if isinstance(item, dict) and item.get("path") and item.get("gemini_supplied_line_ranges")
                )
            else:
                known_repo_paths.update(
                    self._normalize_evidence_path(path)
                    for path in payload.get("file_tree", [])
                    if isinstance(path, str)
                )
            evidence = payload.get("analysis_evidence")
            if isinstance(evidence, dict) and not isinstance(context_bundle, dict):
                known_repo_paths.update(
                    self._normalize_evidence_path(path)
                    for path in evidence.get("source_files", [])
                    if isinstance(path, str)
                )

        raw_components = architecture.get("components", [])
        if isinstance(raw_components, list):
            seen_components = set()
            for item in raw_components:
                if not isinstance(item, dict):
                    continue

                name = str(item.get("name") or "").strip()
                responsibility = str(item.get("responsibility") or "").strip()
                if not name or not responsibility:
                    continue

                component_ref = f"{name} {responsibility}".strip()
                path_like_tokens = [
                    token for token in re.split(r"[\s/]+", component_ref)
                    if self._looks_like_repo_path(token)
                ]
                if path_like_tokens and known_repo_paths:
                    normalized = {
                        self._normalize_evidence_path(token).casefold()
                        for token in path_like_tokens
                    }
                    if normalized and not normalized.intersection({path.casefold() for path in known_repo_paths}):
                        continue

                key = name.casefold()
                if key in seen_components:
                    continue
                seen_components.add(key)

                connected_to = self._normalize_string_list(
                    item.get("connected_to")
                )[:8]
                communications = self._normalize_string_list(
                    item.get("communicates_with")
                )[:8]

                components.append(
                    {
                        "name": name,
                        "responsibility": responsibility,
                        "input": str(item.get("input") or UNKNOWN).strip(),
                        "output": str(item.get("output") or UNKNOWN).strip(),
                        "communicates_with": communications or connected_to or [UNKNOWN],
                        "connected_to": connected_to,
                        "evidence": self._normalize_string_list(item.get("evidence"))[:8],
                    }
                )

        return {
            "architecture_summary": summary or UNKNOWN,
            "summary": summary or UNKNOWN,
            "architecture_type": architecture_type or UNKNOWN,
            "flow": flow or [UNKNOWN],
            "request_lifecycle": lifecycle or [UNKNOWN],
            "sync_path": self._normalize_string_list(architecture.get("sync_path")),
            "async_path": self._normalize_string_list(architecture.get("async_path")),
            "components": components,
            "communication": self._normalize_string_list(
                architecture.get("communication")
            ) or [UNKNOWN],
            "deployment": str(architecture.get("deployment") or UNKNOWN).strip(),
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return list(dict.fromkeys(
            str(item).strip() for item in value if str(item).strip()
        ))

    @staticmethod
    def _coerce_confidence(value: Any) -> int:
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return 80

    @staticmethod
    def _is_generic_module_name(name: str) -> bool:
        normalized = name.strip().lower()
        return normalized.startswith(".") or normalized in {
            "backend", "frontend", "services", "service", "controllers",
            "controller", "utils", "utilities", "helpers", "components",
            "pages", "src", "app", "api", "routes", "models", "schemas",
            "lib", "config", "www", "web", "infra", "infrastructure",
            "docs", "documentation", "tests", "test", "packages",
        }

    @staticmethod
    def _matches_repository_directory(name: str, payload: Dict[str, Any]) -> bool:
        def normalize(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", value.casefold())

        normalized_name = normalize(name.strip())
        return bool(normalized_name) and any(
            normalized_name == normalize(directory.strip())
            for directory in payload.get("top_level_modules", [])
            if isinstance(directory, str)
        )

    def _normalize_executive_overview(
        self, data: Any, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {
                "what_is_this_project": [], "why_was_it_built": UNKNOWN,
                "user_features": [], "typical_use_cases": [], "who_is_this_for": [],
                "why_is_it_valuable": UNKNOWN, "one_line_summary": UNKNOWN,
            }

        paragraphs = data.get("what_is_this_project", [])
        if isinstance(paragraphs, str):
            paragraphs = [
                part.strip()
                for part in re.split(r"\n\s*\n", paragraphs)
                if part.strip()
            ]
        if not isinstance(paragraphs, list):
            paragraphs = []

        feature_paths = self._feature_evidence_paths(payload)
        features = []
        seen_feature_names: set[str] = set()
        raw_features = data.get("user_features", [])
        if isinstance(raw_features, list):
            for item in raw_features:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                description = str(item.get("description") or "").strip()
                raw_evidence = item.get("evidence", [])
                if isinstance(raw_evidence, str):
                    raw_evidence = [raw_evidence]
                if not isinstance(raw_evidence, list):
                    continue

                supported_evidence = []
                for reference in raw_evidence:
                    normalized = self._normalize_evidence_path(reference)
                    route = self._normalize_evidence_path(reference, route=True)
                    if normalized.casefold() in feature_paths or route.casefold() in feature_paths:
                        supported_evidence.append(str(reference).strip())

                if (
                    name
                    and description
                    and not self._is_generic_module_name(name)
                    and not self._matches_repository_directory(name, payload)
                    and not name.strip().lower() in {"storage", "database", "platform"}
                    and supported_evidence
                    and name.casefold() not in seen_feature_names
                ):
                    seen_feature_names.add(name.casefold())
                    features.append({
                        "name": name,
                        "description": description,
                        "evidence": list(dict.fromkeys(supported_evidence))[:4],
                    })

        use_cases = data.get("typical_use_cases", [])
        if isinstance(use_cases, str):
            use_cases = [use_cases]
        audiences = data.get("who_is_this_for", [])
        if isinstance(audiences, str):
            audiences = [audiences]

        normalized = {
            "what_is_this_project": [
                str(item).strip()
                for item in paragraphs
                if str(item).strip()
            ][:3],
            "why_was_it_built": str(
                data.get("why_was_it_built") or ""
            ).strip(),
            "user_features": features[:8],
            "typical_use_cases": [
                str(item).strip()
                for item in use_cases
                if str(item).strip()
            ][:6] if isinstance(use_cases, list) else [],
            "who_is_this_for": [
                str(item).strip()
                for item in audiences
                if str(item).strip()
            ][:6] if isinstance(audiences, list) else [],
            "why_is_it_valuable": str(
                data.get("why_is_it_valuable") or ""
            ).strip(),
            "one_line_summary": str(
                data.get("one_line_summary") or ""
            ).strip(),
        }

        return normalized

    def _feature_evidence_paths(self, payload: Dict[str, Any]) -> set[str]:
        """Return implementation files, API routes, and README allowed as feature evidence."""
        evidence_paths: set[str] = set()
        context_bundle = payload.get("context_bundle")
        manifest = context_bundle.get("coverage_manifest") if isinstance(context_bundle, dict) else None
        if isinstance(manifest, dict):
            for entry in manifest.get("files", []):
                if not isinstance(entry, dict) or entry.get("status") not in {"fully_inspected", "partially_inspected"}:
                    continue
                if entry.get("gemini_supplied_line_ranges"):
                    path = self._normalize_evidence_path(entry.get("path"))
                    if path:
                        evidence_paths.add(path.casefold())
            for excerpt in context_bundle.get("source_excerpts", []):
                if isinstance(excerpt, dict) and excerpt.get("path"):
                    path = self._normalize_evidence_path(excerpt["path"])
                    if path:
                        evidence_paths.add(path.casefold())
            return evidence_paths
        source_evidence = payload.get("source_evidence") or {}
        if isinstance(source_evidence, dict):
            functional_roles = {
                "entrypoint", "api_route", "controller", "service", "model",
                "repository", "database", "auth", "storage", "frontend_page",
                "frontend_component", "frontend_hook", "worker", "middleware",
            }
            for item in source_evidence.get("selected_source_file_details", []):
                if not isinstance(item, dict) or item.get("role") not in functional_roles:
                    continue
                path = self._normalize_evidence_path(item.get("path"))
                if path:
                    evidence_paths.add(path.casefold())

            for route in source_evidence.get("routes", []):
                if isinstance(route, dict):
                    path = self._normalize_evidence_path(route.get("path"), route=True)
                    if path:
                        evidence_paths.add(path.casefold())

        evidence = payload.get("analysis_evidence") or {}
        if isinstance(evidence, dict):
            for route in evidence.get("api_routes", []):
                path = self._normalize_evidence_path(route, route=True)
                if path:
                    evidence_paths.add(path.casefold())

        # Keep feature citations usable for callers that provide only the
        # repository file inventory rather than extractor role metadata.
        source_suffixes = {
            ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java",
            ".js", ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".swift",
            ".ts", ".tsx", ".vue", ".svelte",
        }
        for path in payload.get("file_tree", []):
            normalized = self._normalize_evidence_path(path)
            if (
                normalized
                and PurePosixPath(normalized).suffix.lower() in source_suffixes
                and not re.search(r"(^|/)(tests?|__tests__|spec)(/|$)", normalized)
            ):
                evidence_paths.add(normalized.casefold())

        if str(payload.get("readme_text") or "").strip():
            readme_path = self._readme_evidence_path(payload)
            if readme_path:
                evidence_paths.add(
                    self._normalize_evidence_path(readme_path).casefold()
                )
        return evidence_paths





    def _readme_evidence_path(self, payload: Dict[str, Any]) -> str:
        readme_paths = [
            path
            for path in payload.get("file_tree", [])
            if isinstance(path, str)
            and PurePosixPath(path).name.lower().startswith("readme.")
        ]
        if readme_paths:
            root_readme = next(
                (path for path in readme_paths if "/" not in path.replace("\\", "/")),
                None,
            )
            selected = root_readme or readme_paths[0]
            return selected.replace("\\", "/")
        return "README.md" if str(payload.get("readme_text") or "").strip() else ""





















    def architecture_summary_text(self, analysis: Dict[str, Any]) -> str:
        architecture = analysis.get("architecture", {})
        summary = str(
            architecture.get("architecture_summary")
            or architecture.get("summary")
            or ""
        ).strip()
        flow = architecture.get("flow", [])
        lifecycle = architecture.get("request_lifecycle", [])
        parts = [summary] if summary else []

        if flow:
            parts.append("Flow:\n" + "\n↓\n".join(str(step) for step in flow))
        if lifecycle:
            parts.append(
                "Request Lifecycle:\n"
                + "\n".join(
                    f"{index + 1}. {step}"
                    for index, step in enumerate(lifecycle)
                )
            )
        return "\n\n".join(parts)
