"""Build compact evidence-oriented semantic repository profile for LLM input."""

from __future__ import annotations

from typing import Any


def build_semantic_repository_profile(
    metadata: dict[str, Any],
    readme: str,
    stack: dict[str, Any],
    scan: dict[str, Any],
    code_signals: dict[str, Any],
) -> dict[str, Any]:
    source_evidence = scan.get("source_evidence") or {}
    if not isinstance(source_evidence, dict):
        source_evidence = {}

    categories = stack.get("categories", {}) if isinstance(stack, dict) else {}
    flat_tech: dict[str, list[str]] = {}
    for cat, items in categories.items():
        names = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
                elif isinstance(item, str):
                    names.append(item)
        flat_tech[str(cat)] = list(dict.fromkeys(names))[:30]

    routes = source_evidence.get("routes") or code_signals.get("api_routes_enriched") or []
    if routes and isinstance(routes[0], str):
        routes = [{"path": r, "method": "UNKNOWN", "handler": "", "file": ""} for r in routes]

    frontend_evidence = []
    for key in ("frontend_pages", "frontend_components"):
        for path in source_evidence.get(key, [])[:25]:
            file_meta = _find_selected_file(scan, path)
            frontend_evidence.append({
                "path": path,
                "role": "frontend_page" if key == "frontend_pages" else "frontend_component",
                "symbols": file_meta.get("symbols", [])[:8] if file_meta else [],
                "api_calls": file_meta.get("api_calls", [])[:8] if file_meta else [],
            })

    selected_paths = [
        item for item in scan.get("_selected_source_file_objects", [])
        if isinstance(item, dict)
    ][:40]
    if not selected_paths:
        selected_paths = [
            {"path": p} for p in source_evidence.get("selected_source_files", [])[:40]
            if isinstance(p, str)
        ]

    functional_evidence = list(source_evidence.get("capability_signals", []))[:15]
    domain_signals = [
        {
            "domain": s.get("domain"),
            "confidence": s.get("confidence"),
            "signals": s.get("matched_signals", []),
        }
        for s in functional_evidence
        if isinstance(s, dict)
    ]

    stats = source_evidence.get("stats", {}) if isinstance(source_evidence.get("stats"), dict) else {}

    profile = {
        "project_identity": {
            "name": metadata.get("full_name") or metadata.get("name"),
            "description": metadata.get("description", ""),
            "topics": metadata.get("topics", []),
            "primary_language": metadata.get("language") or metadata.get("primary_language"),
        },
        "domain_signals": domain_signals,
        "application_type_signals": _application_type_signals(flat_tech, source_evidence, metadata),
        "technologies": flat_tech,
        "functional_evidence": functional_evidence,
        "api_evidence": routes[:80],
        "frontend_evidence": frontend_evidence[:40],
        "backend_evidence": _path_evidence(source_evidence, ("controllers", "services", "entrypoints")),
        "data_evidence": _path_evidence(source_evidence, ("models", "repositories", "database_files")),
        "auth_evidence": _path_evidence(source_evidence, ("auth_files",)),
        "storage_evidence": _path_evidence(source_evidence, ("storage_files",)),
        "integration_evidence": _integration_evidence(code_signals, stack),
        "infrastructure_evidence": _path_evidence(source_evidence, ("infrastructure",)),
        "source_evidence_summary": {
            "selected_count": stats.get("selected_evidence_files", len(selected_paths)),
            "routes_count": stats.get("routes_detected", len(routes)),
            "files": [
                {
                    "path": f.get("path"),
                    "role": f.get("role"),
                    "symbols": (f.get("symbols") or [])[:6],
                }
                for f in selected_paths
                if isinstance(f, dict)
            ][:35],
        },
        "test_evidence": _path_evidence(source_evidence, ("tests",)),
        "confidence_signals": {
            "source_files_selected": stats.get("selected_evidence_files", 0),
            "meaningful_routes": len([r for r in routes if isinstance(r, dict) and r.get("handler")]),
            "readme_available": bool((readme or "").strip()),
            "technology_detection_count": sum(len(v) for v in flat_tech.values()),
        },
    }
    return profile


def _find_selected_file(scan: dict[str, Any], path: str) -> dict[str, Any] | None:
    se = scan.get("source_evidence") or {}
    for item in se.get("selected_source_files", []):
        if isinstance(item, dict) and item.get("path") == path:
            return item
    # Full objects stored separately in scan
    for item in scan.get("_selected_source_file_objects", []):
        if isinstance(item, dict) and item.get("path") == path:
            return item
    return None


def _path_evidence(source_evidence: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for key in keys:
        for path in source_evidence.get(key, [])[:30]:
            if isinstance(path, str):
                out.append({"path": path, "category": key.rstrip("s")})
    return out


def _application_type_signals(
    flat_tech: dict[str, list[str]],
    source_evidence: dict[str, Any],
    metadata: dict[str, Any],
) -> list[str]:
    signals: list[str] = []
    if flat_tech.get("frontend"):
        signals.append("has_frontend_implementation")
    if flat_tech.get("backend") or source_evidence.get("entrypoints"):
        signals.append("has_backend_implementation")
    if source_evidence.get("worker_files"):
        signals.append("has_background_processing")
    if source_evidence.get("models") or source_evidence.get("database_files"):
        signals.append("has_persistence_layer")
    desc = str(metadata.get("description") or "").lower()
    if "api" in desc or source_evidence.get("api_routes"):
        signals.append("exposes_http_api")
    if source_evidence.get("infrastructure"):
        signals.append("has_deployment_artifacts")
    return signals


def _integration_evidence(code_signals: dict[str, Any], stack: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for name in code_signals.get("service_names", [])[:20]:
        items.append(f"service:{name}")
    cats = stack.get("categories", {}) if isinstance(stack, dict) else {}
    for cat in ("cloud", "database", "messaging"):
        for item in cats.get(cat, []) or []:
            if isinstance(item, dict) and item.get("name"):
                items.append(f"{cat}:{item['name']}")
    return items[:40]
