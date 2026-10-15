"""Deterministic repository inventory and bounded Gemma context preparation."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.source_evidence_extractor import redact_secrets

logger = logging.getLogger(__name__)
IGNORED_DIRS = {".git", ".yarn", ".claude", ".cache", ".parcel-cache", ".turbo", ".next", ".nuxt", "node_modules", "dist", "build", "out", "coverage", "venv", ".venv", "env", "__pycache__", "target", "vendor", ".idea", ".vscode", ".gradle", ".mvn", ".pnpm-store", "tmp", "temp"}
SECRET_NAME = re.compile(r"(^|/)(\.env(?:\..*)?|id_rsa(?:\.pub)?|[^/]*\.(?:pem|p12|pfx|key|keystore)|[^/]*(?:secret|credential|private[_-]?key)[^/]*)$", re.I)
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs", ".cpp", ".h", ".sql", ".vue", ".svelte"}


class GemmaBatchFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    purpose: str = ""
    subsystems: list[Any] = Field(default_factory=list)
    entry_points: list[Any] = Field(default_factory=list)
    modules: list[Any] = Field(default_factory=list)
    relationships: list[Any] = Field(default_factory=list)
    integrations: list[Any] = Field(default_factory=list)
    data_flows: list[Any] = Field(default_factory=list)
    important_dependencies: list[Any] = Field(default_factory=list)
    uncertainties: list[Any] = Field(default_factory=list)
    conflicts: list[Any] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)


def _role(path: str) -> list[str]:
    name = Path(path).name.lower()
    parts = {p.lower() for p in Path(path).parts}
    roles: list[str] = []
    if name in {"main.py", "app.py", "main.ts", "index.ts", "server.js", "manage.py", "asgi.py", "wsgi.py"}: roles.append("entry_point")
    if parts & {"routes", "route", "routers", "api", "controllers"}: roles.append("route")
    if parts & {"services", "service", "core", "domain"}: roles.append("business_logic")
    if parts & {"models", "repositories", "database", "db", "migrations"}: roles.append("data_access")
    if parts & {"integrations", "clients", "providers"}: roles.append("integration")
    if parts & {"test", "tests", "__tests__", "spec"} or name.startswith("test_"): roles.append("test")
    if name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml", "dockerfile", "makefile"} or name.startswith(".env.example"): roles.append("configuration")
    return roles


def build_inventory(repo_path: str | Path, commit_sha: str, max_file_bytes: int) -> dict[str, Any]:
    root = Path(repo_path).resolve()
    entries: list[dict[str, Any]] = []
    source_text: dict[str, str] = {}
    excluded_directories: list[dict[str, str]] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        for directory in dirs:
            if directory in IGNORED_DIRS:
                excluded_directories.append({
                    "path": (current_path / directory).relative_to(root).as_posix(),
                    "reason": "generated_or_dependency_directory_policy",
                })
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for filename in sorted(files):
            path = Path(current) / filename
            relative = path.relative_to(root).as_posix()
            try:
                size = path.stat().st_size
                ext = path.suffix.lower() or "[no extension]"
                item: dict[str, Any] = {"path": relative, "file_type": ext, "size_bytes": size, "status": "discovered", "reason": None, "roles": _role(relative), "relationships": []}
                if path.is_symlink():
                    item.update(status="excluded", reason="symlink_policy")
                elif SECRET_NAME.search(relative):
                    item.update(status="excluded", reason="secret_or_credential_policy")
                elif size > max_file_bytes:
                    item.update(status="omitted", reason="maximum_file_size")
                elif ext not in SOURCE_SUFFIXES and filename.lower() not in {"readme", "readme.md", "readme.rst", "package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml", "dockerfile", "compose.yaml", "docker-compose.yml", ".env.example"} and ext not in {".md", ".rst", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml", ".sql"}:
                    try:
                        binary = b"\x00" in path.read_bytes()[:8192]
                    except OSError:
                        binary = False
                    item.update(status="excluded", reason="binary_file" if binary else "unsupported_or_nontext_file")
                else:
                    try:
                        raw = path.read_bytes()
                        if b"\x00" in raw[:8192]:
                            item.update(status="excluded", reason="binary_file")
                        else:
                            text = raw.decode("utf-8")
                            item["status"] = "eligible"
                            source_text[relative] = redact_secrets(text)
                    except (OSError, UnicodeError) as exc:
                        item.update(status="unreadable", reason=type(exc).__name__)
                entries.append(item)
            except OSError as exc:
                entries.append({"path": relative, "file_type": path.suffix.lower(), "size_bytes": None, "status": "unreadable", "reason": type(exc).__name__, "roles": _role(relative), "relationships": []})
    # Direct imports are independently discovered from inspected text.
    by_module = {Path(p).with_suffix("").as_posix().replace("/", "."): p for p in source_text}
    for path, text in source_text.items():
        refs: set[str] = set()
        for module in re.findall(r"(?:from|import)\s+([\w.]+)", text):
            candidate = by_module.get(module)
            if candidate and candidate != path: refs.add(candidate)
        for item in entries:
            if item["path"] == path:
                item["relationships"] = sorted(refs)[:40]
                break
    return {"schema_version": "1.0", "commit_sha": commit_sha, "discovered_count": len(entries), "inspected_count": 0, "excluded_count": sum(e["status"] == "excluded" for e in entries), "excluded_directories": sorted(excluded_directories, key=lambda item: item["path"].lower()), "omitted_count": sum(e["status"] == "omitted" for e in entries), "unreadable_count": sum(e["status"] == "unreadable" for e in entries), "unresolved_count": 0, "files": entries}, source_text


def _chat(api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    retries = max(0, min(int(settings.provider_retry_count), 2))
    for attempt in range(retries + 1):
        try:
            response = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://repoiq.local", "X-Title": "RepoIQ"}, json={"model": model, "messages": messages, "temperature": 0.1, "response_format": {"type": "json_object"}, "provider": {"data_collection": "deny", "zdr": True}}, timeout=max(5, int(settings.provider_timeout_seconds)))
            response.raise_for_status()
            try:
                content = response.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("OpenRouter returned a malformed response") from exc
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("OpenRouter returned an empty response")
            return content
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            retryable = status in {429, 500, 502, 503, 504} or status is None
            if attempt >= retries or not retryable: raise RuntimeError(f"OpenRouter request failed{f' ({status})' if status else ''}") from exc
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("OpenRouter request failed")


def prepare_context(metadata: dict[str, Any], scan: dict[str, Any], repo_path: str | Path | None, commit_sha: str, base_payload: dict[str, Any]) -> dict[str, Any]:
    if not repo_path:
        raise RuntimeError("Repository path is required for deterministic context preparation")
    manifest, sources = build_inventory(repo_path, commit_sha, max(1024, int(settings.context_max_file_bytes)))
    eligible = [e for e in manifest["files"] if e["status"] == "eligible"]
    # Prioritize entry points, routes, core implementation and manifests. Stable path ordering makes batches reproducible.
    eligible.sort(key=lambda e: (
        0 if "entry_point" in e["roles"] else 1,
        Path(e["path"]).parts[0].lower() if len(Path(e["path"]).parts) > 1 else "_root",
        e["path"].lower(),
    ))
    batch_size = max(1, min(int(settings.context_batch_files), 20))
    remaining_tokens = max(2_000, int(settings.context_token_budget))
    selected: list[dict[str, Any]] = []
    excerpts: list[dict[str, Any]] = []
    for item in eligible:
        content = sources[item["path"]]
        # A conservative character estimate keeps the aggregate provider input bounded.
        excerpt = content[: min(len(content), 8_000, remaining_tokens * 3)]
        cost = max(1, (len(excerpt) + 3) // 4) + 200
        if cost > remaining_tokens or not excerpt:
            item.update(status="omitted", reason="context_token_budget")
            continue
        selected.append(item)
        excerpts.append({"path": item["path"], "start_line": 1, "end_line": max(1, excerpt.count("\n") + 1), "content": excerpt})
        item["status"] = "inspected"
        if len(excerpt) < len(content):
            item["excerpt_truncated"] = True
        remaining_tokens -= cost
    batches = [selected[i:i + batch_size] for i in range(0, len(selected), batch_size)]
    key = settings.openrouter_api_key
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    if not batches:
        raise RuntimeError("Repository has no readable files within the supported context policy")
    findings: list[dict[str, Any]] = []
    for index, batch in enumerate(batches):
        evidence = []
        for item in batch:
            path = item["path"]
            excerpt = next(e["content"] for e in excerpts if e["path"] == path)
            evidence.append({"path": path, "roles": item["roles"], "imports": item["relationships"], "content": excerpt})
        manifest_paths = {item["path"] for item in batch}
        for item in manifest["files"]:
            if item["path"] in manifest_paths: item["status"] = "inspected"
        prompt = "Analyze only code facts supported by supplied paths. Return JSON with keys purpose, subsystems, entry_points, modules, relationships, integrations, data_flows, important_dependencies, uncertainties, conflicts, evidence_paths. Facts need evidence_paths.\n" + json.dumps({"repository": metadata.get("full_name") or metadata.get("name"), "commit_sha": commit_sha, "batch": index + 1, "total_batches": len(batches), "subsystems": sorted({Path(item["path"]).parts[0] if len(Path(item["path"]).parts) > 1 else "_root" for item in batch}), "files": evidence}, ensure_ascii=False)
        raw = _chat(key, settings.openrouter_model, [{"role": "system", "content": "You prepare source-grounded repository context for a second analysis model. Return valid JSON only; do not invent paths."}, {"role": "user", "content": prompt}])
        try:
            parsed = GemmaBatchFinding.model_validate_json(raw).model_dump(mode="json")
            summary = {key: parsed[key][:20] for key in ("subsystems", "entry_points", "modules", "relationships", "integrations", "data_flows", "important_dependencies", "uncertainties", "conflicts")}
            summary["purpose"] = parsed["purpose"][:2000]
            summary["batch"] = index + 1
            summary["evidence_paths"] = sorted(p for p in parsed["evidence_paths"] if p in manifest_paths)
            findings.append(summary)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Gemma returned malformed context JSON for batch {index + 1}") from exc
    manifest["inspected_count"] = sum(e["status"] == "inspected" for e in manifest["files"])
    unresolved = [e["path"] for e in manifest["files"] if e["status"] == "eligible"]
    manifest["omitted_count"] = sum(e["status"] == "omitted" for e in manifest["files"])
    manifest["unresolved_count"] = len(unresolved)
    unresolved_questions = [str(question)[:500] for finding in findings for question in finding["uncertainties"]]
    conflicts = [str(conflict)[:500] for finding in findings for conflict in finding["conflicts"]]
    bundle = {"repository": metadata.get("full_name") or metadata.get("name"), "commit_sha": commit_sha, "coverage_manifest": manifest, "repository_map": findings, "module_relationships": [{"path": e["path"], "imports": e["relationships"]} for e in manifest["files"] if e["relationships"]], "source_excerpts": excerpts, "limitations": {"unresolved_files": unresolved, "unresolved_questions": unresolved_questions, "conflicting_findings": conflicts, "provider": settings.openrouter_model}}
    # Preserve deterministic extraction already assembled by the legacy evidence builder.
    bundle["deterministic_context"] = {k: base_payload.get(k) for k in ("metadata", "detected_technology_stack", "api_routes_enriched", "services", "controllers", "semantic_repository_profile", "analysis_evidence")}
    return bundle
