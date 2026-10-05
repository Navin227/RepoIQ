from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.repository import Repository
from app.schemas.repository import RepositoryResponse

router = APIRouter()


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository_analysis(repository_id: int, db: Session = Depends(get_db)) -> RepositoryResponse:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository analysis not found")
    return RepositoryResponse.model_validate(repository)
