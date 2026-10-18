from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.repository import Repository
from app.routes import analyze as analyze_route
from app.services.github_service import get_github_service


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_new_and_distinct_repositories_are_persisted(db_session: Session) -> None:
    first = analyze_route._upsert_repository_record(
        db_session, "https://github.com/Example/First"
    )
    second = analyze_route._upsert_repository_record(
        db_session, "https://github.com/example/second.git"
    )

    records = list(db_session.scalars(select(Repository).order_by(Repository.id)))
    assert len(records) == 2
    assert first.id != second.id
    assert first.github_url == "https://github.com/example/first.git"
    assert second.github_url == "https://github.com/example/second.git"


def test_reanalysis_reuses_repository_and_updates_available_metadata(
    db_session: Session,
) -> None:
    first = analyze_route._upsert_repository_record(
        db_session, "https://github.com/example/repo"
    )
    updated = analyze_route._upsert_repository_record(
        db_session,
        "https://github.com/EXAMPLE/REPO.git",
        {"full_name": "Example/Repo", "description": "A repository", "stargazers_count": 12, "language": "Python"},
    )

    assert updated.id == first.id
    assert db_session.scalar(select(Repository).where(Repository.id == first.id)) is not None
    assert db_session.scalar(select(Repository).order_by(Repository.id.desc())).id == first.id
    assert updated.full_name == "Example/Repo"
    assert updated.description == "A repository"
    assert updated.stars == 12
    assert updated.primary_language == "Python"


def test_analysis_result_references_its_repository_and_is_retrievable(
    db_session: Session,
) -> None:
    repository = analyze_route._upsert_repository_record(
        db_session, "https://github.com/example/repo"
    )
    other_repository = analyze_route._upsert_repository_record(
        db_session, "https://github.com/example/other"
    )
    result = AnalysisResult(
        repository_id=other_repository.id,
        stack={"languages": ["Python"]},
        overview="Repository overview",
        modules=[{"name": "API"}],
        architecture_summary="API to database",
        similar_repositories=[],
        analysis_status="complete",
        commit_sha="abc123",
        repository_model={"claims": []},
    )
    db_session.add(result)
    db_session.commit()

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(f"/api/repositories/{other_repository.id}")
        empty_response = TestClient(app).get(f"/api/repositories/{repository.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    payload = response.json()
    assert payload["github_url"] == "https://github.com/example/other.git"
    assert payload["analysis_result"]["overview"] == "Repository overview"
    assert payload["analysis_result"]["analysis_status"] == "complete"
    assert payload["analysis_result"]["commit_sha"] == "abc123"
    assert empty_response.status_code == 200
    assert empty_response.json()["analysis_result"] is None


def test_failed_clone_keeps_repository_record_and_returns_error(monkeypatch, db_session: Session) -> None:
    class FailingGitHubService:
        def clone_repository(self, _repo_url: str) -> dict:
            raise RuntimeError("controlled clone failure")

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_github_service] = FailingGitHubService
    try:
        response = TestClient(app).post(
            "/analyze",
            json={"repo_url": "https://github.com/example/failing-repo", "analysis_run_id": "persistence_failure"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_github_service, None)

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    repository = db_session.scalar(
        select(Repository).where(
            Repository.github_url == "https://github.com/example/failing-repo.git"
        )
    )
    assert repository is not None
    assert repository.analysis_result is None


def test_repository_database_error_is_not_reported_as_success(monkeypatch, db_session: Session) -> None:
    def fail_persistence(*_args, **_kwargs):
        raise OperationalError(
            "repository upsert", {}, RuntimeError("database unavailable")
        )

    class UnusedGitHubService:
        def clone_repository(self, _repo_url: str) -> dict:
            pytest.fail("repository cloning must not run when persistence fails")

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    monkeypatch.setattr(analyze_route, "_upsert_repository_record", fail_persistence)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_github_service] = UnusedGitHubService
    try:
        response = TestClient(app).post(
            "/analyze", json={"repo_url": "https://github.com/example/db-error"}
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_github_service, None)

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["analysis_status"] == "error"

