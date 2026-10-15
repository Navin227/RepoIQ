"""Validated evidence model shared by repository analysis outputs."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from collections import Counter
import re
import shutil
import subprocess
import time
from typing import Literal
import logging

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.services.analysis_diagnostics import emit

logger = logging.getLogger(__name__)


ClaimState = Literal["confirmed", "inferred", "unknown", "rejected"]


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    start_line: int | None = None
    end_line: int | None = None
    commit_sha: str
    excerpt: str | None = None

    @model_validator(mode="after")
    def valid_reference(self):
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path:
            raise ValueError("Evidence path must be a safe repository relative path")
        if (self.start_line is None) != (self.end_line is None):
            raise ValueError("Both evidence line bounds must be supplied")
        if self.start_line is not None and (self.start_line < 1 or self.end_line < self.start_line):
            raise ValueError("Invalid evidence line range")
        return self


class RepositoryClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    state: ClaimState
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    subject: str = ""
    category: str = "claim"
    target_name: str = ""


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    kind: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class FunctionalComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    responsibility: str
    capabilities: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RepositoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commit_sha: str
    components: list[FunctionalComponent] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    claims: list[RepositoryClaim] = Field(default_factory=list)
    contradictions: list[dict[str, str | list[int]]] = Field(default_factory=list)
    evidence_issues: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    coverage: dict[str, int | str | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self):
        references = [e for component in self.components for e in component.evidence]
        references += [e for claim in self.claims for e in claim.evidence]
        references += [e for relation in self.relationships for e in relation.evidence]
        if any(e.commit_sha != self.commit_sha for e in references):
            raise ValueError("Evidence commit does not match analysis commit")
        names = {component.name for component in self.components}
        for relation in self.relationships:
            if relation.source not in names or relation.target not in names:
                raise ValueError("Relationship endpoint is not a component")
            if any(item.commit_sha != self.commit_sha for item in relation.evidence):
                raise ValueError("Relationship evidence commit mismatch")
        return self

    def validate_sources(self, retrieval: "RepositoryRetrieval") -> "RepositoryModel":
        """Verify every cited range and downgrade unsupported or conflicting claims."""
        all_refs = [e for component in self.components for e in component.evidence]
        all_refs += [e for claim in self.claims for e in claim.evidence]
        all_refs += [e for relation in self.relationships for e in relation.evidence]
        emit(logger, "evidence_validation_started", stage="evidence_validation", commit_sha=self.commit_sha,
             claim_count=len(self.claims), evidence_reference_count=len(all_refs), component_count=len(self.components),
             relationship_count=len(self.relationships))
        invalid_refs: set[int] = set()
        for ref in all_refs:
            try:
                source = retrieval.read(ref.path, ref.start_line or 1, ref.end_line)
                if ref.end_line is not None and ref.end_line > source["end_line"]:
                    raise ValueError("Evidence line range is beyond end of file")
                if ref.excerpt and ref.excerpt.strip() not in source["content"]:
                    raise ValueError("Evidence excerpt does not match source")
                if ref.start_line and ref.start_line > source["end_line"]:
                    raise ValueError("Evidence line range is beyond end of file")
            except (OSError, ValueError) as exc:
                invalid_refs.add(id(ref))
                self.evidence_issues.append(f"{ref.path}: {exc}")
                emit(logger, "evidence_reference_rejected", level=logging.WARNING, stage="evidence_validation",
                     commit_sha=self.commit_sha, path=ref.path, start_line=ref.start_line, end_line=ref.end_line,
                     reason=str(exc))

        for claim in self.claims:
            if any(id(ref) in invalid_refs for ref in claim.evidence):
                claim.state = "rejected"
                claim.confidence = min(claim.confidence, 0.2)
        for component in self.components:
            component.evidence = [ref for ref in component.evidence if id(ref) not in invalid_refs]
        for relation in self.relationships:
            relation.evidence = [ref for ref in relation.evidence if id(ref) not in invalid_refs]

        for claim in self.claims:
            if claim.state == "rejected":
                continue
            try:
                corpus = " ".join(ref.excerpt if ref.excerpt else retrieval.read(ref.path, ref.start_line or 1, ref.end_line)["content"] for ref in claim.evidence)
            except (OSError, ValueError):
                claim.state = "rejected"
                claim.confidence = min(claim.confidence, 0.2)
                continue
            claim_tokens = _content_tokens(claim.text)
            source_tokens = set(_content_tokens(corpus))
            overlap = len(set(claim_tokens) & source_tokens) / max(1, len(set(claim_tokens)))
            if not claim.evidence or overlap < 0.25:
                claim.state = ("rejected" if overlap == 0 else "inferred") if claim.evidence else "unknown"
                claim.confidence = min(claim.confidence, 0.2 if overlap == 0 else 0.55) if claim.evidence else 0
            else:
                exact_quotes = bool(claim.evidence) and all(ref.excerpt for ref in claim.evidence)
                claim.state = "confirmed" if exact_quotes and overlap >= 0.5 else "inferred"
                claim.confidence = max(claim.confidence, 0.7) if claim.state == "confirmed" else min(claim.confidence, 0.55)

        unique: dict[tuple[str, str], RepositoryClaim] = {}
        for claim in self.claims:
            key = (claim.category.casefold(), re.sub(r"\W+", " ", claim.text.casefold()).strip())
            previous = unique.get(key)
            if previous is None:
                unique[key] = claim
                continue
            previous.evidence = list({(ref.path, ref.start_line, ref.end_line, ref.commit_sha): ref for ref in previous.evidence + claim.evidence}.values())
            previous.confidence = max(previous.confidence, claim.confidence)
            if claim.state != previous.state:
                previous.state = "inferred"
                previous.confidence = min(previous.confidence, claim.confidence, 0.65)
        self.claims = list(unique.values())

        buckets: dict[str, list[int]] = {}
        for index, claim in enumerate(self.claims):
            subject = claim.subject or _claim_subject(claim.text)
            buckets.setdefault(subject, []).append(index)
        self.contradictions = []
        for subject, indices in buckets.items():
            if not subject or len(indices) < 2:
                continue
            positives = [i for i in indices if not _is_negated(self.claims[i].text)]
            negatives = [i for i in indices if _is_negated(self.claims[i].text)]
            if positives and negatives:
                pair = [positives[0], negatives[0]]
                self.contradictions.append({"subject": subject, "claim_indices": pair})
                for index in pair:
                    claim = self.claims[index]
                    claim.state = "inferred"
                    claim.confidence = min(claim.confidence, 0.49)
        state_counts = {state: sum(claim.state == state for claim in self.claims) for state in ("confirmed", "inferred", "unknown", "rejected")}
        emit(logger, "evidence_validation_completed", stage="evidence_validation", commit_sha=self.commit_sha,
             claim_state_counts=state_counts, evidence_issue_count=len(self.evidence_issues),
             contradiction_count=len(self.contradictions), deduplicated_claim_count=len(self.claims))
        return self


def _content_tokens(value: str) -> list[str]:
    # Generic repository-level wording must not count as evidence for a
    # specific product, capability, or architectural claim.
    ignored = {
        "this", "that", "with", "from", "into", "have", "does", "uses",
        "used", "the", "and", "for", "are", "was", "will", "can",
        "provides", "supports", "project", "repository", "files", "file",
        "documented", "purpose", "visible", "structure", "usable", "product",
        "tool", "intended", "users", "user", "main", "application",
        "experience", "supporting", "areas", "included", "operational",
        "setup", "available", "evidence", "together", "brings", "interact",
        "rely", "maintain", "run", "system", "platform",
    }
    return [word for word in re.findall(r"[a-z0-9_]{3,}", value.casefold()) if word not in ignored]


def _claim_subject(text: str) -> str:
    normalized = re.sub(r"\b(no|not|never|without|doesn't|isn't|does not|is not)\b", " ", text.casefold())
    return " ".join(_content_tokens(normalized))


def _is_negated(text: str) -> bool:
    return bool(re.search(r"\b(no|not|never|without|doesn't|isn't|does not|is not)\b", text.casefold()))


class RepositoryRetrieval:
    """Safe on-demand source retrieval over an already pinned local checkout."""
    MAX_FILE_BYTES = 256_000
    LANGUAGE_BY_SUFFIX = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
        ".ts": "typescript", ".tsx": "tsx", ".go": "go", ".java": "java",
        ".rs": "rust", ".rb": "ruby", ".php": "php", ".cs": "c_sharp",
        ".kt": "kotlin", ".swift": "swift", ".scala": "scala", ".ex": "elixir",
        ".exs": "elixir", ".vue": "vue", ".svelte": "svelte",
    }

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self._unavailable_languages: set[str] = set()
        self._unsupported_languages_logged: set[str] = set()
        self._unsupported_suffixes_logged: set[str] = set()

    def _safe_path(self, relative: str) -> Path:
        lexical = self.root / relative
        if any(part.is_symlink() for part in (lexical, *lexical.parents) if part != self.root.parent):
            raise ValueError("Symlinks are not valid evidence paths")
        candidate = lexical.resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Unsafe repository path")
        return candidate

    def inventory(self) -> list[str]:
        excluded = {".git", "node_modules", "vendor", "third_party", "third-party", "dist", "build", "target", ".venv", "venv", "__pycache__", ".next", ".nuxt", ".yarn", ".cache", "coverage", "generated"}
        found = []
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root)
            if path.is_symlink() or any(part.lower() in excluded for part in rel.parts):
                continue
            if path.is_file():
                found.append(rel.as_posix())
        return sorted(found)

    def read(self, relative: str, start_line: int = 1, end_line: int | None = None) -> dict:
        path = self._safe_path(relative)
        if not path.is_file() or path.stat().st_size > self.MAX_FILE_BYTES:
            raise ValueError("Missing or oversized source file")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        end = min(end_line or len(lines), len(lines))
        start = max(1, start_line)
        if start > len(lines):
            raise ValueError("Evidence line range is beyond end of file")
        return {"path": PurePosixPath(relative).as_posix(), "start_line": start, "end_line": end,
                "content": "\n".join(lines[start - 1:end])}

    def search(self, query: str, paths: list[str] | None = None) -> list[dict]:
        started = time.perf_counter()
        needle = query.casefold()
        results = []
        if not query.strip():
            emit(logger, "retrieval_skipped_empty_query", level=logging.WARNING, stage="retrieval")
            return results
        rg = shutil.which("rg")
        rg_completed = False
        search_backend = "python_fallback"
        fallback_reason = "ripgrep_unavailable"
        if rg:
            command = [rg, "--line-number", "--no-heading", "--color", "never", "--fixed-strings", "--hidden", "--max-columns", "1000"]
            for excluded in (".git", "node_modules", "vendor", "third_party", "third-party", "dist", "build", "target", ".venv", "venv", "__pycache__", ".next", ".nuxt", ".yarn", ".cache", "coverage", "generated"):
                command.extend(["--glob", f"!**/{excluded}/**"])
            command.extend(["--", query])
            search_paths = paths or [str(self.root)]
            safe_paths = []
            for path in search_paths:
                try:
                    safe_paths.append(str(self._safe_path(path)) if paths else path)
                except ValueError:
                    continue
            command.extend(safe_paths)
            try:
                completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
                if completed.returncode in (0, 1):
                    rg_completed = True
                    search_backend = "ripgrep"
                    for raw in completed.stdout.splitlines():
                        match = re.match(r"^(.+):(\d+):(.*)$", raw)
                        if not match:
                            continue
                        absolute, number, line = match.groups()
                        try:
                            relative = Path(absolute).resolve().relative_to(self.root).as_posix()
                        except (OSError, ValueError):
                            continue
                        from app.services.source_evidence_extractor import redact_secrets
                        results.append({"path": relative, "line": int(number), "start_line": int(number), "end_line": int(number), "text": redact_secrets(line[:1000]), "match_kind": "text"})
                else:
                    fallback_reason = f"ripgrep_exit_{completed.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                results = []
                fallback_reason = type(exc).__name__

        if not rg_completed:
            # Portable fallback for hosts without ripgrep or where the command failed.
            emit(logger, "retrieval_python_fallback_started", level=logging.WARNING, stage="retrieval",
                 reason=fallback_reason, query=query)
            candidates = paths if paths is not None else self.inventory()
            for relative in candidates:
                try:
                    data = self.read(relative)
                except (OSError, ValueError):
                    continue
                for number, line in enumerate(data["content"].splitlines(), 1):
                    if needle in line.casefold():
                        from app.services.source_evidence_extractor import redact_secrets
                        results.append({"path": relative, "line": number, "start_line": number, "end_line": number, "text": redact_secrets(line[:1000]), "match_kind": "text"})

        matched_paths = list(dict.fromkeys(item["path"] for item in results))
        for relative in matched_paths:
            try:
                data = self.read(relative)
            except (OSError, ValueError):
                continue
            structural = self.parse(relative, data["content"])
            for item in structural["symbols"] + structural["imports"]:
                if needle in item["name"].casefold() or needle in item["text"].casefold():
                    results.append({"path": relative, **item, "language": structural["language"], "parser": structural["parser"], "match_kind": item["kind"]})
        parser_by_path = {}
        for item in results:
            relative = item["path"]
            if relative not in parser_by_path:
                try:
                    parser_by_path[relative] = self.parse(relative)["parser"]
                except (OSError, ValueError):
                    parser_by_path[relative] = "text_fallback"
            item.setdefault("language", self.LANGUAGE_BY_SUFFIX.get(Path(relative).suffix.lower()))
            item.setdefault("parser", parser_by_path[relative])
        emit(logger, "retrieval_completed", stage="retrieval", query=query, duration_ms=round((time.perf_counter() - started) * 1000),
             backend=search_backend, fallback_reason=fallback_reason if search_backend != "ripgrep" else None, result_count=len(results),
             files_retrieved=len(matched_paths), ranges=[{"path": item["path"], "start_line": item["start_line"], "end_line": item["end_line"], "kind": item["match_kind"]} for item in results[:20]],
             ranges_truncated=max(0, len(results) - 20), empty_result=not bool(results))
        return results

    def parse(self, relative: str, content: str | None = None) -> dict:
        """Return Tree-sitter symbols/import ranges, or an empty result for unsupported/unavailable grammars."""
        suffix = Path(relative).suffix.lower()
        language = self.LANGUAGE_BY_SUFFIX.get(suffix)
        result = {"language": language, "parser": "text_fallback", "symbols": [], "imports": []}
        if not language:
            if suffix not in self._unsupported_suffixes_logged:
                emit(logger, "tree_sitter_unsupported_language", level=logging.INFO, stage="tree_sitter_parse",
                     suffix=suffix or "[none]", fallback="text_search")
                self._unsupported_suffixes_logged.add(suffix)
            return result
        if language in self._unavailable_languages:
            if language and language not in self._unsupported_languages_logged:
                emit(logger, "tree_sitter_unavailable", level=logging.WARNING, stage="tree_sitter_parse", language=language, fallback="text_search")
                self._unsupported_languages_logged.add(language)
            return result
        try:
            from tree_sitter_language_pack import get_parser
            parser = get_parser(language)
            text = content if content is not None else self.read(relative)["content"]
            encoded = text.encode("utf-8")
            root = parser.parse(encoded).root_node
        except Exception as exc:
            self._unavailable_languages.add(language)
            emit(logger, "tree_sitter_parse_failed", level=logging.WARNING, stage="tree_sitter_parse", language=language,
                 path=relative, exception_type=type(exc).__name__, reason=str(exc), fallback="text_search", exc_info=True)
            return result
        result["parser"] = "tree_sitter"
        symbol_types = {"function_definition", "function_declaration", "method_definition", "class_definition", "class_declaration", "struct_item", "enum_item", "interface_declaration", "type_declaration", "impl_item", "trait_item", "module"}
        stack = [root]
        while stack:
            node = stack.pop()
            kind = node.type
            start = node.start_point.row + 1
            end = node.end_point.row + 1
            snippet = encoded[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            if "import" in kind or kind in {"use_declaration", "using_directive", "include_statement", "import_from_statement"}:
                result["imports"].append({"name": snippet.strip()[:500], "text": snippet.strip()[:500], "kind": kind, "start_line": start, "end_line": end})
            if kind in symbol_types:
                name_node = node.child_by_field_name("name")
                if name_node is None:
                    name_node = next((child for child in node.named_children if child.type in {"identifier", "type_identifier", "constant", "namespace_identifier"}), None)
                name = encoded[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else ""
                if name:
                    result["symbols"].append({"name": name, "text": snippet[:1000], "kind": kind, "start_line": start, "end_line": end})
            stack.extend(reversed(node.named_children))
        emit(logger, "tree_sitter_parse_completed", level=logging.DEBUG, stage="tree_sitter_parse", language=language, path=relative,
             symbol_count=len(result["symbols"]), import_count=len(result["imports"]))
        return result


def build_repository_model(analysis: dict, retrieval: RepositoryRetrieval, commit_sha: str) -> RepositoryModel:
    """Build the canonical evidence ledger from the one normalized analysis response."""
    emit(logger, "repository_model_build_started", stage="repository_model", commit_sha=commit_sha,
         input_module_count=len(analysis.get("modules", [])) if isinstance(analysis.get("modules"), list) else 0,
         input_claim_count=len(analysis.get("claims", [])) if isinstance(analysis.get("claims"), list) else 0)
    modules = analysis.get("modules") if isinstance(analysis.get("modules"), list) else []
    components: list[FunctionalComponent] = []
    relationships: list[Relationship] = []
    claims: list[RepositoryClaim] = []
    evidence_issues: list[str] = []
    by_name: dict[str, FunctionalComponent] = {}

    def refs_for(paths: list[str]) -> list[EvidenceReference]:
        refs = []
        for path in dict.fromkeys(paths):
            try:
                source = retrieval.read(path)
            except (OSError, ValueError):
                evidence_issues.append(f"{path}: referenced source is missing, unsafe, or outside retrieval limits")
                continue
            refs.append(EvidenceReference(path=path, start_line=source["start_line"], end_line=source["end_line"], commit_sha=commit_sha))
        return refs

    for module in modules:
        if not isinstance(module, dict) or not module.get("name"):
            continue
        refs = refs_for([str(path) for path in module.get("components", []) if isinstance(path, str)])
        component = FunctionalComponent(name=str(module["name"]), responsibility=str(module.get("purpose") or ""), capabilities=list(module.get("capabilities") or []), evidence=refs)
        components.append(component)
        by_name[component.name.casefold()] = component
        claim_text = f"{component.name}: {component.responsibility}"
        claims.append(RepositoryClaim(text=claim_text, subject=component.name, category="module", target_name=component.name, state="inferred", confidence=float(module.get("confidence", 50)) / 100, evidence=refs))

    executive = analysis.get("executive_overview") or {}
    for feature in executive.get("user_features", []) if isinstance(executive, dict) else []:
        if not isinstance(feature, dict) or not feature.get("name"):
            continue
        refs = refs_for([str(path) for path in feature.get("evidence", []) if isinstance(path, str)])
        claims.append(RepositoryClaim(text=f"{feature['name']}: {feature.get('description', '')}", subject=str(feature["name"]), category="feature", target_name=str(feature["name"]), state="inferred", confidence=0.5, evidence=refs))

    for raw in analysis.get("claims", []) if isinstance(analysis.get("claims"), list) else []:
        if not isinstance(raw, dict) or not str(raw.get("text") or "").strip():
            continue
        refs = []
        for item in raw.get("evidence", []) if isinstance(raw.get("evidence"), list) else []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            try:
                refs.append(EvidenceReference(path=path, start_line=item.get("start_line"), end_line=item.get("end_line"), commit_sha=commit_sha, excerpt=item.get("excerpt")))
            except Exception:
                continue
        claims.append(RepositoryClaim(text=str(raw["text"]).strip(), subject=str(raw.get("subject") or ""), category=str(raw.get("category") or "claim"), target_name=str(raw.get("target_name") or ""), state="inferred", confidence=min(0.8, max(0.0, float(raw.get("confidence", 0.5)))), evidence=refs))

    for module in modules:
        if not isinstance(module, dict):
            continue
        source = by_name.get(str(module.get("name") or "").casefold())
        if source is None:
            continue
        for target_name in module.get("connected_modules", []):
            target = by_name.get(str(target_name).casefold())
            if target:
                relationships.append(Relationship(source=source.name, target=target.name, kind="connected", evidence=source.evidence))

    raw_claim_texts = {re.sub(r"\W+", " ", str(item.get("text") or "").casefold()).strip() for item in analysis.get("claims", []) if isinstance(item, dict)}
    for item in list(claims):
        key = re.sub(r"\W+", " ", item.text.casefold()).strip()
        if key in raw_claim_texts:
            claims.remove(item)
    model = RepositoryModel(commit_sha=commit_sha, components=components, relationships=relationships, claims=claims, evidence_issues=evidence_issues, coverage={"inventory_files": len(retrieval.inventory()), "status": analysis.get("analysis_status", "unknown")})
    for item in analysis.get("claims", []):
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            continue
        refs = []
        for ref in item.get("evidence", []):
            try:
                refs.append(EvidenceReference(path=str(ref["path"]), start_line=ref.get("start_line"), end_line=ref.get("end_line"), commit_sha=commit_sha, excerpt=ref.get("excerpt") or None))
            except (KeyError, TypeError, ValueError) as exc:
                model.evidence_issues.append(f"Invalid claim evidence record: {exc}")
        try:
            model.claims.append(RepositoryClaim(text=str(item["text"]), subject=str(item.get("subject") or ""), category=str(item.get("category") or "claim"), target_name=str(item.get("target_name") or ""), state="inferred", confidence=float(item.get("confidence", 0.5)), evidence=refs))
        except (TypeError, ValueError) as exc:
            model.evidence_issues.append(f"Invalid claim record: {exc}")
    model = model.validate_sources(retrieval)
    emit(logger, "repository_model_build_completed", stage="repository_model", commit_sha=commit_sha,
         module_count=len(model.components), relationship_count=len(model.relationships), claim_count=len(model.claims),
         evidence_issue_count=len(model.evidence_issues), contradiction_count=len(model.contradictions))
    return model
