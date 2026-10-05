from fastapi import APIRouter, Depends, HTTPException, Query
from httpx import HTTPError

from app.schemas.search import SearchRepositoryItem
from app.services.github_service import GitHubService, get_github_service

router = APIRouter()


@router.get("", response_model=list[SearchRepositoryItem])
def search_repositories(
    q: str = Query(..., min_length=2, description="Plain-language idea or repository topic"),
    limit: int = Query(12, ge=1, le=25),
    github_service: GitHubService = Depends(get_github_service),
) -> list[SearchRepositoryItem]:
    try:
        return github_service.search_repositories(query=q, limit=limit)
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail="GitHub search failed") from exc
