
import inspect
import json
import logging
import subprocess
import hashlib
import uuid
import time
import re
from pathlib import Path, PurePosixPath
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_result import AnalysisResult
from app.models.repository import Repository
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.github_service import GitHubService, get_github_service
from app.services.stack_detector import StackDetector
from app.services.repository_structure_service import RepositoryStructureService
from app.services.llm_service import LLMService
from app.services.similar_repo_service import SimilarRepoService
from app.utils.repo_scanner import RepoScanner
from app.utils.git_utils import normalize_github_url
from app.services.repository_model import RepositoryRetrieval, build_repository_model
from app.services.analysis_diagnostics import emit, run_context, stage
from app.services.analysis_status import classify_analysis_status

router = APIRouter()
logger = logging.getLogger(__name__)

UNKNOWN_EVIDENCE_MESSAGE = "Unable to confidently determine from repository evidence."
_SEMANTIC_TERM_GROUPS = (
    {"checkout", "purchase", "purchases", "buy", "order", "orders"},
    {"catalog", "catalogue", "product", "products", "item", "items"},
    {"upload", "uploaded", "uploads", "download", "file", "files", "document"},
    {"persist", "persistence", "save", "store", "storage", "write", "database"},
    {"login", "signin", "authenticate", "authentication", "identity", "credential"},
)


