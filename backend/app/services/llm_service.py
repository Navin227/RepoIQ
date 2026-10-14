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
    ) -> Dict[str, Any]:
        payload = self._build_input_payload(
            metadata, readme, stack, repository_structure, scan
        )
        payload["analysis_id"] = str(
            payload.get("analysis_id") or uuid.uuid4().hex[:12]
        )
        analysis_id = payload["analysis_id"]

        logger.info(
            "ANALYSIS_REQUEST_START analysis_id=%s repo=%s readme_chars=%s",
            analysis_id,
            metadata.get("full_name") or metadata.get("name") or "unknown",
            len(str(readme or "")),
        )

        try:
            self._log_gemini_input(
                analysis_id,
                self.provider,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
            response_text = self._generate_with_gemini(payload)
            self._log_gemini_output(analysis_id, self.provider, response_text)
            generated = self._parse_json_response(response_text)
            analysis = self._normalize_analysis(generated, payload)
            analysis["analysis_evidence"] = payload["analysis_evidence"]
            self._log_analysis_sections(analysis, fallback=False)
            logger.info("ANALYSIS_REQUEST_END analysis_id=%s status=success", analysis_id)
            return analysis
        except Exception as exc:
            logger.warning(
                "Analysis fallback activated: reason=%s analysis_id=%s",
                self._fallback_reason(exc),
                analysis_id,
            )
            analysis = self._fallback_analysis(payload)
            self._log_analysis_sections(analysis, fallback=True)
            logger.info("ANALYSIS_REQUEST_END analysis_id=%s status=fallback", analysis_id)
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
  }
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
- Return up to 10 modules. Each module must reference exact file paths or
  API routes from the supplied inventory.
- Do not accept a filename merely because its basename resembles a real file.
- Explain architecture from observed routes, source, services, stack and
  infrastructure evidence. Do not infer microservices merely from directories.
- Keep Architecture & Flow focused on technical request processing rather
  than repeating the executive overview.
