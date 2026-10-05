import json
import logging
import re
from typing import Any, Dict, List

from app.config import settings
from app.services.repository_discovery import build_analysis_evidence

logger = logging.getLogger(__name__)


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
        payload = self._build_input_payload(metadata, readme, stack, repository_structure, scan)

        try:
            response_text = self._generate_with_gemini(payload)
            generated = self._parse_json_response(response_text)
            analysis = self._normalize_analysis(generated, payload)
            analysis["analysis_evidence"] = payload["analysis_evidence"]
            return analysis
        except Exception as exc:
            logger.warning("Gemini analysis failed; using rule-based fallback: %s", exc)
            return self._fallback_analysis(payload)

    def _generate_with_gemini(self, payload: Dict[str, Any]) -> str:
        if self.provider != "gemini":
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("google-generativeai is not installed") from exc

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        prompt = f"""
You are a repository analysis engine.
Return ONLY valid JSON. Do not include Markdown, comments, or extra text.

Generate exactly these sections:
1. Executive Overview
2. Core Modules
3. Architecture & Flow

Required JSON schema:
{{
  "overview": "A concise executive overview covering what the project does, primary purpose, main capabilities, and intended users.",
  "executive_overview": {{
    "what_is_this_project": ["2-3 concise non-technical paragraphs explaining what the project does, its purpose, and what users can accomplish."],
    "why_was_it_built": "Explain the real-world problem or need this project addresses. Focus on user pain points, not implementation.",
    "user_features": [
      {{
        "name": "Feature name",
        "description": "One-line description"
      }}
    ],
    "typical_use_cases": ["Realistic scenario where this project is useful."],
    "who_is_this_for": ["Actual target audience such as students, businesses, developers, teams, or operators."],
    "why_is_it_valuable": "Explain the practical value users gain.",
    "one_line_summary": "One memorable sentence summarizing the project."
  }},
  "modules": [
    {{
      "name": "Module name",
      "purpose": "2-3 concise sentences explaining the functional responsibility.",
      "capabilities": ["Specific capability supported by repository evidence."],
      "components": ["Exact source file or API route evidence from the repository inventory."],
      "evidence": ["Observed repository path, route, or README evidence supporting this module."],
      "connected_modules": ["Other functional module this interacts with."],
      "confidence": 95
    }}
  ],
  "architecture": {{
    "architecture_summary": "2-4 concise paragraphs explaining how the system works and why this architecture was inferred from evidence.",
    "architecture_type": "Monolith | Layered | Microservice | Serverless | Event-driven | MVC | Clean Architecture | Unable to confidently determine from repository evidence.",
    "flow": ["User", "Frontend", "API Layer", "Business Logic", "Database"],
    "request_lifecycle": ["Repository-specific step describing the main user action."],
    "components": [
      {{
        "name": "Component Name",
        "responsibility": "Specific responsibility supported by repository evidence.",
        "connected_to": ["Other connected component"]
      }}
    ],
    "communication": ["REST APIs: Components communicate through HTTP JSON endpoints."],
    "deployment": "Deployment perspective supported by repository evidence, or Unable to confidently determine from repository evidence."
  }}
}}

Rules:
- Make executive_overview completely non-technical.
- Do not use analogies, metaphors, or generic AI framing.
- Do not hallucinate features. Only include user_features supported by the README, repository structure, detected modules, stack, or metadata.
- Return up to 8 user_features; use an empty list when repository evidence does not support any.
- For modules, identify functional business/application capabilities, not folder names, directories, packages, or generic layers.
- Do not return generic modules like backend, frontend, services, controllers, or utils unless the repository evidence proves they are actual product capabilities.
- Prefer separate modules for distinct user-facing capabilities when file names, routes, functions, or README evidence support them. For example, compression, conversion, PDF merge, PDF split, summarization, upload, authentication, and notifications should be separate modules when they appear as separate capabilities.
- Use multiple signals before deciding each module: README, description, API routes, service names, function names, file names, repository structure, and technology stack.
- Prefer fewer high-confidence modules over many generic ones. Exclude low-confidence modules.
- Return 5 to 10 important modules when enough evidence exists.
- Use the repository evidence; do not invent external facts.
- Treat analysis_evidence as the authoritative inventory of observed repository facts.
- Clearly distinguish observed facts from interpretation. README statements are weaker than source, manifest, route, or configuration evidence.
- Do not invent technologies, modules, architecture components, or user functionality that are not supported by analysis_evidence.
- Use exact repository paths or routes from the evidence when naming module components. Return fewer items when evidence is insufficient.
- Keep module descriptions short.
- For Architecture & Flow, explain HOW the application works for developers and technical reviewers.
- Do not repeat Executive Overview, Core Modules, Technology Stack, or Repository Structure content in Architecture & Flow.
- Infer architecture only from evidence in README, structure, detected modules, stack, routes, services, controllers, and infrastructure signals.
- Use "Unable to confidently determine from repository evidence." for any architecture field that cannot be supported.
- Architecture summary must explain why the architecture type was inferred, not merely name it.
- Flow must be an ordered list of logical components so the frontend can render a vertical timeline.
- Request lifecycle must describe the repository-specific main action when evidence supports it.
- Component cards must use component names, responsibilities, and connected components; do not copy the module list verbatim.
- Communication must identify supported methods such as REST APIs, WebSockets, queues, direct service calls, database access, or cloud service integrations.
- Deployment must include only supported evidence such as Docker, Terraform, serverless, container-based, cloud-native, or traditional deployment.

Repository input:
{json.dumps(payload, indent=2)}
        """.strip()

        genai.configure(api_key=settings.gemini_api_key)
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
        )

        response = None
        errors = []
        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=generation_config)
                break
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")

        if response is None:
            raise RuntimeError("; ".join(errors))

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")
        return text

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
        analysis_evidence = build_analysis_evidence(scan, stack, readme, code_signals)

        return {
            "metadata": {
                "name": metadata.get("name") or metadata.get("repo_name") or metadata.get("full_name"),
                "full_name": metadata.get("full_name"),
                "description": metadata.get("description", ""),
                "primary_language": metadata.get("language") or metadata.get("primary_language"),
                "topics": metadata.get("topics", []),
            },
            "readme_summary": self._summarize_readme(readme),
            "detected_technology_stack": stack,
            "repository_structure": self._trim_structure(repository_structure),
            "file_tree": scan.get("files", [])[:500],
            "code_signals": code_signals,
            "api_routes": code_signals.get("api_routes", []),
            "services": code_signals.get("service_names", []),
            "controllers": code_signals.get("controller_names", []),
            "top_level_modules": scan.get("top_level_dirs", []),
            "detected_cloud_infrastructure": {
                "cloud": cloud,
                "infrastructure": infrastructure,
                "devops": devops,
            },
            "analysis_evidence": analysis_evidence,
        }

    def _summarize_readme(self, readme: str) -> str:
        text = " ".join((readme or "").split())
        return text[:3000]

    def _trim_structure(self, structure: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def trim_node(node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            trimmed = {
                "name": node.get("name"),
                "type": node.get("type"),
            }
            children = node.get("children", [])
            if depth < 2 and isinstance(children, list):
                trimmed["children"] = [trim_node(child, depth + 1) for child in children[:20]]
            return trimmed

        return [trim_node(node) for node in structure[:3] if isinstance(node, dict)]

    def _extract_code_signals(self, scan: Dict[str, Any]) -> Dict[str, List[str]]:
        files = [str(path) for path in scan.get("files", [])]
        dependencies = scan.get("dependencies", {})
        source_previews = scan.get("source_previews", {})
        route_patterns = [
            re.compile(r'["\'](/api/[^"\']+)["\']'),
            re.compile(r'@\w+\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']'),
            re.compile(r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']'),
        ]
        function_patterns = [
            re.compile(r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
            re.compile(r"\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
            re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s*)?\("),
        ]

        api_routes: list[str] = []
        function_names: list[str] = []
        evidence_blobs = [str(dep_data.get("content", "")) for dep_data in dependencies.values()]
        evidence_blobs.extend(str(content) for content in source_previews.values())
        for content in evidence_blobs:
            for pattern in route_patterns:
                api_routes.extend(pattern.findall(content))
            for pattern in function_patterns:
                function_names.extend(pattern.findall(content))

        service_names = []
        controller_names = []
        for path in files:
            name = path.rsplit("/", 1)[-1]
            stem = name.rsplit(".", 1)[0]
            lower = path.lower()
            if "service" in lower:
                service_names.append(stem)
            if "controller" in lower:
                controller_names.append(stem)

        business_file_names = [
            path for path in files
            if re.search(
                r"(auth|upload|download|file|document|compress|convert|merge|split|"
                r"summar|payment|checkout|cart|product|order|inventory|notification|"
                r"chat|message|analytics|storage|worker|queue|pdf)",
                path,
                re.IGNORECASE,
            )
        ][:80]

        return {
            "api_routes": list(dict.fromkeys(api_routes))[:80],
            "service_names": list(dict.fromkeys(service_names))[:80],
            "controller_names": list(dict.fromkeys(controller_names))[:80],
            "function_names": list(dict.fromkeys(function_names))[:120],
            "business_file_names": business_file_names,
            "infrastructure_files": [
                path for path in files
                if re.search(r"(dockerfile|docker-compose|compose\.ya?ml|\.tf$|k8s|kubernetes|helm|chart\.yaml|values\.yaml|\.github/workflows|gitlab-ci|jenkinsfile)", path, re.IGNORECASE)
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
                raise
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object")
        return parsed

    def _normalize_analysis(self, analysis: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        overview = str(analysis.get("overview") or "").strip()
        executive_overview = self._normalize_executive_overview(analysis.get("executive_overview"), payload)
        modules = analysis.get("modules")
        architecture = analysis.get("architecture")

        if not overview:
            raise ValueError("Gemini response missing overview")
        if not isinstance(modules, list):
            raise ValueError("Gemini response missing modules")
        if not isinstance(architecture, dict):
            raise ValueError("Gemini response missing architecture")

        normalized_modules = []
        analysis_evidence = payload.get("analysis_evidence", {})
        evidence_paths = []
        if isinstance(analysis_evidence, dict):
            for key in ("source_files", "infrastructure_files", "business_file_names"):
                values = analysis_evidence.get(key, [])
                if isinstance(values, list):
                    evidence_paths.extend(values)
        known_paths = {
            str(path).replace("\\", "/").lower()
            for path in [*payload.get("file_tree", []), *evidence_paths]
        }
        known_basenames = {
            path.rsplit("/", 1)[-1]
            for path in known_paths
        }
        known_routes = {
            str(route).lower()
            for route in payload.get("api_routes", [])
        }
        readme_evidence = str(payload.get("readme_summary") or "").lower()
        for item in modules:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            purpose = str(item.get("purpose") or item.get("description") or item.get("summary") or "").strip()
            confidence = self._coerce_confidence(item.get("confidence", 80))
            if not name or not purpose or confidence < 50 or self._is_generic_module_name(name):
                continue
            raw_components = self._normalize_string_list(item.get("components"))[:8]
            supported_components = []
            for component in raw_components:
                normalized_component = component.replace("\\", "/").lower().lstrip("./")
                basename = normalized_component.rsplit("/", 1)[-1]
                if (
                    normalized_component in known_paths
                    or basename in known_basenames
                    or normalized_component in known_routes
                    or (normalized_component.startswith("/") and normalized_component in known_routes)
                    or (len(normalized_component) >= 5 and normalized_component in readme_evidence)
                ):
                    supported_components.append(component)
            if not supported_components:
                continue
            evidence = self._normalize_string_list(item.get("evidence"))[:8]
            supported_evidence = [
                reference for reference in evidence
                if reference in raw_components or reference in supported_components
            ]
            normalized_modules.append({
                "name": name,
                "purpose": purpose,
                "description": purpose,
                "capabilities": self._normalize_string_list(item.get("capabilities"))[:8],
                "components": supported_components,
                "evidence": supported_evidence or supported_components,
                "connected_modules": self._normalize_string_list(item.get("connected_modules"))[:8],
                "confidence": confidence,
            })

        if not normalized_modules:
            raise ValueError("Gemini response contained no usable modules")

        normalized_architecture = self._normalize_architecture(architecture)

        return {
            "overview": overview,
            "executive_overview": executive_overview,
            "modules": normalized_modules[:10],
            "architecture": normalized_architecture,
        }

    def _normalize_architecture(self, architecture: Dict[str, Any]) -> Dict[str, Any]:
        unknown = "Unable to confidently determine from repository evidence."
        summary = str(
            architecture.get("architecture_summary")
            or architecture.get("summary")
            or ""
        ).strip()
        architecture_type = str(architecture.get("architecture_type") or "").strip()
        flow = self._normalize_string_list(architecture.get("flow"))
        request_lifecycle = self._normalize_string_list(architecture.get("request_lifecycle"))

        components = []
        raw_components = architecture.get("components", [])
        if isinstance(raw_components, list):
            for item in raw_components:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                responsibility = str(item.get("responsibility") or "").strip()
                input_value = str(item.get("input") or "").strip()
                output = str(item.get("output") or "").strip()
                communicates_with = self._normalize_string_list(item.get("communicates_with"))
                connected_to = self._normalize_string_list(item.get("connected_to"))
                if name and responsibility:
                    components.append({
                        "name": name,
                        "responsibility": responsibility,
                        "input": input_value or unknown,
                        "output": output or unknown,
                        "communicates_with": communicates_with or connected_to or [unknown],
                        "connected_to": connected_to[:8],
                    })

        communication = self._normalize_string_list(architecture.get("communication"))
        deployment = str(architecture.get("deployment") or "").strip()
        sync_path = self._normalize_string_list(architecture.get("sync_path"))
        async_path = self._normalize_string_list(architecture.get("async_path"))

        return {
            "architecture_summary": summary or unknown,
            "summary": summary or unknown,
            "architecture_type": architecture_type or unknown,
            "flow": flow or [unknown],
            "request_lifecycle": request_lifecycle or [unknown],
            "sync_path": sync_path,
            "async_path": async_path,
            "components": components,
            "communication": communication or [unknown],
            "deployment": deployment or unknown,
        }

    def _normalize_string_list(self, value: Any) -> List[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _coerce_confidence(self, value: Any) -> int:
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return 80

    def _is_generic_module_name(self, name: str) -> bool:
        generic = {
            "backend", "frontend", "services", "service", "controllers", "controller",
            "utils", "utilities", "helpers", "components", "pages", "src", "app",
            "api", "routes", "models", "schemas", "lib", "config"
        }
        return name.strip().lower() in generic

    def _normalize_executive_overview(self, data: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._fallback_executive_overview(payload, self._fallback_modules(payload))

        paragraphs = data.get("what_is_this_project", [])
        if isinstance(paragraphs, str):
            paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", paragraphs) if paragraph.strip()]
        if not isinstance(paragraphs, list):
            paragraphs = []

        features = []
        for item in data.get("user_features", []) if isinstance(data.get("user_features"), list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if name and description:
                features.append({"name": name, "description": description})

        use_cases = data.get("typical_use_cases", [])
        if isinstance(use_cases, str):
            use_cases = [use_cases]
        audiences = data.get("who_is_this_for", [])
        if isinstance(audiences, str):
            audiences = [audiences]

        normalized = {
            "what_is_this_project": [str(item).strip() for item in paragraphs if str(item).strip()][:3],
            "why_was_it_built": str(data.get("why_was_it_built") or "").strip(),
            "user_features": features[:8],
            "typical_use_cases": [str(item).strip() for item in use_cases if str(item).strip()][:6] if isinstance(use_cases, list) else [],
            "who_is_this_for": [str(item).strip() for item in audiences if str(item).strip()][:6] if isinstance(audiences, list) else [],
            "why_is_it_valuable": str(data.get("why_is_it_valuable") or "").strip(),
            "one_line_summary": str(data.get("one_line_summary") or "").strip(),
        }

        fallback = self._fallback_executive_overview(payload, self._fallback_modules(payload))
        for key, value in fallback.items():
            if not normalized.get(key):
                normalized[key] = value
        return normalized

    def _fallback_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = payload["metadata"]
        stack = payload["detected_technology_stack"]
        categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
        tech_names = self._category_names(categories)
        modules = self._fallback_modules(payload)

        project_name = metadata.get("full_name") or metadata.get("name") or "This repository"
        description = str(metadata.get("description") or "").strip()
        evidence = payload.get("analysis_evidence", {})
        source_count = evidence.get("source_file_count", 0) if isinstance(evidence, dict) else 0
        detected_technologies = evidence.get("technology_detections", []) if isinstance(evidence, dict) else []
        overview_parts = []
        if description:
            overview_parts.append(f"{project_name} is described as {description}.")
        else:
            overview_parts.append(
                f"The available repository evidence is insufficient to determine the user-facing purpose of {project_name}."
            )
        overview_parts.append(
            f"Analysis found {source_count} source files and {len(detected_technologies)} concrete technology detections."
        )
        overview = " ".join(overview_parts)

        flow = self._fallback_flow(tech_names, payload)
        architecture_type = self._infer_architecture_type(tech_names, payload)
        architecture_summary = self._build_architecture_summary(tech_names, payload)
        request_lifecycle = self._build_request_lifecycle(tech_names, payload)
        sync_path, async_path = self._build_sync_async_paths(tech_names, flow)
        component_cards = [
            {
                "name": step,
                "responsibility": self._fallback_component_responsibility(step),
                "input": self._fallback_component_input(step, tech_names),
                "output": self._fallback_component_output(step, tech_names),
                "communicates_with": self._fallback_component_communications(step, flow),
                "connected_to": [flow[index + 1]] if index + 1 < len(flow) else [],
            }
            for index, step in enumerate(flow)
        ]

        return {
            "overview": overview,
            "executive_overview": self._fallback_executive_overview(payload, modules),
            "modules": modules,
            "architecture": {
                "architecture_summary": architecture_summary,
                "summary": architecture_summary,
                "architecture_type": architecture_type,
                "flow": flow,
                "request_lifecycle": request_lifecycle,
                "sync_path": sync_path,
                "async_path": async_path,
                "components": component_cards,
                "communication": self._fallback_communication(tech_names, payload),
                "deployment": self._fallback_deployment(tech_names, payload),
            },
            "analysis_evidence": payload.get("analysis_evidence", {}),
        }

    def _fallback_executive_overview(self, payload: Dict[str, Any], modules: List[Dict[str, str]]) -> Dict[str, Any]:
        metadata = payload["metadata"]
        project_name = metadata.get("full_name") or metadata.get("name") or "This project"
        description = str(metadata.get("description") or "").strip()
        evidence = payload.get("analysis_evidence", {})
        source_count = evidence.get("source_file_count", 0) if isinstance(evidence, dict) else 0
        observed_summary = (
            f"{project_name} is described as {description}."
            if description
            else f"Available repository evidence is insufficient to determine what {project_name} is intended to do."
        )
        paragraphs = [observed_summary]
        if source_count:
            paragraphs.append(
                f"The repository contains {source_count} source files available for inspection."
            )

        feature_candidates = [
            {"name": module["name"], "description": module["description"]}
            for module in modules
            if module.get("name") and module.get("description") and module.get("evidence")
        ]

        return {
            "what_is_this_project": paragraphs,
            "why_was_it_built": "Repository evidence does not establish why this project was built.",
            "user_features": feature_candidates[:8],
            "typical_use_cases": [],
            "who_is_this_for": [],
            "why_is_it_valuable": "Repository evidence does not establish the project's practical value to users.",
            "one_line_summary": (
                f"{project_name}: {description}"
                if description
                else f"{project_name}: user-facing purpose is not clear from the available repository evidence."
            ),
        }

    def _category_names(self, categories: Dict[str, Any]) -> Dict[str, List[str]]:
        names: Dict[str, List[str]] = {}
        for category, items in categories.items():
            category_names = []
            for item in items or []:
                if isinstance(item, dict) and item.get("name"):
                    category_names.append(str(item["name"]))
                elif isinstance(item, str):
                    category_names.append(item)
            names[category] = category_names
        return names

    def _has_tech(self, tech_names: Dict[str, List[str]], search: str) -> bool:
        return any(search.lower() in item.lower() for items in tech_names.values() for item in items)

    def _find_frontend_component(self, tech_names: Dict[str, List[str]]) -> str | None:
        frontend = [item for item in tech_names.get("frontend", []) if isinstance(item, str)]
        if any("next" in item.lower() for item in frontend):
            return "Next.js Frontend"
        if any("react" == item.lower() or "react" in item.lower() for item in frontend):
            if self._has_tech(tech_names, "vite"):
                return "React + Vite Frontend"
            return "React Frontend"
        if any("vue" in item.lower() for item in frontend):
            return "Vue Frontend"
        if any("svelte" in item.lower() for item in frontend):
            return "Svelte Frontend"
        if any("angular" in item.lower() for item in frontend):
            return "Angular Frontend"
        return None

    def _find_backend_component(self, tech_names: Dict[str, List[str]]) -> str | None:
        backend = [item for item in tech_names.get("backend", []) if isinstance(item, str)]
        if any("fastapi" in item.lower() for item in backend):
            return "FastAPI Service"
        if any("express" in item.lower() for item in backend):
            return "Express API"
        if any("nest" in item.lower() for item in backend):
            return "NestJS Service"
        if any("flask" in item.lower() for item in backend):
            return "Flask Service"
        if any("django" in item.lower() for item in backend):
            return "Django Application"
        if any("spring" in item.lower() for item in backend):
            return "Spring Boot Service"
        if any("gin" in item.lower() for item in backend):
            return "Gin Service"
        if any("go" in item.lower() for item in backend):
            return "Go Backend Service"
        return None

    def _infer_deployment_type(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> str:
        if self._has_tech(tech_names, "lambda") or self._has_tech(tech_names, "serverless"):
            return "Serverless"
        if self._has_tech(tech_names, "eks") or self._has_tech(tech_names, "kubernetes"):
            return "Kubernetes"
        if self._has_tech(tech_names, "ecs"):
            return "ECS"
        if self._has_tech(tech_names, "docker"):
            return "Docker Container"
        if self._has_tech(tech_names, "terraform") or payload.get("code_signals", {}).get("infrastructure_files"):
            return "Terraform"
        if self._has_tech(tech_names, "aws") or self._has_tech(tech_names, "gcp") or self._has_tech(tech_names, "azure"):
            return "Cloud Native"
        return "Unable to confidently determine from repository evidence."

    def _infer_architecture_type(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> str:
        if self._has_tech(tech_names, "lambda") or self._has_tech(tech_names, "serverless"):
            return "Serverless"
        if self._has_tech(tech_names, "eks") or self._has_tech(tech_names, "kubernetes") or self._has_tech(tech_names, "ecs"):
            if self._has_tech(tech_names, "sqs") or self._has_tech(tech_names, "sns"):
                return "Event-driven"
            return "Microservice"
        if self._has_tech(tech_names, "sqs") or self._has_tech(tech_names, "sns"):
            return "Event-driven"
        frontend_present = bool(tech_names.get("frontend"))
        backend_present = bool(tech_names.get("backend"))
        database_present = bool(tech_names.get("database"))
        top_level = [str(name).lower() for name in payload.get("top_level_modules", [])]
        if frontend_present and backend_present:
            return "Layered"
        if backend_present and database_present:
            return "Layered"
        if backend_present:
            return "Monolith"
        if "frontend" in top_level and "backend" in top_level:
            return "Layered"
        if "api" in top_level and database_present:
            return "Layered"
        return "Unable to confidently determine from repository evidence."

    def _build_architecture_summary(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> str:
        parts: List[str] = []
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)
        deployment = self._infer_deployment_type(tech_names, payload)
        if frontend:
            parts.append(f"The repository includes a {frontend} as the user-facing application layer.")
        elif payload.get("top_level_modules") and any(str(dir_name).lower() == "frontend" for dir_name in payload.get("top_level_modules", [])):
            parts.append("The repository includes a frontend application layer based on the top-level project structure.")
        if backend:
            parts.append(f"Backend logic runs in a {backend} that handles incoming application requests.")
        elif self._has_tech(tech_names, "fastapi") or self._has_tech(tech_names, "express") or self._has_tech(tech_names, "flask") or self._has_tech(tech_names, "django"):
            parts.append("Backend application code exposes HTTP APIs for request processing.")
        if self._has_tech(tech_names, "api gateway"):
            parts.append("Requests are routed through an API Gateway layer before reaching service logic.")
        if self._has_tech(tech_names, "lambda"):
            parts.append("AWS Lambda functions host the serverless compute portion of the application.")
        if self._has_tech(tech_names, "sqs") or self._has_tech(tech_names, "sns"):
            parts.append("Asynchronous queue and pub/sub patterns connect services and background processing.")
        if self._has_tech(tech_names, "dynamodb"):
            parts.append("DynamoDB provides the managed persistence layer for application data.")
        elif self._has_tech(tech_names, "s3"):
            parts.append("S3 is used for object storage and static content within the repository workflow.")
        elif self._has_tech(tech_names, "postgresql"):
            parts.append("PostgreSQL provides relational storage for application data.")
        elif self._has_tech(tech_names, "mysql"):
            parts.append("MySQL provides relational storage for application data.")
        if deployment and deployment != "Unable to confidently determine from repository evidence.":
            parts.append(f"Deployment is inferred as {deployment} based on the repository's infrastructure evidence.")
        return " ".join(parts) if parts else "The repository architecture is inferred from detected technology and infrastructure evidence."

    def _build_request_lifecycle(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> List[str]:
        lifecycle: List[str] = []
        top_level = [str(name).lower() for name in payload.get("top_level_modules", [])]
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)

        if frontend:
            lifecycle.append(f"The user interacts with the {frontend} to start the workflow.")
        elif "frontend" in top_level:
            lifecycle.append("The user interacts with the frontend application to start the workflow.")

        if self._has_tech(tech_names, "api gateway"):
            lifecycle.append("The request passes through API Gateway before reaching application services.")
        elif backend:
            lifecycle.append(f"The request reaches the {backend} over HTTP.")
        elif self._has_tech(tech_names, "fastapi") or self._has_tech(tech_names, "express") or self._has_tech(tech_names, "flask") or self._has_tech(tech_names, "django"):
            lifecycle.append("The request reaches an HTTP API endpoint implemented by repository backend code.")

        if self._has_tech(tech_names, "lambda"):
            lifecycle.append("AWS Lambda executes the detected serverless business logic.")

        if self._has_tech(tech_names, "sqs"):
            lifecycle.append("A job message is published to SQS for background processing.")
        if self._has_tech(tech_names, "sns"):
            lifecycle.append("An SNS notification is broadcast to downstream services.")

        if self._has_tech(tech_names, "dynamodb"):
            lifecycle.append("The application reads from or writes to DynamoDB for persistence.")
        elif self._has_tech(tech_names, "s3"):
            lifecycle.append("The workflow stores or retrieves objects from S3.")
        elif self._has_tech(tech_names, "postgresql"):
            lifecycle.append("The workflow reads from or writes to PostgreSQL storage.")
        elif self._has_tech(tech_names, "mysql"):
            lifecycle.append("The workflow reads from or writes to MySQL storage.")

        if not lifecycle:
            return ["Unable to confidently determine from repository evidence."]

        if lifecycle[-1] != "The final response is returned to the caller after the detected processing completes." and "response" not in lifecycle[-1].lower():
            lifecycle.append("The final response is returned to the caller after the detected processing completes.")
        return lifecycle

    def _fallback_modules(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        candidates: List[Dict[str, str]] = []
        paths = payload.get("analysis_evidence", {}).get("business_file_names", [])
        if not isinstance(paths, list):
            return candidates

        module_rules = [
            ("Authentication", re.compile(r"(auth|login|identity|session)", re.I),
             "Implements authentication-related behavior evidenced by repository source paths."),
            ("File Upload", re.compile(r"(upload|multipart)", re.I),
             "Implements file upload behavior evidenced by repository source paths."),
            ("File Management", re.compile(r"(file|document|drive)", re.I),
             "Implements file or document management behavior evidenced by repository source paths."),
            ("File Storage", re.compile(r"(storage|bucket|s3)", re.I),
             "Implements storage-related behavior evidenced by repository source paths."),
            ("Commerce", re.compile(r"(payment|checkout|cart|product|order)", re.I),
             "Implements commerce behavior evidenced by repository source paths."),
            ("Messaging", re.compile(r"(chat|message|notification)", re.I),
             "Implements messaging behavior evidenced by repository source paths."),
            ("Background Processing", re.compile(r"(worker|queue|job)", re.I),
             "Implements background processing evidenced by repository source paths."),
        ]
        for name, pattern, purpose in module_rules:
            matches = list(dict.fromkeys(
                str(path) for path in paths if pattern.search(str(path))
            ))[:8]
            if not matches:
                continue
            candidates.append({
                "name": name,
                "purpose": purpose,
                "description": purpose,
                "capabilities": [],
                "components": matches,
                "evidence": matches,
                "connected_modules": [],
                "confidence": 70,
            })

        return candidates[:10]

    def _fallback_capabilities_for_module(self, name: str) -> List[str]:
        lowered = name.lower()
        if "auth" in lowered:
            return ["Manage user identity", "Support protected access", "Connect sign-in state to the application"]
        if "upload" in lowered or "storage" in lowered:
            return ["Store user data", "Track saved content", "Connect stored data to application workflows"]
        if "worker" in lowered or "processing" in lowered:
            return ["Handle background tasks", "Process queued work", "Separate long-running work from user actions"]
        if "infrastructure" in lowered:
            return ["Define deployment resources", "Organize environment setup", "Support repeatable operations"]
        return ["Provide a major project responsibility", "Coordinate related application behavior", "Support the user workflow"]

    def _fallback_components_for_module(self, name: str, payload: Dict[str, Any]) -> List[str]:
        files = payload.get("file_tree", [])
        tokens = [part for part in re.split(r"\s+|[-_]", name.lower()) if len(part) > 2]
        matches = []
        for path in files:
            lower = str(path).lower()
            if any(token in lower for token in tokens):
                matches.append(str(path))
            if len(matches) >= 6:
                break
        return matches

    def _fallback_flow(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> List[str]:
        flow = ["User"]
        frontend = self._find_frontend_component(tech_names)
        backend = self._find_backend_component(tech_names)
        top_level = [str(name).lower() for name in payload.get("top_level_modules", [])]

        if frontend:
            flow.append(frontend)
        elif "frontend" in top_level:
            flow.append("Frontend")

        if self._has_tech(tech_names, "api gateway"):
            flow.append("API Gateway")
        elif backend:
            flow.append(backend)
        elif self._has_tech(tech_names, "fastapi") or self._has_tech(tech_names, "express") or self._has_tech(tech_names, "nest") or self._has_tech(tech_names, "flask") or self._has_tech(tech_names, "django"):
            flow.append("HTTP API")
        elif "backend" in top_level or "server" in top_level or "api" in top_level:
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
        elif self._has_tech(tech_names, "eks") or self._has_tech(tech_names, "kubernetes"):
            flow.append("Kubernetes Pod")
        elif self._has_tech(tech_names, "docker"):
            flow.append("Docker Container")

        if self._has_tech(tech_names, "postgresql"):
            flow.append("PostgreSQL")
        elif self._has_tech(tech_names, "mysql"):
            flow.append("MySQL")
        elif self._has_tech(tech_names, "mongodb"):
            flow.append("MongoDB")
        elif self._has_tech(tech_names, "redis"):
            flow.append("Redis")
        elif self._has_tech(tech_names, "dynamodb"):
            flow.append("DynamoDB")
        elif self._has_tech(tech_names, "s3"):
            flow.append("S3")
        elif self._has_tech(tech_names, "cloudwatch"):
            flow.append("CloudWatch")
        elif self._has_tech(tech_names, "database") and "Storage" not in flow:
            flow.append("Storage")

        deployment = self._infer_deployment_type(tech_names, payload)
        if flow[-1] != "Response":
            flow.append("Response")

        seen = set()
        unique_flow = []
        for step in flow:
            if step not in seen:
                seen.add(step)
                unique_flow.append(step)
        return unique_flow

    def _fallback_component_responsibility(self, name: str) -> str:
        lowered = name.lower()
        if "user" in lowered:
            return "Initiates the workflow and receives the final outcome."
        if "frontend" in lowered or "react" in lowered or "next" in lowered:
            return "Handles user interaction and sends application requests to the backend."
        if "api gateway" in lowered:
            return "Routes and secures incoming API requests before they reach service logic."
        if "fastapi" in lowered or "express" in lowered or "flask" in lowered or "django" in lowered:
            return "Processes HTTP requests and coordinates downstream services or persistence."
        if "lambda" in lowered:
            return "Executes serverless business logic in response to API or queue events."
        if "sqs" in lowered or "sns" in lowered:
            return "Manages asynchronous event delivery for background processing." 
        if "dynamodb" in lowered:
            return "Stores and retrieves application data in a managed NoSQL table."
        if "postgresql" in lowered or "mysql" in lowered or "mongodb" in lowered or "redis" in lowered:
            return "Provides persistent storage for the application's data model."
        if "s3" in lowered:
            return "Holds application objects, assets, or processed output in object storage."
        if "terraform" in lowered or "docker" in lowered or "kubernetes" in lowered or "ecs" in lowered:
            return "Represents deployment infrastructure rather than runtime execution flow."
        return "Performs a specific runtime responsibility inferred from repository architecture evidence."

    def _fallback_communication(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> List[str]:
        communication = []
        if payload.get("api_routes") or self._has_tech(tech_names, "fastapi") or self._has_tech(tech_names, "express") or self._has_tech(tech_names, "flask") or self._has_tech(tech_names, "django"):
            communication.append("REST APIs: Components communicate through HTTP endpoints exposed by the backend.")
        if self._has_tech(tech_names, "sqs"):
            communication.append("SQS: Queued messages hand off work from request processing to background workers.")
        if self._has_tech(tech_names, "sns"):
            communication.append("SNS: Pub/sub messages broadcast events to downstream services.")
        if self._has_tech(tech_names, "websocket") or self._has_tech(tech_names, "socket.io"):
            communication.append("WebSockets: Real-time updates are exchanged over bidirectional sockets.")
        if self._has_tech(tech_names, "dynamodb") or self._has_tech(tech_names, "postgresql") or self._has_tech(tech_names, "mysql") or self._has_tech(tech_names, "mongodb") or self._has_tech(tech_names, "redis"):
            communication.append("Database access: Runtime components communicate with managed persistence services.")
        if not communication:
            communication.append("Unable to confidently determine from repository evidence.")
        return communication

    def _build_sync_async_paths(self, tech_names: Dict[str, List[str]], flow: List[str]) -> tuple[list[str], list[str]]:
        sync_path: List[str] = []
        async_path: List[str] = []

        if "User" in flow and any(self._has_tech(tech_names, key) for key in ["react", "next", "vue", "svelte", "angular"]):
            sync_path.append("User")
            sync_path.append(self._find_frontend_component(tech_names) or "Frontend")
        elif "User" in flow:
            sync_path.append("User")

        if "API Gateway" in flow:
            sync_path.append("API Gateway")
        elif any(self._has_tech(tech_names, key) for key in ["fastapi", "express", "flask", "django", "nest"]):
            sync_path.append(self._find_backend_component(tech_names) or "HTTP API")

        if self._has_tech(tech_names, "lambda"):
            sync_path.append("AWS Lambda")

        if self._has_tech(tech_names, "sqs") or self._has_tech(tech_names, "sns"):
            async_path.append("SQS") if self._has_tech(tech_names, "sqs") else None
            async_path.append("SNS") if self._has_tech(tech_names, "sns") else None
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

    def _fallback_component_input(self, name: str, tech_names: Dict[str, List[str]]) -> str:
        lowered = name.lower()
        if "frontend" in lowered or "react" in lowered or "next" in lowered:
            return "User actions and browser events"
        if "api gateway" in lowered:
            return "HTTP requests from client or frontend"
        if "fastapi" in lowered or "express" in lowered or "flask" in lowered or "django" in lowered or "http api" in lowered:
            return "HTTP request payload"
        if "lambda" in lowered:
            return "API events or queue messages"
        if "sqs" in lowered or "sns" in lowered:
            return "Event messages from application services"
        if "dynamodb" in lowered or "postgresql" in lowered or "mysql" in lowered or "mongodb" in lowered or "redis" in lowered:
            return "Data queries and persistence requests"
        if "s3" in lowered:
            return "Object write/read requests"
        return "Validated runtime input based on detected component behavior."

    def _fallback_component_output(self, name: str, tech_names: Dict[str, List[str]]) -> str:
        lowered = name.lower()
        if "frontend" in lowered or "react" in lowered or "next" in lowered:
            return "API calls and user interface updates"
        if "api gateway" in lowered:
            return "Forwarded requests to backend services"
        if "fastapi" in lowered or "express" in lowered or "flask" in lowered or "django" in lowered or "http api" in lowered:
            return "Backend responses or queued work requests"
        if "lambda" in lowered:
            return "Function results or queue/notification events"
        if "sqs" in lowered or "sns" in lowered:
            return "Queued messages to workers or subscribers"
        if "dynamodb" in lowered or "postgresql" in lowered or "mysql" in lowered or "mongodb" in lowered or "redis" in lowered:
            return "Stored or retrieved persistence results"
        if "s3" in lowered:
            return "Stored objects or static content links"
        return "Detected runtime output based on component activity."

    def _fallback_component_communications(self, name: str, flow: List[str]) -> List[str]:
        lowered = name.lower()
        communications: List[str] = []
        if "frontend" in lowered or "react" in lowered or "next" in lowered:
            communications.append("API Gateway")
            communications.append("Backend Service")
        if "api gateway" in lowered:
            communications.append("Frontend")
            communications.append("Backend Service")
        if "fastapi" in lowered or "express" in lowered or "flask" in lowered or "django" in lowered or "http api" in lowered:
            communications.extend(["Frontend", "DynamoDB", "S3", "SQS", "SNS"])
        if "lambda" in lowered:
            communications.extend(["API Gateway", "SQS", "SNS", "DynamoDB", "S3"])
        if "sqs" in lowered or "sns" in lowered:
            communications.append("Worker")
            communications.append("Backend Service")
        if "dynamodb" in lowered or "postgresql" in lowered or "mysql" in lowered or "mongodb" in lowered or "redis" in lowered:
            communications.append("Backend Service")
            communications.append("Lambda")
        if "s3" in lowered:
            communications.append("Backend Service")
            communications.append("Lambda")
        if not communications:
            idx = flow.index(name) if name in flow else -1
            if idx != -1:
                if idx > 0:
                    communications.append(flow[idx - 1])
                if idx + 1 < len(flow):
                    communications.append(flow[idx + 1])
        return list(dict.fromkeys([item for item in communications if item]))

    def _fallback_deployment(self, tech_names: Dict[str, List[str]], payload: Dict[str, Any]) -> str:
        infrastructure_files = payload.get("code_signals", {}).get("infrastructure_files", [])
        names = " ".join(tech_names.get("infrastructure", []) + tech_names.get("devops", []) + tech_names.get("cloud", []) + tech_names.get("tooling", []))
        evidence = " ".join(str(path) for path in infrastructure_files).lower()
        if self._has_tech(tech_names, "terraform") or ".tf" in evidence:
            if self._has_tech(tech_names, "lambda"):
                return "Serverless deployment on AWS Lambda with Terraform provisioning."
            if self._has_tech(tech_names, "ecs"):
                return "Container-based deployment on ECS with Terraform infrastructure definitions."
            if self._has_tech(tech_names, "eks") or self._has_tech(tech_names, "kubernetes"):
                return "Kubernetes deployment defined through Terraform manifests."
            return "Terraform-provisioned infrastructure is used for deployment."
        if self._has_tech(tech_names, "docker") or "docker" in evidence:
            return "Container-based deployment is supported by Docker configuration evidence."
        if self._has_tech(tech_names, "serverless") or self._has_tech(tech_names, "lambda"):
            return "Serverless deployment is supported by AWS Lambda evidence."
        if self._has_tech(tech_names, "aws") or self._has_tech(tech_names, "gcp") or self._has_tech(tech_names, "azure"):
            return "Cloud-native deployment is indicated by cloud service detection."
        return "Unable to confidently determine from repository evidence."

    def architecture_summary_text(self, analysis: Dict[str, Any]) -> str:
        architecture = analysis.get("architecture", {})
        summary = str(architecture.get("architecture_summary") or architecture.get("summary") or "").strip()
        flow = architecture.get("flow", [])
        lifecycle = architecture.get("request_lifecycle", [])
        parts = [summary] if summary else []
        if flow:
            parts.append("Flow:\n" + "\n↓\n".join(str(step) for step in flow))
        if lifecycle:
            parts.append("Request Lifecycle:\n" + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(lifecycle)))
        return "\n\n".join(parts)
        if flow:
            return f"{summary}\n\nFlow:\n" + "\n↓\n".join(str(step) for step in flow)
        return summary

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

        repo_name = kwargs.get("repo_name") or (args[0] if args else "Repository")
        description = kwargs.get("description") or ""
        return self._fallback_analysis({
            "metadata": {"full_name": repo_name, "description": description},
            "readme_summary": kwargs.get("readme", ""),
            "detected_technology_stack": kwargs.get("technologies", {}),
            "repository_structure": kwargs.get("repo_structure", []),
            "top_level_modules": [],
            "detected_cloud_infrastructure": {},
        })["overview"]

    def generate_modules(self, *args: Any, **kwargs: Any) -> List[Dict[str, str]]:
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
            "top_level_modules": [node.get("name") for node in structure if isinstance(node, dict) and node.get("type") == "folder"],
            "detected_cloud_infrastructure": {},
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

        analysis = self._fallback_analysis({
            "metadata": {"full_name": kwargs.get("repo_name", "Repository")},
            "readme_summary": kwargs.get("readme", ""),
            "detected_technology_stack": kwargs.get("technologies", {}),
            "repository_structure": kwargs.get("repo_structure", []),
            "top_level_modules": [],
            "detected_cloud_infrastructure": {},
        })
        return self.architecture_summary_text(analysis)

    def generate_ai_insights(self, *args: Any, **kwargs: Any) -> List[str]:
        return []