def _semantically_related_tokens(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    return any(bool(left & group) and bool(right & group) for group in _SEMANTIC_TERM_GROUPS)


def _normalise_text(value: Any) -> str:
    """Normalize labels for conservative, case-insensitive comparisons."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()


def _as_dict(value: Any) -> dict:
    """Return a dictionary for optional AI-generated objects."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    """Return a list for optional AI-generated collections."""
    return value if isinstance(value, list) else []


def _narrative_count(executive: Any) -> int:
    data = _as_dict(executive)
    count = 0
    for key in ("what_is_this_project", "typical_use_cases", "who_is_this_for"):
        value = data.get(key)
        count += len(value) if isinstance(value, list) else int(bool(value.strip())) if isinstance(value, str) else 0
    for key in ("why_was_it_built", "why_is_it_valuable", "one_line_summary"):
        count += int(bool(str(data.get(key) or "").strip()))
    return count


def _run_output_filter(operation, *args):
    try:
        return operation(*args)
    except Exception as exc:
        emit(logger, "analysis_output_filtering_failed", level=logging.ERROR,
             stage="output_filtering", operation=getattr(operation, "__name__", "unknown"),
             exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
        raise RuntimeError("output_filtering_failure") from exc


def _filter_claims_by_coverage(claims: list, manifest: dict) -> list:
    inspected = {
        str(item.get("path")).replace("\\", "/").casefold(): item
        for item in _as_list(manifest.get("files"))
        if isinstance(item, dict) and item.get("status") in {"inspected", "fully_inspected", "partially_inspected"}
    }
    filtered = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        item = dict(claim)
        refs = _as_list(item.get("evidence"))
        valid_refs = []
        reasons = list(_as_list(item.get("validation_reasons")))
        for ref in refs:
            if not isinstance(ref, dict):
                reasons.append({"reason_code": "invalid_schema", "stage": "coverage_filter"})
                continue
            path = str(ref.get("path") or "").replace("\\", "/")
            entry = inspected.get(path.casefold())
            if entry is None:
                reasons.append({"reason_code": "path_not_in_manifest", "stage": "coverage_filter", "path": path})
                continue
            supplied_ranges = _as_list(entry.get("gemini_supplied_line_ranges"))
            start, end = ref.get("start_line"), ref.get("end_line")
            if "gemini_supplied_line_ranges" in entry and not any(
                isinstance(bounds, dict)
                and isinstance(start, int) and isinstance(end, int)
                and start >= int(bounds.get("start_line") or 1)
                and end <= int(bounds.get("end_line") or 0)
                for bounds in supplied_ranges
            ):
                reasons.append({"reason_code": "partial_source_coverage", "stage": "coverage_filter", "path": path})
                continue
            valid_refs.append(ref)
        item["evidence"] = valid_refs
        item["validation_reasons"] = reasons
        if refs and not item["evidence"]:
            try:
                item["confidence"] = min(float(item.get("confidence") or 0), 0.2)
            except (TypeError, ValueError):
                item["confidence"] = 0.0
        filtered.append(item)
    return filtered


def _validate_report_recommendations(report: dict, retrieval: RepositoryRetrieval, manifest: dict) -> dict:
    inspected = {
        str(item.get("path")).replace("\\", "/").casefold(): item
        for item in _as_list(manifest.get("files"))
        if isinstance(item, dict) and item.get("status") in {"inspected", "fully_inspected", "partially_inspected"}
    }
    validated = dict(report)
    recommendations = []
    for recommendation in _as_list(report.get("recommendations")):
        if not isinstance(recommendation, dict):
            continue
        valid_refs = []
        rejected_refs = []
        for reference in _as_list(recommendation.get("evidence")):
            if not isinstance(reference, dict):
                rejected_refs.append({"reason_code": "invalid_schema", "stage": "recommendation_validation"})
                continue
            path = str(reference.get("path") or "").replace("\\", "/")
            entry = inspected.get(path.casefold())
            start = reference.get("start_line")
            end = reference.get("end_line")
            excerpt = str(reference.get("excerpt") or "")
            if entry is None:
                rejected_refs.append({"reason_code": "path_not_in_manifest", "stage": "recommendation_validation", "path": path})
                continue
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
                rejected_refs.append({"reason_code": "invalid_line_range", "stage": "recommendation_validation", "path": path})
                continue
            supplied_ranges = _as_list(entry.get("gemini_supplied_line_ranges"))
            if "gemini_supplied_line_ranges" in entry and not any(
                isinstance(bounds, dict)
                and start >= int(bounds.get("start_line") or 1)
                and end <= int(bounds.get("end_line") or 0)
                for bounds in supplied_ranges
            ):
                rejected_refs.append({"reason_code": "partial_source_coverage", "stage": "recommendation_validation", "path": path})
                continue
            try:
                source = retrieval.read(path, start, end)
                if end <= source["end_line"] and excerpt and excerpt in source["content"]:
                    valid_refs.append(reference)
                else:
                    rejected_refs.append({"reason_code": "excerpt_mismatch", "stage": "recommendation_validation", "path": path})
            except (OSError, ValueError):
                rejected_refs.append({"reason_code": "path_not_in_repository", "stage": "recommendation_validation", "path": path})
        if valid_refs:
            recommendations.append({**recommendation, "evidence": valid_refs, "validation_reasons": rejected_refs})
    validated["recommendations"] = recommendations
    return validated


def _claim_is_usable(claim: Any) -> bool:
    return (
        getattr(claim, "state", "unknown") in {"confirmed", "inferred"}
        and bool(str(getattr(claim, "text", "") or "").strip())
    )


def _claim_supports_label(label: str, claims: list) -> bool:
    """
    Require a usable repository claim to mention the architecture label.

    A claim about an unrelated architecture component must not validate every
    component in the architecture response.
    """
    normalized_label = _normalise_text(label)
    if not normalized_label:
        return False

    generic = {"api", "service", "system", "module", "component", "application", "backend", "frontend", "layer", "data", "flow", "architecture", "repository", "process"}
    label_tokens = {
        token for token in re.findall(r"[a-z0-9_+#.-]+", normalized_label)
        if len(token) > 2 and token not in generic
    }
    if not label_tokens:
        return False

    for claim in claims:
        if not _claim_is_usable(claim):
            continue
        claim_text = _normalise_text(getattr(claim, "text", ""))
        claim_target = _normalise_text(getattr(claim, "target_name", ""))
        claim_subject = _normalise_text(getattr(claim, "subject", ""))
        if not getattr(claim, "evidence", []):
            continue

        if (
            normalized_label in claim_text
            or normalized_label == claim_target
            or normalized_label == claim_subject
        ):
            return True

        claim_tokens = {
            token for token in re.findall(r"[a-z0-9_+#.-]+", claim_text)
            if len(token) > 2
        }
        # A single distinctive token is enough to associate an entry with an
        # independently source-verified claim; requiring every noun phrase
        # token loses valid labels such as "order persistence service".
        if label_tokens and _semantically_related_tokens(label_tokens, claim_tokens):
            return True

    return False


def _filter_architecture(
    architecture: Any,
    claims: list,
) -> dict:
    """
    Conservatively filter architecture components and steps.

    The architecture is not accepted wholesale just because one architecture
    claim exists. Each component and each flow/lifecycle entry must have a
    corresponding usable claim. Summary text is retained only when at least
    one architecture claim is usable.
    """
    source = _as_dict(architecture)
    usable_architecture_claims = [
        claim for claim in claims
        if _claim_is_usable(claim)
        and bool(getattr(claim, "evidence", []))
        and str(getattr(claim, "category", "") or "").casefold()
        in {"architecture", "data_flow", "integration", "deployment", "module", "feature", "component", "flow", "relationship", "infrastructure"}
    ]

    if not usable_architecture_claims:
        return {
            "architecture_summary": UNKNOWN_EVIDENCE_MESSAGE,
            "summary": UNKNOWN_EVIDENCE_MESSAGE,
            "architecture_type": "unknown",
            "flow": [],
            "request_lifecycle": [],
            "components": [],
            "communication": [],
            "deployment": "unknown",
        }

    filtered = dict(source)
    summary = str(source.get("architecture_summary") or source.get("summary") or "").strip()
    if summary:
        supported_summary = _filter_narrative_sentences(summary, usable_architecture_claims)
        filtered["architecture_summary"] = supported_summary or UNKNOWN_EVIDENCE_MESSAGE
        filtered["summary"] = supported_summary or UNKNOWN_EVIDENCE_MESSAGE

    # Component-level validation: do not keep every component merely because
    # another architecture claim passed validation.
    components = []
    seen_components = set()
    for component in _as_list(source.get("components")):
        if isinstance(component, str):
            name = component.strip()
            component_data = {"name": name}
        elif isinstance(component, dict):
            component_data = dict(component)
            name = str(
                component_data.get("name")
                or component_data.get("component")
                or component_data.get("label")
                or ""
            ).strip()
        else:
            continue

        if not name or not _claim_supports_label(name, usable_architecture_claims):
            continue

        key = _normalise_text(name)
        if key in seen_components:
            continue
        seen_components.add(key)
        components.append(component_data)

    filtered["components"] = components

    # Keep flow/lifecycle entries only when a claim explicitly supports the
    # entry text. This prevents a generic request lifecycle from passing on
    # the strength of an unrelated architecture claim.
    for field in ("flow", "request_lifecycle", "communication"):
        entries = []
        seen_entries = set()

        for entry in _as_list(source.get(field)):
            if isinstance(entry, str):
                text = entry.strip()
                entry_data = entry
            elif isinstance(entry, dict):
                entry_data = dict(entry)
                text = " ".join(
                    str(entry_data.get(key) or "")
                    for key in (
                        "name", "step", "description", "from", "to",
                        "source", "target", "interaction", "type",
                    )
                ).strip()
            else:
                continue

            if not text or not _claim_supports_label(text, usable_architecture_claims):
                continue

            key = _normalise_text(text)
            if key in seen_entries:
                continue
            seen_entries.add(key)
            entries.append(entry_data)

        filtered[field] = entries

    # Deployment should not imply a platform merely because a model supplied
    # a plausible deployment description.
    deployment = source.get("deployment")
    if isinstance(deployment, str):
        filtered["deployment"] = (
            deployment
            if _claim_supports_label(deployment, usable_architecture_claims)
            else "unknown"
        )
    elif isinstance(deployment, list):
        filtered["deployment"] = [
            item for item in deployment
            if isinstance(item, str)
            and _claim_supports_label(item, usable_architecture_claims)
        ]
    elif isinstance(deployment, dict):
        filtered["deployment"] = (
            deployment
            if _claim_supports_label(
                " ".join(str(value) for value in deployment.values()),
                usable_architecture_claims,
            )
            else "unknown"
        )
    else:
        filtered["deployment"] = "unknown"

    return filtered


def _filter_executive_overview(executive: Any, valid_features: set) -> dict:
    """Keep only user-facing features that survived evidence validation."""
    result = dict(_as_dict(executive))
    features = []

    for feature in _as_list(result.get("user_features")):
        if not isinstance(feature, dict):
            continue

        name = str(feature.get("name") or "").strip()
        if not name or _normalise_text(name) not in valid_features:
            continue

        features.append(feature)

    result["user_features"] = features
    return result


def _narrative_supported_by_claims(text: Any, claims: list) -> bool:
    """Reject generic narrative unless validated overview claims support it."""
    stop_words = {
        "the", "and", "for", "with", "from", "into", "this", "that", "are",
        "was", "were", "can", "will", "its", "their", "users", "user",
        "project", "repository", "files", "file", "documented", "purpose",
        "visible", "structure", "usable", "product", "tool", "intended",
        "main", "application", "experience", "supporting", "areas", "included",
        "operational", "setup", "available", "evidence", "together", "brings",
        "interact", "rely", "maintain", "run", "built", "designed", "provides",
        "supports", "offers", "helps", "allows", "enables", "use", "using",
    }

    def tokens(value: Any) -> set[str]:
        if not isinstance(value, str):
            return set()
        return {
            token for token in re.findall(r"[a-z0-9_+#.-]{3,}", value.casefold())
            if token not in stop_words
        }

    narrative_tokens = tokens(text)
    if not narrative_tokens:
        return False
    claim_tokens = set().union(*(
        tokens(claim.text)
        for claim in claims
        if _claim_is_usable(claim)
        and str(getattr(claim, "category", "") or "").casefold()
        in {"overview", "executive_summary"}
    )) if claims else set()
    return _semantically_related_tokens(narrative_tokens, claim_tokens)


def _filter_narrative_sentences(text: Any, claims: list) -> str:
    """Keep supported sentences independently so one unsupported clause cannot erase a section."""
    if not isinstance(text, str):
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    return " ".join(sentence for sentence in sentences if _narrative_supported_by_claims(sentence, claims))


@router.post("", response_model=AnalyzeResponse)
def analyze_repository(
    payload: AnalyzeRequest,
    github_service: GitHubService = Depends(get_github_service),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    run_id = payload.analysis_run_id or uuid.uuid4().hex
    payload.analysis_run_id = run_id
    identity = payload.repo_url or (
        Path(payload.local_path).name if payload.local_path else "unknown"
    )

    with run_context(run_id):
        emit(
            logger,
            "analysis_request_received",
            stage="request",
            repository=identity,
            repository_url=payload.repo_url,
        )

        with stage(
            logger,
            "analysis_request",
            repository=identity,
            repository_url=payload.repo_url,
        ):
            try:
                response = _run_analysis(payload, github_service, db)
            except HTTPException as exc:
                emit(
                    logger,
                    "analysis_request_rejected",
                    level=logging.WARNING,
                    stage="request",
                    repository=identity,
                    http_status=exc.status_code,
                    reason=str(exc.detail),
                )
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={
                        "message": (
                            "Analysis request rejected. Use correlation ID "
                            f"{run_id} for diagnostics."
                        ),
                        "analysis_run_id": run_id,
                    },
                    headers={"X-Analysis-Run-Id": run_id},
                ) from exc
            except Exception as exc:
                emit(
                    logger,
                    "analysis_request_failed",
                    level=logging.ERROR,
                    stage="request",
                    repository=identity,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                    exc_info=True,
                )
                response = AnalyzeResponse(
                    status="error",
                    analysis_status="error",
                    analysis_run_id=run_id,
                    error_code=f"analysis_failed:{type(exc).__name__}",
                    message=(
                        "Analysis failed. Use correlation ID "
                        f"{run_id} to find server diagnostics."
                    ),
                )

            response.analysis_run_id = run_id

            if response.status == "error":
                emit(
                    logger,
                    "analysis_failed",
                    level=logging.ERROR,
                    stage="response",
                    repository=identity,
                    error_code=response.error_code or "analysis_error",
                    analysis_status=response.analysis_status,
                )

            emit(
                logger,
                "analysis_request_completed",
                stage="response",
                repository=response.repo_name or identity,
                commit_sha=response.commit_sha,
                status=response.status,
                analysis_status=response.analysis_status,
                error_code=response.error_code,
                claim_count=len(
                    (response.repository_model or {}).get("claims", [])
                ),
                module_count=len(response.modules or []),
            )
            return response


def _run_analysis(
    payload: AnalyzeRequest,
    github_service: GitHubService,
    db: Session,
) -> AnalyzeResponse:
    try:
        acquisition_started = time.perf_counter()
        emit(
            logger,
            "repository_acquisition_started",
            stage="repository_acquisition",
            repository_url=payload.repo_url,
            local_path=payload.local_path,
            acquisition_kind="github" if payload.repo_url else "local",
        )

        if payload.local_path:
            repo_path = Path(payload.local_path)
            if not repo_path.exists() or not repo_path.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail="Local path does not exist or is not a directory",
                )

            repo_name = repo_path.name
            clone_result = {"commit_sha": "", "status": "local_checkout"}
            description = ""
            repository_metadata = {
                "name": repo_name,
                "full_name": repo_name,
                "description": description,
                "topics": [],
            }
            readme_path, readme_source = github_service.find_readme_path(repo_path)
            readme_content = github_service.find_readme(repo_path) or ""
            repository_metadata["readme_source"] = readme_source

        elif payload.repo_url:
            clone_result = github_service.clone_repository(payload.repo_url)
            repo_path = Path(clone_result["local_path"])
            repo_name = clone_result["repo_name"]
            description = clone_result.get("description", "")

            try:
                repository_metadata = github_service.fetch_metadata(payload.repo_url)
                description = repository_metadata.get("description") or description
            except Exception as exc:
                emit(
                    logger,
                    "metadata_fetch_skipped",
                    level=logging.WARNING,
                    stage="repository_acquisition",
                    repository=repo_name,
                    reason=type(exc).__name__,
                    exc_info=True,
                )
                repository_metadata = {
                    "name": repo_name,
                    "full_name": repo_name,
                    "description": description,
                    "topics": [],
                    "readme_source": "local_path",
                }

            readme_path, readme_source = github_service.find_readme_path(repo_path)
            readme_content = github_service.find_readme(repo_path)

            if readme_content:
                readme_source = f"clone:{readme_source}"
            else:
                readme_content = github_service.fetch_readme(
                    payload.repo_url,
                    clone_result.get("commit_sha"),
                ) or ""
                readme_source = "github_api" if readme_content else "not_found"

            repository_metadata["readme_source"] = readme_source
            emit(
                logger,
                "readme_selected",
                stage="repository_acquisition",
                repository=repo_name,
                readme_path=str(readme_path) if readme_path else None,
                source=readme_source,
                bytes=len(readme_content.encode("utf-8")) if readme_content else 0,
                chars=len(readme_content) if readme_content else 0,
                empty_result=not bool(readme_content),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either repo_url or local_path is required",
            )

        emit(
            logger,
            "repository_acquisition_completed",
            stage="repository_acquisition",
            repository=repo_name,
            repository_url=payload.repo_url,
            checkout_path=str(repo_path),
            clone_cache_status=clone_result.get("status", "unknown"),
            commit_sha=clone_result.get("commit_sha"),
            duration_ms=round(
                (time.perf_counter() - acquisition_started) * 1000
            ),
        )

        emit(
            logger,
            "repository_scan_started",
            stage="inventory",
            repository=repo_name,
        )
        inventory_started = time.perf_counter()
        scan = RepoScanner().scan(repo_path)
        commit_sha = str(clone_result.get("commit_sha") or "")

        if not commit_sha:
            try:
                commit_sha = subprocess.run(
                    ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            except (subprocess.CalledProcessError, OSError):
                digest = hashlib.sha256()
                for relative in RepositoryRetrieval(repo_path).inventory():
                    digest.update(relative.encode("utf-8", errors="replace"))
                    try:
                        digest.update((repo_path / relative).read_bytes())
                    except OSError:
                        continue
                commit_sha = "local-sha256:" + digest.hexdigest()

        repository_metadata["commit_sha"] = commit_sha
        se_stats = (scan.get("source_evidence") or {}).get("stats", {})

        emit(
            logger,
            "repository_inventory_completed",
            stage="inventory",
            repository=repo_name,
            commit_sha=commit_sha,
            duration_ms=round(
                (time.perf_counter() - inventory_started) * 1000
            ),
            inventory_file_count=se_stats.get(
                "total_files_in_scan", len(scan.get("files", []))
            ),
            source_file_count=se_stats.get("discovered_source_files", 0),
            selected_files=se_stats.get("selected_evidence_files", 0),
            excluded_counts=se_stats.get("excluded_file_counts", {}),
            unreadable_file_count=se_stats.get(
                "excluded_file_counts", {}
            ).get("file_unreadable", 0),
        )

        stack = StackDetector().detect(scan)
        emit(
            logger,
            "stack_detection_completed",
            level=logging.DEBUG,
            stage="stack_detection",
            repository=repo_name,
            commit_sha=commit_sha,
            language_count=len(stack.get("languages", [])),
            technology_count=len(stack.get("flat", [])),
        )

        folder_structure = RepositoryStructureService().build_tree(repo_path)
        llm_service = LLMService()
        repository_metadata["analysis_run_id"] = payload.analysis_run_id

        try:
            signature = inspect.signature(
                llm_service.generate_repository_analysis
            )
            if "repo_path" in signature.parameters:
                ai_analysis = llm_service.generate_repository_analysis(
                    metadata=repository_metadata,
                    readme=readme_content or "",
                    stack=stack,
                    repository_structure=(
                        [folder_structure] if folder_structure else []
                    ),
                    scan=scan,
                    repo_path=repo_path,
                )
            else:
                ai_analysis = llm_service.generate_repository_analysis(
                    metadata=repository_metadata,
                    readme=readme_content or "",
                    stack=stack,
                    repository_structure=(
                        [folder_structure] if folder_structure else []
                    ),
                    scan=scan,
                )
        except TypeError:
            ai_analysis = llm_service.generate_repository_analysis(
                metadata=repository_metadata,
                readme=readme_content or "",
                stack=stack,
                repository_structure=(
                    [folder_structure] if folder_structure else []
                ),
                scan=scan,
            )

        if not isinstance(ai_analysis, dict):
            raise ValueError("LLM analysis returned an invalid response")

        # Normalize optional objects once so missing/null AI fields cannot
        # cause nested-key access failures during evidence validation.
        ai_analysis["analysis_evidence"] = _as_dict(
            ai_analysis.get("analysis_evidence")
        )
        ai_analysis["executive_overview"] = _as_dict(
            ai_analysis.get("executive_overview")
        )
        ai_analysis["modules"] = _as_list(ai_analysis.get("modules"))
        ai_analysis["claims"] = _as_list(ai_analysis.get("claims"))
        ai_analysis["report_sections"] = _as_dict(ai_analysis.get("report_sections"))
        ai_analysis["analysis_evidence"]["commit_sha"] = commit_sha

        coverage_manifest = _as_dict(ai_analysis.get("coverage_manifest"))
        if not coverage_manifest:
            coverage_manifest = _as_dict(
                ai_analysis["analysis_evidence"].get("coverage_manifest")
            )
        claims_before_coverage_filter = len(ai_analysis["claims"])
        claims_before_coverage = claims_before_coverage_filter
        evidence_refs_before_filter = sum(
            len(_as_list(claim.get("evidence"))) for claim in ai_analysis["claims"] if isinstance(claim, dict)
        )
        if coverage_manifest:
            ai_analysis["claims"] = _run_output_filter(_filter_claims_by_coverage,
                ai_analysis["claims"], coverage_manifest
            )
        evidence_refs_after_filter = sum(
            len(_as_list(claim.get("evidence"))) for claim in ai_analysis["claims"] if isinstance(claim, dict)
        )
        recommendations_before_filter = len(_as_list(ai_analysis["report_sections"].get("recommendations")))
        modules_before_filter = len(ai_analysis["modules"])
        features_before_filter = len(_as_list(ai_analysis["executive_overview"].get("user_features")))
        architecture_before = _as_dict(ai_analysis.get("architecture"))
        architecture_components_before_filter = len(_as_list(architecture_before.get("components")))
        architecture_flow_before_filter = sum(len(_as_list(architecture_before.get(field))) for field in ("flow", "request_lifecycle", "communication"))
        overview_before_filter = bool(str(ai_analysis.get("overview") or "").strip())
        narratives_before_filter = _narrative_count(ai_analysis["executive_overview"]) + int(overview_before_filter)

        analysis_status = ai_analysis.get("analysis_status", "degraded")
        if analysis_status not in {"complete", "partial", "unavailable", "failed", "ai_generated", "degraded"}:
            analysis_status = "degraded"

        model_started = time.perf_counter()
        source_retrieval = RepositoryRetrieval(repo_path)
        if ai_analysis["report_sections"]:
            ai_analysis["report_sections"] = _run_output_filter(_validate_report_recommendations,
                ai_analysis["report_sections"], source_retrieval, coverage_manifest
            )
        repository_model = build_repository_model(
            ai_analysis,
            source_retrieval,
            commit_sha,
            coverage_manifest,
        )
        pipeline_diagnostics = ai_analysis["analysis_evidence"].setdefault("pipeline_diagnostics", {})
        if not isinstance(pipeline_diagnostics, dict):
            pipeline_diagnostics = {}
            ai_analysis["analysis_evidence"]["pipeline_diagnostics"] = pipeline_diagnostics
        pipeline_diagnostics["evidence_validation"] = {
            "status": "partial" if repository_model.evidence_issues or any(claim.state == "rejected" for claim in repository_model.claims) else "passed",
            "code": "evidence_validation_partial" if repository_model.evidence_issues or any(claim.state == "rejected" for claim in repository_model.claims) else "ok",
            "invalid_reference_count": len(repository_model.evidence_issues),
            "rejected_claim_count": sum(claim.state == "rejected" for claim in repository_model.claims),
            **repository_model.validation_diagnostics,
        }

        if analysis_status == "degraded":
            repository_model.unresolved_questions = [
                "LLM analysis failed; repository claims remain unverified."
            ]
            repository_model.coverage["status"] = "degraded"
        else:
            unresolved = [
                claim.text
                for claim in repository_model.claims
                if claim.state != "confirmed"
            ]
            unresolved.extend(repository_model.evidence_issues)
            unresolved.extend(
                str(item.get("description") or item.get("question") or item)
                if isinstance(item, dict) else str(item)
                for item in _as_list(ai_analysis["report_sections"].get("limitations"))
            )
            if coverage_manifest:
                omitted = int(coverage_manifest.get("omitted_count") or 0)
                unreadable = int(coverage_manifest.get("unreadable_count") or 0)
                if omitted:
                    unresolved.append(f"{omitted} repository files were omitted by size or context limits.")
                if unreadable:
                    unresolved.append(f"{unreadable} repository files could not be read.")
                repository_model.coverage.update({
                    "discovered_files": int(coverage_manifest.get("discovered_count") or 0),
                    "inspected_files": int(coverage_manifest.get("inspected_count") or 0),
                    "excluded_files": int(coverage_manifest.get("excluded_count") or 0),
                    "omitted_files": omitted,
                    "unreadable_files": unreadable,
                })
            investigation_coverage = _as_dict(
                ai_analysis["analysis_evidence"].get(
                    "investigation_coverage"
                )
            )
            unresolved.extend(
                str(
                    item.get("question")
                    or item.get("query")
                    or item
                )
                if isinstance(item, dict)
                else str(item)
                for item in _as_list(
                    investigation_coverage.get("unresolved")
                )
            )
            unresolved.extend(
                f"Contradictory claims about {item['subject']}"
                for item in repository_model.contradictions
                if isinstance(item, dict) and item.get("subject")
            )
            repository_model.unresolved_questions = list(
                dict.fromkeys(unresolved)
            )

            if unresolved:
                analysis_status = "partial"

            repository_model.coverage["status"] = analysis_status

            valid_modules = {
                _normalise_text(claim.target_name)
                for claim in repository_model.claims
                if claim.category == "module"
                and claim.state in {"confirmed", "inferred"}
                and claim.target_name
            }
            ai_analysis["modules"] = [
                module
                for module in ai_analysis["modules"]
                if isinstance(module, dict)
                and _normalise_text(module.get("name")) in valid_modules
            ]

            valid_features = {
                _normalise_text(claim.target_name)
                for claim in repository_model.claims
                if claim.category == "feature"
                and claim.state in {"confirmed", "inferred"}
                and claim.target_name
            }
            executive = _run_output_filter(_filter_executive_overview,
                ai_analysis["executive_overview"],
                valid_features,
            )
            ai_analysis["executive_overview"] = executive

            valid_overview_claims = [
                claim for claim in repository_model.claims
                if claim.category in {"overview", "executive_summary"}
                and claim.state in {"confirmed", "inferred"}
            ]
            if not valid_overview_claims:
                ai_analysis["overview"] = ""
                executive["what_is_this_project"] = []
                executive["why_was_it_built"] = UNKNOWN_EVIDENCE_MESSAGE
                executive["why_is_it_valuable"] = UNKNOWN_EVIDENCE_MESSAGE
                executive["one_line_summary"] = UNKNOWN_EVIDENCE_MESSAGE
                executive["typical_use_cases"] = []
                executive["who_is_this_for"] = []
            else:
                ai_analysis["overview"] = _filter_narrative_sentences(
                    ai_analysis.get("overview", ""), valid_overview_claims
                )
                executive["what_is_this_project"] = [
                    retained for item in _as_list(executive.get("what_is_this_project"))
                    if (retained := _filter_narrative_sentences(item, valid_overview_claims))
                ]
                for field in (
                    "why_was_it_built", "why_is_it_valuable", "one_line_summary"
                ):
                    value = executive.get(field)
                    executive[field] = _filter_narrative_sentences(value, valid_overview_claims) or UNKNOWN_EVIDENCE_MESSAGE
                for field in ("typical_use_cases", "who_is_this_for"):
                    executive[field] = [
                        retained for item in _as_list(executive.get(field))
                        if (retained := _filter_narrative_sentences(item, valid_overview_claims))
                    ]

            ai_analysis["architecture"] = _run_output_filter(_filter_architecture,
                ai_analysis.get("architecture"),
                repository_model.claims,
            )

            kept = valid_modules
            repository_model.components = [
                component
                for component in repository_model.components
                if _normalise_text(component.name) in kept
            ]
            repository_model.relationships = [
                relation
                for relation in repository_model.relationships
                if _normalise_text(relation.source) in kept
                and _normalise_text(relation.target) in kept
            ]

        recommendations_after_filter = len(_as_list(ai_analysis["report_sections"].get("recommendations")))
        architecture_after = _as_dict(ai_analysis.get("architecture"))
        architecture_components_after = len(_as_list(architecture_after.get("components")))
        architecture_flow_after = sum(len(_as_list(architecture_after.get(field))) for field in ("flow", "request_lifecycle", "communication"))
        narratives_after_filter = _narrative_count(ai_analysis["executive_overview"]) + int(bool(str(ai_analysis.get("overview") or "").strip()))
        validation_reason_counts = {}
        for claim in repository_model.claims:
            for reason in claim.validation_reasons:
                code = reason.get("reason_code")
                if code:
                    validation_reason_counts[code] = validation_reason_counts.get(code, 0) + 1
        filtering_counts = {
            "claim_evidence_references_removed": max(0, evidence_refs_before_filter - evidence_refs_after_filter),
            "recommendations_removed": max(0, recommendations_before_filter - recommendations_after_filter),
            "modules_removed": max(0, modules_before_filter - len(ai_analysis["modules"])),
            "features_removed": max(0, features_before_filter - len(_as_list(ai_analysis["executive_overview"].get("user_features")))),
            "architecture_components_removed": max(0, architecture_components_before_filter - architecture_components_after),
            "architecture_flow_entries_removed": max(0, architecture_flow_before_filter - architecture_flow_after),
            "overview_removed": int(overview_before_filter and not bool(str(ai_analysis.get("overview") or "").strip())),
            "narratives_removed": max(0, narratives_before_filter - narratives_after_filter),
        }
        recommendation_reason_counts = {}
        for recommendation in _as_list(ai_analysis["report_sections"].get("recommendations")):
            if not isinstance(recommendation, dict):
                continue
            for reason in _as_list(recommendation.get("validation_reasons")):
                if isinstance(reason, dict) and reason.get("reason_code"):
                    code = str(reason["reason_code"])
                    recommendation_reason_counts[code] = recommendation_reason_counts.get(code, 0) + 1
        pipeline_diagnostics["output_filtering"] = {
            "status": "filtered" if any(filtering_counts.values()) else "passed",
            "code": "unsupported_or_unverified_output_removed" if any(filtering_counts.values()) else "ok",
            "stages": {
                "coverage_filter": {"claims_before": claims_before_coverage, "claims_after": len(ai_analysis["claims"]), "evidence_references_before": evidence_refs_before_filter, "evidence_references_after": evidence_refs_after_filter},
                "recommendation_validation": {"before": recommendations_before_filter, "after": recommendations_after_filter},
                "module_validation": {"before": modules_before_filter, "after": len(ai_analysis["modules"])},
                "feature_validation": {"before": features_before_filter, "after": len(_as_list(ai_analysis["executive_overview"].get("user_features")))},
                "architecture_validation": {"components_before": architecture_components_before_filter, "components_after": architecture_components_after, "flow_entries_before": architecture_flow_before_filter, "flow_entries_after": architecture_flow_after},
                "overview_validation": {"before": int(overview_before_filter), "after": int(bool(str(ai_analysis.get("overview") or "").strip()))},
                "narrative_validation": {"before": narratives_before_filter, "after": narratives_after_filter},
            },
            "reason_counts": {
                **validation_reason_counts,
                **recommendation_reason_counts,
                **({"unsupported_architecture_relationship": filtering_counts["architecture_components_removed"] + filtering_counts["architecture_flow_entries_removed"]} if filtering_counts["architecture_components_removed"] + filtering_counts["architecture_flow_entries_removed"] else {}),
                **({"insufficient_semantic_support": filtering_counts["narratives_removed"]} if filtering_counts["narratives_removed"] else {}),
            },
            **filtering_counts,
        }
        gate = _as_dict(pipeline_diagnostics.get("coverage"))
        manifest_gate = _as_dict(coverage_manifest.get("coverage"))
        classification = classify_analysis_status(
            ai_analysis,
            pipeline=pipeline_diagnostics,
            coverage_gate=manifest_gate or gate,
            insufficient_inputs=gate.get("status") == "insufficient",
        )
        analysis_status = classification["status"]
        pipeline_diagnostics["status_classification"] = classification
        repository_model.coverage["status"] = analysis_status
        ai_analysis["analysis_status"] = analysis_status
        pipeline_diagnostics["status"] = analysis_status
        pipeline_diagnostics["analysis_run_id"] = payload.analysis_run_id
        pipeline_diagnostics["commit_sha"] = commit_sha

        emit(
            logger,
            "claim_validation_completed",
            stage="evidence_validation",
            repository=repo_name,
            commit_sha=commit_sha,
            duration_ms=round(
                (time.perf_counter() - model_started) * 1000
            ),
            claim_count=len(repository_model.claims),
            contradiction_count=len(repository_model.contradictions),
            evidence_issue_count=len(repository_model.evidence_issues),
            unresolved_question_count=len(
                repository_model.unresolved_questions
            ),
            analysis_status=analysis_status,
            generated_output={
                "overview": ai_analysis.get("overview"),
                "executive_overview": ai_analysis.get("executive_overview"),
                "modules": ai_analysis.get("modules", [])[:8],
                "architecture": ai_analysis.get("architecture"),
                "validated_claims": [
                    {
                        "text": claim.text,
                        "state": claim.state,
                        "category": claim.category,
                        "target_name": claim.target_name,
                        "confidence": claim.confidence,
                        "model_confidence": claim.model_confidence,
                        "validation_reasons": claim.validation_reasons,
                        "evidence": [
                            {
                                "path": ref.path,
                                "start_line": ref.start_line,
                                "end_line": ref.end_line,
                                "excerpt": ref.excerpt,
                            }
                            for ref in claim.evidence[:3]
                        ],
                    }
                    for claim in repository_model.claims[:24]
                ],
                "evidence_issues": repository_model.evidence_issues[:20],
                "contradictions": repository_model.contradictions[:20],
                "unresolved_questions": repository_model.unresolved_questions[:20],
            },
        )

        semantic_repository_profile = ai_analysis["analysis_evidence"].get(
            "semantic_repository_profile", {}
        )

        try:
            similar_repositories = (
                SimilarRepoService(github_service).find_similar_repositories(
                    metadata={
                        **repository_metadata,
                        "language": repository_metadata.get("language")
                        or (stack.get("languages") or [None])[0],
                    },
                    stack=stack,
                    readme=readme_content or "",
                    stats={"files": len(scan.get("files", []))},
                    analysis_context={
                        **ai_analysis,
                        "analysis_evidence": ai_analysis.get(
                            "analysis_evidence", {}
                        ),
                        "semantic_repository_profile": (
                            semantic_repository_profile
                        ),
                    },
                    repository_structure=(
                        [folder_structure] if folder_structure else []
                    ),
                )
            )
        except Exception as exc:
            emit(
                logger,
                "similar_repository_analysis_failed",
                level=logging.WARNING,
                stage="similar_repositories",
                repository=repo_name,
                commit_sha=commit_sha,
                exception_type=type(exc).__name__,
                reason=str(exc),
                exc_info=True,
            )
            similar_repositories = []

        ai_insights = [
            item.get("name", "")
            for item in _as_list(
                ai_analysis["executive_overview"].get("user_features")
            )
            if isinstance(item, dict) and item.get("name")
        ]

        repository = None
        if payload.repo_url:
            persistence_started = time.perf_counter()
            emit(
                logger,
                "persistence_started",
                stage="persistence",
                repository=repo_name,
                commit_sha=commit_sha,
            )
            repository_url = normalize_github_url(payload.repo_url)
            repository = db.scalar(
                select(Repository).where(
                    Repository.github_url == repository_url
                )
            )

            if repository is None:
                repository = Repository(
                    github_url=repository_url,
                    full_name=repository_metadata.get("full_name") or repo_name,
                    description=(
                        repository_metadata.get("description") or description
                    ),
                    stars=repository_metadata.get("stargazers_count") or 0,
                    primary_language=repository_metadata.get("language")
                    or (stack.get("languages") or [None])[0],
                )
                db.add(repository)
                db.flush()
            else:
                repository.full_name = (
                    repository_metadata.get("full_name") or repo_name
                )
                repository.description = (
                    repository_metadata.get("description") or description
                )
                repository.stars = (
                    repository_metadata.get("stargazers_count") or 0
                )
                repository.primary_language = (
                    repository_metadata.get("language")
                    or (stack.get("languages") or [None])[0]
                )

            result = repository.analysis_result
            if result is None:
                result = AnalysisResult(repository_id=repository.id)
                db.add(result)

            result.stack = stack
            result.overview = ai_analysis.get("overview") or ""
            result.modules = ai_analysis.get("modules") or []
            result.architecture_summary = (
                llm_service.architecture_summary_text(ai_analysis)
            )
            result.similar_repositories = similar_repositories
            result.readme = readme_content
            result.readme_path = (
                readme_path.relative_to(repo_path).as_posix()
                if readme_path
                else None
            )
            result.folder_structure = (
                [folder_structure] if folder_structure else []
            )
            result.languages = stack.get("languages", [])
            result.architecture = ai_analysis.get("architecture")
            result.executive_overview = ai_analysis.get("executive_overview")
            result.analysis_evidence = ai_analysis.get("analysis_evidence")
            if ai_analysis["report_sections"]:
                result.analysis_evidence["report_sections"] = ai_analysis["report_sections"]
            result.analysis_status = analysis_status
            result.commit_sha = commit_sha
            result.repository_model = repository_model.model_dump(mode="json")

            db.commit()
            db.refresh(repository)

            emit(
                logger,
                "persistence_completed",
                stage="persistence",
                repository=repo_name,
                commit_sha=commit_sha,
                duration_ms=round(
                    (time.perf_counter() - persistence_started) * 1000
                ),
                repository_id=repository.id,
                analysis_status=analysis_status,
                claim_count=len(repository_model.claims),
            response_preview={
                "analysis_run_id": response.analysis_run_id,
                "repo_name": response.repo_name,
                "analysis_status": response.analysis_status,
                "commit_sha": response.commit_sha,
                "overview": response.overview,
                "modules": response.modules[:8],
                "architecture": response.architecture,
                "repository_model": response.repository_model,
            },
            )
        else:
            emit(
                logger,
                "persistence_skipped",
                level=logging.INFO,
                stage="persistence",
                reason="local_path_analysis_has_no_repository_record",
            )

        response = AnalyzeResponse(
            # "success" means the request completed and returned a response.
            # Analysis quality is expressed separately in analysis_status.
            status="success",
            repository_id=repository.id if repository else None,
            repo_name=repo_name,
            repo_url=payload.repo_url,
            local_path=str(repo_path) if payload.local_path else None,
            readme=readme_content,
            readme_path=(
                readme_path.relative_to(repo_path).as_posix()
                if readme_path
                else None
            ),
            stack=stack,
            folder_structure=[folder_structure] if folder_structure else [],
            languages=stack.get("languages", []),
            overview=ai_analysis.get("overview", ""),
            executive_overview=ai_analysis.get("executive_overview"),
            architecture=ai_analysis.get("architecture"),
            architecture_summary=llm_service.architecture_summary_text(
                ai_analysis
            ),
            modules=ai_analysis["modules"],
            analysis_evidence=ai_analysis.get("analysis_evidence"),
            ai_insights=ai_insights,
            analysis_status=analysis_status,
            error_code=ai_analysis.get("analysis_error") if ai_analysis.get("analysis_error") else None,
            commit_sha=commit_sha,
            repository_model=repository_model.model_dump(mode="json"),
            coverage_manifest=coverage_manifest or None,
            report_sections=ai_analysis["report_sections"] or None,
            similar_repositories=similar_repositories,
        )

        # Force Pydantic serialization now so invalid response payloads are
        # caught and logged before returning from the route.
        response.model_dump(mode="json")
        emit(
            logger,
            "response_schema_validated",
            stage="response_serialization",
            repository=repo_name,
            commit_sha=commit_sha,
            field_count=len(response.model_fields_set),
            status=response.status,
            analysis_status=response.analysis_status,
        )
        return response

    except ValueError as exc:
        emit(
            logger,
            "analysis_validation_failed",
            level=logging.ERROR,
            repository=payload.repo_url or "local",
            reason=str(exc),
            exc_info=True,
        )
        return AnalyzeResponse(
            status="error",
            analysis_status="error",
            error_code="analysis_validation_failed",
            message=(
                "Analysis failed validation. Use correlation ID "
                f"{payload.analysis_run_id} for diagnostics."
            ),
        )
    except RuntimeError as exc:
        emit(
            logger,
            "analysis_runtime_failed",
            level=logging.ERROR,
            repository=payload.repo_url or "local",
            reason=str(exc),
            exc_info=True,
        )
        return AnalyzeResponse(
            status="error",
            analysis_status="error",
            error_code="output_filtering_failure" if "output_filtering_failure" in str(exc) else "analysis_runtime_failed",
            message=(
                "Analysis could not complete. Use correlation ID "
                f"{payload.analysis_run_id} for diagnostics."
            ),
        )
