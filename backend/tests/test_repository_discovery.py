import pytest

from app.services.repository_discovery import (
    build_candidate_queries,
    expand_query,
    rank_candidates,
    score_analyzability,
    score_relevance,
)
from app.services.github_service import GitHubService
from app.services import repository_discovery


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
    assert ranked[0]["evidence_readiness"] == "low"
    assert ranked[0]["tree_inspection_state"] == "inspected"


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
    assert results[0].tree_inspection_state == "inspected"
    assert results[1].tree_inspection_state == "inspected"
    assert results[0].ranking_score > results[1].ranking_score
    assert results[0].analyzability_score > results[1].analyzability_score


def test_high_relevance_low_readiness_does_not_beat_moderate_relevance_strong_source(monkeypatch):
    monkeypatch.setattr(repository_discovery, "score_relevance", lambda query, item: item["test_relevance"])
    candidates = [
        {"name": "topical-docs", "full_name": "a/topical-docs", "test_relevance": 98, "_repo_paths": ["README.md", "package.json"], "_tree_inspection_state": "inspected", "_readme_present": True},
        {"name": "working-library", "full_name": "b/working-library", "test_relevance": 70, "_repo_paths": ["pyproject.toml", "src/lib/core.py", "src/lib/io.py", "src/lib/model.py", "tests/test_core.py"], "_tree_inspection_state": "inspected"},
    ]
    ranked = rank_candidates("project", candidates)
    assert ranked[0]["full_name"] == "b/working-library"
    topical = next(item for item in ranked if item["full_name"] == "a/topical-docs")
    assert topical["relevance_score"] == 98
    assert topical["evidence_readiness"] == "low"
    assert topical["analyzability_score"] < ranked[0]["analyzability_score"]


def test_missing_tree_evidence_is_unknown_not_zero_and_ranks_after_inspected(monkeypatch):
    monkeypatch.setattr(repository_discovery, "score_relevance", lambda query, item: item["test_relevance"])
    candidates = [
        {"full_name": "a/not-inspected", "test_relevance": 100},
        {"full_name": "b/inspected", "test_relevance": 50, "_repo_paths": ["src/main.py", "pyproject.toml"], "_tree_inspection_state": "inspected"},
    ]
    ranked = rank_candidates("query", candidates)
    assert ranked[0]["full_name"] == "b/inspected"
    missing = next(item for item in ranked if item["full_name"] == "a/not-inspected")
    assert missing["analyzability_score"] is None
    assert missing["ranking_score"] is None
    assert missing["tree_inspection_state"] == "not_inspected"
    assert missing["evidence_readiness"] == "unknown"


def test_tree_inspection_failure_is_distinct_from_an_empty_repository(monkeypatch):
    service = GitHubService(token="test")
    candidates = [{"id": 1, "full_name": "a/fail"}, {"id": 2, "full_name": "b/empty"}]

    def fetch(candidate):
        if candidate["id"] == 1:
            raise RuntimeError("private provider details must not be logged")
        return []

    monkeypatch.setattr(service, "_fetch_candidate_tree", fetch)
    service._add_candidate_evidence(candidates)
    ranked = rank_candidates("repo", [
        {**candidates[0], "name": "repo-fail", "description": "repo", "_tree_inspection_state": "inspection_failed"},
        {**candidates[1], "name": "repo-empty", "description": "repo"},
    ])
    failed = next(item for item in ranked if item["id"] == 1)
    empty = next(item for item in ranked if item["id"] == 2)
    assert failed["tree_inspection_state"] == "inspection_failed"
    assert failed["analyzability_score"] is None
    assert empty["tree_inspection_state"] == "inspected"
    assert empty["analyzability_score"] == 0
    assert empty["readiness_reason"].startswith("empty_repository")


def test_truncated_tree_is_explicit_and_not_scored_as_complete(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"truncated": True, "tree": [
                {"path": "src/main.py", "type": "blob"},
                {"path": "src", "type": "tree"},
                {"path": "src/service.py", "type": "blob"},
            ]}

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def get(self, *args, **kwargs): return Response()

    monkeypatch.setattr("app.services.github_service.httpx.Client", Client)
    candidate = {"full_name": "owner/repo", "default_branch": "main"}
    paths = GitHubService(token="test")._fetch_candidate_tree(candidate)
    candidate.update(_repo_paths=paths, _tree_inspection_state="inspected")
    ranked = rank_candidates("repo", [candidate])[0]
    assert paths == ["src/main.py", "src/service.py"]
    assert ranked["tree_truncated"] is True
    assert ranked["analyzability_score"] is None
    assert ranked["evidence_readiness"] == "partial"
    assert ranked["meaningful_source_file_count"] == 2


def test_direct_url_search_does_not_run_idea_ranking(monkeypatch):
    service = GitHubService(token="test")
    monkeypatch.setattr(service, "_search_discovery", lambda *args: pytest.fail("idea ranking invoked"))

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"id": 9, "name": "repo", "full_name": "owner/repo", "owner": {"login": "owner"}, "html_url": "https://github.com/owner/repo", "stargazers_count": 1}

    monkeypatch.setattr("app.services.github_service.httpx.get", lambda *args, **kwargs: Response())
    result = service.search_repositories("https://github.com/owner/repo")
    assert len(result) == 1
    assert result[0].tree_inspection_state == "not_assessed"
    assert result[0].analyzability_score is None
    assert result[0].ranking_score is None


def test_equal_candidate_scores_use_stable_name_order(monkeypatch):
    monkeypatch.setattr(repository_discovery, "score_relevance", lambda query, item: 50)
    first = {"full_name": "z/project", "_repo_paths": ["src/main.py"], "_tree_inspection_state": "inspected"}
    second = {"full_name": "a/project", "_repo_paths": ["src/main.py"], "_tree_inspection_state": "inspected"}
    assert [item["full_name"] for item in rank_candidates("x", [first, second])] == ["a/project", "z/project"]
