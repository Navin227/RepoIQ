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
    analyzability_score: float = 0
    ranking_score: float = 0
