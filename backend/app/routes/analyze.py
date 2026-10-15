import inspect
import json
import logging
import subprocess
import hashlib
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

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=AnalyzeResponse)
def analyze_repository(
    payload: AnalyzeRequest,
    github_service: GitHubService = Depends(get_github_service),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    try:
        if payload.local_path:
            repo_path = Path(payload.local_path)
            if not repo_path.exists() or not repo_path.is_dir():
                raise HTTPException(status_code=400, detail="Local path does not exist or is not a directory")
            repo_name = repo_path.name
            clone_result = {"commit_sha": ""}
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
            except Exception:
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
            logger.info(
                "README selected for analysis repo=%s path=%s source=%s bytes=%s chars=%s",
                repository_metadata.get("full_name") or repo_name,
                str(readme_path) if readme_path else ("github_api" if readme_source == "github_api" else "missing"),
                readme_source,
                len(readme_content.encode("utf-8")) if readme_content else 0,
                len(readme_content) if readme_content else 0,
            )
        else:
            raise HTTPException(status_code=400, detail="Either repo_url or local_path is required")

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
        if se_stats:
            logger.info(
                "Evidence scan summary: %s",
                json.dumps(
                    {
                        "selected_files": se_stats.get("selected_evidence_files"),
                        "routes": se_stats.get("routes_detected"),
                        "payload_chars": se_stats.get("evidence_payload_chars"),
                    }
                ),
            )
        stack = StackDetector().detect(scan)
        logger.debug("Detected repository stack: %s", json.dumps(stack, ensure_ascii=False, default=str))
        folder_structure = RepositoryStructureService().build_tree(repo_path)

        llm_service = LLMService()
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
            logger.exception("Similar repository analysis failed: %s", exc)
            similar_repositories = []

        ai_insights = [item.get("name", "") for item in (ai_analysis.get("executive_overview") or {}).get("user_features", []) if item.get("name")]

        repository = None
        if payload.repo_url:
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

        return AnalyzeResponse(
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
    except ValueError as e:
        return AnalyzeResponse(status="error", analysis_status="error", message=str(e))
    except RuntimeError as e:
        return AnalyzeResponse(status="error", analysis_status="error", message=str(e))
