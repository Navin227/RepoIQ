import math
import re
from pathlib import PurePosixPath
from typing import Any

from app.config import settings


DOMAIN_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "file manager": (
        "file management", "file explorer", "file browser", "file sharing",
        "cloud storage", "document management", "file storage", "file upload",
    ),
    "file sharing": (
        "file manager", "cloud storage", "file upload", "document sharing",
    ),
    "e commerce": (
        "ecommerce", "e-commerce", "online store", "shopping platform",
        "marketplace", "product catalog", "cart", "checkout",
    ),
    "ecommerce": (
        "e-commerce", "online store", "shopping platform", "marketplace",
        "product catalog", "cart", "checkout",
    ),
    "e-commerce": (
        "ecommerce", "online store", "shopping platform", "marketplace",
        "product catalog", "cart", "checkout",
    ),
    "chat application": (
        "chat app", "messaging", "real-time chat", "instant messaging",
        "chatroom", "team communication",
    ),
    "chat app": (
        "chat application", "messaging", "real-time chat",
        "instant messaging", "chatroom",
    ),
    "devops dashboard": (
        "deployment dashboard", "infrastructure dashboard", "ci cd dashboard",
        "kubernetes dashboard", "operations dashboard",
    ),
    "cloud storage": (
        "file storage", "file sharing", "object storage", "file manager",
        "document management",
    ),
}

QUERY_STOP_WORDS = {
    "a", "an", "app", "application", "for", "of", "the", "to", "with",
}

MANIFEST_NAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", "go.mod", "cargo.toml",
    "composer.json", "gemfile", "mix.exs", "pubspec.yaml",
}
SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".swift", ".ts", ".tsx",
}
INFRASTRUCTURE_NAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "compose.yaml", "chart.yaml", "values.yaml", "kustomization.yaml",
    "kustomization.yml",
}
FUNCTIONAL_PATH_TERMS = re.compile(
    r"(auth|upload|download|storage|file|document|payment|checkout|cart|"
    r"product|order|route|controller|service|handler|worker|queue|api)",
    re.IGNORECASE,
)


def normalize_query(query: str) -> str:
    return " ".join(re.sub(r"[-_]+", " ", str(query or "").lower()).split())


def expand_query(query: str) -> list[str]:
    normalized = normalize_query(query)
    if not normalized:
        return []

    expansions = [normalized]
    expansions.extend(DOMAIN_EXPANSIONS.get(normalized, ()))
    # Related phrase groups may add a useful expansion without matching every
    # constituent token (for example, "file manager" should not match "file").
    for phrase, related in DOMAIN_EXPANSIONS.items():
        if phrase in normalized and phrase != normalized:
            expansions.extend(related[:2])

    return list(dict.fromkeys(normalize_query(term) for term in expansions if term))


def build_candidate_queries(query: str) -> list[str]:
    normalized = " ".join(str(query or "").split())
    if not normalized:
        return []

    expanded = expand_query(normalized)
    queries = [f'"{normalized}" in:name,description,readme']
    if len(expanded) > 1:
        queries.append(f'"{expanded[1]}" in:name,description,readme')

    topic = re.sub(r"[^a-z0-9]+", "-", normalize_query(normalized)).strip("-")
    if topic:
        queries.append(f"topic:{topic}")

    return list(dict.fromkeys(queries))[:3]


def _phrase_present(phrase: str, text: str) -> bool:
    return bool(phrase and re.search(
        rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
        normalize_query(text),
    ))


