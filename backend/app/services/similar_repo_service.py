import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from app.services.github_service import GitHubService
from app.services.repository_discovery import expand_query, normalize_query

logger = logging.getLogger(__name__)

SIMILARITY_WEIGHTS = {
    "domain": 0.30,
    "modules": 0.25,
    "technology": 0.15,
    "architecture": 0.15,
    "structure": 0.05,
    "metadata": 0.05,
    "quality": 0.05,
}
MIN_SIMILARITY = 25
MAX_RESULTS = 5

CONCEPT_ALIASES = {
    "file management": {"file", "document", "file management", "file manager", "file browser", "file explorer"},
    "storage": {"storage", "cloud storage", "object storage", "file storage", "drive", "bucket"},
    "file sharing": {"sharing", "file sharing", "document sharing", "share"},
    "upload": {"upload", "file upload", "multipart upload"},
    "download": {"download", "file download"},
    "authentication": {"authentication", "auth", "login", "identity", "oauth", "jwt"},
    "product catalog": {"product catalog", "products", "catalog"},
    "cart": {"cart", "shopping cart", "basket"},
    "checkout": {"checkout"},
    "payments": {"payment", "payments", "billing", "stripe"},
    "orders": {"order", "orders", "order management"},
    "messaging": {"chat", "chat app", "chat application", "messaging", "message", "realtime chat", "instant messaging"},
    "analytics": {"analytics", "metrics", "reporting", "dashboard"},
    "content management": {"cms", "content management", "publishing", "blog"},
    "infrastructure management": {"infrastructure management", "devops", "deployment", "operations"},
    "ecommerce": {"ecommerce", "e commerce", "e-commerce", "online store", "shopping platform", "marketplace"},
    "devops": {"devops", "deployment dashboard", "infrastructure dashboard", "kubernetes dashboard"},
}

FUNCTIONAL_PATH_RULES = {
    "authentication": re.compile(r"(auth|login|identity|session|oauth)", re.I),
    "upload": re.compile(r"(upload|multipart)", re.I),
    "download": re.compile(r"(download|export)", re.I),
    "file management": re.compile(r"(file|document|drive|browser|explorer)", re.I),
    "file sharing": re.compile(r"(share|sharing|public-link)", re.I),
    "storage": re.compile(r"(storage|bucket|s3|object-store)", re.I),
    "product catalog": re.compile(r"(product|catalog|inventory)", re.I),
    "cart": re.compile(r"(cart|basket)", re.I),
    "checkout": re.compile(r"(checkout)", re.I),
    "payments": re.compile(r"(payment|billing|stripe)", re.I),
    "orders": re.compile(r"(order|fulfillment)", re.I),
    "messaging": re.compile(r"(chat|message|conversation|notification)", re.I),
    "analytics": re.compile(r"(analytics|metrics|report|dashboard)", re.I),
    "background processing": re.compile(r"(worker|queue|job|task)", re.I),
}

MEANINGFUL_TECHNOLOGIES = {
    "react", "vue", "angular", "svelte", "next.js", "nuxt",
    "fastapi", "express", "django", "flask", "spring", "nestjs",
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "dynamodb",
    "docker", "kubernetes", "terraform", "aws", "azure", "gcp",
    "s3", "graphql", "grpc", "rabbitmq", "kafka",
}

