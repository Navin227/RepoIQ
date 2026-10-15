import inspect
import json
import logging
import subprocess
import hashlib
import uuid
import time
from pathlib import Path
from typing import List, Optional

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
from app.services.semantic_profile_builder import build_semantic_repository_profile
from app.services.similar_repo_service import SimilarRepoService
from app.utils.repo_scanner import RepoScanner
from app.utils.git_utils import normalize_github_url
from app.services.repository_model import RepositoryRetrieval, build_repository_model
from app.services.analysis_diagnostics import emit, run_context, stage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=AnalyzeResponse)
def analyze_repository(
    payload: AnalyzeRequest,
    github_service: GitHubService = Depends(get_github_service),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    run_id = payload.analysis_run_id or uuid.uuid4().hex
    payload.analysis_run_id = run_id
    identity = payload.repo_url or (Path(payload.local_path).name if payload.local_path else "unknown")
    with run_context(run_id):
        emit(logger, "analysis_request_received", stage="request", repository=identity, repository_url=payload.repo_url)
        with stage(logger, "analysis_request", repository=identity, repository_url=payload.repo_url):
            try:
                response = _run_analysis(payload, github_service, db)
            except HTTPException as exc:
                emit(logger, "analysis_request_rejected", level=logging.WARNING, stage="request",
                     repository=identity, http_status=exc.status_code, reason=str(exc.detail))
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"message": f"Analysis request rejected. Use correlation ID {run_id} for diagnostics.",
                            "analysis_run_id": run_id},
                    headers={"X-Analysis-Run-Id": run_id},
                ) from exc
            except Exception as exc:
                emit(logger, "analysis_request_failed", level=logging.ERROR, stage="request", repository=identity,
                     exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
                response = AnalyzeResponse(
                    status="error", analysis_status="error", analysis_run_id=run_id,
                    error_code=f"analysis_failed:{type(exc).__name__}",
                    message=f"Analysis failed. Use correlation ID {run_id} to find server diagnostics.",
                )
            response.analysis_run_id = run_id
            if response.status == "error":
                emit(logger, "analysis_failed", level=logging.ERROR, stage="response", repository=identity,
                     error_code=response.error_code or "analysis_error", analysis_status=response.analysis_status)
            emit(logger, "analysis_request_completed", stage="response", repository=response.repo_name or identity,
                 commit_sha=response.commit_sha, status=response.status, analysis_status=response.analysis_status,
                 error_code=response.error_code, claim_count=len((response.repository_model or {}).get("claims", [])),
                 module_count=len(response.modules or []))
            return response


def _run_analysis(
    payload: AnalyzeRequest,
    github_service: GitHubService,
    db: Session,
) -> AnalyzeResponse:
    try:
        acquisition_started = time.perf_counter()
        emit(logger, "repository_acquisition_started", stage="repository_acquisition", repository_url=payload.repo_url,
             local_path=payload.local_path, acquisition_kind="github" if payload.repo_url else "local")
        if payload.local_path:
            repo_path = Path(payload.local_path)
            if not repo_path.exists() or not repo_path.is_dir():
                raise HTTPException(status_code=400, detail="Local path does not exist or is not a directory")
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
                emit(logger, "metadata_fetch_skipped", level=logging.WARNING, stage="repository_acquisition",
                     repository=repo_name, reason=type(exc).__name__, exc_info=True)
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
            emit(logger, "readme_selected", stage="repository_acquisition", repository=repo_name,
                 readme_path=str(readme_path) if readme_path else None, source=readme_source,
                 bytes=len(readme_content.encode("utf-8")) if readme_content else 0,
                 chars=len(readme_content) if readme_content else 0, empty_result=not bool(readme_content))
        else:
            raise HTTPException(status_code=400, detail="Either repo_url or local_path is required")

        emit(logger, "repository_acquisition_completed", stage="repository_acquisition", repository=repo_name,
             repository_url=payload.repo_url, checkout_path=str(repo_path), clone_cache_status=clone_result.get("status", "unknown"),
             commit_sha=clone_result.get("commit_sha"), duration_ms=round((time.perf_counter() - acquisition_started) * 1000))

        emit(logger, "repository_scan_started", stage="inventory", repository=repo_name)
        inventory_started = time.perf_counter()
        scan = RepoScanner().scan(repo_path)
        commit_sha = str(clone_result.get("commit_sha") or "")
        if not commit_sha:
            try:
                commit_sha = subprocess.run(["git", "-C", str(repo_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
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
        emit(logger, "repository_inventory_completed", stage="inventory", repository=repo_name, commit_sha=commit_sha,
             duration_ms=round((time.perf_counter() - inventory_started) * 1000),
             inventory_file_count=se_stats.get("total_files_in_scan", len(scan.get("files", []))),
             source_file_count=se_stats.get("discovered_source_files", 0), selected_files=se_stats.get("selected_evidence_files", 0),
             excluded_counts=se_stats.get("excluded_file_counts", {}), unreadable_file_count=se_stats.get("excluded_file_counts", {}).get("file_unreadable", 0))
        stack = StackDetector().detect(scan)
        emit(logger, "stack_detection_completed", level=logging.DEBUG, stage="stack_detection", repository=repo_name,
             commit_sha=commit_sha, language_count=len(stack.get("languages", [])), technology_count=len(stack.get("flat", [])))
        folder_structure = RepositoryStructureService().build_tree(repo_path)

        llm_service = LLMService()
        repository_metadata["analysis_run_id"] = payload.analysis_run_id
        try:
            signature = inspect.signature(llm_service.generate_repository_analysis)
            if "repo_path" in signature.parameters:
                ai_analysis = llm_service.generate_repository_analysis(
                    metadata=repository_metadata,
                    readme=readme_content or "",
                    stack=stack,
                    repository_structure=[folder_structure] if folder_structure else [],
                    scan=scan,
                    repo_path=repo_path,
                )
            else:
                ai_analysis = llm_service.generate_repository_analysis(
                    metadata=repository_metadata,
                    readme=readme_content or "",
                    stack=stack,
                    repository_structure=[folder_structure] if folder_structure else [],
                    scan=scan,
                )
        except TypeError:
            ai_analysis = llm_service.generate_repository_analysis(
                metadata=repository_metadata,
                readme=readme_content or "",
                stack=stack,
                repository_structure=[folder_structure] if folder_structure else [],
                scan=scan,
            )
        ai_analysis.setdefault("analysis_evidence", {})["commit_sha"] = commit_sha
        analysis_status = ai_analysis.get("analysis_status", "degraded")
        model_started = time.perf_counter()
        repository_model = build_repository_model(ai_analysis, RepositoryRetrieval(repo_path), commit_sha)
        if analysis_status == "degraded":
            repository_model.unresolved_questions = ["LLM analysis failed; repository claims remain unverified."]
            repository_model.coverage["status"] = "degraded"
        else:
            unresolved = [claim.text for claim in repository_model.claims if claim.state != "confirmed"]
            unresolved.extend(repository_model.evidence_issues)
            unresolved.extend(str(item.get("question") or item.get("query") or item) if isinstance(item, dict) else str(item) for item in ai_analysis["analysis_evidence"].get("investigation_coverage", {}).get("unresolved", []))
            unresolved.extend(f"Contradictory claims about {item['subject']}" for item in repository_model.contradictions)
            repository_model.unresolved_questions = list(dict.fromkeys(unresolved))
            if unresolved:
                analysis_status = "partial"
            repository_model.coverage["status"] = analysis_status
            valid_modules = {claim.target_name.casefold() for claim in repository_model.claims if claim.category == "module" and claim.state in {"confirmed", "inferred"}}
            ai_analysis["modules"] = [module for module in ai_analysis.get("modules", []) if module.get("name", "").casefold() in valid_modules]
            valid_features = {claim.target_name.casefold() for claim in repository_model.claims if claim.category == "feature" and claim.state in {"confirmed", "inferred"}}
            executive = ai_analysis.get("executive_overview") or {}
            executive["user_features"] = [feature for feature in executive.get("user_features", []) if feature.get("name", "").casefold() in valid_features]
            if not any(claim.category in {"overview", "executive_summary"} and claim.state in {"confirmed", "inferred"} for claim in repository_model.claims):
                ai_analysis["overview"] = ""
                executive["what_is_this_project"] = []
                executive["why_was_it_built"] = "Unable to confidently determine from repository evidence."
                executive["why_is_it_valuable"] = "Unable to confidently determine from repository evidence."
                executive["one_line_summary"] = "Unable to confidently determine from repository evidence."
            if not any(claim.category in {"architecture", "data_flow", "integration", "deployment"} and claim.state in {"confirmed", "inferred"} for claim in repository_model.claims):
                ai_analysis["architecture"] = {"architecture_summary": "Unable to confidently determine from repository evidence.", "summary": "Unable to confidently determine from repository evidence.", "architecture_type": "unknown", "flow": [], "request_lifecycle": [], "components": [], "communication": [], "deployment": "unknown"}
            kept = {name.casefold() for name in valid_modules}
            repository_model.components = [component for component in repository_model.components if component.name.casefold() in kept]
            repository_model.relationships = [relation for relation in repository_model.relationships if relation.source.casefold() in kept and relation.target.casefold() in kept]
        ai_analysis["analysis_status"] = analysis_status
        emit(logger, "claim_validation_completed", stage="evidence_validation", repository=repo_name, commit_sha=commit_sha,
             duration_ms=round((time.perf_counter() - model_started) * 1000), claim_count=len(repository_model.claims),
             contradiction_count=len(repository_model.contradictions), evidence_issue_count=len(repository_model.evidence_issues),
             unresolved_question_count=len(repository_model.unresolved_questions), analysis_status=analysis_status)
        semantic_repository_profile = build_semantic_repository_profile(
            repository_metadata,
            readme_content or "",
            stack,
            scan,
            llm_service._extract_code_signals(scan),
        )
        try:
            similar_repositories = SimilarRepoService(github_service).find_similar_repositories(
                metadata={
                    **repository_metadata,
                    "language": repository_metadata.get("language") or (stack.get("languages") or [None])[0],
                },
                stack=stack,
                readme=readme_content or "",
                stats={"files": len(scan.get("files", []))},
                analysis_context={
                    **ai_analysis,
                    "analysis_evidence": ai_analysis.get("analysis_evidence", {}),
                    "semantic_repository_profile": semantic_repository_profile,
                },
                repository_structure=[folder_structure] if folder_structure else [],
            )
        except Exception as exc:
            emit(logger, "similar_repository_analysis_failed", level=logging.WARNING, stage="similar_repositories",
                 repository=repo_name, commit_sha=commit_sha, exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
            similar_repositories = []

        ai_insights = [item.get("name", "") for item in (ai_analysis.get("executive_overview") or {}).get("user_features", []) if item.get("name")]

        repository = None
        if payload.repo_url:
            persistence_started = time.perf_counter()
            emit(logger, "persistence_started", stage="persistence", repository=repo_name, commit_sha=commit_sha)
            repository_url = normalize_github_url(payload.repo_url)
            repository = db.scalar(select(Repository).where(Repository.github_url == repository_url))
            if repository is None:
                repository = Repository(
                    github_url=repository_url,
                    full_name=repository_metadata.get("full_name") or repo_name,
                    description=repository_metadata.get("description") or description,
                    stars=repository_metadata.get("stargazers_count") or 0,
                    primary_language=repository_metadata.get("language")
                    or (stack.get("languages") or [None])[0],
                )
                db.add(repository)
                db.flush()
            else:
                repository.full_name = repository_metadata.get("full_name") or repo_name
                repository.description = repository_metadata.get("description") or description
                repository.stars = repository_metadata.get("stargazers_count") or 0
                repository.primary_language = repository_metadata.get("language") or (stack.get("languages") or [None])[0]

            result = repository.analysis_result
            if result is None:
                result = AnalysisResult(repository_id=repository.id)
                db.add(result)
            result.stack = stack
            result.overview = ai_analysis.get("overview") or ""
            result.modules = ai_analysis.get("modules") or []
            result.architecture_summary = llm_service.architecture_summary_text(ai_analysis)
            result.similar_repositories = similar_repositories
            result.readme = readme_content
            result.readme_path = readme_path.relative_to(repo_path).as_posix() if readme_path else None
            result.folder_structure = [folder_structure] if folder_structure else []
            result.languages = stack.get("languages", [])
            result.architecture = ai_analysis.get("architecture")
            result.executive_overview = ai_analysis.get("executive_overview")
            result.analysis_evidence = ai_analysis.get("analysis_evidence")
            result.analysis_status = analysis_status
            result.commit_sha = commit_sha
            result.repository_model = repository_model.model_dump(mode="json")
            db.commit()
            db.refresh(repository)
            emit(logger, "persistence_completed", stage="persistence", repository=repo_name, commit_sha=commit_sha,
                 duration_ms=round((time.perf_counter() - persistence_started) * 1000), repository_id=repository.id,
                 analysis_status=analysis_status, claim_count=len(repository_model.claims))
        else:
            emit(logger, "persistence_skipped", level=logging.INFO, stage="persistence", reason="local_path_analysis_has_no_repository_record")

        response = AnalyzeResponse(
            status="success",
            repository_id=repository.id if repository else None,
            repo_name=repo_name,
            repo_url=payload.repo_url,
            local_path=str(repo_path) if payload.local_path else None,
            readme=readme_content,
            readme_path=readme_path.relative_to(repo_path).as_posix() if readme_path else None,
            stack=stack,
            folder_structure=[folder_structure],
            languages=stack.get("languages", []),
            overview=ai_analysis.get("overview", ""),
            executive_overview=ai_analysis.get("executive_overview"),
            architecture=ai_analysis.get("architecture"),
            architecture_summary=llm_service.architecture_summary_text(ai_analysis),
            modules=ai_analysis["modules"],
            analysis_evidence=ai_analysis.get("analysis_evidence"),
            ai_insights=ai_insights,
            analysis_status=analysis_status,
            commit_sha=commit_sha,
            repository_model=repository_model.model_dump(mode="json"),
            similar_repositories=similar_repositories,
        )
        response.model_dump(mode="json")
        emit(logger, "response_schema_validated", stage="response_serialization", repository=repo_name, commit_sha=commit_sha,
             field_count=len(response.model_fields_set), status=response.status, analysis_status=response.analysis_status)
        return response
    except ValueError as e:
        emit(logger, "analysis_validation_failed", level=logging.ERROR, repository=payload.repo_url or "local", reason=str(e), exc_info=True)
        return AnalyzeResponse(status="error", analysis_status="error", error_code="analysis_validation_failed", message=f"Analysis failed validation. Use correlation ID {payload.analysis_run_id} for diagnostics.")
    except RuntimeError as e:
        emit(logger, "analysis_runtime_failed", level=logging.ERROR, repository=payload.repo_url or "local", reason=str(e), exc_info=True)
        return AnalyzeResponse(status="error", analysis_status="error", error_code="analysis_runtime_failed", message=f"Analysis could not complete. Use correlation ID {payload.analysis_run_id} for diagnostics.")