def score_relevance(query: str, candidate: dict[str, Any]) -> float:
    normalized = normalize_query(query)
    if not normalized:
        return 0.0

    expanded = expand_query(normalized)
    name = normalize_query(
        " ".join(str(candidate.get(key) or "") for key in ("full_name", "name"))
    )
    raw_topics = candidate.get("topics", [])
    topics = [
        normalize_query(topic)
        for topic in raw_topics
        if isinstance(topic, str)
    ] if isinstance(raw_topics, list) else []
    description = normalize_query(candidate.get("description") or "")
    query_terms = [
        term for term in normalized.split()
        if term not in QUERY_STOP_WORDS and len(term) > 1
    ]
    score = 0.0

    if _phrase_present(normalized, name):
        score += 48
    elif query_terms and all(_phrase_present(term, name) for term in query_terms):
        score += 34
    elif any(_phrase_present(term, name) for term in query_terms):
        score += 8

    alias_matches_name = [
        phrase for phrase in expanded[1:]
        if _phrase_present(phrase, name)
    ]
    if alias_matches_name:
        score += 42

    exact_topic_matches = [
        topic for topic in topics
        if any(topic == phrase or topic == phrase.replace(" ", "-") for phrase in expanded)
    ]
    if exact_topic_matches:
        score += min(38, 28 + 5 * (len(exact_topic_matches) - 1))
    else:
        topic_terms = {term for topic in topics for term in topic.split()}
        score += min(18, 9 * len(set(query_terms) & topic_terms))

    if _phrase_present(normalized, description):
        score += 25
    elif any(_phrase_present(phrase, description) for phrase in expanded[1:]):
        score += 22
    if query_terms:
        description_terms = set(description.split())
        score += min(15, 5 * len(set(query_terms) & description_terms))

    # Popularity is a small tie-breaker only; it cannot compensate for missing
    # topic/name/description evidence.
    stars = candidate.get("stargazers_count", candidate.get("stars", 0))
    if isinstance(stars, (int, float)) and stars > 0:
        score += min(0.5, math.log10(stars + 1) * 0.125)

    return round(min(100.0, score), 2)


def classify_repository_type(paths: list[str], language: str | None = None) -> str:
    normalized = [str(path).replace("\\", "/") for path in paths if isinstance(path, str)]
    source = [path for path in normalized if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES]
    manifests = sum(PurePosixPath(path).name.lower() in MANIFEST_NAMES for path in normalized)
    roots = {PurePosixPath(path).parts[0].lower() for path in normalized if len(PurePosixPath(path).parts) > 1}
    infra = sum(PurePosixPath(path).name.lower() in INFRASTRUCTURE_NAMES or path.lower().endswith((".tf", ".tfvars")) or path.lower().startswith((".github/workflows/", "k8s/", "kubernetes/")) for path in normalized)
    if manifests >= 2 or len(roots & {"apps", "packages", "services", "frontend", "backend"}) >= 3:
        return "monorepo"
    if infra >= 2 and len(source) < 2:
        return "infrastructure"
    if any(PurePosixPath(p).suffix.lower() in {".tsx", ".jsx", ".vue", ".svelte"} for p in source):
        return "frontend_application"
    if any(part in {"lib", "libs"} for path in source for part in PurePosixPath(path).parts[:-1]):
        return "library"
    if manifests and source and not any(PurePosixPath(p).name.lower() in {"main.py", "app.py", "__main__.py", "main.ts", "main.tsx", "index.ts", "index.tsx", "index.js", "index.jsx", "server.py", "server.ts", "manage.py"} for p in source) and not any(FUNCTIONAL_PATH_TERMS.search(p) for p in source):
        return "library"
    return "application"


