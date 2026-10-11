"""High-value source evidence extraction for repository analysis."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".kt", ".rs",
    ".php", ".rb", ".cs", ".swift", ".scala", ".ex", ".exs", ".vue", ".svelte",
}

LOW_VALUE_NAME_PATTERNS = re.compile(
    r"(^_|\.min\.|\.bundle\.|\.generated\.|lock$|\.lock$|"
    r"^package-lock|^yarn\.lock|^pnpm-lock|\.map$|\.d\.ts$|"
    r"^index\.(test|spec)\.|^setup\.(test|spec)\.)",
    re.IGNORECASE,
)

GENERATED_DIR_MARKERS = {
    "generated", "gen", "vendor", "third_party", "third-party",
    "dist", "build", "out", ".next", "coverage",
}

ENTRYPOINT_NAMES = {
    "main.py", "app.py", "app.tsx", "server.py", "wsgi.py", "asgi.py", "manage.py",
    "index.ts", "index.js", "index.tsx", "main.ts", "main.js", "main.tsx", "server.ts", "server.js",
    "main.go", "Main.java", "Application.java", "Program.cs",
}

MAX_CANDIDATE_FILES = 800
MAX_FILE_READ_ATTEMPTS = 120
MAX_SELECTED_FILES = 45
MAX_CHARS_PER_FILE = 8000
MAX_TOTAL_EVIDENCE_CHARS = 120_000

PROJECT_MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "go.mod",
    "cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "gemfile", "mix.exs", "pubspec.yaml",
}
TOOL_CONFIG_PATTERN = re.compile(
    r"(^|/)(?:[^/]*\.config\.[^/]+|[^/]*config\.[^/]+|config/[^/]+|"
    r"tsconfig(?:\.[^/]*)?\.json|angular\.json|\.babelrc(?:\.[^/]*)?|"
    r"\.eslintrc(?:\.[^/]*)?)$",
    re.IGNORECASE,
)

SECRET_PATTERNS = [
    (
        re.compile(
            r"""(?i)((?:[A-Z0-9_-]*)(?:api[_-]?key|secret(?:[_-]?key)?|"""
            r"""access[_-]?(?:token|key)|refresh[_-]?token|auth[_-]?token|"""
            r"""token|password|passwd|pwd|credentials?)\s*[=:]\s*)"""
            r"""(?:"[^"]*"|'[^']*'|[^\s,;]+)"""
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(aws_secret_access_key|private_key)\s*[=:]\s*['\"]?[^\s'\"]+"), r"\1=[REDACTED]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)(mongodb(\+srv)?|postgres(ql)?|mysql|redis)://[^\s'\"@]+:[^\s'\"@]+@"), r"\1://[REDACTED]@"),
]