- Flow must be ordered. Component cards should describe actual responsibilities.
- Communication and deployment must be supported by repository evidence.
"""
        prompt = (
            instructions
            + "\n\nRepository input:\n"
            + json.dumps(provider_payload, ensure_ascii=False, indent=2)
        )

        genai.configure(api_key=settings.gemini_api_key)
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
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
                    logger.warning(
                        "Gemini token counting unavailable: model=%s error_type=%s "
                        "estimated_tokens=%s",
                        model_name,
                        type(exc).__name__,
                        token_count,
                    )

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
                        logger.warning(
                            "Gemini token counting unavailable after prioritization: "
                            "model=%s error_type=%s estimated_tokens=%s",
                            model_name,
                            type(exc).__name__,
                            token_count,
                        )

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

                logger.info(
                    "Gemini request prepared: model=%s payload_chars=%s "
                    "source_chars_selected=%s selected_files=%s excluded_files=%s "
                    "input_tokens=%s",
                    model_name,
                    len(prompt),
                    selected_chars,
                    selected_files,
                    omitted_files,
                    token_count,
                )
                self._log_gemini_input(analysis_id, model_name, prompt)
                provider_started = time.perf_counter()
                response = model.generate_content(
                    prompt, generation_config=generation_config
                )
                logger.info(
                    "Gemini provider request: model=%s status=success latency_ms=%s "
                    "input_tokens=%s",
                    model_name,
                    round((time.perf_counter() - provider_started) * 1000),
                    token_count,
                )

                response_text = getattr(response, "text", "") or ""
                if not response_text.strip():
                    raise RuntimeError("Gemini returned an empty response")
                return response_text

            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
                if provider_started is None:
                    logger.warning(
                        "Gemini request preparation failed: model=%s error_type=%s "
                        "latency_ms=%s",
                        model_name,
                        type(exc).__name__,
                        round((time.perf_counter() - request_started) * 1000),
                    )
                else:
                    logger.warning(
                        "Gemini provider request: model=%s status=failure "
                        "error_type=%s latency_ms=%s",
                        model_name,
                        type(exc).__name__,
                        round((time.perf_counter() - provider_started) * 1000),
                    )

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
        logger.info(
            "GEMINI_INPUT_START analysis_id=%s model=%s prompt_chars=%s",
            analysis_id,
            model_name,
            len(prompt),
        )
        logger.info(
            "GEMINI_INPUT_PREVIEW analysis_id=%s %s",
            analysis_id,
            LLMService._debug_preview(prompt, preview_limit),
        )
        logger.info("GEMINI_INPUT_END analysis_id=%s", analysis_id)

    @staticmethod
    def _log_gemini_output(
        analysis_id: str, model_name: str, response_text: str
    ) -> None:
        if not settings.analysis_debug_logging:
            return
        preview_limit = max(
            1, int(getattr(settings, "analysis_debug_preview_chars", 12_000) or 12_000)
        )
        logger.info(
            "GEMINI_OUTPUT_START analysis_id=%s model=%s response_chars=%s",
            analysis_id,
            model_name,
            len(str(response_text or "")),
        )
        logger.info(
            "GEMINI_OUTPUT_PREVIEW analysis_id=%s %s",
            analysis_id,
            LLMService._debug_preview(response_text, preview_limit),
        )
        logger.info("GEMINI_OUTPUT_END analysis_id=%s", analysis_id)

    @staticmethod
    def _fallback_reason(exc: Exception) -> str:
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
        analysis: Dict[str, Any], fallback: bool
    ) -> None:
        executive = analysis.get("executive_overview")
        architecture = analysis.get("architecture")
        logger.info(
            "Analysis sections complete: fallback=%s overview=%s "
            "executive_features=%s modules=%s architecture_components=%s",
            fallback,
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
            "readme_text": readme_text[:12_000],
            "readme_summary": self._summarize_readme(readme_text),
            "detected_technology_stack": stack,
            "repository_structure": self._trim_structure(repository_structure),
            "file_tree": scan.get("files", [])[:500],
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
        logger.info(
            "Analysis payload assembled: %s",
            {
                "payload_chars": len(json.dumps(payload, ensure_ascii=False)),
                "source_chars_selected": stats.get("source_chars_selected", 0),
                "selected_source_files": semantic_profile.get(
                    "confidence_signals", {}
                ).get("source_files_selected"),
                "routes": stats.get("routes_detected", 0),
                "symbols": stats.get("symbols_detected", 0),
                "models": stats.get("models_detected", 0),
                "semantic_profile_item_counts": {
                    key: len(value) if isinstance(value, (list, dict)) else 0
                    for key, value in semantic_profile.items()
                },
                "domain_signals": [
                    item.get("domain")
                    for item in analysis_evidence.get("domain_signals", [])[:5]
                    if isinstance(item, dict)
                ],
            },
        )
        return payload

    def _build_source_evidence_payload(self, scan: Dict[str, Any]) -> Dict[str, Any]:
        raw = scan.get("source_evidence") or {}
        details = scan.get("_selected_source_file_objects") or []
        if not isinstance(raw, dict):
            raw = {}
        payload = dict(raw)
        payload["selected_source_file_details"] = (
            details[:45] if isinstance(details, list) else []
        )
        return payload

    def _summarize_readme(self, readme: str) -> str:
        return " ".join((readme or "").split())[:8000]

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
        normalized_architecture = self._normalize_architecture(architecture)

        return {
            "overview": overview,
            "executive_overview": executive,
            "modules": normalized_modules[:10],
            "architecture": normalized_architecture,
        }

    def _normalize_architecture(
        self, architecture: Dict[str, Any]
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
            return self._fallback_executive_overview(
                payload, self._fallback_modules(payload)
            )

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
                ):
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

        fallback = self._fallback_executive_overview(
            payload, self._fallback_modules(payload)
        )
        if not normalized["user_features"]:
            normalized["user_features"] = fallback["user_features"]
        for key, value in fallback.items():
            if not normalized.get(key):
                normalized[key] = value
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

    def _fallback_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = payload.get("metadata") or {}
        stack = payload.get("detected_technology_stack") or {}
        categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
        tech_names = self._category_names(categories)
        modules = self._fallback_modules(payload)

        project_name = (
            metadata.get("full_name") or metadata.get("name") or "This repository"
        )
        description = str(metadata.get("description") or "").strip()
        readme_summary = self._readme_product_summary(payload)
        project_summary = readme_summary or description
        evidence = payload.get("analysis_evidence", {})
        source_count = (
            evidence.get("source_file_count", 0)
            if isinstance(evidence, dict)
            else 0
        )
        detections = (
            evidence.get("technology_detections", [])
            if isinstance(evidence, dict)
            else []
        )

        if project_summary:
            overview = (
                f"{project_name}: {project_summary}"
            )
        else:
            overview = (
                f"The available repository evidence is insufficient to determine "
                f"the user-facing purpose of {project_name}. Analysis found "
                f"{source_count} source files and {len(detections)} concrete "
                "technology detections."
            )

        flow = self._fallback_flow(tech_names, payload)
        architecture_type = self._infer_architecture_type(tech_names, payload)
        architecture_summary = self._build_architecture_summary(tech_names, payload)
        lifecycle = self._build_request_lifecycle(tech_names, payload)
        sync_path, async_path = self._build_sync_async_paths(tech_names, flow)

        component_cards = []
        for index, step in enumerate(flow):
            component_cards.append(
                {
                    "name": step,
                    "responsibility": self._fallback_component_responsibility(step),
                    "input": self._fallback_component_input(step, tech_names),
                    "output": self._fallback_component_output(step, tech_names),
                    "communicates_with": self._fallback_component_communications(
                        step, flow
                    ),
                    "connected_to": [flow[index + 1]]
                    if index + 1 < len(flow)
                    else [],
                }
            )

        return {
            "overview": overview,
            "executive_overview": self._fallback_executive_overview(
                payload, modules
            ),
            "modules": modules,
            "architecture": {
                "architecture_summary": architecture_summary,
                "summary": architecture_summary,
                "architecture_type": architecture_type,
                "flow": flow,
                "request_lifecycle": lifecycle,
                "sync_path": sync_path,
                "async_path": async_path,
                "components": component_cards,
                "communication": self._fallback_communication(
                    tech_names, payload
                ),
                "deployment": self._fallback_deployment(tech_names, payload),
            },
            "analysis_evidence": payload.get("analysis_evidence", {}),
        }

    def _fallback_executive_overview(
        self, payload: Dict[str, Any], modules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        metadata = payload.get("metadata") or {}
        project_name = (
            metadata.get("full_name") or metadata.get("name") or "This project"
        )
        description = str(metadata.get("description") or "").strip()
        readme_summary = self._readme_product_summary(payload)
        evidence = payload.get("analysis_evidence", {})
        source_count = (
            evidence.get("source_file_count", 0)
            if isinstance(evidence, dict)
            else 0
        )

        summary = (
            readme_summary
            if readme_summary
            else f"{project_name} is described as {description}."
            if description
            else f"Available repository evidence is insufficient to determine "
                 f"what {project_name} is intended to do."
        )
        paragraphs = [summary]

        features = self._readme_features(payload)
        if not features:
            features = [
                {
                    "name": item["name"],
                    "description": item["description"],
                    "evidence": item["evidence"],
                }
                for item in modules
                if item.get("name") and item.get("description") and item.get("evidence")
            ]
        features = features[:8]

        return {
            "what_is_this_project": paragraphs,
            "why_was_it_built": (
                "Repository evidence does not establish why this project was built."
            ),
            "user_features": features,
            "typical_use_cases": [],
            "who_is_this_for": [],
            "why_is_it_valuable": (
                "Repository evidence does not establish the project's practical "
                "value to users."
            ),
            "one_line_summary": (
                f"{project_name}: {readme_summary or description}"
                if readme_summary or description
                else f"{project_name}: user-facing purpose is not clear from "
                     "the available repository evidence."
            ),
        }

    @staticmethod
    def _clean_readme_text(line: str) -> str:
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("`", "").replace("**", "").replace("__", "")
        return " ".join(text.split()).strip(" -*#>|")

    def _readme_product_summary(self, payload: Dict[str, Any]) -> str:
        readme = str(payload.get("readme_text") or "")
        if not readme.strip():
            return ""

        blocks: list[str] = []
        current: list[str] = []
        in_code_block = False
        for raw_line in readme.splitlines():
            line = raw_line.strip()
            if line.startswith("```") or line.startswith("~~~"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if not line:
                if current:
                    blocks.append(" ".join(current))
                    current = []
                continue
            if line.startswith("#"):
                if current:
                    blocks.append(" ".join(current))
                    current = []
                continue
            if re.match(r"^(?:[-*_]\s*){3,}$", line) or "shields.io" in line.lower():
                continue
            cleaned = self._clean_readme_text(line)
            if cleaned and not cleaned.startswith(("http://", "https://")):
                current.append(cleaned)
        if current:
            blocks.append(" ".join(current))

        for block in blocks:
            if len(block) < 35:
                continue
            if re.search(
                r"\b(install|installation|contribut|license|prerequisite|"
                r"quick start|getting started|development setup)\b",
                block[:100].lower(),
            ):
                continue
            sentences = re.split(r"(?<=[.!?])\s+", block)
            summary = " ".join(sentences[:3]).strip()
            return summary[:900].rstrip()
        return ""

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

    def _readme_features(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        readme = str(payload.get("readme_text") or "")
        if not readme.strip():
            return []

        in_feature_section = False
        features = []
        for raw_line in readme.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                heading = self._clean_readme_text(line.lstrip("#")).lower()
                in_feature_section = bool(
                    re.search(r"\b(features?|capabilities|what you can do|"
                              r"key functionality|highlights)\b", heading)
                )
                continue
            if not in_feature_section or not re.match(r"^(?:[-*+]|\d+[.)])\s+", line):
                continue
            text = self._clean_readme_text(re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line))
            if len(text) < 16:
                continue
            name_match = re.match(r"^([^:—–-]{3,48})\s*[:—–-]\s*(.+)$", text)
            if name_match:
                name, description = name_match.groups()
            else:
                name = " ".join(text.split()[:5]).rstrip(".,;:")
                description = text
            if self._is_generic_module_name(name):
                continue
            features.append({
                "name": name,
                "description": description[:280],
                "evidence": [self._readme_evidence_path(payload)],
            })
            if len(features) == 8:
                break
        return features

    @staticmethod
    def _category_names(categories: Dict[str, Any]) -> Dict[str, List[str]]:
        names = {}
        for category, items in categories.items():
            values = []
            for item in items or []:
                if isinstance(item, dict) and item.get("name"):
                    values.append(str(item["name"]))
                elif isinstance(item, str):
                    values.append(item)
            names[category] = values
        return names

    @staticmethod
    def _has_tech(tech_names: Dict[str, List[str]], search: str) -> bool:
        return any(
            search.lower() in item.lower()
            for items in tech_names.values()
            for item in items
        )

    def _find_frontend_component(
        self, tech_names: Dict[str, List[str]]
    ) -> str | None:
        frontend = [
            item for item in tech_names.get("frontend", [])
            if isinstance(item, str)
        ]
        if any("next" in item.lower() for item in frontend):
            return "Next.js Frontend"
        if any("react" in item.lower() for item in frontend):
            return (
                "React + Vite Frontend"
                if self._has_tech(tech_names, "vite")
                else "React Frontend"
            )
        if any("vue" in item.lower() for item in frontend):
            return "Vue Frontend"
        if any("svelte" in item.lower() for item in frontend):
            return "Svelte Frontend"
        if any("angular" in item.lower() for item in frontend):
            return "Angular Frontend"
        return None

    def _find_backend_component(
        self, tech_names: Dict[str, List[str]]
    ) -> str | None:
        backend = [
            item for item in tech_names.get("backend", [])
            if isinstance(item, str)
        ]
        for needle, label in (
            ("fastapi", "FastAPI Service"),
            ("express", "Express API"),
            ("nest", "NestJS Service"),
            ("flask", "Flask Service"),
            ("django", "Django Application"),
            ("spring", "Spring Boot Service"),
            ("gin", "Gin Service"),
            ("go", "Go Backend Service"),
        ):
            if any(needle in item.lower() for item in backend):
                return label
        return None

    def _infer_deployment_type(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> str:
        if self._has_tech(tech_names, "lambda") or self._has_tech(
            tech_names, "serverless"
        ):
            return "Serverless"
        if self._has_tech(tech_names, "eks") or self._has_tech(
            tech_names, "kubernetes"
        ):
            return "Kubernetes"
        if self._has_tech(tech_names, "ecs"):
            return "ECS"
        if self._has_tech(tech_names, "docker"):
            return "Docker Container"
        if self._has_tech(tech_names, "terraform") or (
            payload.get("code_signals", {}).get("infrastructure_files")
        ):
            return "Terraform"
        if any(
            self._has_tech(tech_names, cloud)
            for cloud in ("aws", "gcp", "azure")
        ):
            return "Cloud Native"
        return UNKNOWN

    def _infer_architecture_type(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> str:
        if self._has_tech(tech_names, "lambda") or self._has_tech(
            tech_names, "serverless"
        ):
            return "Serverless"
        if any(
            self._has_tech(tech_names, key)
            for key in ("eks", "kubernetes", "ecs")
        ):
            if self._has_tech(tech_names, "sqs") or self._has_tech(
                tech_names, "sns"
            ):
                return "Event-driven"
            return "Microservice"
        if self._has_tech(tech_names, "sqs") or self._has_tech(
            tech_names, "sns"
        ):
            return "Event-driven"

        frontend = bool(tech_names.get("frontend"))
        backend = bool(tech_names.get("backend"))
        database = bool(tech_names.get("database"))
        top_level = [
            str(name).lower() for name in payload.get("top_level_modules", [])
        ]

        if (frontend and backend) or (backend and database):
            return "Layered"
        if backend:
            return "Monolith"
        if "frontend" in top_level and "backend" in top_level:
            return "Layered"
        if "api" in top_level and database:
            return "Layered"
        return UNKNOWN

    def _build_architecture_summary(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> str:
        parts = []
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)
        deployment = self._infer_deployment_type(tech_names, payload)

        if frontend:
            parts.append(
                f"The repository includes a {frontend} as the user-facing "
                "application layer."
            )
        elif any(
            str(name).lower() == "frontend"
            for name in payload.get("top_level_modules", [])
        ):
            parts.append(
                "The repository includes a frontend application layer based "
                "on the top-level project structure."
            )

        if backend:
            parts.append(
                f"Backend logic runs in a {backend} that handles incoming "
                "application requests."
            )
        elif any(
            self._has_tech(tech_names, key)
            for key in ("fastapi", "express", "flask", "django")
        ):
            parts.append(
                "Backend application code exposes HTTP APIs for request processing."
            )

        if self._has_tech(tech_names, "api gateway"):
            parts.append(
                "Requests are routed through an API Gateway layer before "
                "reaching service logic."
            )
        if self._has_tech(tech_names, "lambda"):
            parts.append(
                "AWS Lambda functions host the serverless compute portion "
                "of the application."
            )
        if self._has_tech(tech_names, "sqs") or self._has_tech(
            tech_names, "sns"
        ):
            parts.append(
                "Asynchronous queue and pub/sub patterns connect services "
                "and background processing."
            )

        storage_options = (
            ("dynamodb", "DynamoDB provides the managed persistence layer."),
            ("s3", "S3 is used for object storage."),
            ("postgresql", "PostgreSQL provides relational storage."),
            ("mysql", "MySQL provides relational storage."),
            ("mongodb", "MongoDB provides document storage."),
        )
        for needle, description in storage_options:
            if self._has_tech(tech_names, needle):
                parts.append(description)
                break

        if deployment != UNKNOWN:
            parts.append(
                f"Deployment is inferred as {deployment} based on repository "
                "infrastructure evidence."
            )
        return " ".join(parts) if parts else UNKNOWN

    def _build_request_lifecycle(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> List[str]:
        lifecycle = []
        top_level = [
            str(name).lower() for name in payload.get("top_level_modules", [])
        ]
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)

        if frontend:
            lifecycle.append(
                f"The user interacts with the {frontend} to start the workflow."
            )
        elif "frontend" in top_level:
            lifecycle.append(
                "The user interacts with the frontend application to start "
                "the workflow."
            )

        if self._has_tech(tech_names, "api gateway"):
            lifecycle.append(
                "The request passes through API Gateway before reaching "
                "application services."
            )
        elif backend:
            lifecycle.append(f"The request reaches the {backend} over HTTP.")
        elif any(
            self._has_tech(tech_names, key)
            for key in ("fastapi", "express", "flask", "django")
        ):
            lifecycle.append(
                "The request reaches an HTTP API endpoint implemented by "
                "repository backend code."
            )

        if self._has_tech(tech_names, "lambda"):
            lifecycle.append(
                "AWS Lambda executes the detected serverless business logic."
            )
        if self._has_tech(tech_names, "sqs"):
            lifecycle.append(
                "A job message is published to SQS for background processing."
            )
        if self._has_tech(tech_names, "sns"):
            lifecycle.append(
                "An SNS notification is broadcast to downstream services."
            )

        for needle, statement in (
            ("dynamodb", "The application reads from or writes to DynamoDB."),
            ("s3", "The workflow stores or retrieves objects from S3."),
            ("postgresql", "The workflow reads from or writes to PostgreSQL."),
            ("mysql", "The workflow reads from or writes to MySQL."),
            ("mongodb", "The workflow reads from or writes to MongoDB."),
        ):
            if self._has_tech(tech_names, needle):
                lifecycle.append(statement)
                break

        if not lifecycle:
            return [UNKNOWN]

        if "response" not in lifecycle[-1].lower():
            lifecycle.append(
                "The final response is returned to the caller after the "
                "detected processing completes."
            )
        return lifecycle

    def _fallback_modules(
        self, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        evidence = payload.get("analysis_evidence", {})
        paths = evidence.get("business_file_names", []) if isinstance(
            evidence, dict
        ) else []
        if not isinstance(paths, list):
            return []

        rules = [
            (
                "Authentication",
                re.compile(r"(auth|login|identity|session)", re.I),
                "Implements authentication-related behavior evidenced by repository source paths.",
            ),
            (
                "File Upload",
                re.compile(r"(upload|multipart)", re.I),
                "Implements file upload behavior evidenced by repository source paths.",
            ),
            (
                "File Management",
                re.compile(r"(file|document|drive)", re.I),
                "Implements file or document management behavior evidenced by repository source paths.",
            ),
            (
                "File Storage",
                re.compile(r"(storage|bucket|s3)", re.I),
                "Implements storage-related behavior evidenced by repository source paths.",
            ),
            (
                "Commerce",
                re.compile(r"(payment|checkout|cart|product|order)", re.I),
                "Implements commerce behavior evidenced by repository source paths.",
            ),
            (
                "Messaging",
                re.compile(r"(chat|message|notification)", re.I),
                "Implements messaging behavior evidenced by repository source paths.",
            ),
            (
                "Background Processing",
                re.compile(r"(worker|queue|job)", re.I),
                "Implements background processing evidenced by repository source paths.",
            ),
        ]

        candidates = []
        for name, pattern, purpose in rules:
            matches = list(
                dict.fromkeys(
                    str(path) for path in paths if pattern.search(str(path))
                )
            )[:8]
            if not matches:
                continue
            candidates.append(
                {
                    "name": name,
                    "purpose": purpose,
                    "description": purpose,
                    "capabilities": [],
                    "components": matches,
                    "evidence": matches,
                    "connected_modules": [],
                    "confidence": 70,
                }
            )
        return candidates[:10]

    def _fallback_capabilities_for_module(self, name: str) -> List[str]:
        lowered = name.lower()
        if "auth" in lowered:
            return [
                "Manage user identity",
                "Support protected access",
                "Connect sign-in state to the application",
            ]
        if "upload" in lowered or "storage" in lowered:
            return [
                "Store user data",
                "Track saved content",
                "Connect stored data to application workflows",
            ]
        if "worker" in lowered or "processing" in lowered:
            return [
                "Handle background tasks",
                "Process queued work",
                "Separate long-running work from user actions",
            ]
        if "infrastructure" in lowered:
            return [
                "Define deployment resources",
                "Organize environment setup",
                "Support repeatable operations",
            ]
        return [
            "Provide a major project responsibility",
            "Coordinate related application behavior",
            "Support the user workflow",
        ]

    def _fallback_components_for_module(
        self, name: str, payload: Dict[str, Any]
    ) -> List[str]:
        files = payload.get("file_tree", [])
        tokens = [
            part for part in re.split(r"\s+|[-_]", name.lower()) if len(part) > 2
        ]
        matches = []
        for path in files:
            lower = str(path).lower()
            if any(token in lower for token in tokens):
                matches.append(str(path))
            if len(matches) >= 6:
                break
        return matches

    def _fallback_flow(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> List[str]:
        flow = ["User"]
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)
        top_level = [
            str(name).lower() for name in payload.get("top_level_modules", [])
        ]

        if frontend:
            flow.append(frontend)
        elif "frontend" in top_level:
            flow.append("Frontend")

        if self._has_tech(tech_names, "api gateway"):
            flow.append("API Gateway")
        elif backend:
            flow.append(backend)
        elif any(
            self._has_tech(tech_names, key)
            for key in ("fastapi", "express", "nest", "flask", "django")
        ):
            flow.append("HTTP API")
        elif any(
            name in top_level for name in ("backend", "server", "api")
        ):
            flow.append("Backend Service")

        if self._has_tech(tech_names, "lambda"):
            if "API Gateway" not in flow:
                flow.append("API Gateway")
            flow.append("AWS Lambda")

        if self._has_tech(tech_names, "sns"):
            flow.append("SNS")
        if self._has_tech(tech_names, "sqs"):
            flow.append("SQS")

        if self._has_tech(tech_names, "ecs"):
            flow.append("ECS Container")
        elif self._has_tech(tech_names, "eks") or self._has_tech(
            tech_names, "kubernetes"
        ):
            flow.append("Kubernetes Pod")
        elif self._has_tech(tech_names, "docker"):
            flow.append("Docker Container")

        for needle, label in (
            ("postgresql", "PostgreSQL"),
            ("mysql", "MySQL"),
            ("mongodb", "MongoDB"),
            ("redis", "Redis"),
            ("dynamodb", "DynamoDB"),
            ("s3", "S3"),
            ("cloudwatch", "CloudWatch"),
        ):
            if self._has_tech(tech_names, needle):
                flow.append(label)
                break
        else:
            if self._has_tech(tech_names, "database"):
                flow.append("Storage")

        flow.append("Response")
        return list(dict.fromkeys(flow))

    def _fallback_component_responsibility(self, name: str) -> str:
        lowered = name.lower()
        if "user" in lowered:
            return "Initiates the workflow and receives the final outcome."
        if any(word in lowered for word in ("frontend", "react", "next")):
            return "Handles user interaction and sends application requests to the backend."
        if "api gateway" in lowered:
            return "Routes incoming API requests before they reach service logic."
        if any(
            word in lowered
            for word in ("fastapi", "express", "flask", "django", "http api")
        ):
            return "Processes HTTP requests and coordinates application logic."
        if "lambda" in lowered:
            return "Executes serverless business logic in response to API or queue events."
        if "sqs" in lowered or "sns" in lowered:
            return "Manages asynchronous event delivery for background processing."
        if "dynamodb" in lowered:
            return "Stores and retrieves application data in a managed NoSQL table."
        if any(
            word in lowered
            for word in ("postgresql", "mysql", "mongodb", "redis")
        ):
            return "Provides persistent storage for application data."
        if "s3" in lowered:
            return "Holds application objects, assets, or processed output."
        if any(
            word in lowered
            for word in ("terraform", "docker", "kubernetes", "ecs")
        ):
            return "Represents deployment infrastructure rather than runtime execution."
        return "Performs a runtime responsibility inferred from repository evidence."

    def _fallback_communication(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> List[str]:
        communication = []
        if payload.get("api_routes") or any(
            self._has_tech(tech_names, key)
            for key in ("fastapi", "express", "flask", "django")
        ):
            communication.append(
                "REST APIs: Components communicate through HTTP endpoints exposed by the backend."
            )
        if self._has_tech(tech_names, "sqs"):
            communication.append(
                "SQS: Queued messages hand off work to background workers."
            )
        if self._has_tech(tech_names, "sns"):
            communication.append(
                "SNS: Pub/sub messages broadcast events to downstream services."
            )
        if self._has_tech(tech_names, "websocket") or self._has_tech(
            tech_names, "socket.io"
        ):
            communication.append(
                "WebSockets: Real-time updates are exchanged over bidirectional sockets."
            )
        if any(
            self._has_tech(tech_names, key)
            for key in ("dynamodb", "postgresql", "mysql", "mongodb", "redis")
        ):
            communication.append(
                "Database access: Runtime components communicate with persistence services."
            )
        return communication or [UNKNOWN]

    def _build_sync_async_paths(
        self, tech_names: Dict[str, List[str]], flow: List[str]
    ) -> tuple[list[str], list[str]]:
        sync_path = []
        async_path = []

        if "User" in flow and any(
            self._has_tech(tech_names, key)
            for key in ("react", "next", "vue", "svelte", "angular")
        ):
            sync_path.extend(
                ["User", self._find_frontend_component(tech_names) or "Frontend"]
            )
        elif "User" in flow:
            sync_path.append("User")

        if "API Gateway" in flow:
            sync_path.append("API Gateway")
        elif any(
            self._has_tech(tech_names, key)
            for key in ("fastapi", "express", "flask", "django", "nest")
        ):
            sync_path.append(self._find_backend_component(tech_names) or "HTTP API")

        if self._has_tech(tech_names, "lambda"):
            sync_path.append("AWS Lambda")

        if self._has_tech(tech_names, "sqs"):
            async_path.append("SQS")
        if self._has_tech(tech_names, "sns"):
            async_path.append("SNS")
        if async_path:
            async_path.append("Worker")

        if self._has_tech(tech_names, "dynamodb"):
            async_path.append("DynamoDB")
        elif self._has_tech(tech_names, "s3"):
            async_path.append("S3")

        if not sync_path and not async_path:
            return [], []
        if sync_path and sync_path[-1] != "Response":
            sync_path.append("Response")
        return sync_path, async_path

    def _fallback_component_input(
        self, name: str, tech_names: Dict[str, List[str]]
    ) -> str:
        lowered = name.lower()
        if any(word in lowered for word in ("frontend", "react", "next")):
            return "User actions and browser events"
        if "api gateway" in lowered:
            return "HTTP requests from client or frontend"
        if any(
            word in lowered
            for word in ("fastapi", "express", "flask", "django", "http api")
        ):
            return "HTTP request payload"
        if "lambda" in lowered:
            return "API events or queue messages"
        if "sqs" in lowered or "sns" in lowered:
            return "Event messages from application services"
        if any(
            word in lowered
            for word in ("dynamodb", "postgresql", "mysql", "mongodb", "redis")
        ):
            return "Data queries and persistence requests"
        if "s3" in lowered:
            return "Object write/read requests"
        return "Runtime input based on detected component behavior."

    def _fallback_component_output(
        self, name: str, tech_names: Dict[str, List[str]]
    ) -> str:
        lowered = name.lower()
        if any(word in lowered for word in ("frontend", "react", "next")):
            return "API calls and user interface updates"
        if "api gateway" in lowered:
            return "Forwarded requests to backend services"
        if any(
            word in lowered
            for word in ("fastapi", "express", "flask", "django", "http api")
        ):
            return "Backend responses or queued work requests"
        if "lambda" in lowered:
            return "Function results or queue/notification events"
        if "sqs" in lowered or "sns" in lowered:
            return "Queued messages to workers or subscribers"
        if any(
            word in lowered
            for word in ("dynamodb", "postgresql", "mysql", "mongodb", "redis")
        ):
            return "Stored or retrieved persistence results"
        if "s3" in lowered:
            return "Stored objects or static content links"
        return "Runtime output based on component activity."

    def _fallback_component_communications(
        self, name: str, flow: List[str]
    ) -> List[str]:
        lowered = name.lower()
        communications = []

        if any(word in lowered for word in ("frontend", "react", "next")):
            communications.extend(["API Gateway", "Backend Service"])
        if "api gateway" in lowered:
            communications.extend(["Frontend", "Backend Service"])
        if any(
            word in lowered
            for word in ("fastapi", "express", "flask", "django", "http api")
        ):
            communications.extend(["Frontend", "DynamoDB", "S3", "SQS", "SNS"])
        if "lambda" in lowered:
            communications.extend(["API Gateway", "SQS", "SNS", "DynamoDB", "S3"])
        if "sqs" in lowered or "sns" in lowered:
            communications.extend(["Worker", "Backend Service"])
        if any(
            word in lowered
            for word in ("dynamodb", "postgresql", "mysql", "mongodb", "redis")
        ):
            communications.extend(["Backend Service", "Lambda"])
        if "s3" in lowered:
            communications.extend(["Backend Service", "Lambda"])

        if not communications and name in flow:
            index = flow.index(name)
            if index > 0:
                communications.append(flow[index - 1])
            if index + 1 < len(flow):
                communications.append(flow[index + 1])

        return list(dict.fromkeys(item for item in communications if item))

    def _fallback_deployment(
        self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]
    ) -> str:
        infrastructure_files = (
            payload.get("code_signals", {}).get("infrastructure_files", [])
        )
        evidence = " ".join(str(path) for path in infrastructure_files).lower()

        if self._has_tech(tech_names, "terraform") or ".tf" in evidence:
            if self._has_tech(tech_names, "lambda"):
                return "Serverless deployment on AWS Lambda with Terraform provisioning."
            if self._has_tech(tech_names, "ecs"):
                return "Container-based deployment on ECS with Terraform infrastructure definitions."
            if self._has_tech(tech_names, "eks") or self._has_tech(
                tech_names, "kubernetes"
            ):
                return "Kubernetes deployment defined through Terraform manifests."
            return "Terraform-provisioned infrastructure is used for deployment."

        if self._has_tech(tech_names, "docker") or "docker" in evidence:
            return "Container-based deployment is supported by Docker configuration evidence."
        if self._has_tech(tech_names, "serverless") or self._has_tech(
            tech_names, "lambda"
        ):
            return "Serverless deployment is supported by AWS Lambda evidence."
        if any(
            self._has_tech(tech_names, cloud)
            for cloud in ("aws", "gcp", "azure")
        ):
            return "Cloud-native deployment is indicated by cloud service detection."
        return UNKNOWN

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

    def generate_overview(self, *args: Any, **kwargs: Any) -> str:
        if "metadata" in kwargs and "scan" in kwargs and "stack" in kwargs:
            analysis = self.generate_repository_analysis(
                metadata=kwargs["metadata"],
                readme=kwargs["scan"].get("readme", ""),
                stack=kwargs["stack"],
                repository_structure=[],
                scan=kwargs["scan"],
            )
            return analysis["overview"]

        repo_name = kwargs.get("repo_name") or (
            args[0] if args else "Repository"
        )
        payload = {
            "metadata": {
                "full_name": repo_name,
                "description": kwargs.get("description") or "",
            },
            "readme_summary": kwargs.get("readme", ""),
            "detected_technology_stack": kwargs.get("technologies", {}),
            "repository_structure": kwargs.get("repo_structure", []),
            "top_level_modules": [],
            "detected_cloud_infrastructure": {},
            "analysis_evidence": {},
            "file_tree": [],
        }
        return self._fallback_analysis(payload)["overview"]

    def generate_modules(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if "scan" in kwargs and "stack" in kwargs:
            analysis = self.generate_repository_analysis(
                metadata={},
                readme=kwargs["scan"].get("readme", ""),
                stack=kwargs["stack"],
                repository_structure=[],
                scan=kwargs["scan"],
            )
            return analysis["modules"]

        structure = kwargs.get("repo_structure", [])
        technologies = kwargs.get("technologies", {})
        payload = {
            "metadata": {"full_name": kwargs.get("repo_name", "Repository")},
            "readme_summary": "",
            "detected_technology_stack": technologies,
            "repository_structure": structure,
            "top_level_modules": [
                node.get("name")
                for node in structure
                if isinstance(node, dict) and node.get("type") == "folder"
            ],
            "detected_cloud_infrastructure": {},
            "analysis_evidence": {},
            "file_tree": [],
        }
        return self._fallback_analysis(payload)["modules"]

    def generate_architecture_summary(self, *args: Any, **kwargs: Any) -> str:
        if "scan" in kwargs and "stack" in kwargs:
            analysis = self.generate_repository_analysis(
                metadata={},
                readme=kwargs["scan"].get("readme", ""),
                stack=kwargs["stack"],
                repository_structure=[],
                scan=kwargs["scan"],
            )
            return self.architecture_summary_text(analysis)

        analysis = self._fallback_analysis(
            {
                "metadata": {"full_name": kwargs.get("repo_name", "Repository")},
                "readme_summary": kwargs.get("readme", ""),
                "detected_technology_stack": kwargs.get("technologies", {}),
                "repository_structure": kwargs.get("repo_structure", []),
                "top_level_modules": [],
                "detected_cloud_infrastructure": {},
                "analysis_evidence": {},
                "file_tree": [],
            }
        )
        return self.architecture_summary_text(analysis)

    def generate_ai_insights(self, *args: Any, **kwargs: Any) -> List[str]:
        return []