def score_analyzability(
    paths: list[str],
    readme_present: bool = False,
    scan: dict[str, Any] | None = None,
    repository_type: str | None = None,
) -> float:
    """Heuristic readiness score; these weights are configurable, not calibrated.

    README and manifests describe a project but cannot substitute for inspected
    implementation. Generated/vendor paths are excluded from all file counts.
    """
    ignored = {".git", "node_modules", "vendor", "dist", "build", "coverage", ".next", ".nuxt", ".venv", "venv", "site-packages", "target", "bower_components"}
    normalized_paths = sorted({
        str(path).replace("\\", "/").strip("/")
        for path in paths
        if isinstance(path, str) and path.strip()
        and not any(part.lower() in ignored for part in PurePosixPath(str(path).replace("\\", "/")).parts[:-1])
    })
    basenames = [PurePosixPath(path).name.lower() for path in normalized_paths]
    source_paths = [path for path in normalized_paths if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES]
    implementation_paths = [path for path in source_paths if not re.search(r"(^|/)(test|tests|__tests__|spec)(/|$)|(^|/)(test_|.*\.(test|spec)\.)", path, re.I)]
    manifest_count = sum(name in MANIFEST_NAMES for name in basenames)
    entrypoint_count = sum(PurePosixPath(path).name.lower() in {"main.py", "app.py", "__main__.py", "main.ts", "main.tsx", "index.ts", "index.tsx", "index.js", "index.jsx", "server.py", "server.ts", "manage.py", "lib.rs"} for path in implementation_paths)
    test_count = len(source_paths) - len(implementation_paths)
    functional_count = sum(bool(FUNCTIONAL_PATH_TERMS.search(path)) for path in implementation_paths)
    boundaries = {PurePosixPath(path).parts[-2].lower() if len(PurePosixPath(path).parts) > 1 else "_root" for path in implementation_paths}
    infra_count = sum(PurePosixPath(path).name.lower() in INFRASTRUCTURE_NAMES or path.lower().endswith((".tf", ".tfvars")) or path.lower().startswith((".github/workflows/", "k8s/", "kubernetes/")) for path in normalized_paths)
    roots = {PurePosixPath(path).parts[0].lower() for path in normalized_paths if len(PurePosixPath(path).parts) > 1}
    repository_type = repository_type or classify_repository_type(normalized_paths)

    # Heuristic points reward inspected implementation, runnable structure,
    # manifests, tests, and module boundaries. No points for README presence.
    score = min(30, len(implementation_paths) * 6)
    score += min(16, entrypoint_count * 8)
    score += min(12, manifest_count * 6)
    score += min(10, test_count * 3)
    score += min(12, len(boundaries) * 4)
    score += min(12, functional_count * 3)
    if repository_type == "infrastructure":
        score += min(20, infra_count * 8)
    if repository_type == "library" and implementation_paths and manifest_count:
        score += 8
    if repository_type == "frontend_application" and manifest_count and implementation_paths:
        score += 6
    if repository_type == "monorepo":
        score += min(12, max(0, len(roots) - 1) * 3)
    if isinstance(scan, dict):
        source_evidence = scan.get("source_evidence") or {}
        stats = source_evidence.get("stats") if isinstance(source_evidence.get("stats"), dict) else {}
        selected = stats.get("selected_evidence_files", 0)
        routes = stats.get("routes_detected", 0)
        if isinstance(selected, (int, float)) and selected > 0: score += min(8, int(selected) * 2)
        if isinstance(routes, (int, float)) and routes > 0: score += min(8, int(routes) * 2)
    return float(min(100, score))


def score_readme_quality(
    readme_text: str | None,
    candidate: dict[str, Any] | None = None,
    paths: list[str] | None = None,
) -> float | None:
    """Estimate README usefulness only when content was actually inspected."""
    if not isinstance(readme_text, str) or not readme_text.strip():
        return None

    text = readme_text.casefold()
    words = set(re.findall(r"[a-z0-9]{3,}", text))
    word_count = len(re.findall(r"\b[a-z0-9]+\b", text))
    score = float(int(word_count >= 40) + int(word_count >= 120))
    section_groups = (
        ("overview", "about", "what it does", "introduction", "purpose"),
        ("install", "installation", "setup", "getting started", "requirements"),
        ("usage", "quick start", "examples", "features", "capabilities"),
        ("architecture", "design", "how it works", "development", "configuration"),
    )
    score += sum(1.5 for group in section_groups if any(term in text for term in group))
    score += float(bool(re.search(r"```|\$\s+[a-z]|npm (?:run|install)|pip install|docker compose", text)))

    candidate = candidate or {}
    anchors = set(re.findall(
        r"[a-z0-9]{4,}", " ".join(str(candidate.get(key) or "") for key in ("name", "full_name", "description")),
    ))
    anchors.update(
        token
        for path in (paths or [])
        for token in re.findall(r"[a-z0-9]{4,}", PurePosixPath(path).stem.casefold())
    )
    if anchors:
        overlap = len(anchors & words) / max(1, min(len(anchors), 12))
        score += 1.5 * min(1.0, overlap)
    return round(min(10.0, score), 2)


