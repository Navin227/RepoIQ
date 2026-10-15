"""Deterministic repository inventory and bounded Gemma context preparation."""
from __future__ import annotations

import ast
import json
import logging
import os
import re
import time
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.source_evidence_extractor import redact_secrets

logger = logging.getLogger(__name__)
IGNORED_DIRS = {".git", ".yarn", ".claude", ".cache", ".parcel-cache", ".turbo", ".next", ".nuxt", "node_modules", "dist", "build", "out", "coverage", "venv", ".venv", "env", "__pycache__", "target", "vendor", ".idea", ".vscode", ".gradle", ".mvn", ".pnpm-store", "tmp", "temp"}
SECRET_NAME = re.compile(r"(^|/)(\.env(?:\..*)?|id_rsa(?:\.pub)?|[^/]*\.(?:pem|p12|pfx|key|keystore)|[^/]*(?:secret|credential|private[_-]?key)[^/]*)$", re.I)
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs", ".cpp", ".h", ".sql", ".vue", ".svelte"}
EXECUTION_RE = re.compile(r"\b(if __name__\s*==|FastAPI\s*\(|Flask\s*\(|express\s*\(|createServer\s*\(|createRoot\s*\(|createApp\s*\(|urlpatterns\s*=|@app\.(get|post|put|delete|patch)|router\.(get|post|put|delete|patch)|\.listen\s*\(|func main\s*\(|public static void main|@SpringBootApplication)\b")
ENTRY_POINT_RE = re.compile(r"\b(if __name__\s*==|FastAPI\s*\(|Flask\s*\(|express\s*\(|createServer\s*\(|createRoot\s*\(|createApp\s*\(|\.listen\s*\(|func main\s*\(|public static void main|@SpringBootApplication)\b")
IMPORTANT_RE = re.compile(r"\b(class |def |function |export (default )?(async )?(function|class|const)|router\.|app\.(get|post|put|delete|patch)|@app\.|SELECT\s+|CREATE TABLE|interface |type )", re.I)
IMPORT_RE = re.compile(r"(?:^|\n)\s*(?:import\s+(?:[^;\n]*?\s+from\s+)?|export\s+[^;\n]*?\s+from\s+|require\s*\(|import\s*\()\s*['\"]([^'\"]+)['\"]", re.M)
STATUS_INSPECTED = {"fully_inspected", "partially_inspected"}


class ContextPreparationError(RuntimeError):
    def __init__(self, message: str, diagnostic_code: str):
        super().__init__(message)
        self.diagnostic_code = diagnostic_code


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
    evidence_references: list[Any] = Field(default_factory=list)


def _role(path: str, content: str = "") -> list[str]:
    name = PurePosixPath(path).name.lower()
    parts = {p.lower() for p in PurePosixPath(path).parts}
    text = content[:120_000]
    roles: list[str] = []
    if name in {"main.py", "app.py", "main.ts", "index.ts", "server.js", "manage.py", "asgi.py", "wsgi.py", "main.go", "main.rs"} or ENTRY_POINT_RE.search(text): roles.append("entry_point")
    if parts & {"routes", "route", "routers", "api", "controllers"} or re.search(r"@app\.(get|post)|router\.(get|post)|urlpatterns\s*=", text): roles.append("route")
    if parts & {"services", "service", "core", "domain"} or re.search(r"\b(class .*Service|def .*service|function .*service)\b", text, re.I): roles.append("business_logic")
    if parts & {"models", "repositories", "database", "db", "migrations", "schemas"} or re.search(r"\b(CREATE TABLE|class .*Model|BaseModel|Schema\()", text): roles.append("data_access")
    if parts & {"integrations", "clients", "providers"} or re.search(r"\b(fetch\(|axios\.|requests\.|httpx\.|boto3\.)", text): roles.append("integration")
    if parts & {"test", "tests", "__tests__", "spec"} or name.startswith("test_"): roles.append("test")
    if name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml", "dockerfile", "makefile", "tsconfig.json", "jsconfig.json"} or name.startswith(".env.example"): roles.append("configuration")
    return roles


