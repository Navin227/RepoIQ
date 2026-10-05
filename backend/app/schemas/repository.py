from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class AnalysisResultResponse(BaseModel):
    stack: dict
    overview: str
    modules: list[dict]
    architecture_summary: str
    similar_repositories: list[dict]

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