ROLE_PATTERNS: list[tuple[str, re.Pattern[str], int, list[str]]] = [
    ("entrypoint", re.compile(r"(^|/)(main|app|server|index|wsgi|asgi|manage)\.(py|js|ts|go|java)$", re.I), 98, ["application entrypoint"]),
    ("api_route", re.compile(r"(routes?|routers?|api|endpoints?)/", re.I), 92, ["API routing layer"]),
    ("api_route", re.compile(r"(routes?|router)\.(py|ts|js|go)$", re.I), 90, ["route definition file"]),
    ("service", re.compile(r"(^|/)(api|api-client|http-client)\.(py|ts|tsx|js|jsx)$", re.I), 80, ["API client or service implementation"]),
    ("controller", re.compile(r"controllers?/", re.I), 88, ["HTTP controller"]),
    ("controller", re.compile(r"Controller\.(java|kt|cs)$"), 88, ["controller class file"]),
    ("service", re.compile(r"services?/", re.I), 86, ["business/service layer"]),
    ("service", re.compile(r"Service\.(py|ts|js|java|go)$"), 84, ["service implementation"]),
    ("model", re.compile(r"(models?|entities?|schemas?)/", re.I), 82, ["data model or schema"]),
    ("repository", re.compile(r"(repositories?|repo/|data-access|dao)/", re.I), 80, ["data access layer"]),
    ("database", re.compile(r"(migrations?|alembic|prisma/schema)", re.I), 78, ["database schema or migration"]),
    ("auth", re.compile(r"(auth|authentication|oauth|jwt|session|login|register)", re.I), 85, ["authentication implementation"]),
    ("storage", re.compile(r"(storage|upload|download|s3|blob|file-store)", re.I), 83, ["storage or file handling"]),
    ("frontend_page", re.compile(r"(pages?|views?|routes?)/.*\.(tsx|jsx|vue|svelte)$", re.I), 84, ["frontend page or view"]),
    ("frontend_component", re.compile(r"(components?|features?)/.*\.(tsx|jsx|vue|svelte)$", re.I), 76, ["UI component"]),
    ("frontend_hook", re.compile(r"(hooks?|stores?)/.*\.(ts|tsx|js)$", re.I), 74, ["frontend hook or state"]),
    ("worker", re.compile(r"(workers?|jobs?|queues?|tasks?|celery|bull)", re.I), 82, ["background worker or job"]),
    ("middleware", re.compile(r"middleware", re.I), 80, ["request middleware"]),
    ("test", re.compile(r"(^|/)(tests?|__tests__|spec)/", re.I), 55, ["automated test"]),
    ("infrastructure", re.compile(r"(Dockerfile|docker-compose|\.tf$|k8s|kubernetes|helm|\.github/workflows)", re.I), 70, ["deployment infrastructure"]),
    ("config", re.compile(r"(config/settings|application\.(yml|yaml|properties))", re.I), 65, ["application configuration"]),
]

DOMAIN_SIGNAL_GROUPS: dict[str, tuple[str, ...]] = {
    "ecommerce": ("cart", "checkout", "product", "order", "payment", "inventory", "shop", "catalog"),
    "file_management": ("upload", "download", "file", "document", "folder", "storage", "drive"),
    "chat_messaging": ("chat", "message", "conversation", "channel", "websocket", "socket"),
    "authentication": ("login", "register", "signup", "jwt", "session", "oauth", "password"),
    "analytics_dashboard": ("dashboard", "analytics", "metric", "report", "chart"),
    "content_cms": ("blog", "post", "article", "cms", "content", "editor"),
    "devops_ci": ("pipeline", "deploy", "workflow", "ci", "cd", "kubernetes"),
}


def redact_secrets(text: str) -> str:
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _language_from_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    mapping = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".go": "go", ".java": "java", ".kt": "kotlin", ".rs": "rust",
        ".php": "php", ".rb": "ruby", ".cs": "csharp", ".swift": "swift", ".vue": "vue",
        ".scala": "scala", ".ex": "elixir", ".exs": "elixir",
    }
    return mapping.get(ext, ext.lstrip(".") or "unknown")


