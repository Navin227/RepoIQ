from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.repository import Repository
from app.routes.repository import get_repository_history
import pytest
from fastapi import HTTPException


def make_repository(db: Session, name: str, created_at: datetime, analysis_at: datetime | None):
    repository = Repository(
        github_url=f"https://github.com/{name}",
        full_name=name,
        description=None,
        stars=0,
        primary_language=None,
        created_at=created_at,
    )
    db.add(repository)
    db.flush()
    if analysis_at:
        db.add(AnalysisResult(
            repository_id=repository.id,
            stack={}, overview="Stored overview", modules=[], architecture_summary="",
            similar_repositories=[], created_at=analysis_at,
        ))
    db.flush()
    return repository


def test_history_sorts_by_analysis_time_and_paginates_without_duplicate_repositories():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime(2026, 10, 17)
        make_repository(db, "owner/old-analysis", now, now - timedelta(days=5))
        make_repository(db, "owner/recent-analysis", now - timedelta(days=10), now - timedelta(days=1))
        make_repository(db, "owner/no-result", now, None)
        db.commit()

        first_page = get_repository_history(offset=0, limit=1, db=db)
        next_page = get_repository_history(offset=1, limit=2, db=db)

    assert first_page.total == 3
    assert [item.full_name for item in first_page.items] == ["owner/recent-analysis"]
    assert len(next_page.items) == 2
    assert next_page.items[0].full_name == "owner/old-analysis"
    assert next_page.items[1].full_name == "owner/no-result"
    assert next_page.items[1].analysis_result is None
    assert next_page.items[1].description is None
    engine.dispose()


def test_history_empty_database_returns_empty_page():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        page = get_repository_history(offset=0, limit=20, db=db)
    assert page.items == []
    assert page.total == 0
    engine.dispose()


def test_history_database_error_returns_retryable_service_error():
    class BrokenSession:
        def scalar(self, _query):
            raise SQLAlchemyError("database unavailable")

    with pytest.raises(HTTPException) as error:
        get_repository_history(offset=0, limit=20, db=BrokenSession())
    assert error.value.status_code == 503


def test_exact_history_api_route_returns_saved_analysis_page(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history-api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime(2026, 10, 17)
        make_repository(db, "owner/saved", now, now)
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/repositories/history?offset=0&limit=20")
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["full_name"] == "owner/saved"
    assert payload["items"][0]["analysis_result"]["overview"] == "Stored overview"


def test_exact_history_api_route_returns_503_on_database_error():
    class BrokenSession:
        def scalar(self, _query):
            raise SQLAlchemyError("database unavailable")

    def override_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/repositories/history?offset=0&limit=20")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Repository history is temporarily unavailable"
