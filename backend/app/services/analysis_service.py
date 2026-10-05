from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis_job import AnalysisJob, AnalysisJobStatus
from app.models.analysis_result import AnalysisResult
from app.models.repository import Repository
from app.schemas.analysis import AnalyzeResponse
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
from app.services.repository_structure_service import RepositoryStructureService
from app.services.similar_repo_service import SimilarRepoService
from app.services.stack_detector import StackDetector
from app.utils.repo_scanner import RepoScanner


class AnalysisService:
    def __init__(
        self,
        github_service: GitHubService | None = None,
        stack_detector: StackDetector | None = None,
        llm_service: LLMService | None = None,
        similar_repo_service: SimilarRepoService | None = None,
        repo_scanner: RepoScanner | None = None,
    ) -> None:
        self.github_service = github_service or GitHubService()
        self.stack_detector = stack_detector or StackDetector()
        self.llm_service = llm_service or LLMService()
        self.similar_repo_service = similar_repo_service or SimilarRepoService(self.github_service)
        self.repo_scanner = repo_scanner or RepoScanner()

    def analyze_repository(self, db: Session, repo_url: str) -> AnalyzeResponse:
        job = AnalysisJob(repo_url=repo_url, status=AnalysisJobStatus.running)
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            metadata = self.github_service.fetch_metadata(repo_url)
            repo_path = Path(settings.clone_base_dir) / str(job.id)
            self.github_service.clone_repository(repo_url, repo_path)

            scan = self.repo_scanner.scan(repo_path)
            stack = self.stack_detector.detect(scan)
            repository_structure_service = RepositoryStructureService()
            folder_structure = repository_structure_service.build_tree(repo_path)
            overview = self.llm_service.generate_overview(metadata=metadata, scan=scan, stack=stack)
            modules = self.llm_service.generate_modules(scan=scan, stack=stack)
            architecture = self.llm_service.generate_architecture_summary(scan=scan, stack=stack)
            analysis_context = {
                "overview": overview,
                "modules": modules,
                "architecture": architecture,
                "stack": stack,
            }
            similar = self.similar_repo_service.find_similar_repositories(
                metadata=metadata,
                stack=stack,
                analysis_context=analysis_context,
                repository_structure=[folder_structure] if folder_structure else [],
            )

            repository = Repository(
                github_url=repo_url,
                full_name=metadata["full_name"],
                description=metadata.get("description"),
                stars=metadata.get("stargazers_count", 0),
                primary_language=metadata.get("language"),
            )
            db.add(repository)
            db.flush()

            result = AnalysisResult(
                repository_id=repository.id,
                stack=stack,
                overview=overview,
                modules=modules,
                architecture_summary=architecture,
                similar_repositories=similar,
            )
            db.add(result)
            job.status = AnalysisJobStatus.completed
            job.repository_id = repository.id
            db.commit()
            db.refresh(repository)

            return AnalyzeResponse(
                job_id=job.id,
                repository_id=repository.id,
                status=job.status,
                message="Repository analysis completed",
            )
        except Exception:
            job.status = AnalysisJobStatus.failed
            db.commit()
            raise

    def enqueue_analysis(self, repo_url: str) -> AnalyzeResponse:
        # Future SQS integration point: publish repo_url and job_id to a queue.
        return AnalyzeResponse(job_id=None, repository_id=None, status="queued", message="Queued for analysis")


def get_analysis_service() -> AnalysisService:
    return AnalysisService()