def _extract_imports(content: str, language: str) -> list[str]:
    imports: list[str] = []
    if language == "python":
        for m in re.finditer(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", content, re.M):
            imports.append(m.group(1) or m.group(2))
    elif language in ("javascript", "typescript"):
        for m in re.finditer(r"""from\s+['"]([^'"]+)['"]""", content):
            imports.append(m.group(1))
        for m in re.finditer(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", content):
            imports.append(m.group(1))
    elif language == "go":
        for m in re.finditer(r'^\s*"([^"]+)"', content, re.M):
            if "/" in m.group(1):
                imports.append(m.group(1))
    elif language == "java":
        for m in re.finditer(r"^import\s+([\w.]+);", content, re.M):
            imports.append(m.group(1))
    return list(dict.fromkeys(imports))[:40]


def _extract_symbols(content: str, language: str) -> list[str]:
    symbols: list[str] = []
    if language == "python":
        symbols.extend(re.findall(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.M))
        symbols.extend(re.findall(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.M))
        symbols.extend(re.findall(r"^async def\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.M))
    elif language in ("javascript", "typescript"):
        symbols.extend(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)", content))
        symbols.extend(re.findall(r"export\s+(?:default\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", content))
        symbols.extend(re.findall(r"(?:const|let|var)\s+([A-Z][A-Za-z0-9_]*)\s*=\s*(?:\([^)]*\)\s*=>|function)", content))
        symbols.extend(re.findall(r"function\s+([A-Z][A-Za-z0-9_]*)\s*\(", content))
    elif language == "go":
        symbols.extend(re.findall(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z_][A-Za-z0-9_]*)", content, re.M))
        symbols.extend(re.findall(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct", content, re.M))
    elif language == "java":
        symbols.extend(re.findall(r"(?:public|private|protected)\s+(?:static\s+)?(?:class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", content))
        symbols.extend(re.findall(r"(?:public|private|protected)\s+[\w<>,\s]+\s+([a-z][A-Za-z0-9_]*)\s*\(", content))
    else:
        symbols.extend(re.findall(r"(?:class|def|function|func)\s+([A-Za-z_][A-Za-z0-9_]*)", content))
    return list(dict.fromkeys(s for s in symbols if s and not s.startswith("_")))[:50]


def _extract_api_calls(content: str) -> list[str]:
    calls: list[str] = []
    for m in re.finditer(r"""['"](/api/[^'"]+)['"]""", content):
        calls.append(m.group(1))
    for m in re.finditer(r"""fetch\s*\(\s*['"`]([^'"`]+)['"`]""", content):
        calls.append(m.group(1))
    for m in re.finditer(r"""axios\.(?:get|post|put|delete|patch)\s*\(\s*['"`]([^'"`]+)['"`]""", content):
        calls.append(m.group(1))
    return list(dict.fromkeys(calls))[:30]


def extract_routes_from_content(content: str, file_path: str) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    patterns = [
        (re.compile(r"@(?:app|router|api)\.(get|post|put|delete|patch|route)\(\s*['\"]([^'\"]+)['\"]"), None),
        (re.compile(r"@(?:get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"), "GET"),
        (re.compile(r"router\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"), None),
        (re.compile(r"app\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"), None),
        (re.compile(r"\.(?:Get|Post|Put|Delete|Patch)\(\s*['\"]([^'\"]+)['\"]"), None),
    ]
    lines = content.splitlines()
    for i, line in enumerate(lines):
        for pattern, default_method in patterns:
            for match in pattern.finditer(line):
                groups = match.groups()
                if len(groups) == 2:
                    method, path = groups[0].upper(), groups[1]
                elif len(groups) == 1:
                    method = (default_method or "GET").upper()
                    path = groups[0]
                else:
                    continue
                handler = ""
                for j in range(i, min(i + 8, len(lines))):
                    fn = re.search(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)", lines[j])
                    if fn:
                        handler = fn.group(1)
                        break
                    fn = re.search(r"(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)", lines[j])
                    if fn:
                        handler = fn.group(1)
                        break
                routes.append({
                    "method": method,
                    "path": path,
                    "handler": handler,
                    "file": file_path,
                })
    for m in re.finditer(r'["\'](/api/[^"\']+)["\']', content):
        path = m.group(1)
        if not any(r["path"] == path for r in routes):
            routes.append({"method": "UNKNOWN", "path": path, "handler": "", "file": file_path})
    return routes


def _smart_truncate(content: str, max_chars: int, language: str) -> str:
    if len(content) <= max_chars:
        return content
    lines = content.splitlines()
    selected: set[int] = set()
    budget = max_chars
    import_budget = min(1500, max_chars // 4)

    anchors: list[tuple[int, int, int]] = []
    for index, line in enumerate(lines):
        if re.match(r"^\s*(?:import |from )", line):
            line_cost = len(line) + 1
            if line_cost <= import_budget:
                selected.add(index)
                import_budget -= line_cost
                budget -= line_cost
        elif re.search(r"(?:router|app|api)\.(?:get|post|put|delete|patch|route)\s*\(", line, re.I):
            anchors.append((12, index, min(index + 14, len(lines) - 1)))
        elif re.match(
            r"^\s*(?:export\s+|async\s+)?(?:default\s+)?"
            r"(?:class|function|def|func|type|interface|enum)\b|"
            r"^\s*(?:async\s+)?def\b|^\s*@",
            line,
        ):
            anchors.append((10, index, min(index + 12, len(lines) - 1)))
        elif language == "java" and re.match(
            r"^\s*(?:public|private|protected)\s+", line
        ):
            anchors.append((9, index, min(index + 12, len(lines) - 1)))

    for _, start, end in sorted(anchors, key=lambda item: (-item[0], item[1])):
        new_indexes = [index for index in range(start, end + 1) if index not in selected]
        cost = sum(len(lines[index]) + 1 for index in new_indexes)
        if cost <= budget:
            selected.update(new_indexes)
            budget -= cost

    ordered = sorted(selected)
    preserved: list[str] = []
    previous = -1
    for index in ordered:
        if index > previous + 1:
            preserved.append("# ... [intervening source omitted] ...\n")
        preserved.append(lines[index] + "\n")
        previous = index

    result = "".join(preserved)
    return result[:max_chars]


@dataclass
class ScoredFile:
    path: str
    role: str
    priority: int
    reasons: list[str] = field(default_factory=list)


def _score_file(rel_path: str) -> ScoredFile | None:
    lower = rel_path.lower()
    name = Path(rel_path).name
    if any(part in GENERATED_DIR_MARKERS for part in lower.split("/")):
        return None
    if LOW_VALUE_NAME_PATTERNS.search(name):
        return None

    if name.lower() in PROJECT_MANIFEST_NAMES:
        return ScoredFile(
            path=rel_path,
            role="dependency_manifest",
            priority=91,
            reasons=["project dependency manifest"],
        )

    if TOOL_CONFIG_PATTERN.search(lower):
        return ScoredFile(
            path=rel_path,
            role="tooling_config",
            priority=77,
            reasons=["build or framework configuration"],
        )

    suffix = Path(rel_path).suffix.lower()
    if suffix not in SOURCE_SUFFIXES and not (
        name.lower() in ("dockerfile",) or name.endswith((".yml", ".yaml", ".tf"))
    ):
        return None

    best_role = "source"
    best_priority = 40
    reasons: list[str] = ["source file"]

    if name in ENTRYPOINT_NAMES or name.lower() in {n.lower() for n in ENTRYPOINT_NAMES}:
        best_role = "entrypoint"
        best_priority = 99
        reasons = ["application entrypoint filename"]

    for role, pattern, priority, role_reasons in ROLE_PATTERNS:
        if pattern.search(rel_path):
            if priority > best_priority:
                best_role = role
                best_priority = priority
                reasons = list(role_reasons)

    if best_priority <= 45 and suffix not in SOURCE_SUFFIXES:
        return None
    return ScoredFile(path=rel_path, role=best_role, priority=best_priority, reasons=reasons)


def _exclusion_reason(rel_path: str) -> str:
    lower = rel_path.lower()
    name = Path(rel_path).name
    if any(part in GENERATED_DIR_MARKERS for part in lower.split("/")):
        return "generated_directory"
    if LOW_VALUE_NAME_PATTERNS.search(name):
        return "low_value_filename"
    return "no_matching_file_role"


def _categorize_path(role: str, rel_path: str, buckets: dict[str, list[str]]) -> None:
    key_map = {
        "entrypoint": "entrypoints",
        "api_route": "api_routes",
        "controller": "controllers",
        "service": "services",
        "model": "models",
        "repository": "repositories",
        "frontend_page": "frontend_pages",
        "frontend_component": "frontend_components",
        "auth": "auth_files",
        "storage": "storage_files",
        "database": "database_files",
        "worker": "worker_files",
        "test": "tests",
        "infrastructure": "infrastructure",
    }
    bucket = key_map.get(role)
    if bucket and rel_path not in buckets[bucket]:
        buckets[bucket].append(rel_path)


def _collect_capability_signals(
    symbols: list[str],
    routes: list[dict[str, Any]],
    paths: list[str],
    readme: str,
) -> list[dict[str, Any]]:
    tokens: set[str] = set()
    for s in symbols:
        for part in re.findall(r"[A-Za-z][a-z0-9]+|[a-z]+", s):
            if len(part) > 2:
                tokens.add(part.lower())
    for r in routes:
        for part in re.findall(r"[a-z]+", str(r.get("path", "")).lower()):
            if len(part) > 2:
                tokens.add(part)
    for p in paths:
        for part in re.findall(r"[a-z]+", p.lower()):
            if len(part) > 3:
                tokens.add(part)
    readme_lower = (readme or "").lower()
    signals: list[dict[str, Any]] = []
    for domain, keywords in DOMAIN_SIGNAL_GROUPS.items():
        matched = [kw for kw in keywords if kw in tokens or kw in readme_lower]
        if len(matched) >= 2:
            confidence = min(95, 40 + 15 * len(matched))
            signals.append({
                "domain": domain,
                "matched_signals": matched[:12],
                "confidence": confidence,
            })
        elif len(matched) == 1:
            signals.append({
                "domain": domain,
                "matched_signals": matched,
                "confidence": 35,
            })
    return sorted(signals, key=lambda x: -x["confidence"])[:15]


class SourceEvidenceExtractor:
    def extract(
        self,
        repo_path: Path,
        files: list[str],
        readme: str = "",
    ) -> dict[str, Any]:
        buckets: dict[str, list[str]] = {
            "entrypoints": [],
            "api_routes": [],
            "controllers": [],
            "services": [],
            "models": [],
            "repositories": [],
            "frontend_pages": [],
            "frontend_components": [],
            "auth_files": [],
            "storage_files": [],
            "database_files": [],
            "worker_files": [],
            "tests": [],
            "infrastructure": [],
            "selected_source_files": [],
        }

        candidates: list[ScoredFile] = []
        source_file_count = 0
        excluded: list[dict[str, str]] = []
        for rel in files:
            if Path(rel).suffix.lower() in SOURCE_SUFFIXES:
                source_file_count += 1
            scored = _score_file(rel)
            if scored:
                candidates.append(scored)
            elif (
                Path(rel).suffix.lower() in SOURCE_SUFFIXES
                or Path(rel).name.lower() in PROJECT_MANIFEST_NAMES
                or TOOL_CONFIG_PATTERN.search(rel.lower())
                or Path(rel).name.lower() == "dockerfile"
                or Path(rel).suffix.lower() in {".yml", ".yaml", ".tf"}
            ):
                excluded.append({"path": rel, "reason": _exclusion_reason(rel)})

        candidates.sort(key=lambda c: (-c.priority, c.path))
        discovered_candidate_count = len(candidates)
        for cand in candidates[MAX_CANDIDATE_FILES:]:
            excluded.append({"path": cand.path, "reason": "candidate_limit"})
        candidates = candidates[:MAX_CANDIDATE_FILES]

        all_routes: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        total_chars = 0
        total_available_chars = 0
        successfully_read: list[str] = []
        read_attempts = 0

        for candidate_index, cand in enumerate(candidates):
            if len(selected) >= MAX_SELECTED_FILES:
                excluded.extend(
                    {"path": item.path, "reason": "selected_file_limit"}
                    for item in candidates[candidate_index:]
                )
                break
            if total_chars >= MAX_TOTAL_EVIDENCE_CHARS:
                excluded.extend(
                    {"path": item.path, "reason": "total_character_budget"}
                    for item in candidates[candidate_index:]
                )
                break
            if read_attempts >= MAX_FILE_READ_ATTEMPTS:
                excluded.extend(
                    {"path": item.path, "reason": "read_attempt_limit"}
                    for item in candidates[candidate_index:]
                )
                break

            abs_path = repo_path / cand.path
            if not abs_path.is_file():
                excluded.append({"path": cand.path, "reason": "file_missing"})
                continue
            read_attempts += 1
            try:
                raw = abs_path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                logger.warning(
                    "Source evidence read failed: path=%s error_type=%s",
                    cand.path,
                    type(exc).__name__,
                )
                excluded.append({
                    "path": cand.path,
                    "reason": f"read_error_{type(exc).__name__}",
                })
                continue

            successfully_read.append(cand.path)
            total_available_chars += len(raw)
            lang = _language_from_path(cand.path)
            redacted = redact_secrets(raw)
            content = _smart_truncate(redacted, MAX_CHARS_PER_FILE, lang)
            chunk_len = len(content)
            if total_chars + chunk_len > MAX_TOTAL_EVIDENCE_CHARS:
                remaining = MAX_TOTAL_EVIDENCE_CHARS - total_chars
                if remaining < 500:
                    excluded.append({
                        "path": cand.path,
                        "reason": "remaining_character_budget_below_500",
                    })
                    excluded.extend(
                        {"path": item.path, "reason": "total_character_budget"}
                        for item in candidates[candidate_index + 1:]
                    )
                    break
                content = _smart_truncate(content, remaining, lang)
                chunk_len = len(content)

            symbols = _extract_symbols(redacted, lang)
            imports = _extract_imports(redacted, lang)
            api_calls = _extract_api_calls(redacted) if cand.role.startswith("frontend") else []
            file_routes = extract_routes_from_content(redacted, cand.path)
            all_routes.extend(file_routes)

            entry = {
                "path": cand.path,
                "role": cand.role,
                "language": lang,
                "priority": cand.priority,
                "reason": cand.reasons,
                "symbols": symbols,
                "imports": imports,
            }
            if len(redacted) > len(content):
                entry["content_truncated"] = True
                entry["content_truncation_reason"] = "source evidence character budget"
                entry["content_chars_available"] = len(redacted)
                entry["content_chars_selected"] = len(content)
            if api_calls:
                entry["api_calls"] = api_calls
            entry["content"] = content

            selected.append(entry)
            buckets["selected_source_files"].append(cand.path)
            _categorize_path(cand.role, cand.path, buckets)
            total_chars += chunk_len

        for rel in files:
            if (
                Path(rel).suffix.lower() in SOURCE_SUFFIXES
                and rel not in {cand.path for cand in candidates}
                and not any(item["path"] == rel for item in excluded)
            ):
                excluded.append({"path": rel, "reason": "not_selected_by_file_policy"})

        # Dedupe routes
        seen_routes: set[tuple[str, str, str]] = set()
        unique_routes: list[dict[str, Any]] = []
        for r in all_routes:
            key = (r.get("method", ""), r.get("path", ""), r.get("file", ""))
            if key in seen_routes:
                continue
            seen_routes.add(key)
            unique_routes.append(r)

        capability_signals = _collect_capability_signals(
            [s for f in selected for s in f.get("symbols", [])],
            unique_routes,
            [f["path"] for f in selected],
            readme,
        )

        stats = {
            "total_files_in_scan": len(files),
            "discovered_source_files": source_file_count,
            "source_files_count": source_file_count,
            "candidate_evidence_files": discovered_candidate_count,
            "selected_evidence_files": len(selected),
            "routes_detected": len(unique_routes),
            "symbols_detected": len({
                symbol for item in selected for symbol in item.get("symbols", [])
            }),
            "models_detected": len({
                symbol
                for item in selected
                if item.get("role") == "model"
                for symbol in item.get("symbols", [])
            }),
            "source_files_read": len(successfully_read),
            "source_chars_available": total_available_chars,
            "source_chars_selected": total_chars,
            "evidence_payload_chars": total_chars,
            "excluded_file_counts": {
                reason: sum(item["reason"] == reason for item in excluded)
                for reason in dict.fromkeys(item["reason"] for item in excluded)
            },
        }

        logger.info(
            "Repository evidence selection: %s",
            json.dumps({
                "discovered_files": files,
                "discovered_source_files": [
                    path for path in files if Path(path).suffix.lower() in SOURCE_SUFFIXES
                ],
                "source_files_read": successfully_read,
                "candidate_evidence_files": [cand.path for cand in candidates],
                "selected_evidence_files": [item["path"] for item in selected],
                "excluded_files": excluded,
                **stats,
            }, ensure_ascii=False),
        )

        return {
            **buckets,
            "selected_source_file_details": selected,
            "routes": unique_routes[:120],
            "capability_signals": capability_signals,
            "stats": stats,
        }
