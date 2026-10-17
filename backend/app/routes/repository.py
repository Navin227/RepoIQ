import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.repository import Repository
from app.models.analysis_result import AnalysisResult
from app.schemas.repository import RepositoryHistoryPage, RepositoryResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/history", response_model=RepositoryHistoryPage)
def get_repository_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RepositoryHistoryPage:
    try:
        total = db.scalar(select(func.count(Repository.id))) or 0
        repositories = db.scalars(
            select(Repository)
            .outerjoin(AnalysisResult)
            .options(joinedload(Repository.analysis_result))
            .order_by(AnalysisResult.created_at.desc().nullslast(), Repository.id.desc())
            .offset(offset)
            .limit(limit)
        ).unique().all()
        return RepositoryHistoryPage(
            items=repositories, offset=offset, limit=limit, total=total
        )
    except SQLAlchemyError as exc:
        logger.exception("Repository history query failed")
        raise HTTPException(status_code=503, detail="Repository history is temporarily unavailable") from exc


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository_analysis(repository_id: int, db: Session = Depends(get_db)) -> RepositoryResponse:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository analysis not found")
    return RepositoryResponse.model_validate(repository)
