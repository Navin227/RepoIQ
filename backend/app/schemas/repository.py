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


class HistoryAnalysisResponse(BaseModel):
    stack: dict | None = None
    overview: str | None = None
    modules: list[dict] | None = None
    architecture_summary: str | None = None
    similar_repositories: list[dict] | None = None
    readme: str | None = None
    readme_path: str | None = None
    folder_structure: list | None = None
    languages: list | None = None
    architecture: dict | None = None
    executive_overview: dict | None = None
    analysis_evidence: dict | None = None
    analysis_status: str | None = None
    commit_sha: str | None = None
    repository_model: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryHistoryItem(BaseModel):
    id: int
    github_url: HttpUrl
    full_name: str
    description: str | None = None
    stars: int | None = None
    primary_language: str | None = None
    created_at: datetime
    analysis_result: HistoryAnalysisResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class RepositoryHistoryPage(BaseModel):
    items: list[RepositoryHistoryItem]
    offset: int
    limit: int
    total: int
