from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SearchRepositoryItem(BaseModel):
    id: int
    name: str
    owner: str
    full_name: str
    description: str | None = None
    stars: int
    forks: int = 0
    language: str | None = None
    html_url: HttpUrl
    topics: list[str] = Field(default_factory=list)
    relevance_score: float = 0
    analyzability_score: float | None = None
    ranking_score: float | None = None
    ranking_adjustment: float | None = None
    comparable_relevance_cohort: bool | None = None
    tree_inspection_state: Literal["inspected", "inspection_failed", "not_inspected", "not_assessed"] = "not_assessed"
    tree_truncated: bool | None = None
    evidence_readiness: Literal["ready", "limited", "low", "partial", "unknown", "not_assessed"] = "not_assessed"
    readiness_reason: str | None = None
    repository_type: str | None = None
    inspected_file_count: int | None = None
    tree_reported_file_count: int | None = None
    meaningful_source_file_count: int | None = None
