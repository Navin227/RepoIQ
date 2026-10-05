from app.services.repository_discovery import (
    build_candidate_queries,
    expand_query,
    rank_candidates,
    score_analyzability,
    score_relevance,
)
from app.services.github_service import GitHubService


def test_query_expansion_is_conceptual_and_candidate_queries_are_limited():
    expanded = expand_query("file manager")

    assert "file manager" in expanded
    assert "file sharing" in expanded
    assert "cloud storage" in expanded
    assert len(build_candidate_queries("file manager")) <= 3


def test_ecommerce_normalization_supports_spacing_and_hyphen_variants():
    expanded = expand_query("e commerce")

    assert "ecommerce" in expanded
    assert "e commerce" in expanded
    assert any("online store" in term for term in expanded)


def test_relevant_repository_outscores_unrelated_popular_repository():
    relevant = {
        "full_name": "example/awesome-file-manager",
        "name": "awesome-file-manager",
        "description": "A personal file browser and sharing application.",
        "topics": ["file-manager", "file-sharing"],
        "stargazers_count": 80,
    }
    unrelated = {
        "full_name": "example/popular-library",
        "name": "popular-library",
        "description": "A general purpose developer utility.",
        "topics": ["utilities"],
        "stargazers_count": 2_000_000,
    }

    assert score_relevance("file manager", relevant) > score_relevance("file manager", unrelated)
    assert rank_candidates("file manager", [unrelated, relevant])[0]["full_name"] == relevant["full_name"]


def test_source_and_configuration_evidence_outweigh_readme_presence():
    readme_only_score = score_analyzability(["README.md"], readme_present=True)
    implementation_score = score_analyzability(
        [
            "README.md",
            "package.json",
            "src/routes/files.ts",
            "src/services/storage.ts",
            "src/controllers/upload.ts",
            "src/models/file.ts",
            "Dockerfile",
            "tests/files.test.ts",
        ],
        readme_present=False,
    )

    assert implementation_score > readme_only_score


def test_highly_relevant_low_evidence_repository_is_not_removed():
    repository = {
        "full_name": "example/file-manager",
        "name": "file-manager",
        "description": None,
        "topics": [],
        "stargazers_count": 0,
        "_repo_paths": [],
    }

    ranked = rank_candidates("file manager", [repository])

    assert len(ranked) == 1
    assert ranked[0]["relevance_score"] >= 12
    assert ranked[0]["analyzability_score"] == 0


def test_relevance_floor_excludes_unrelated_repository_even_with_strong_evidence():
    unrelated = {
        "full_name": "example/fast-database",
        "name": "fast-database",
        "description": "A high performance database engine.",
        "topics": ["database", "storage"],
        "stargazers_count": 1_000_000,
        "_repo_paths": [
            "package.json",
            "src/server.ts",
            "src/database/query.ts",
            "Dockerfile",
            "tests/query.test.ts",
        ],
    }

    assert rank_candidates("file manager", [unrelated]) == []


def test_missing_github_metadata_is_scored_defensively():
    assert score_relevance("cloud storage", {}) == 0
    assert rank_candidates("cloud storage", [{}, None]) == []


def test_github_search_uses_broad_candidates_and_ranks_with_tree_evidence(monkeypatch):
    relevant_without_sources = {
        "id": 1,
        "name": "file-manager",
        "full_name": "example/file-manager",
        "owner": {"login": "example"},
        "description": "A file manager.",
        "stargazers_count": 200,
        "forks_count": 20,
        "language": "TypeScript",
        "html_url": "https://github.com/example/file-manager",
        "topics": ["file-manager"],
        "default_branch": "main",
    }
    relevant_with_sources = {
        **relevant_without_sources,
        "id": 2,
        "name": "file-manager-pro",
        "full_name": "example/file-manager-pro",
        "html_url": "https://github.com/example/file-manager-pro",
        "stargazers_count": 80,
    }
    unrelated_popular = {
        **relevant_without_sources,
        "id": 3,
        "name": "database-engine",
        "full_name": "example/database-engine",
        "description": "A popular database engine.",
        "html_url": "https://github.com/example/database-engine",
        "topics": ["database"],
        "stargazers_count": 2_000_000,
    }
    queried = []

    class Response:
        def json(self):
            return {
                "items": [
                    relevant_without_sources,
                    relevant_with_sources,
                    unrelated_popular,
                ]
            }

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, params):
            queried.append(params["q"])
            return Response()

    service = GitHubService(token="test-token")
    monkeypatch.setattr("app.services.github_service.httpx.Client", Client)
    monkeypatch.setattr(
        service,
        "_fetch_candidate_tree",
        lambda repo: (
            ["README.md"]
            if repo["id"] == 1
            else [
                "package.json",
                "src/routes/files.ts",
                "src/services/storage.ts",
                "src/controllers/upload.ts",
                "Dockerfile",
                "tests/files.test.ts",
            ]
        ),
    )

    results = service.search_repositories("file manager", limit=10)

    assert len(queried) == 3
    assert len(results) == 2
    assert results[0].full_name == "example/file-manager-pro"
    assert results[0].relevance_score >= results[1].relevance_score
    assert results[0].analyzability_score > results[1].analyzability_score