class SimilarRepoService:
    def __init__(self, github_service: GitHubService) -> None:
        self.github_service = github_service

    def find_similar_repositories(
        self,
        metadata: dict | None,
        stack: dict | None,
        readme: str = "",
        stats: dict | None = None,
        limit: int = 8,
        analysis_context: dict | None = None,
        repository_structure: list[dict] | None = None,
    ) -> list[dict]:
        try:
            metadata = metadata if isinstance(metadata, dict) else {}
            stack = stack if isinstance(stack, dict) else {}
            readme = readme if isinstance(readme, str) else str(readme or "")
            analysis_context = analysis_context if isinstance(analysis_context, dict) else {}
            repository_structure = repository_structure if isinstance(repository_structure, list) else []
            if isinstance(stats, dict) and stats.get("files") is not None:
                logger.debug("Creating similarity profile from %s scanned files", stats.get("files"))

            current_identifiers = self._repository_identifiers(metadata)
            fingerprint = self._build_fingerprint(
                metadata=metadata,
                stack=stack,
                readme=readme,
                analysis_context=analysis_context,
                repository_structure=repository_structure,
            )
            if not fingerprint.get("domain_terms") and not fingerprint.get("module_terms"):
                logger.info("Skipping similar repository search: no functional profile evidence")
                return []

            queries = self._build_search_queries(fingerprint)
            candidates = self._search_github(queries, per_query=30)
            preliminary = self._rank_candidates(
                candidates=candidates,
                fingerprint=fingerprint,
                current_full_name=current_identifiers,
            )
            self._add_candidate_tree_evidence(candidates, preliminary[:10])
            ranked = self._rank_candidates(
                candidates=candidates,
                fingerprint=fingerprint,
                current_full_name=current_identifiers,
            )
            return ranked[:min(max(0, limit), MAX_RESULTS)]
        except Exception as exc:
            logger.exception("Similar repository generation failed: %s", exc)
            return []

    def _minimal_fingerprint(self, metadata: dict, stack: dict, readme: str) -> dict:
        fallback_terms = self._keywords(
            " ".join(filter(None, [metadata.get("description"), metadata.get("name"), readme])),
            max_terms=8,
        )
        technology_terms = self._extract_technology_terms_from_stack(stack, metadata)
        return {
            "project_type_terms": fallback_terms,
            "architecture_terms": [],
            "technology_terms": technology_terms,
            "module_terms": fallback_terms,
            "structure_terms": [],
            "domain_terms": fallback_terms,
            "topics": [str(topic).lower() for topic in metadata.get("topics", []) if isinstance(topic, str) and topic],
            "language": str(metadata.get("language") or metadata.get("primary_language") or "").lower(),
        }

    def _build_search_queries(self, fingerprint: dict) -> list[str]:
        if not isinstance(fingerprint, dict):
            return []

        domain_phrases = [
            str(term) for term in fingerprint.get("domain_phrases", [])
            if str(term).strip()
        ][:3]
        module_names = [
            str(term) for term in fingerprint.get("modules", [])
            if str(term).strip()
        ][:3]
        topics = [
            str(topic).replace(" ", "-").lower()
            for topic in fingerprint.get("topics", [])
            if str(topic).strip()
        ][:2]
        queries: list[str] = []

        if domain_phrases:
            queries.append(" OR ".join(f'"{term}"' for term in domain_phrases[:3]))
        functional_modules = [
            module for module in module_names
            if module.lower() not in {"frontend", "backend", "api", "database"}
        ]
        if functional_modules:
            queries.append(" ".join(f'"{term}"' for term in functional_modules[:3]))
        if topics:
            queries.append(" ".join(f"topic:{topic}" for topic in topics))

        return list(dict.fromkeys(" ".join(query.split()) for query in queries if query))[:3]

    def _search_github(self, queries: list[str], per_query: int) -> list[dict]:
        merged: dict[int, dict] = {}
        if not isinstance(queries, list) or not queries:
            return []

        headers = {}
        if self.github_service is not None and hasattr(self.github_service, "_headers"):
            headers = self.github_service._headers()
        with httpx.Client(headers=headers, timeout=20) as client:
            for query in queries:
                try:
                    response = client.get(
                        "https://api.github.com/search/repositories",
                        params={
                            "q": str(query),
                            "per_page": per_query,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json() if hasattr(response, "json") else {}
                    for item in payload.get("items", []) if isinstance(payload, dict) else []:
                        repo_id = item.get("id") if isinstance(item, dict) else None
                        if repo_id is not None and repo_id not in merged:
                            merged[repo_id] = item
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("GitHub similar repository search failed for query %r: %s", query, exc)

        return list(merged.values())

    def _rank_candidates(
        self,
        candidates: list[dict],
        fingerprint: dict,
        current_full_name: set[str] | str,
    ) -> list[dict]:
        deduped: dict[str, dict] = {}
        seen_identifiers: set[str] = set()
        if not isinstance(fingerprint, dict):
            fingerprint = {}
        current_identifiers = (
            current_full_name
            if isinstance(current_full_name, set)
            else {str(current_full_name).strip().lower()}
        )

        for candidate in candidates or []:
            if not isinstance(candidate, dict):
                continue

            full_name = self._candidate_full_name(candidate)
            identifiers = self._repository_identifiers(candidate)
            if not full_name or identifiers & current_identifiers or identifiers & seen_identifiers:
                continue
            normalized_name = full_name.lower().strip("/")
            seen_identifiers.update(identifiers)

            try:
                candidate_profile = self._build_candidate_profile(candidate)
                scores = self._similarity_signals(fingerprint, candidate_profile, candidate)
                similarity = round(sum(
                    scores[key] * weight for key, weight in SIMILARITY_WEIGHTS.items()
                ))

                if (
                    similarity < MIN_SIMILARITY
                    or (scores["domain"] < 15 and scores["modules"] < 20)
                ):
                    continue

                shared_technologies = self._shared_concepts(
                    fingerprint.get("technology_terms", []),
                    candidate_profile.get("technology_terms", []),
                )[:6]
                shared_modules = self._shared_concepts(
                    fingerprint.get("modules", []),
                    candidate_profile.get("modules", []),
                )[:6]
                shared_architecture = self._shared_concepts(
                    fingerprint.get("architecture_terms", []),
                    candidate_profile.get("architecture_terms", []),
                )[:4]
                shared_domain = self._shared_concepts(
                    fingerprint.get("domain_terms", []),
                    candidate_profile.get("domain_terms", []),
                )[:5]

                deduped[normalized_name] = self._format_recommendation(
                    candidate=candidate,
                    similarity=similarity,
                    candidate_profile=candidate_profile,
                    shared_technologies=shared_technologies,
                    shared_modules=shared_modules,
                    shared_architecture=shared_architecture,
                    shared_domain=shared_domain,
                    scores=scores,
                )
            except Exception as exc:
                logger.warning("Failed to rank candidate %s: %s", full_name, exc)

        return sorted(
            deduped.values(),
            key=lambda item: (
                item["similarity"],
                item.get("similarity_breakdown", {}).get("domain", 0),
                item.get("similarity_breakdown", {}).get("modules", 0),
            ),
            reverse=True,
        )

    def _similarity_signals(self, source: dict, target: dict, candidate: dict) -> dict[str, float]:
        return {
            "domain": self._concept_overlap(source.get("domain_terms", []), target.get("domain_terms", [])),
            "modules": self._concept_overlap(source.get("modules", []), target.get("modules", [])),
            "technology": self._concept_overlap(source.get("technology_terms", []), target.get("technology_terms", [])),
            "architecture": self._concept_overlap(source.get("architecture_terms", []), target.get("architecture_terms", [])),
            "structure": self._concept_overlap(source.get("structure_terms", []), target.get("structure_terms", [])),
            "metadata": self._concept_overlap(source.get("metadata_terms", []), target.get("metadata_terms", [])),
            "quality": self._quality_score(candidate),
        }

    def _concept_overlap(self, source: list[str], target: list[str]) -> float:
        source_concepts = {self._canonical_concept(item) for item in source if item}
        target_concepts = {self._canonical_concept(item) for item in target if item}
        source_concepts.discard("")
        target_concepts.discard("")
        if not source_concepts or not target_concepts:
            return 0.0
        exact_matches = source_concepts & target_concepts
        related_matches = 0.0
        unmatched_targets = target_concepts - exact_matches
        for source_concept in source_concepts - exact_matches:
            related = next(
                (
                    target_concept
                    for target_concept in unmatched_targets
                    if self._concepts_are_related(source_concept, target_concept)
                ),
                None,
            )
            if related:
                related_matches += 0.5
                unmatched_targets.remove(related)
        intersection = len(exact_matches) + related_matches
        union = len(source_concepts) + len(target_concepts) - intersection
        return round(100 * intersection / union, 2) if union else 0.0

    def _concepts_are_related(self, first: str, second: str) -> bool:
        related_groups = (
            {"file management", "storage", "file sharing", "upload", "download"},
            {"product catalog", "cart", "checkout", "payments", "orders"},
            {"messaging", "analytics"},
        )
        return any(first in group and second in group for group in related_groups)

    def _canonical_concept(self, value: str) -> str:
        normalized = normalize_query(value)
        for canonical, aliases in CONCEPT_ALIASES.items():
            if normalized == canonical or normalized in {
                normalize_query(alias) for alias in aliases
            }:
                return canonical
        related_expansions = set(expand_query(normalized))
        for canonical, aliases in CONCEPT_ALIASES.items():
            if related_expansions & {
                normalize_query(alias) for alias in aliases
            }:
                return canonical
        return normalized

    def _shared_concepts(self, source: list[str], target: list[str]) -> list[str]:
        target_by_canonical = {
            self._canonical_concept(value): value
            for value in target if value
        }
        shared = []
        for value in source:
            canonical = self._canonical_concept(value)
            if canonical in target_by_canonical and canonical not in {
                self._canonical_concept(item) for item in shared
            }:
                shared.append(str(value).strip().title())
        return shared

    def _quality_score(self, candidate: dict) -> float:
        stars = self._safe_int(candidate.get("stargazers_count"), candidate.get("stars"))
        forks = self._safe_int(candidate.get("forks_count"), candidate.get("forks"))
        star_signal = min(70.0, 20 * math.log10(stars + 1)) if stars else 0.0
        fork_signal = min(30.0, 10 * math.log10(forks + 1)) if forks else 0.0
        return min(100.0, star_signal + fork_signal)

    def _repository_identifiers(self, repository: dict) -> set[str]:
        identifiers: set[str] = set()
        for key in ("full_name", "fullName", "html_url", "url", "repo_url"):
            value = repository.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            normalized = value.strip().lower().rstrip("/")
            normalized = re.sub(r"^https?://(www\.)?github\.com/", "", normalized)
            normalized = normalized.removesuffix(".git")
            if normalized:
                identifiers.add(normalized)

        full_name = self._candidate_full_name(repository).strip().lower().rstrip("/")
        if full_name:
            identifiers.add(full_name.removesuffix(".git"))
        return identifiers

    def _add_candidate_tree_evidence(self, candidates: list[dict], ranked: list[dict]) -> None:
        fetch_tree = getattr(self.github_service, "_fetch_candidate_tree", None)
        if not callable(fetch_tree):
            return
        candidate_by_name = {
            self._candidate_full_name(candidate).lower(): candidate
            for candidate in candidates
            if isinstance(candidate, dict)
        }
        selected = []
        for recommendation in ranked:
            full_name = str(recommendation.get("full_name") or "").lower()
            candidate = candidate_by_name.get(full_name)
            if candidate is not None and "_tree_paths" not in candidate:
                selected.append((full_name, candidate))

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fetch_tree, candidate): (full_name, candidate)
                for full_name, candidate in selected
            }
            for future in as_completed(futures):
                full_name, candidate = futures[future]
                try:
                    candidate["_tree_paths"] = future.result()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("Could not inspect similar repository tree %s: %s", full_name, exc)

    def _format_recommendation(
        self,
        candidate: dict,
        similarity: int,
        candidate_profile: dict,
        shared_technologies: list[str],
        shared_modules: list[str],
        shared_architecture: list[str],
        shared_domain: list[str],
        scores: dict[str, float],
    ) -> dict:
        candidate = candidate if isinstance(candidate, dict) else {}
        owner = candidate.get("owner", {})
        owner_name = owner.get("login") if isinstance(owner, dict) else candidate.get("owner", "")
        name = str(candidate.get("name") or "")
        full_name = str(candidate.get("full_name") or "") or f"{owner_name}/{name}".strip("/")
        url = candidate.get("html_url") or candidate.get("url") or f"https://github.com/{full_name}"
        stars = self._safe_int(candidate.get("stargazers_count"), candidate.get("stars"))
        language = str(candidate.get("language") or "")
        topics = candidate.get("topics") if isinstance(candidate.get("topics"), list) else []

        reason = self._build_reason(
            shared_technologies=shared_technologies,
            shared_modules=shared_modules,
            shared_architecture=shared_architecture,
            shared_domain=shared_domain,
        )

        return {
            "name": name,
            "owner": owner_name,
            "fullName": full_name,
            "full_name": full_name,
            "url": str(url or ""),
            "html_url": str(url or ""),
            "description": str(candidate.get("description") or ""),
            "stars": stars,
            "forks": self._safe_int(candidate.get("forks_count"), candidate.get("forks")),
            "language": language,
            "topics": [str(topic) for topic in topics if str(topic).strip()],
            "similarity": max(0, min(100, similarity)),
            "reason": reason,
            "project_type": self._display_value(candidate_profile.get("domain_terms") or []),
            "architecture": self._display_value(candidate_profile.get("architecture_terms") or []) if candidate_profile.get("architecture_terms") else "",
            "shared_technologies": [str(item) for item in shared_technologies if str(item).strip()],
            "shared_modules": [str(item) for item in shared_modules if str(item).strip()],
            "badges": self._build_badges(shared_technologies, shared_architecture, shared_modules),
            "similarity_breakdown": scores,
        }

    def _build_reason(
        self,
        shared_technologies: list[str],
        shared_modules: list[str],
        shared_architecture: list[str],
        shared_domain: list[str],
    ) -> str:
        reasons: list[str] = []
        if shared_domain:
            reasons.append(f"Related domain: {', '.join(shared_domain[:3])}")
        if shared_modules:
            reasons.append(f"Shared functionality: {', '.join(shared_modules[:4])}")
        if shared_architecture:
            reasons.append(f"Comparable architecture: {', '.join(shared_architecture[:3])}")
        if shared_technologies:
            reasons.append(f"Shared technologies: {', '.join(shared_technologies[:4])}")
        return "; ".join(reasons) or "Related repository domain and functionality."

    def _build_badges(
        self,
        shared_technologies: list[str],
        shared_architecture: list[str],
        shared_modules: list[str] | None = None,
    ) -> list[str]:
        badges = []
        badges.extend([str(item) for item in (shared_modules or [])[:3] if str(item).strip()])
        badges.extend([str(item) for item in shared_architecture[:3] if str(item).strip()])
        badges.extend([str(item) for item in shared_technologies[:4] if str(item).strip()])
        return list(dict.fromkeys(badges))

    def _build_candidate_profile(self, candidate: dict) -> dict:
        candidate = candidate if isinstance(candidate, dict) else {}
        candidate_text = self._candidate_text(candidate)
        tree_paths = candidate.get("_tree_paths", [])
        tree_text = " ".join(str(path).replace("/", " ") for path in tree_paths) if isinstance(tree_paths, list) else ""
        combined_text = " ".join((candidate_text, tree_text))
        domain_terms = self._domain_concepts(combined_text)
        module_terms = self._functional_modules(combined_text)
        topics = candidate.get("topics", [])
        metadata_text = " ".join(
            [str(candidate.get("description") or "")]
            + [str(topic) for topic in topics if isinstance(topic, str)]
        ) if isinstance(topics, list) else str(candidate.get("description") or "")
        meaningful_tech = self._extract_meaningful_technologies(combined_text)
        return {
            "domain_terms": domain_terms,
            "architecture_terms": self._extract_architecture_characteristics(combined_text),
            "technology_terms": meaningful_tech,
            "modules": module_terms,
            "structure_terms": self._structure_characteristics(tree_paths),
            "metadata_terms": self._metadata_concepts(metadata_text),
        }

    def _build_fingerprint(
        self,
        metadata: dict,
        stack: dict,
        readme: str,
        analysis_context: dict | None,
        repository_structure: list[dict] | None,
    ) -> dict:
        metadata = metadata if isinstance(metadata, dict) else {}
        stack = stack if isinstance(stack, dict) else {}
        analysis_context = analysis_context if isinstance(analysis_context, dict) else {}
        repository_structure = repository_structure if isinstance(repository_structure, list) else []

        executive = analysis_context.get("executive_overview", {})
        executive_text = self._collect_text(executive) if isinstance(executive, dict) else ""
        overview_text = " ".join([
            str(analysis_context.get("overview") or ""),
            str(metadata.get("description") or ""),
            str(metadata.get("name") or ""),
            executive_text,
            str(readme or "")[:4000],
        ])
        modules = self._extract_profile_modules(analysis_context)
        evidence = analysis_context.get("analysis_evidence", {})
        evidence_text = self._collect_text(evidence) if isinstance(evidence, dict) else ""
        domain_terms = self._domain_concepts(overview_text)
        if not domain_terms and readme:
            domain_terms = self._domain_concepts(str(readme)[:4000])
        technologies = self._extract_meaningful_technologies(
            self._stack_technology_text(stack) + " " + evidence_text
        )
        architecture_text = self._collect_text(analysis_context.get("architecture", {}))
        architecture_text += " " + self._stack_architecture_text(stack)
        architecture_terms = self._extract_architecture_characteristics(architecture_text)
        module_text = " ".join(modules) + " " + evidence_text
        modules = list(dict.fromkeys(modules + self._functional_modules(module_text)))
        topics = [
            str(topic).lower() for topic in metadata.get("topics", [])
            if isinstance(topic, str) and topic.strip()
        ] if isinstance(metadata.get("topics"), list) else []
        structure_terms = self._structure_characteristics_from_tree(repository_structure)
        metadata_terms = self._metadata_concepts(
            " ".join([str(metadata.get("description") or ""), *topics])
        )
        project_type_terms = domain_terms[:8]
        return {
            "project_type_terms": project_type_terms,
            "domain_phrases": self._domain_phrases(overview_text, domain_terms),
            "architecture_terms": architecture_terms,
            "technology_terms": technologies,
            "modules": modules,
            "module_terms": modules,
            "structure_terms": structure_terms,
            "domain_terms": domain_terms,
            "metadata_terms": metadata_terms,
            "topics": topics,
            "language": str(metadata.get("language") or metadata.get("primary_language") or "").lower(),
        }

    def _domain_concepts(self, text: str) -> list[str]:
        normalized_text = normalize_query(text)
        phrases = {
            "file management": ("file manager", "file management", "file browser", "file explorer", "document management"),
            "storage": ("cloud storage", "object storage", "file storage", "storage platform"),
            "file sharing": ("file sharing", "document sharing", "sharing platform"),
            "ecommerce": ("ecommerce", "e commerce", "online store", "shopping platform", "marketplace", "retail"),
            "messaging": ("chat application", "chat app", "messaging", "instant messaging"),
            "devops": ("devops", "infrastructure dashboard", "deployment dashboard", "kubernetes dashboard"),
            "analytics": ("analytics", "business intelligence", "reporting dashboard"),
            "content management": ("content management", "cms", "publishing platform", "blog"),
        }
        found = [
            concept
            for concept, terms in phrases.items()
            if any(self._contains_phrase(normalized_text, term) for term in terms)
        ]
        return list(dict.fromkeys(found))

    def _domain_phrases(self, text: str, concepts: list[str]) -> list[str]:
        phrase_by_concept = {
            "file management": ("file manager", "file management", "file browser"),
            "storage": ("cloud storage", "object storage"),
            "file sharing": ("file sharing", "document sharing"),
            "ecommerce": ("ecommerce", "online store", "shopping platform"),
            "messaging": ("chat application", "messaging", "chat app"),
            "devops": ("devops dashboard", "infrastructure dashboard", "kubernetes dashboard"),
            "analytics": ("analytics dashboard", "business intelligence"),
            "content management": ("content management", "cms", "blog"),
        }
        normalized_text = normalize_query(text)
        phrases = []
        for concept in concepts:
            for phrase in phrase_by_concept.get(concept, ()):
                if self._contains_phrase(normalized_text, phrase):
                    phrases.append(phrase)
                    break
        return list(dict.fromkeys(phrases))[:4]

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        normalized_phrase = normalize_query(phrase)
        return bool(normalized_phrase and re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            text,
        ))

    def _functional_modules(self, text: str) -> list[str]:
        normalized_text = normalize_query(text)
        concepts = []
        for module, pattern in FUNCTIONAL_PATH_RULES.items():
            if pattern.search(normalized_text):
                concepts.append(module)
        return list(dict.fromkeys(concepts))

    def _extract_profile_modules(self, analysis_context: dict) -> list[str]:
        modules = analysis_context.get("modules", [])
        if not isinstance(modules, list):
            return []
        names = []
        excluded = {"frontend", "backend", "api layer", "infrastructure", "database", "worker"}
        for module in modules:
            if isinstance(module, dict):
                name = str(module.get("name") or "").strip()
            elif isinstance(module, str):
                name = module.strip()
            else:
                continue
            normalized = normalize_query(name)
            if normalized and normalized not in excluded:
                names.append(normalized)
        return list(dict.fromkeys(names))

    def _extract_meaningful_technologies(self, text: str) -> list[str]:
        normalized = normalize_query(text)
        detected = []
        for technology in MEANINGFUL_TECHNOLOGIES:
            term = normalize_query(technology)
            if self._contains_phrase(normalized, term):
                detected.append(technology)
        return sorted(detected)

    def _stack_technology_text(self, stack: dict) -> str:
        names = self._stack_technologies(stack)
        return " ".join(names)

    def _stack_architecture_text(self, stack: dict) -> str:
        categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
        selected = []
        if isinstance(categories, dict):
            for category in ("frontend", "backend", "database", "infrastructure", "devops", "cloud", "messaging"):
                selected.extend(categories.get(category, []) if isinstance(categories.get(category), list) else [])
        return self._collect_text(selected)

    def _extract_architecture_characteristics(self, text: str) -> list[str]:
        normalized = normalize_query(text)
        rules = {
            "client server": r"(client server|frontend|backend|http api|rest api|server side)",
            "microservices": r"(microservice|distributed service)",
            "monolith": r"\bmonolith\b",
            "rest api": r"(rest api|restful|api route|http endpoint)",
            "graphql": r"graphql",
            "event driven": r"(event driven|message queue|kafka|rabbitmq|sqs)",
            "serverless": r"(serverless|aws lambda|cloud functions)",
            "containerized": r"(docker|container)",
            "kubernetes": r"(kubernetes|k8s|helm)",
            "database backed": r"(postgresql|mysql|mongodb|dynamodb|sqlite|database)",
            "object storage backed": r"(object storage|cloud storage|\bs3\b|bucket)",
        }
        return [name for name, pattern in rules.items() if re.search(pattern, normalized)]

    def _structure_characteristics_from_tree(self, structure: list[dict]) -> list[str]:
        paths: list[str] = []
        for node in structure:
            self._collect_paths(node, "", paths)
        return self._structure_characteristics(paths)

    def _collect_paths(self, node: dict | None, parent: str, paths: list[str]) -> None:
        if not isinstance(node, dict):
            return
        name = str(node.get("name") or "")
        path = f"{parent}/{name}".strip("/")
        if path:
            paths.append(path)
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                self._collect_paths(child, path, paths)

    def _collect_structure_text(self, structure: list[dict]) -> str:
        names = []
        for node in structure:
            self._collect_structure_names(node, names)
        return " ".join(names)

    def _structure_characteristics(self, paths: Any) -> list[str]:
        if not isinstance(paths, list):
            return []
        text = " ".join(str(path).replace("\\", "/").lower() for path in paths)
        rules = {
            "frontend/backend split": r"(frontend|client).*(backend|server)|(backend|server).*(frontend|client)",
            "api routing": r"(routes?|routers?|controllers?)/",
            "service layer": r"services?/",
            "component based": r"components?/",
            "database models": r"(models?|migrations?|schemas?)/",
            "deployment configuration": r"(dockerfile|compose\.ya?ml|\.tf$|k8s/|kubernetes/)",
            "tests": r"(^|/)(tests?|spec)/",
            "multi package": r"(packages?|apps)/",
        }
        return [name for name, pattern in rules.items() if re.search(pattern, text)]

    def _metadata_concepts(self, text: str) -> list[str]:
        return self._domain_concepts(text) + self._keywords(text, max_terms=8)

    def _candidate_full_name(self, candidate: dict) -> str:
        if not isinstance(candidate, dict):
            return ""
        if candidate.get("full_name"):
            return str(candidate["full_name"])
        owner = candidate.get("owner", {})
        owner_name = owner.get("login") if isinstance(owner, dict) else candidate.get("owner")
        name = candidate.get("name")
        if owner_name and name:
            return f"{owner_name}/{name}"
        for key in ("html_url", "url", "repo_url"):
            value = candidate.get(key)
            if isinstance(value, str) and "github.com/" in value.lower():
                return re.sub(
                    r"\.git$",
                    "",
                    value.strip().rstrip("/").split("github.com/", 1)[-1],
                    flags=re.IGNORECASE,
                )
        return ""

    def _candidate_text(self, candidate: dict) -> str:
        candidate = candidate if isinstance(candidate, dict) else {}
        topics = candidate.get("topics", [])
        topic_text = " ".join(
            str(topic) for topic in topics
            if isinstance(topic, str) and topic.strip()
        ) if isinstance(topics, list) else ""
        return " ".join([
            str(candidate.get("name") or ""),
            str(candidate.get("description") or ""),
            topic_text,
        ])

    def _extract_structure_terms(self, repository_structure: list[dict] | None) -> list[str]:
        names: list[str] = []
        if not repository_structure:
            return []
        for node in repository_structure:
            self._collect_structure_names(node, names)
        return self._keywords(" ".join(names), max_terms=8)

    def _collect_structure_names(self, node: dict | None, names: list[str]) -> None:
        if not isinstance(node, dict):
            return
        if node.get("name"):
            names.append(str(node["name"]))
        for child in node.get("children", []) or []:
            self._collect_structure_names(child, names)

    def _extract_module_terms(self, analysis_context: dict | None, metadata: dict, readme: str) -> list[str]:
        modules: list[str] = []
        if isinstance(analysis_context, dict):
            module_sources = analysis_context.get("modules") or []
            if isinstance(module_sources, list):
                for item in module_sources:
                    if isinstance(item, dict):
                        for key in ("name", "purpose", "description"):
                            value = item.get(key)
                            if value:
                                modules.append(str(value))
                    elif isinstance(item, str):
                        modules.append(item)
        terms = self._keywords(" ".join(modules + [str(metadata.get("description") or ""), str(readme or "")]), max_terms=10)
        return [term for term in terms if len(term) > 2]

    def _extract_technology_terms_from_stack(self, stack: dict, metadata: dict) -> list[str]:
        names = self._stack_technologies(stack)
        language = str(metadata.get("language") or metadata.get("primary_language") or "")
        if language:
            names.append(language)
        return list(dict.fromkeys([name for name in names if name]))

    def _extract_technology_terms(self, candidate: dict) -> list[str]:
        names = []
        if candidate.get("language"):
            names.append(str(candidate.get("language")))
        names.extend(str(topic) for topic in candidate.get("topics", []) if topic)
        return list(dict.fromkeys([name for name in names if name]))

    def _extract_architecture_terms(self, text: str) -> list[str]:
        lowered = str(text).lower()
        patterns = [
            "serverless",
            "microservices",
            "monolith",
            "event driven",
            "event-driven",
            "distributed",
            "streaming",
            "pipeline",
            "queue",
            "worker",
            "api",
            "graphql",
            "rest",
            "modular",
            "layered",
            "headless",
        ]
        found = [pattern for pattern in patterns if pattern in lowered]
        return found[:5]

    def _collect_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(self._collect_text(item) for item in value)
        if isinstance(value, dict):
            parts = []
            for item in value.values():
                text = self._collect_text(item)
                if text:
                    parts.append(text)
            return " ".join(parts)
        return str(value)

    def _stack_technologies(self, stack: dict) -> list[str]:
        categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
        names: list[str] = []
        for items in categories.values():
            for item in items or []:
                if isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
                elif isinstance(item, str):
                    names.append(item)
        return list(dict.fromkeys(names))

    def _overlap_score(self, source: set[str], target: set[str]) -> float:
        if not source:
            return 0.0
        if not target:
            return 0.0
        return len(source & target) / len(source)

    def _keywords(self, text: str | None, max_terms: int) -> list[str]:
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into", "your",
            "you", "are", "was", "were", "platform", "application", "project",
            "repository", "open", "source", "using", "based"
        }
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text or "")
        filtered = [word.lower() for word in words if word.lower() not in stop_words]
        return list(dict.fromkeys(filtered))[:max_terms]

    def _display_value(self, values: list[str]) -> str:
        cleaned = [value for value in values if value]
        if not cleaned:
            return "Software platform"
        return " ".join(cleaned[:4]).replace("-", " ").title()

    def _safe_int(self, *values: Any) -> int:
        for value in values:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip():
                try:
                    return int(float(value))
                except ValueError:
                    continue
        return 0

    def _popularity_score(self, stars: int) -> float:
        if stars <= 0:
            return 0.0
        return min(1.0, stars / 100000.0)

    def _strip_json_markdown(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        return stripped
