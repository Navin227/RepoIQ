from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class AnalysisResultResponse(BaseModel):
    stack: dict
    overview: str
    modules: list[dict]
    architecture_summary: str
    similar_repositories: list[dict]
    readme: str | None = None
    readme_path: str | None = None
    executive_overview: dict | None = None
    architecture: dict | None = None
    analysis_evidence: dict | None = None
    analysis_status: str | None = None
    commit_sha: str | None = None
    repository_model: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class RepositoryResponse(BaseModel):
    id: int
    github_url: HttpUrl
    full_name: str
    description: str | None
    stars: int
    primary_language: str | None
    created_at: datetime
    analysis_result: AnalysisResultResponse | None = None

    model_config = ConfigDict(from_attributes=True)
