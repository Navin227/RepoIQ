from fastapi.testclient import TestClient

from app.main import app
from app.services.github_service import get_github_service


def test_health_check() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_production_amplify_origin() -> None:
    client = TestClient(app)
    response = client.options(
        "/search",
        headers={
            "Origin": "https://main.d20r18yhh140ff.amplifyapp.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://main.d20r18yhh140ff.amplifyapp.com"
    )


def test_cors_does_not_allow_unrelated_origin() -> None:
    client = TestClient(app)
    response = client.options(
        "/search",
        headers={
            "Origin": "https://unrelated.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_search_route_accepts_plain_language_query() -> None:
    class FakeGitHubService:
        def search_repositories(self, query: str, limit: int) -> list[dict]:
            assert query == "healthcare platforms"
            assert limit == 12
            return [{
                "id": 42,
                "name": "care-platform",
                "owner": "example",
                "full_name": "example/care-platform",
                "description": "Healthcare platform",
                "stars": 10,
                "forks": 2,
                "language": "Python",
                "html_url": "https://github.com/example/care-platform",
                "topics": ["healthcare"],
                "relevance_score": 90,
                "analyzability_score": 80,
                "ranking_score": 86,
            }]

    app.dependency_overrides[get_github_service] = FakeGitHubService
    try:
        response = TestClient(app).get(
            "/search",
            params={"q": "healthcare platforms"},
        )
    finally:
        app.dependency_overrides.pop(get_github_service, None)

    assert response.status_code == 200
    assert response.json()[0]["full_name"] == "example/care-platform"