def _resolve_imports(relative: str, text: str, all_paths: set[str], aliases: dict[str, str]) -> tuple[list[str], str]:
    """Resolve Python and JS/TS local imports; other languages are explicitly unsupported."""
    suffix = PurePosixPath(relative).suffix.lower()
    refs: set[str] = set()
    unsupported = ""
    if suffix == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                        _add_python_ref(refs, relative, module, all_paths)
                elif isinstance(node, ast.ImportFrom):
                    base = "." * node.level + (node.module or "")
                    _add_python_ref(refs, relative, base, all_paths)
                    for alias in node.names:
                        _add_python_ref(refs, relative, f"{base}.{alias.name}", all_paths)
        except (SyntaxError, ValueError):
            unsupported = "python_import_parse_failed"
    elif suffix in {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}:
        for specifier in IMPORT_RE.findall(text):
            if specifier.startswith((".", "/")):
                _add_js_ref(refs, relative, specifier, all_paths)
            else:
                for alias, target in aliases.items():
                    if specifier == alias or specifier.startswith(alias.rstrip("/") + "/"):
                        _add_js_ref(refs, relative, "/" + (target.rstrip("/") + specifier[len(alias):]), all_paths)
    elif suffix in SOURCE_SUFFIXES:
        unsupported = f"relationship_extraction_unsupported:{suffix}"
    return sorted(refs), unsupported


def _add_python_ref(refs: set[str], source: str, module: str, all_paths: set[str]) -> None:
    base = list(PurePosixPath(source).parent.parts)
    dots = len(module) - len(module.lstrip("."))
    if dots:
        base = base[:max(0, len(base) - dots + 1)]
    name = module.lstrip(".")
    parts = base + ([p for p in name.split(".") if p] if name else [])
    candidate = "/".join(parts)
    possibilities = [candidate + ".py", candidate + "/__init__.py"]
    if not dots:
        possibilities.extend([name.replace(".", "/") + ".py", name.replace(".", "/") + "/__init__.py"])
    refs.update(p for p in possibilities if p in all_paths and p != source)


