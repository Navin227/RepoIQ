import json
import logging
import re
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from app.config import settings
from app.services.repomix_service import RepomixContextService
from app.services.repository_discovery import build_analysis_evidence
from app.services.semantic_profile_builder import build_semantic_repository_profile
from app.services.source_evidence_extractor import redact_secrets
from app.services.repository_model import RepositoryRetrieval
from app.services.analysis_diagnostics import emit

logger = logging.getLogger(__name__)
MAX_GEMINI_INPUT_TOKENS = 100_000
UNKNOWN = "Unable to confidently determine from repository evidence."


class LLMService:
    def __init__(self, provider: str = "gemini") -> None:
        self.provider = provider

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

        emit(logger, "analysis_request_start", stage="llm_analysis", analysis_run_id=analysis_id,
             repository=metadata.get("full_name") or metadata.get("name") or "unknown",
             commit_sha=metadata.get("commit_sha"), readme_chars=len(str(readme or "")))

        try:
            self._log_gemini_input(
                analysis_id,
                self.provider,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
            generated = None
            retrieval = RepositoryRetrieval(repo_path) if repo_path else None
            for round_number in range(3):
                payload["investigation_round"] = round_number + 1
                llm_started = time.perf_counter()
                emit(logger, "llm_request_started", stage="llm_request", analysis_run_id=analysis_id,
                     repository=metadata.get("full_name") or metadata.get("name"), commit_sha=metadata.get("commit_sha"),
                     round=round_number + 1, purpose="initial_analysis" if round_number == 0 else "evidence_followup",
                     evidence_file_count=len(payload.get("selected_source_file_details", [])),
                     retrieved_match_count=len(payload.get("on_demand_source_matches", [])))
                source_details = (
                    (payload.get("source_evidence") or {}).get(
                        "selected_source_file_details", []
                    )
                    if isinstance(payload.get("source_evidence"), dict)
                    else []
                )
                emit(logger, "llm_request_context_snapshot", stage="llm_request",
                     analysis_run_id=analysis_id, round=round_number + 1,
                     repository=metadata.get("full_name") or metadata.get("name"),
                     commit_sha=metadata.get("commit_sha"),
                     context={
                         "metadata": payload.get("metadata"),
                         "readme_preview": str(payload.get("readme_text") or "")[:1800],
                         "technology_stack": payload.get("detected_technology_stack"),
                         "inventory_count": payload.get("inventory_file_count"),
                         "source_file_previews": [
                             {key: item.get(key) for key in ("path", "role", "symbols", "imports")}
                             | {"content_preview": str(item.get("content") or "")[:500]}
                             for item in source_details[:8] if isinstance(item, dict)
                         ],
                         "retrieved_matches": [
                             {key: item.get(key) for key in ("path", "start_line", "end_line", "text", "match_kind")}
                             for item in payload.get("on_demand_source_matches", [])[:12]
                             if isinstance(item, dict)
                         ],
                         "investigation_coverage": payload.get("investigation_coverage"),
                     })
                response_text = self._generate_with_gemini(payload)
                self._log_gemini_output(analysis_id, self.provider, response_text)
                emit(logger, "llm_response_received", stage="llm_request", analysis_run_id=analysis_id,
                     round=round_number + 1, duration_ms=round((time.perf_counter() - llm_started) * 1000),
                     response_chars=len(response_text), response_status="received",
                     response_preview=response_text[:2400])
                try:
                    generated = self._parse_json_response(response_text)
                except Exception as exc:
                    emit(logger, "llm_response_parse_failed", level=logging.ERROR, stage="llm_response_parse",
                         analysis_run_id=analysis_id, round=round_number + 1, response_chars=len(response_text),
                         exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
                    raise
                requests = generated.get("investigation_requests", []) if isinstance(generated, dict) else []
                emit(logger, "llm_response_parsed", stage="llm_response_parse", analysis_run_id=analysis_id,
                     round=round_number + 1, claim_count=len(generated.get("claims", [])),
                     module_count=len(generated.get("modules", [])), investigation_request_count=len(requests),
                     parsed_result={
                         "overview": generated.get("overview"),
                         "executive_overview": generated.get("executive_overview"),
                         "modules": generated.get("modules", [])[:6]
                         if isinstance(generated.get("modules"), list) else [],
                         "architecture": generated.get("architecture"),
                         "claims": generated.get("claims", [])[:16]
                         if isinstance(generated.get("claims"), list) else [],
                         "investigation_requests": requests[:12]
                         if isinstance(requests, list) else [],
                     })
                if not requests:
                    if payload.get("investigation_coverage"):
                        payload["investigation_coverage"] = {
                            "rounds": round_number + 1,
                            "unresolved": [],
                            "additional_matches": len(payload.get("on_demand_source_matches", [])),
                        }
                    break
                if not retrieval or round_number == 2:
                    payload["investigation_coverage"] = {"rounds": round_number + 1, "unresolved": requests, "additional_matches": len(payload.get("on_demand_source_matches", []))}
                    break
                retrieved = []
                for request in requests[:12]:
                    if not isinstance(request, dict):
                        continue
                    query = str(request.get("query") or "").strip()
                    if query:
                        previous_match_count = len(retrieved)
                        emit(logger, "retrieval_query_started", stage="retrieval", analysis_run_id=analysis_id,
                             repository=metadata.get("full_name") or metadata.get("name"), commit_sha=metadata.get("commit_sha"),
                             round=round_number + 1, query=query)
                        retrieved.extend(retrieval.search(query))
                        emit(logger, "retrieval_query_completed", stage="retrieval", analysis_run_id=analysis_id,
                             round=round_number + 1, query=query,
                             match_count=len(retrieved) - previous_match_count,
                             empty_result=len(retrieved) == previous_match_count)
                if not retrieved:
                    emit(logger, "retrieval_round_empty", level=logging.WARNING, stage="retrieval",
                         analysis_run_id=analysis_id, round=round_number + 1, query_count=len(requests))
                    payload["investigation_coverage"] = {"rounds": round_number + 1, "unresolved": requests, "additional_matches": 0}
                    break
                for item in retrieved:
                    item["commit_sha"] = str(metadata.get("commit_sha") or "")
                payload.setdefault("on_demand_source_matches", []).extend(retrieved)
                emit(logger, "retrieval_round_completed", stage="retrieval", analysis_run_id=analysis_id,
                     round=round_number + 1, files_retrieved=len({item["path"] for item in retrieved}),
                     range_count=len(retrieved), matches_total=len(payload["on_demand_source_matches"]))
                payload["investigation_coverage"] = {"rounds": round_number + 1, "unresolved": requests, "additional_matches": len(payload["on_demand_source_matches"])}
            if generated is None:
                raise ValueError("Gemini returned no analysis")
            analysis = self._normalize_analysis(generated, payload)
            analysis["analysis_evidence"] = payload["analysis_evidence"]
            if payload.get("on_demand_source_matches"):
                analysis["analysis_evidence"]["on_demand_source_matches"] = payload["on_demand_source_matches"]
            analysis["ai_insights"] = []
            coverage = payload.get("investigation_coverage") or {}
            if coverage:
                payload["analysis_evidence"]["investigation_coverage"] = coverage
            analysis["analysis_status"] = "partial" if coverage.get("unresolved") else "ai_generated"
            emit(logger, "llm_analysis_completed", stage="llm_analysis", analysis_run_id=analysis_id,
                 duration_ms=round((time.perf_counter() - started) * 1000), status=analysis["analysis_status"],
                 claim_count=len(analysis.get("claims", [])), module_count=len(analysis.get("modules", [])))
            self._log_analysis_sections(analysis, degraded=False)
            emit(logger, "analysis_request_end", stage="llm_analysis", analysis_run_id=analysis_id,
                 status=analysis["analysis_status"])
            return analysis
        except Exception as exc:
            emit(logger, "llm_analysis_failed", level=logging.ERROR, stage="llm_analysis",
                 analysis_run_id=analysis_id, duration_ms=round((time.perf_counter() - started) * 1000),
                 exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
            emit(logger, "analysis_degraded", level=logging.WARNING, stage="llm_analysis",
                 analysis_run_id=analysis_id, error_code=self._failure_reason(exc))
            # Provider failure is a degraded result. Never turn metadata or filenames
            # into a fabricated successful architecture.
            analysis = {
                "overview": "",
                "executive_overview": None,
                "modules": [],
                "architecture": {"architecture_summary": "", "summary": "", "architecture_type": "unknown", "flow": [], "request_lifecycle": [], "components": [], "communication": [], "deployment": "unknown"},
                "analysis_evidence": payload["analysis_evidence"],
                "ai_insights": [],
                "analysis_status": "degraded",
                "analysis_error": self._failure_reason(exc),
            }
            analysis["analysis_evidence"]["investigation_coverage"] = {"status": "degraded", "unresolved": ["LLM analysis failed."]}
            emit(logger, "analysis_request_end", stage="llm_analysis", analysis_run_id=analysis_id,
                 status="degraded", error_code=self._failure_reason(exc))
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
        analysis_id = str(provider_payload.get("analysis_id") or uuid.uuid4().hex[:12])
        provider_payload["analysis_id"] = analysis_id

        instructions = """
You are a repository analysis engine. Return ONLY valid JSON, without Markdown
or extra text.

Use exactly these top-level fields:
{
  "overview": "Concise executive overview of the project and its purpose.",
  "executive_overview": {
    "what_is_this_project": ["Non-technical explanation of the project."],
    "why_was_it_built": "The user problem supported by repository evidence.",
    "user_features": [{
      "name": "User action or capability",
      "description": "What a user can do and the result.",
      "evidence": ["Exact source file path or README.md"]
    }],
    "typical_use_cases": ["Evidence-supported use case."],
    "who_is_this_for": ["Evidence-supported audience."],
    "why_is_it_valuable": "Practical value supported by evidence.",
    "one_line_summary": "One-sentence summary."
  },
  "claims": [{
    "text": "One significant repository finding",
    "subject": "stable subject for contradiction checks",
    "category": "overview|feature|module|architecture|deployment|integration|data_flow",
    "target_name": "matching feature/module name when applicable",
    "confidence": 0.0,
    "evidence": [{"path": "exact/repository/path", "start_line": 1, "end_line": 2, "excerpt": "Exact source text from these lines"}]
  }],
  "modules": [{
    "name": "Functional capability",
    "purpose": "Concise responsibility.",
    "capabilities": ["Supported capability"],
    "components": ["Exact repository file path or API route"],
    "evidence": ["Exact observed evidence"],
    "connected_modules": ["Related functional module"],
    "confidence": 90
  }],
  "architecture": {
    "architecture_summary": "Explain the architecture and evidence behind the inference.",
    "architecture_type": "Supported architecture type or the unknown value",
    "flow": ["User", "Frontend", "Backend"],
    "request_lifecycle": ["Repository-specific request step"],
    "components": [{
      "name": "Component",
      "responsibility": "Evidence-supported responsibility",
      "input": "Supported input",
      "output": "Supported output",
      "communicates_with": ["Connected component"],
      "connected_to": ["Connected component"]
    }],
    "communication": ["Supported communication method"],
    "deployment": "Deployment evidence or the unknown value"
  },
  "investigation_requests": [{"query": "symbol or identifier to search", "question": "what remains unresolved"}]
}

Rules:
- Treat analysis_evidence, source_evidence and semantic_repository_profile as
  the authoritative inventory of repository facts.
- Prefer actual source code, enriched API routes, service/controller/model
  evidence, manifests/configuration and infrastructure files over README text
  or filenames alone.
- Do not invent features, modules, technologies, components or deployment
  details. Use the supplied unknown value whenever evidence is insufficient.
- Executive overview must be non-technical.
- Read the README's project description, feature list, and usage instructions
  before drafting the overview. Explain the actual product and concrete user
  workflows; do not pad the overview with generic statements about repository
  contents, folders, or application layers.
- Never describe the repository itself as bringing files, documentation,
  folders, or operational setup together into a product. Such statements are
  filler and are not findings. Identify the named product/domain, concrete
  user action, and observable result from repository evidence; if those are
  not clear, return the supplied unknown value and an investigation request.
- Every user_features item must describe a user-visible action or outcome,
  not a technology, directory, package, or architectural layer. Include
  evidence: exact implementation source paths or README.md that supports it.
  Return no feature when the repository does not provide supporting evidence.
- Typical use cases must explain how a user would use the product, based on
  README instructions or observed application flows. Do not invent audiences
  or workflows.
- Modules must represent actual functional capabilities, not generic folders
  or layers such as backend, frontend, services, controllers or utils.
- Prefer distinct capabilities when supported by routes, source symbols and
  implementation evidence. Return fewer modules when evidence is weak.
- Return at most 6 modules. Each module must reference exact file paths or
  API routes from the supplied inventory.
- Do not accept a filename merely because its basename resembles a real file.
- Explain architecture from observed routes, source, services, stack and
  infrastructure evidence. Do not infer microservices merely from directories.
- Keep Architecture & Flow focused on technical request processing rather
  than repeating the executive overview.
- Flow must be ordered. Component cards should describe actual responsibilities.
- Communication and deployment must be supported by repository evidence.
- Return a claim record for every significant summary, capability, module, architecture, deployment, integration, or data-flow statement. Cite exact source paths, exact line ranges, and exact excerpts. Do not cite a file without a relevant range. If evidence is missing, omit the claim and leave investigation_requests.
- A verbatim excerpt is not sufficient by itself: the excerpt must directly
  support the full meaning of its claim. Keep overview claims specific to this
  repository and cite product documentation plus implementation evidence when
  available. Do not generalize from filenames or directory names.
- Keep the complete JSON concise. Return at most 6 user features and 16 claims. Keep each evidence excerpt under 240 characters. Do not repeat the same fact in multiple claims.
- When required source evidence is missing, return up to 12 focused investigation_requests. Search exact symbols, identifiers, imports or configuration keys. Leave the list empty when findings are supported.
"""
        prompt = (
            instructions
            + "\n\nRepository input:\n"
            + json.dumps(provider_payload, ensure_ascii=False, indent=2)
        )

        genai.configure(api_key=settings.gemini_api_key)
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=16_384,
            response_mime_type="application/json",
        )

        errors = []
        for model_name in (
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ):
            request_started = time.perf_counter()
            provider_started = None

            try:
                model = genai.GenerativeModel(model_name)
                try:
                    token_response = model.count_tokens(prompt)
                    token_count = getattr(token_response, "total_tokens", None)
                    if not isinstance(token_count, int):
                        raise ValueError("Gemini token counter returned no token count")
                except Exception as exc:
                    token_count = (len(prompt) + 1) // 2
                    emit(logger, "gemini_token_count_unavailable", level=logging.WARNING, stage="gemini_prepare",
                         analysis_run_id=analysis_id, model=model_name, exception_type=type(exc).__name__, estimated_tokens=token_count)

                details = (
                    provider_payload.get("source_evidence", {}).get(
                        "selected_source_file_details", []
                    )
                )
                omitted_files = []

                while token_count > MAX_GEMINI_INPUT_TOKENS and details:
                    ranked = sorted(
                        (
                            item
                            for item in details
                            if isinstance(item, dict) and item.get("content")
                        ),
                        key=lambda item: (
                            int(item.get("priority", 0)),
                            str(item.get("path", "")),
                        ),
                    )
                    if not ranked:
                        break

                    drop_count = max(1, (len(ranked) + 3) // 4)
                    for item in ranked[:drop_count]:
                        item["content"] = ""
                        item["content_omitted_reason"] = "Gemini input token budget"
                        omitted_files.append(str(item.get("path") or ""))

                    provider_payload["provider_evidence_exclusions"] = [
                        {"path": path, "reason": "Gemini input token budget"}
                        for path in omitted_files
                    ]
                    prompt = (
                        instructions
                        + "\n\nRepository input:\n"
                        + json.dumps(provider_payload, ensure_ascii=False, indent=2)
                    )

                    try:
                        token_response = model.count_tokens(prompt)
                        token_count = getattr(token_response, "total_tokens", None)
                        if not isinstance(token_count, int):
                            raise ValueError("Gemini token counter returned no token count")
                    except Exception as exc:
                        token_count = (len(prompt) + 1) // 2
                        emit(logger, "gemini_token_count_unavailable", level=logging.WARNING, stage="gemini_prepare",
                             analysis_run_id=analysis_id, model=model_name, exception_type=type(exc).__name__, estimated_tokens=token_count)

                if token_count > MAX_GEMINI_INPUT_TOKENS:
                    raise RuntimeError("Gemini input exceeds the bounded token budget")

                selected_chars = sum(
                    len(item.get("content") or "")
                    for item in details
                    if isinstance(item, dict)
                )
                selected_files = sum(
                    bool(item.get("content"))
                    for item in details
                    if isinstance(item, dict)
                )

                emit(logger, "gemini_request_prepared", stage="gemini_prepare", analysis_run_id=analysis_id,
                     model=model_name, payload_chars=len(prompt), source_chars_selected=selected_chars,
                     selected_file_count=selected_files, excluded_file_count=len(omitted_files), input_tokens=token_count)
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
        message = str(exc).lower()
        if "not configured" in message:
            return "gemini_credentials_not_configured"
        if "not installed" in message:
            return "gemini_dependency_missing"
        if any(term in message for term in ("empty response", "valid json", "json object")):
            return "invalid_provider_response"
        if "token budget" in message:
            return "gemini_input_token_budget_exceeded"
        return f"provider_or_validation_error:{type(exc).__name__}"

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
        semantic_profile = build_semantic_repository_profile(
            metadata, readme, stack, scan, code_signals
        )
        scan_evidence = scan.get("source_evidence") or {}
        functional_evidence = (
            scan_evidence.get("capability_signals", [])
            if isinstance(scan_evidence, dict)
            else []
        )

        readme_text = str(readme or "")
        repomix_context = self._collect_repomix_context(repo_path)
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
            # The complete inventory stays in RepositoryRetrieval. A bounded
            # preview is enough for prompt orientation; all paths remain searchable.
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
            "repomix_context": repomix_context,
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

    def _collect_repomix_context(self, repo_path: str | Path | None) -> Dict[str, Any]:
        try:
            return RepomixContextService().collect_context(repo_path) or {}
        except Exception as exc:
            emit(logger, "repomix_context_collection_failed", level=logging.WARNING, stage="repomix_context",
                 exception_type=type(exc).__name__, reason=str(exc), fallback="repository_scan", exc_info=True)
            return {}

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

        raw_paths = list(payload.get("file_tree", [])) + evidence_paths
        raw_paths += [
            item.get("path") for item in payload.get("on_demand_source_matches", [])
            if isinstance(item, dict) and item.get("path")
        ]
        known_paths = {
            normalized
            for normalized in (
                self._normalize_evidence_path(path) for path in raw_paths
            )
            if normalized
        }

        known_routes = {
            normalized
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
                    known_routes.add(normalized)

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
            confidence = self._coerce_confidence(item.get("confidence", 80))

            if (
                not name
                or not purpose
                or confidence < 50
                or self._is_generic_module_name(name)
                or name.casefold() in {
                    str(directory).strip().casefold()
                    for directory in payload.get("top_level_modules", [])
                    if isinstance(directory, str)
                }
            ):
                continue

            module_key = re.sub(r"\s+", " ", name).casefold()
            if module_key in seen_module_names:
                continue

            raw_components = self._normalize_string_list(item.get("components"))[:8]
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
                    normalized_path in known_paths
                    or normalized_route in known_routes
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
                    "confidence": confidence,
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
        }

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
            for ref in item.get("evidence", []) if isinstance(item.get("evidence"), list) else []:
                if not isinstance(ref, dict):
                    continue
                path = str(ref.get("path") or "").strip()
                start = ref.get("start_line")
                end = ref.get("end_line")
                if path and isinstance(start, int) and isinstance(end, int) and start >= 1 and end >= start:
                    evidence.append({"path": path, "start_line": start, "end_line": end, "excerpt": str(ref.get("excerpt") or "")})
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            claims.append({"text": text, "subject": str(item.get("subject") or ""), "category": str(item.get("category") or "claim"), "target_name": str(item.get("target_name") or ""), "confidence": confidence, "evidence": evidence})
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
            known_repo_paths.update(
                self._normalize_evidence_path(path)
                for path in payload.get("file_tree", [])
                if isinstance(path, str)
            )
            evidence = payload.get("analysis_evidence")
            if isinstance(evidence, dict):
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
                        self._normalize_evidence_path(token)
                        for token in path_like_tokens
                    }
                    if normalized and not normalized.intersection(known_repo_paths):
                        continue
                elif name and not path_like_tokens and not any(
                    keyword in name.casefold()
                    for keyword in (
                        "api", "gateway", "frontend", "backend", "worker",
                        "database", "cache", "queue", "storage", "auth",
                        "service", "db", "server", "client", "worker",
                    )
                ):
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
                    if normalized in feature_paths or route in feature_paths:
                        supported_evidence.append(str(reference).strip())

                if (
                    name
                    and description
                    and not self._is_generic_module_name(name)
                    and not self._matches_repository_directory(name, payload)
                    and name.strip().lower() not in {"storage", "database", "platform"}
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
                    evidence_paths.add(path)

            for route in source_evidence.get("routes", []):
                if isinstance(route, dict):
                    path = self._normalize_evidence_path(route.get("path"), route=True)
                    if path:
                        evidence_paths.add(path)

        evidence = payload.get("analysis_evidence") or {}
        if isinstance(evidence, dict):
            for route in evidence.get("api_routes", []):
                path = self._normalize_evidence_path(route, route=True)
                if path:
                    evidence_paths.add(path)

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
                evidence_paths.add(normalized)

        if str(payload.get("readme_text") or "").strip():
            readme_path = self._readme_evidence_path(payload)
            if readme_path:
                evidence_paths.add(
                    self._normalize_evidence_path(readme_path)
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