def build_analysis_evidence(
    scan: dict[str, Any],
    stack: dict[str, Any],
    readme: str,
    code_signals: dict[str, list[str]],
) -> dict[str, Any]:
    raw_files = scan.get("files", [])
    files = [
        str(path) for path in raw_files if isinstance(path, str)
    ] if isinstance(raw_files, list) else []
    dependencies = scan.get("dependencies", {})
    categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
    technology_detections = [
        {
            "name": str(item.get("name")),
            "source": str(item.get("source") or ""),
            "evidence": str(item.get("evidence") or ""),
            "confidence": item.get("confidence", 0),
        }
        for items in categories.values()
        if isinstance(items, list)
        for item in items
        if isinstance(item, dict) and item.get("name")
    ]
    dependency_files = [
        {"path": str(path), "type": str(value.get("type") or "configuration")}
        for path, value in dependencies.items()
        if isinstance(value, dict)
    ] if isinstance(dependencies, dict) else []
    source_files = [
        path for path in files
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
    ]
    infrastructure_files = [
        path for path in files
        if PurePosixPath(path).name.lower() in INFRASTRUCTURE_NAMES
        or path.lower().endswith((".tf", ".tfvars"))
        or path.lower().startswith((".github/workflows/", "k8s/", "kubernetes/"))
    ]
    has_readme = bool(str(readme or "").strip())
    score = score_analyzability(files, readme_present=has_readme, scan=scan)

    source_evidence = scan.get("source_evidence") if isinstance(scan, dict) else {}
    if not isinstance(source_evidence, dict):
        source_evidence = {}
    enriched_routes = code_signals.get("api_routes_enriched") or source_evidence.get("routes") or []
    route_paths = code_signals.get("api_routes", [])[:80]
    evidence_stats = source_evidence.get("stats", {}) if isinstance(source_evidence.get("stats"), dict) else {}
    selected_evidence_paths = source_evidence.get("selected_source_files", [])[:80]

    return {
        "analyzability_score": score,
        "confidence": "high" if score >= 70 else "medium" if score >= 35 else "low",
        "readme_available": has_readme,
        "source_file_count": len(source_files),
        "source_files": source_files[:120],
        "selected_evidence_files": selected_evidence_paths,
        "selected_evidence_file_count": evidence_stats.get("selected_evidence_files", len(selected_evidence_paths)),
        "dependency_and_configuration_files": dependency_files[:80],
        "infrastructure_files": infrastructure_files[:80],
        "technology_detections": technology_detections[:100],
        "api_routes": route_paths,
        "api_routes_enriched": enriched_routes[:80],
        "service_names": code_signals.get("service_names", [])[:80],
        "controller_names": code_signals.get("controller_names", [])[:80],
        "business_file_names": code_signals.get("business_file_names", [])[:80],
        "capability_signals": source_evidence.get("capability_signals", [])[:20],
        "domain_signals": [
            {
                "domain": item.get("domain"),
                "confidence": item.get("confidence"),
                "signals": item.get("matched_signals", []),
            }
            for item in (source_evidence.get("capability_signals") or [])
            if isinstance(item, dict)
        ][:15],
        "evidence_quality": {
            "meaningful_source_files": evidence_stats.get("selected_evidence_files", 0),
            "routes_with_handlers": len([
                r for r in enriched_routes
                if isinstance(r, dict) and r.get("handler")
            ]) if enriched_routes else 0,
            "payload_chars": evidence_stats.get("evidence_payload_chars", 0),
        },
    }