def _add_js_ref(refs: set[str], source: str, specifier: str, all_paths: set[str]) -> None:
    base = PurePosixPath(source).parent
    path = PurePosixPath(specifier)
    if specifier.startswith("/"):
        candidate = path.as_posix().lstrip("/")
    else:
        candidate = (base / path).as_posix()
    candidate = str(PurePosixPath(candidate))
    suffixes = ["", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".json", "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]
    refs.update((candidate + suffix) for suffix in suffixes if candidate + suffix in all_paths and candidate + suffix != source)


def _aliases(root: Path) -> dict[str, str]:
    for filename in ("tsconfig.json", "jsconfig.json"):
        try:
            raw = json.loads((root / filename).read_text(encoding="utf-8"))
            compiler = raw.get("compilerOptions", {})
            base = str(compiler.get("baseUrl") or ".")
            paths = compiler.get("paths", {})
            result = {}
            for alias, targets in paths.items() if isinstance(paths, dict) else []:
                if isinstance(targets, list) and targets:
                    key = alias.removesuffix("/*")
                    value = str(targets[0]).removesuffix("/*")
                    result[key] = (PurePosixPath(base) / value).as_posix()
            return result
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            continue
    return {}


def build_inventory(repo_path: str | Path, commit_sha: str, max_file_bytes: int) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(repo_path).resolve()
    entries: list[dict[str, Any]] = []
    source_text: dict[str, str] = {}
    excluded_directories: list[dict[str, str]] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        for directory in dirs:
            if directory in IGNORED_DIRS:
                excluded_directories.append({"path": (current_path / directory).relative_to(root).as_posix(), "reason": "generated_or_dependency_directory_policy"})
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for filename in sorted(files):
            path = Path(current) / filename
            relative = path.relative_to(root).as_posix()
            try:
                size = path.stat().st_size
                ext = path.suffix.lower() or "[no extension]"
                item: dict[str, Any] = {"path": relative, "file_type": ext, "size_bytes": size, "status": "omitted", "reason": "not_yet_selected", "roles": [], "relationships": [], "important_to_execution_path": False, "gemma_processed": False, "inspection_mode": "none", "line_ranges_supplied": []}
                if path.is_symlink(): item.update(status="excluded", reason="symlink_policy")
                elif SECRET_NAME.search(relative): item.update(status="excluded", reason="secret_or_credential_policy")
                elif size > max_file_bytes: item.update(status="omitted", reason="maximum_file_size")
                elif ext not in SOURCE_SUFFIXES and filename.lower() not in {"readme", "readme.md", "readme.rst", "package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml", "dockerfile", "compose.yaml", "docker-compose.yml", ".env.example", "tsconfig.json", "jsconfig.json"} and ext not in {".md", ".rst", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml", ".sql"}:
                    try: binary = b"\x00" in path.read_bytes()[:8192]
                    except OSError: binary = False
                    item.update(status="excluded", reason="binary_file" if binary else "unsupported_or_nontext_file")
                else:
                    try:
                        raw = path.read_bytes()
                        if b"\x00" in raw[:8192]: item.update(status="excluded", reason="binary_file")
                        else:
                            text = raw.decode("utf-8")
                            source_text[relative] = redact_secrets(text)
                            item.update(status="omitted", reason="not_yet_selected", roles=_role(relative, text))
                    except (OSError, UnicodeError) as exc: item.update(status="unreadable", reason=type(exc).__name__)
                entries.append(item)
            except OSError as exc:
                entries.append({"path": relative, "file_type": path.suffix.lower(), "size_bytes": None, "status": "unreadable", "reason": type(exc).__name__, "roles": [], "relationships": [], "important_to_execution_path": False, "gemma_processed": False, "inspection_mode": "none", "line_ranges_supplied": []})

    all_paths = set(source_text)
    aliases = _aliases(root)
    entry_paths = {item["path"] for item in entries if "entry_point" in item["roles"]}
    reverse: dict[str, set[str]] = {path: set() for path in all_paths}
    unsupported: set[str] = set()
    for item in entries:
        path = item["path"]
        if path not in source_text: continue
        refs, limitation = _resolve_imports(path, source_text[path], all_paths, aliases)
        item["relationships"] = refs
        item["relationship_extraction"] = "python_ast_or_js_ts_imports" if PurePosixPath(path).suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"} else limitation
        if limitation: unsupported.add(limitation)
        for ref in refs: reverse.setdefault(ref, set()).add(path)
    # Traverse both imports and reverse imports from discovered entry points.
    distance: dict[str, int] = {}
    queue = deque((path, 0) for path in sorted(entry_paths))
    while queue:
        path, depth = queue.popleft()
        if path in distance: continue
        distance[path] = depth
        if depth >= 12: continue
        related = set(reverse.get(path, ()))
        related.update(next((e["relationships"] for e in entries if e["path"] == path), []))
        for related_path in sorted(related):
            if related_path not in distance: queue.append((related_path, depth + 1))
    for item in entries:
        path = item["path"]
        item["important_to_execution_path"] = path in distance
        item["execution_path_distance"] = distance.get(path)

    return {"schema_version": "2.0", "commit_sha": commit_sha, "discovered_count": len(entries), "eligible_source_count": sum(e["file_type"] in SOURCE_SUFFIXES and e["status"] != "excluded" for e in entries), "fully_inspected_count": 0, "partially_inspected_count": 0, "inspected_count": 0, "excluded_count": sum(e["status"] == "excluded" for e in entries), "excluded_directories": sorted(excluded_directories, key=lambda item: item["path"].lower()), "omitted_count": sum(e["status"] == "omitted" for e in entries), "unreadable_count": sum(e["status"] == "unreadable" for e in entries), "inspection_failed_count": 0, "unresolved_count": 0, "unsupported_relationship_extraction": sorted(unsupported), "files": entries}, source_text


def _chat(api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    retries = max(0, min(int(settings.provider_retry_count), 2))
    for attempt in range(retries + 1):
        try:
            response = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://repoiq.local", "X-Title": "RepoIQ"}, json={"model": model, "messages": messages, "temperature": 0.1, "response_format": {"type": "json_object"}, "provider": {"data_collection": "deny", "zdr": True}}, timeout=max(5, int(settings.provider_timeout_seconds)))
            response.raise_for_status()
            try: content = response.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc: raise RuntimeError("OpenRouter returned a malformed response") from exc
            if not isinstance(content, str) or not content.strip(): raise RuntimeError("OpenRouter returned an empty response")
            return content
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            retryable = status in {429, 500, 502, 503, 504} or status is None
            if attempt >= retries or not retryable: raise RuntimeError(f"OpenRouter request failed{f' ({status})' if status else ''}") from exc
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("OpenRouter request failed")


def _selected_ranges(content: str, per_file_tokens: int, important: bool) -> list[dict[str, Any]]:
    lines = content.splitlines()
    budget_chars = max(800, per_file_tokens * 3)
    if len(content) <= budget_chars:
        return [{"start_line": 1, "end_line": max(1, len(lines)), "content": content}]
    # Keep imports/header, executable declarations, and the tail (where late
    # handlers/main blocks commonly live), retaining real source line numbers.
    anchors = {1, 2, 3, 4, 5, len(lines)}
    for number, line in enumerate(lines, 1):
        if IMPORTANT_RE.search(line) or (important and EXECUTION_RE.search(line)):
            anchors.update(range(max(1, number - 2), min(len(lines), number + 5) + 1))
    windows: list[tuple[int, int]] = []
    for number in sorted(anchors):
        if windows and number <= windows[-1][1] + 1: windows[-1] = (windows[-1][0], number)
        else: windows.append((number, number))
    chosen: list[tuple[int, int]] = []
    used = 0
    for start, end in windows:
        window_cost = sum(len(lines[i - 1]) + 1 for i in range(start, end + 1))
        if used + window_cost <= budget_chars:
            chosen.append((start, end)); used += window_cost
        elif start <= 5 or end == len(lines):
            # A budget too small to fit essential edge context is handled as
            # an explicitly partial excerpt, never as a complete inspection.
            remaining = max(0, budget_chars - used)
            if remaining > 0:
                count = max(1, remaining // max(1, (window_cost // (end - start + 1))))
                if start <= 5: chosen.append((start, min(end, start + count - 1)))
                else: chosen.append((max(start, end - count + 1), end))
                used = budget_chars
        if used >= budget_chars: break
    return [{"start_line": start, "end_line": end, "content": "\n".join(lines[start - 1:end])} for start, end in chosen]


def _complement_ranges(total_lines: int, supplied_ranges: list[dict[str, Any]]) -> list[dict[str, int]]:
    omitted: list[dict[str, int]] = []
    cursor = 1
    for item in sorted(supplied_ranges, key=lambda value: value["start_line"]):
        start, end = item["start_line"], item["end_line"]
        if cursor < start: omitted.append({"start_line": cursor, "end_line": start - 1})
        cursor = max(cursor, end + 1)
    if cursor <= total_lines: omitted.append({"start_line": cursor, "end_line": total_lines})
    return omitted


def _merge_findings(findings: list[dict[str, Any]], valid_paths: set[str]) -> dict[str, Any]:
    list_keys = ("subsystems", "entry_points", "modules", "relationships", "integrations", "data_flows", "important_dependencies", "uncertainties", "conflicts")
    merged: dict[str, Any] = {key: [] for key in list_keys}
    full_purpose = "\n".join(dict.fromkeys(f["purpose"] for f in findings if f.get("purpose")))
    merged["purpose"] = full_purpose[:8_000]
    merged["purpose_truncated_chars"] = max(0, len(full_purpose) - len(merged["purpose"]))
    unsupported: list[str] = []
    for finding in findings:
        for key in list_keys:
            for value in finding.get(key, []):
                serialized = json.dumps(value, sort_keys=True, ensure_ascii=False)
                if serialized not in {json.dumps(old, sort_keys=True, ensure_ascii=False) for old in merged[key]}:
                    merged[key].append(value)
        unsupported.extend(finding.get("unsupported_evidence_paths", []))
    merged["evidence_paths"] = sorted({path for finding in findings for path in finding.get("evidence_paths", []) if path in valid_paths})
    refs = [ref for finding in findings for ref in finding.get("evidence_references", []) if isinstance(ref, dict) and ref.get("path") in valid_paths]
    merged["evidence_references"] = list({json.dumps(ref, sort_keys=True, ensure_ascii=False): ref for ref in refs}.values())
    merged["truncated_evidence_references"] = max(0, len(merged["evidence_references"]) - 500)
    merged["evidence_references"] = merged["evidence_references"][:500]
    merged["unsupported_evidence_paths"] = sorted(set(unsupported))
    merged["truncated_categories"] = {}
    merged["truncated_categories"]["evidence_references"] = merged["truncated_evidence_references"]
    merged["truncated_categories"]["purpose"] = merged["purpose_truncated_chars"]
    for key in list_keys:
        if key in {"uncertainties", "conflicts"}: cap = 200
        else: cap = 100
        merged["truncated_categories"][key] = max(0, len(merged[key]) - cap)
        def priority(value: Any) -> tuple[int, str]:
            if isinstance(value, dict):
                raw = str(value.get("priority") or value.get("importance") or "").casefold()
                rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(raw, 4)
                return rank, json.dumps(value, sort_keys=True, ensure_ascii=False)
            return 4, str(value)
        merged[key] = sorted(merged[key], key=priority)[:cap]
    return merged


def prepare_context(metadata: dict[str, Any], scan: dict[str, Any], repo_path: str | Path | None, commit_sha: str, base_payload: dict[str, Any]) -> dict[str, Any]:
    if not repo_path: raise ContextPreparationError("Repository path is required for deterministic context preparation", "context_preparation_failure")
    manifest, sources = build_inventory(repo_path, commit_sha, max(1024, int(settings.context_max_file_bytes)))
    records = manifest["files"]
    by_path = {e["path"]: e for e in records}
    eligible = [e for e in records if e["status"] == "omitted" and e["reason"] == "not_yet_selected" and e["path"] in sources]
    eligible.sort(key=lambda e: (
        0 if e["important_to_execution_path"] else 1,
        0 if "entry_point" in e["roles"] else 1,
        0 if e["roles"] and set(e["roles"]) & {"route", "business_logic", "data_access", "integration"} else 1,
        e.get("execution_path_distance") if e.get("execution_path_distance") is not None else 999,
        e["path"].casefold(),
    ))
    batch_size = max(1, min(int(settings.context_batch_files), 20))
    total_budget = max(256, int(settings.context_token_budget))
    per_file_budget = max(128, int(settings.context_per_file_token_budget))
    batch_budget = max(256, int(settings.context_batch_token_budget))
    used_total = 0
    selected: list[dict[str, Any]] = []
    excerpts: list[dict[str, Any]] = []
    for item in eligible:
        if used_total >= total_budget:
            item.update(status="omitted", reason="total_context_token_budget")
            continue
        text = sources[item["path"]]
        allowance = min(per_file_budget, total_budget - used_total)
        ranges = _selected_ranges(text, allowance, bool(item["important_to_execution_path"] or item["roles"]))
        char_cost = sum(len(r["content"]) for r in ranges)
        cost = max(1, (char_cost + 3) // 4) + 200
        if not ranges or cost > allowance:
            item.update(status="omitted", reason="per_file_or_context_token_budget")
            continue
        excerpted = len(ranges) != 1 or ranges[0]["start_line"] != 1 or ranges[0]["end_line"] < max(1, len(text.splitlines()) - 1)
        item.update(status="omitted", reason="awaiting_gemma", inspection_mode="excerpt" if excerpted else "full", line_ranges_supplied=[{"start_line": r["start_line"], "end_line": r["end_line"]} for r in ranges])
        selected.append(item)
        for range_item in ranges:
            excerpts.append({"path": item["path"], **range_item, "inspection_mode": "excerpt" if excerpted else "full"})
        used_total += cost

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0
    for item in selected:
        file_ranges = [e for e in excerpts if e["path"] == item["path"]]
        token_cost = sum((len(e["content"]) + 3) // 4 for e in file_ranges) + 200
        if current and (len(current) >= batch_size or current_tokens + token_cost > batch_budget):
            batches.append(current); current = []; current_tokens = 0
        if token_cost > batch_budget:
            item.update(status="omitted", reason="per_batch_token_budget")
            excerpts = [e for e in excerpts if e["path"] != item["path"]]
            continue
        current.append(item); current_tokens += token_cost
    if current: batches.append(current)

    key = settings.openrouter_api_key
    if not key: raise ContextPreparationError("OPENROUTER_API_KEY is not configured", "gemma_provider_failure")
    if not batches: raise ContextPreparationError("Repository has no readable files within the supported context policy", "insufficient_repository_coverage")
    findings: list[dict[str, Any]] = []
    for index, batch in enumerate(batches):
        batch_paths = {item["path"] for item in batch}
        evidence = [{"path": item["path"], "roles": item["roles"], "imports": item["relationships"], "important_to_execution_path": item["important_to_execution_path"], "ranges": [{k: e[k] for k in ("start_line", "end_line", "content")} for e in excerpts if e["path"] == item["path"]]} for item in batch]
        prompt = "Analyze only supplied code and exact source ranges. Return JSON keys purpose, subsystems, entry_points, modules, relationships, integrations, data_flows, important_dependencies, uncertainties, conflicts, evidence_paths, evidence_references. Every finding must include exact evidence path and line ranges or a supporting excerpt. Never cite a path or line outside supplied ranges.\n" + json.dumps({"repository": metadata.get("full_name") or metadata.get("name"), "commit_sha": commit_sha, "batch": index + 1, "total_batches": len(batches), "files": evidence}, ensure_ascii=False)
        try:
            raw = _chat(key, settings.openrouter_model, [{"role": "system", "content": "You prepare concise, source-grounded repository context for a second analysis model. Return valid JSON only. Use the supplied file paths, exact line ranges, detected roles, imports, symbols, routes and configuration as evidence. Identify real module boundaries and only direct relationships supported by imports or explicit interactions. Exclude generated, vendored and dependency files from functional findings. Keep uncertainty explicit, preserve exact evidence references, and prefer fewer accurate findings over generic summaries. Never invent paths, line ranges, capabilities or architecture edges."}, {"role": "user", "content": prompt}])
        except Exception as exc:
            for item in batch:
                item.update(status="inspection_failed", reason=f"gemma_request_failed:{type(exc).__name__}", gemma_processed=False)
            manifest["inspection_failed_count"] = sum(e["status"] == "inspection_failed" for e in records)
            raise ContextPreparationError(f"Gemma provider request failed: {type(exc).__name__}", "gemma_provider_failure") from exc
        try:
            parsed = GemmaBatchFinding.model_validate_json(raw).model_dump(mode="json")
        except (json.JSONDecodeError, ValueError) as exc:
            for item in batch: item.update(status="inspection_failed", reason="malformed_gemma_output", gemma_processed=False)
            manifest["inspection_failed_count"] = sum(e["status"] == "inspection_failed" for e in records)
            raise ContextPreparationError(f"Gemma returned malformed context JSON for batch {index + 1}", "gemma_malformed_output") from exc
        cited = set(parsed["evidence_paths"])
        unsupported = sorted(cited - batch_paths)
        supplied_ranges = {(e["path"], r["start_line"], r["end_line"], r["content"]) for e in evidence for r in e["ranges"]}
        valid_refs = []
        for ref in parsed["evidence_references"]:
            if not isinstance(ref, dict) or ref.get("path") not in batch_paths:
                if isinstance(ref, dict) and ref.get("path"): unsupported.append(str(ref["path"]))
                continue
            path = ref["path"]
            start, end = ref.get("start_line"), ref.get("end_line")
            excerpt = ref.get("excerpt")
            matching = []
            if isinstance(start, int) and isinstance(end, int) and isinstance(excerpt, str) and excerpt:
                for range_path, lo, hi, content in supplied_ranges:
                    if range_path != path or start < lo or end > hi: continue
                    sliced_lines = content.splitlines()[start - lo:end - lo + 1]
                    if excerpt in "\n".join(sliced_lines): matching.append(True)
            if matching:
                valid_refs.append({"path": path, "start_line": start, "end_line": end, "excerpt": excerpt})
            else:
                unsupported.append(path)
        # Pydantic tolerates fields of the wrong inner shape; validate that all
        # structured collections remain lists of serializable bounded content.
        summary: dict[str, Any] = {k: parsed[k] for k in ("subsystems", "entry_points", "modules", "relationships", "integrations", "data_flows", "important_dependencies", "uncertainties", "conflicts")}
        summary.update(purpose=parsed["purpose"][:8_000], batch=index + 1, evidence_paths=sorted(cited & batch_paths), evidence_references=valid_refs, unsupported_evidence_paths=sorted(set(unsupported)))
        findings.append(summary)
        for item in batch:
            ranges = item["line_ranges_supplied"]
            full_lines = max(1, len(sources[item["path"]].splitlines()))
            status = "fully_inspected" if len(ranges) == 1 and ranges[0]["start_line"] == 1 and ranges[0]["end_line"] >= full_lines else "partially_inspected"
            omitted_ranges = _complement_ranges(full_lines, ranges)
            item.update(status=status, reason="bounded_excerpt_policy" if omitted_ranges else None, gemma_processed=True, source_lines_total=full_lines, omitted_line_ranges=omitted_ranges)

    for item in records:
        if item["status"] == "omitted" and item["reason"] == "awaiting_gemma": item.update(status="omitted", reason="not_included_in_successful_batch")
    merged = _merge_findings(findings, set(by_path))
    # Preserve each finding's line-level citations only when both path and range
    # were included in the successful Gemma batches.
    manifest["fully_inspected_count"] = sum(e["status"] == "fully_inspected" for e in records)
    manifest["partially_inspected_count"] = sum(e["status"] == "partially_inspected" for e in records)
    manifest["inspected_count"] = manifest["fully_inspected_count"] + manifest["partially_inspected_count"]
    manifest["omitted_count"] = sum(e["status"] == "omitted" for e in records)
    manifest["excluded_count"] = sum(e["status"] == "excluded" for e in records)
    manifest["unreadable_count"] = sum(e["status"] == "unreadable" for e in records)
    source_entries = [e for e in records if e["file_type"] in SOURCE_SUFFIXES and "test" not in e.get("roles", [])]
    important_entries = [e for e in source_entries if "entry_point" in e["roles"]]
    inspected_entries = [e for e in important_entries if e["status"] == "fully_inspected"]
    fully_inspected_paths = {e["path"] for e in records if e["status"] == "fully_inspected"}
    critical = [e for e in records if e["important_to_execution_path"] and e["file_type"] in SOURCE_SUFFIXES and e["path"] not in fully_inspected_paths]
    if important_entries:
        core_covered = len(inspected_entries) == len(important_entries) and not critical
    elif source_entries:
        # Libraries and non-executable repositories often have no `main`
        # entrypoint. Require direct inspection of at least one implementation
        # file instead of declaring every such repository incomplete.
        role_paths = [e for e in source_entries if set(e.get("roles", [])) & {"route", "business_logic", "data_access", "integration"}]
        analysis_roots = role_paths or source_entries
        core_covered = any(e["status"] == "fully_inspected" for e in analysis_roots)
    else:
        core_covered = True
    manifest["unresolved_count"] = sum(e["status"] in {"omitted", "unreadable", "inspection_failed"} for e in records)
    manifest["coverage"] = {"total_discovered_files": manifest["discovered_count"], "eligible_source_files": manifest["eligible_source_count"], "fully_inspected_files": manifest["fully_inspected_count"], "partially_inspected_files": manifest["partially_inspected_count"], "omitted_files": manifest["omitted_count"], "excluded_files": manifest["excluded_count"], "unreadable_files": manifest["unreadable_count"], "inspection_failed_files": manifest["inspection_failed_count"], "important_entry_points": len(important_entries), "important_entry_points_fully_inspected": len(inspected_entries), "known_critical_dependencies_not_inspected": [e["path"] for e in critical], "core_execution_paths_sufficiently_covered": core_covered, "status": "sufficient" if core_covered else "partial", "reason": "all discovered entry points and traced critical dependencies were inspected" if important_entries and core_covered else "at least one implementation file was inspected in a repository without a detected executable entry point" if core_covered and source_entries else "one or more entry points or traced execution-path dependencies lack complete Gemma evidence"}
    unresolved = [e["path"] for e in records if e["status"] in {"omitted", "unreadable", "inspection_failed"}]
    bundle = {"repository": metadata.get("full_name") or metadata.get("name"), "commit_sha": commit_sha, "coverage_manifest": manifest, "coverage_gate": manifest["coverage"], "repository_map": merged, "source_excerpts": excerpts, "batches_processed": len(findings), "limitations": {"unresolved_files": unresolved, "unresolved_questions": merged["uncertainties"], "conflicting_findings": merged["conflicts"], "unsupported_evidence_paths": merged["unsupported_evidence_paths"], "truncated_finding_categories": merged["truncated_categories"], "provider": settings.openrouter_model, "unsupported_relationship_extraction": manifest["unsupported_relationship_extraction"]}}
    return bundle
