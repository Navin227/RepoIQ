import json
import logging
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
            description = ""
            repository_metadata = {
                "name": repo_name,
                "full_name": repo_name,
                "description": description,
                "topics": [],
            }
            readme_content = None
            for readme_name in ["README.md", "README.rst", "README.txt"]:
                readme_path = repo_path / readme_name
                if readme_path.exists():
                    readme_content = readme_path.read_text()
                    break
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
                }
            readme_content = github_service.find_readme(repo_path) or ""
        else:
            raise HTTPException(status_code=400, detail="Either repo_url or local_path is required")

        scan = RepoScanner().scan(repo_path)
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
        print("📊 DETECTED STACK (JSON):")
        print(json.dumps(stack, indent=2, default=str))
        folder_structure = RepositoryStructureService().build_tree(repo_path)

        llm_service = LLMService()
        ai_analysis = llm_service.generate_repository_analysis(
            metadata=repository_metadata,
            readme=readme_content or "",
            stack=stack,
            repository_structure=[folder_structure] if folder_structure else [],
            scan=scan,
        )
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
            result.folder_structure = [folder_structure] if folder_structure else []
            result.languages = stack.get("languages", [])
            result.architecture = ai_analysis.get("architecture")
            result.executive_overview = ai_analysis.get("executive_overview")
            result.analysis_evidence = ai_analysis.get("analysis_evidence")
            db.commit()
            db.refresh(repository)

        return AnalyzeResponse(
            status="success",
            repository_id=repository.id if repository else None,
            repo_name=repo_name,
            repo_url=payload.repo_url,
            local_path=str(repo_path) if payload.local_path else None,
            readme=readme_content,
            stack=stack,
            folder_structure=[folder_structure],
            languages=stack.get("languages", []),
            overview=ai_analysis["overview"],
            executive_overview=ai_analysis.get("executive_overview"),
            architecture=ai_analysis.get("architecture"),
            architecture_summary=llm_service.architecture_summary_text(ai_analysis),
            modules=ai_analysis["modules"],
            analysis_evidence=ai_analysis.get("analysis_evidence"),
            ai_insights=[],
            similar_repositories=similar_repositories,
        )
    except ValueError as e:
        return AnalyzeResponse(status="error", message=str(e))
    except RuntimeError as e:
        return AnalyzeResponse(status="error", message=str(e))