def rank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    relevance_floor: float = 12.0,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in candidates:
        if not isinstance(source, dict):
            continue
        candidate = dict(source)
        full_name = str(
            candidate.get("full_name")
            or candidate.get("name")
            or candidate.get("html_url")
            or ""
        ).lower()
        if full_name in seen:
            continue
        seen.add(full_name)

        relevance = score_relevance(query, candidate)
        if relevance < relevance_floor:
            continue
        paths = candidate.get("_repo_paths")
        state = candidate.get("_tree_inspection_state")
        # Direct callers may supply an explicit tree list without the GitHub
        # service metadata; its presence still means the tree was inspected.
        if state is None and isinstance(paths, list):
            state = "inspected"
        state = state or "not_inspected"
        truncated = bool(candidate.get("_tree_truncated"))
        tree_complete = state == "inspected" and not truncated and isinstance(paths, list)
        repository_type = classify_repository_type(paths if isinstance(paths, list) else [], candidate.get("language")) if tree_complete else None
        analysis_score = score_analyzability(paths, repository_type=repository_type) if tree_complete else None
        if not tree_complete:
            readiness = "partial" if state == "inspected" and truncated else "unknown"
            readiness_reason = "tree_truncated" if truncated else "tree_inspection_failed" if state == "inspection_failed" else "tree_not_inspected"
            ranking_score = relevance
        else:
            readiness, readiness_reason = assess_evidence_readiness(
                paths, bool(candidate.get("_readme_present")), repository_type,
            )
            ranking_score = relevance
        candidate["relevance_score"] = relevance
        candidate["analyzability_score"] = analysis_score
        candidate["readme_quality_score"] = score_readme_quality(
            candidate.get("_readme_text"), candidate, paths if isinstance(paths, list) else []
        )
        candidate["ranking_score"] = ranking_score
        candidate["tree_inspection_state"] = state
        candidate["tree_truncated"] = truncated
        candidate["evidence_readiness"] = readiness
        candidate["readiness_reason"] = readiness_reason
        candidate["repository_type"] = repository_type
        candidate["inspected_file_count"] = len(paths) if state == "inspected" and isinstance(paths, list) else None
        candidate["tree_reported_file_count"] = candidate.get("_tree_reported_count", len(paths)) if state == "inspected" and isinstance(paths, list) else None
        candidate["meaningful_source_file_count"] = _meaningful_source_count(paths) if state == "inspected" and isinstance(paths, list) else None
        ranked.append(candidate)

    # Relevance defines the candidate pool and the comparable cohort. Only
    # promote a fully ready repository over the most relevant result when its
    # relevance is within the documented, configurable comparison margin.
    # This is a selection heuristic, not a calibrated probability or quality
    # score. Unknown/failed inspections keep a relevance-only rank score and
    # never receive a fabricated analyzability value.
    if ranked:
        best_relevance = max(item["relevance_score"] for item in ranked)
        margin = max(0.0, float(settings.discovery_readiness_relevance_margin))
        top_candidates = [item for item in ranked if item["relevance_score"] == best_relevance]
        top_is_ready = any(item["evidence_readiness"] == "ready" for item in top_candidates)
        if not top_is_ready:
            for item in ranked:
                delta = best_relevance - item["relevance_score"]
                item["comparable_relevance_cohort"] = delta <= margin
                if item["evidence_readiness"] == "ready" and delta <= margin:
                    # Lift a ready candidate just above the best-relevance
                    # baseline, while leaving all out-of-cohort candidates
                    # relevance-ranked.
                    quality_tiebreak = (
                        float(item.get("analyzability_score") or 0) / 1000
                        + float(item.get("readme_quality_score") or 0) / 100
                    )
                    item["ranking_adjustment"] = round(delta + 0.01 + quality_tiebreak, 2)
                else:
                    item["ranking_adjustment"] = 0.0
                item["ranking_score"] = round(item["relevance_score"] + item["ranking_adjustment"], 2)
        else:
            for item in ranked:
                item["comparable_relevance_cohort"] = best_relevance - item["relevance_score"] <= margin
                item["ranking_adjustment"] = 0.0

    return sorted(
        ranked,
        key=lambda item: (
            -(item["ranking_score"] if item["ranking_score"] is not None else item["relevance_score"]),
            -item["relevance_score"],
            0 if item["evidence_readiness"] == "ready" else 1,
            -(item["analyzability_score"] if item["analyzability_score"] is not None else -1),
            -(item["readme_quality_score"] if item["readme_quality_score"] is not None else -1),
            0 if item["tree_inspection_state"] == "inspected" and not item["tree_truncated"] else 1 if item["tree_inspection_state"] == "inspected" else 2,
            -_safe_popularity(item.get("stargazers_count")),
            str(item.get("full_name") or item.get("name") or "").casefold(),
        ),
    )


