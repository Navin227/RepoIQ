import math
import re
from pathlib import PurePosixPath
from typing import Any


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

    # Popularity only breaks close relevance ties; it cannot compensate for
    # missing topic/name/description evidence.
    stars = candidate.get("stargazers_count", candidate.get("stars", 0))
    if isinstance(stars, (int, float)) and stars > 0:
        score += min(2.0, math.log10(stars + 1) * 0.5)

    return round(min(100.0, score), 2)


def score_analyzability(paths: list[str], readme_present: bool = False) -> float:
    normalized_paths = [
        str(path).replace("\\", "/").strip("/")
        for path in paths
        if isinstance(path, str) and path.strip()
    ]
    basenames = [PurePosixPath(path).name.lower() for path in normalized_paths]
    source_count = sum(
        PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
        for path in normalized_paths
    )
    manifest_count = sum(name in MANIFEST_NAMES for name in basenames)
    meaningful_directories = {
        path.split("/", 1)[0].lower()
        for path in normalized_paths
        if "/" in path
    }
    functional_paths = sum(
        bool(FUNCTIONAL_PATH_TERMS.search(path))
        for path in normalized_paths
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
    )
    infrastructure_count = sum(
        name in INFRASTRUCTURE_NAMES
        or name.endswith((".tf", ".tfvars"))
        or path.lower().startswith((".github/workflows/", "k8s/", "kubernetes/"))
        for path, name in zip(normalized_paths, basenames)
    )
    test_count = sum(
        "test" in path.lower() or "spec" in path.lower()
        for path in normalized_paths
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
    )
    data_config_count = sum(
        any(term in path.lower() for term in (
            "database", "migration", "storage", "schema", "config",
        ))
        for path in normalized_paths
    )

    score = (
        min(25, source_count * 3)
        + min(20, manifest_count * 10)
        + min(12, len(meaningful_directories) * 3)
        + min(18, functional_paths * 3)
        + min(12, infrastructure_count * 6)
        + min(8, test_count * 2)
        + min(10, data_config_count * 2)
        + (5 if readme_present else 0)
    )
    return float(min(100, score))


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
    score = score_analyzability(files, readme_present=has_readme)

    return {
        "analyzability_score": score,
        "confidence": "high" if score >= 70 else "medium" if score >= 35 else "low",
        "readme_available": has_readme,
        "source_file_count": len(source_files),
        "source_files": source_files[:120],
        "dependency_and_configuration_files": dependency_files[:80],
        "infrastructure_files": infrastructure_files[:80],
        "technology_detections": technology_detections[:100],
        "api_routes": code_signals.get("api_routes", [])[:80],
        "service_names": code_signals.get("service_names", [])[:80],
        "controller_names": code_signals.get("controller_names", [])[:80],
        "business_file_names": code_signals.get("business_file_names", [])[:80],
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
        analysis_score = score_analyzability(
            paths if isinstance(paths, list) else [],
            readme_present=bool(candidate.get("_readme_present")),
        )
        # Keep relevance dominant, but prefer evidence-rich repositories
        # among candidates that are genuinely about the requested topic.
        ranking_score = relevance * 0.65 + analysis_score * 0.35
        candidate["relevance_score"] = relevance
        candidate["analyzability_score"] = analysis_score
        candidate["ranking_score"] = round(ranking_score, 2)
        ranked.append(candidate)

    return sorted(
        ranked,
        key=lambda item: (
            item["ranking_score"],
            item["relevance_score"],
            _safe_popularity(item.get("stargazers_count")),
        ),
        reverse=True,
    )


def _safe_popularity(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