def _meaningful_source_count(paths: list[str] | None) -> int:
    if not isinstance(paths, list):
        return 0
    ignored = {".git", "node_modules", "vendor", "dist", "build", "coverage", ".next", ".nuxt", ".venv", "venv", "site-packages", "target", "bower_components"}
    return sum(
        1 for path in paths
        if isinstance(path, str)
        and PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
        and not any(part.lower() in ignored for part in PurePosixPath(path.replace("\\", "/")).parts[:-1])
        and not re.search(r"(^|/)(test|tests|__tests__|spec)(/|$)|(^|/)(test_|.*\.(test|spec)\.)", path, re.I)
    )


def assess_evidence_readiness(paths: list[str], readme_present: bool, repository_type: str) -> tuple[str, str]:
    def readiness(status: str, reason: str) -> tuple[str, str]:
        if not readme_present:
            reason += "; README not found"
        return status, reason

    source_count = _meaningful_source_count(paths)
    manifest_count = sum(PurePosixPath(path).name.lower() in MANIFEST_NAMES for path in paths)
    infra_count = sum(PurePosixPath(path).name.lower() in INFRASTRUCTURE_NAMES or path.lower().endswith((".tf", ".tfvars")) or path.lower().startswith((".github/workflows/", "k8s/", "kubernetes/")) for path in paths)
    entrypoints = sum(PurePosixPath(path).name.lower() in {"main.py", "app.py", "__main__.py", "main.ts", "main.tsx", "index.ts", "index.tsx", "index.js", "index.jsx", "server.py", "server.ts", "manage.py", "lib.rs"} for path in paths)
    if not paths:
        return readiness("low", "empty_repository")
    if source_count == 0 and not (repository_type == "infrastructure" and infra_count >= 2):
        return readiness("low", "mostly_generated_vendor_or_nonimplementation_files")
    if repository_type == "infrastructure":
        if infra_count >= 2: return readiness("ready", "multiple_infrastructure_implementation_files")
        return readiness("limited", "infrastructure_evidence_is_sparse")
    if repository_type == "library":
        if source_count >= 2 and manifest_count: return readiness("ready", "library_source_and_manifest_present")
        return readiness("limited", "library_has_source_but_limited_package_or_module_evidence")
    if repository_type == "frontend_application":
        if source_count >= 2 and (entrypoints or manifest_count): return readiness("ready", "frontend_source_and_application_structure_present")
        return readiness("limited", "frontend_implementation_evidence_is_sparse")
    if repository_type == "monorepo":
        roots = {PurePosixPath(path).parts[0].lower() for path in paths if len(PurePosixPath(path).parts) > 1}
        if source_count >= 3 and len(roots) >= 2: return readiness("ready", "multiple_implemented_subsystems_found")
        return readiness("limited", "monorepo_boundaries_or_implementations_are_sparse")
    if source_count >= 2 and (entrypoints or manifest_count): return readiness("ready", "implementation_and_project_structure_present")
    return readiness("limited", "source_exists_but_project_structure_is_sparse")


def _safe_popularity(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
