import pytest

from app.services.github_service import GitHubService
from app.services.similar_repo_service import SimilarRepoService


def candidate(owner, name, description="", stars=0, language=None, topics=None, tree=None):
    return {
        "id": abs(hash(f"{owner}/{name}")) % 1_000_000,
        "name": name,
        "owner": {"login": owner},
        "full_name": f"{owner}/{name}",
        "html_url": f"https://github.com/{owner}/{name}",
        "description": description,
        "stargazers_count": stars,
        "forks_count": 12,
        "language": language,
        "topics": topics or [],
        "_tree_paths": tree or [],
    }


def stack(*names):
    categories = {
        "frontend": [],
        "backend": [],
        "database": [],
        "infrastructure": [],
        "devops": [],
        "cloud": [],
    }
    tech_categories = {
        "React": "frontend",
        "Vue": "frontend",
        "FastAPI": "backend",
        "Django": "backend",
        "PostgreSQL": "database",
        "MongoDB": "database",
        "Docker": "devops",
        "Kubernetes": "devops",
        "Terraform": "infrastructure",
        "AWS": "cloud",
        "S3": "cloud",
    }
    for name in names:
        category = tech_categories.get(name)
        if category:
            categories[category].append({
                "name": name,
                "source": "manifest",
                "evidence": "dependency/config evidence",
            })
    return {"categories": categories}


def source_profile(service):
    return service._build_fingerprint(
        metadata={
            "full_name": "source/files",
            "name": "files",
            "description": "File management and sharing platform",
            "topics": ["file-manager", "file-sharing"],
            "language": "Python",
        },
        stack=stack("React", "FastAPI", "PostgreSQL", "Docker", "S3"),
        readme="Users upload, manage, download, and share files.",
        analysis_context={
            "overview": "File management platform with secure file sharing.",
            "executive_overview": {
                "what_is_this_project": ["A web file management and storage system."],
            },
            "modules": [
                {"name": "Authentication", "components": ["src/auth.py"]},
                {"name": "File Upload", "components": ["src/routes/upload.py"]},
                {"name": "File Management", "components": ["src/services/files.py"]},
                {"name": "File Sharing", "components": ["src/routes/share.py"]},
                {"name": "Storage", "components": ["src/storage/s3.py"]},
            ],
            "architecture": {
                "architecture_type": "Layered",
                "architecture_summary": "React client calls a FastAPI REST API backed by PostgreSQL and S3.",
                "flow": ["React frontend", "FastAPI REST API", "PostgreSQL", "S3"],
                "deployment": "Docker",
            },
            "analysis_evidence": {
                "technology_detections": [
                    {"name": "FastAPI", "source": "requirements.txt"},
                    {"name": "PostgreSQL", "source": "settings.py"},
                    {"name": "S3", "source": "storage.py"},
                ],
                "api_routes": ["/upload", "/share"],
            },
        },
        repository_structure=[
            {
                "name": "root",
                "type": "folder",
                "children": [
                    {"name": "frontend", "type": "folder", "children": []},
                    {"name": "backend", "type": "folder", "children": [
                        {"name": "routes", "type": "folder", "children": []},
                        {"name": "services", "type": "folder", "children": []},
                    ]},
                    {"name": "tests", "type": "folder", "children": []},
                    {"name": "Dockerfile", "type": "file"},
                ],
            }
        ],
    )


def run_rank(service, candidates, profile=None):
    return service._rank_candidates(
        candidates=candidates,
        fingerprint=profile or source_profile(service),
        current_full_name={"source/files"},
    )


def test_similar_repositories_deduplicate_and_exclude_repository_by_name_or_url():
    service = SimilarRepoService(GitHubService())
    current = candidate("source", "files", "File management", topics=["file-manager"])
    current["html_url"] = "https://github.com/source/files.git"
    similar = candidate(
        "nextcloud",
        "files",
        "Cloud storage and file sharing platform",
        200,
        "PHP",
        ["file-manager", "file-sharing"],
        ["src/auth/login.php", "src/routes/files.php", "src/storage/share.php", "Dockerfile"],
    )
    duplicate = dict(similar)
    duplicate["id"] += 1

    ranked = run_rank(service, [current, similar, duplicate])

    assert [repo["fullName"] for repo in ranked] == ["nextcloud/files"]
    assert ranked[0]["reason"]
    assert "file" in ranked[0]["reason"].lower()


def test_domain_and_module_similarity_outweigh_same_language():
    service = SimilarRepoService(GitHubService())
    file_platform = candidate(
        "example",
        "cloud-drive",
        "File sharing and cloud storage platform",
        language="Python",
        topics=["cloud-storage"],
        tree=[
            "src/auth/login.py",
            "src/upload/files.py",
            "src/storage/objects.py",
            "src/share/links.py",
        ],
    )
    portfolio = candidate(
        "example",
        "portfolio",
        "Personal developer portfolio website",
        language="Python",
        topics=["portfolio"],
        tree=["src/auth/login.py"],
    )

    ranked = run_rank(service, [portfolio, file_platform])

    assert ranked[0]["fullName"] == "example/cloud-drive"
    assert len(ranked) == 1
    portfolio_profile = service._build_candidate_profile(portfolio)
    file_profile = service._build_candidate_profile(file_platform)
    source = source_profile(service)
    assert service._similarity_signals(source, file_profile, file_platform)["domain"] > service._similarity_signals(
        source, portfolio_profile, portfolio
    )["domain"]


def test_module_overlap_strongly_affects_score():
    service = SimilarRepoService(GitHubService())
    profile = source_profile(service)
    matching = service._build_candidate_profile(candidate(
        "example",
        "sharebox",
        "File sharing",
        topics=["file-sharing"],
        tree=[
            "src/auth/login.ts",
            "src/upload/file.ts",
            "src/storage/file.ts",
            "src/share/link.ts",
        ],
    ))
    unrelated = service._build_candidate_profile(candidate(
        "example",
        "shop",
        "Online shopping store",
        topics=["ecommerce"],
        tree=["src/auth/login.ts", "src/cart/items.ts", "src/checkout/payments.ts"],
    ))

    assert service._concept_overlap(profile["modules"], matching["modules"]) > service._concept_overlap(
        profile["modules"], unrelated["modules"]
    )


def test_technology_only_overlap_is_not_a_valid_recommendation():
    service = SimilarRepoService(GitHubService())
    tech_only = candidate(
        "example",
        "react-portfolio",
        "React portfolio and personal website",
        stars=100_000,
        language="TypeScript",
        topics=["react"],
        tree=["src/components/hero.tsx", "src/pages/about.tsx"],
    )

    assert run_rank(service, [tech_only]) == []


def test_architecture_contributes_without_overriding_domain_or_modules():
    service = SimilarRepoService(GitHubService())
    profile = source_profile(service)
    same_architecture = {
        "domain_terms": [],
        "modules": [],
        "technology_terms": [],
        "architecture_terms": ["client server", "rest api", "database backed"],
        "structure_terms": [],
        "metadata_terms": [],
    }
    no_architecture = {**same_architecture, "architecture_terms": []}
    a = service._similarity_signals(profile, same_architecture, {})
    b = service._similarity_signals(profile, no_architecture, {})

    assert a["architecture"] > b["architecture"]
    assert sum(a[key] * weight for key, weight in service_weights().items()) > sum(
        b[key] * weight for key, weight in service_weights().items()
    )


def service_weights():
    from app.services.similar_repo_service import SIMILARITY_WEIGHTS

    return SIMILARITY_WEIGHTS


def test_popularity_is_minor_and_does_not_outweigh_functional_similarity():
    service = SimilarRepoService(GitHubService())
    related = candidate(
        "example",
        "file-sharing",
        "File management, upload, storage, and sharing",
        stars=10,
        topics=["file-manager", "file-sharing"],
        tree=["src/auth/login.py", "src/upload/file.py", "src/storage/files.py", "src/share/link.py"],
    )
    unrelated = candidate(
        "popular",
        "react-library",
        "Popular React component library",
        stars=2_000_000,
        language="Python",
        topics=["react"],
        tree=["src/components/button.py"],
    )

    ranked = run_rank(service, [unrelated, related])

    assert ranked[0]["fullName"] == "example/file-sharing"
    assert len(ranked) == 1
    assert service._quality_score(unrelated) > service._quality_score(related)


def test_semantically_related_file_management_and_cloud_storage_match():
    service = SimilarRepoService(GitHubService())
    source = service._concept_overlap(["file management"], ["cloud storage"])

    assert 0 < source < 100


def test_missing_github_metadata_is_defensive_and_fewer_than_five_are_returned(monkeypatch):
    service = SimilarRepoService(GitHubService())
    candidates = [
        candidate(
            "example",
            "file-browser",
            "A file browser and document management system",
            topics=["file-manager"],
            tree=["src/files/browser.py", "src/storage/files.py"],
        ),
        {
            "id": 5,
            "full_name": "example/minimal",
            "name": "minimal",
            "owner": {"login": "example"},
            "description": None,
            "topics": None,
            "stargazers_count": None,
            "language": None,
            "_tree_paths": [],
        },
    ]
    monkeypatch.setattr(service, "_search_github", lambda queries, per_query: candidates)

    results = service.find_similar_repositories(
        metadata={"full_name": "source/files", "description": "File management"},
        stack={"categories": {}},
        analysis_context={
            "overview": "A file management and sharing platform.",
            "modules": [{"name": "File Management"}],
        },
    )

    assert len(results) == 1
    assert results[0]["fullName"] == "example/file-browser"


def test_github_queries_are_focused_and_not_built_from_technology_list():
    service = SimilarRepoService(GitHubService())
    profile = source_profile(service)
    queries = service._build_search_queries(profile)

    assert 1 <= len(queries) <= 3
    assert any("file" in query.lower() or "sharing" in query.lower() for query in queries)
    assert not any("fastapi" in query.lower() or "postgresql" in query.lower() for query in queries)


def test_explanation_uses_functional_matching_signals():
    service = SimilarRepoService(GitHubService())
    result = run_rank(service, [
        candidate(
            "example",
            "file-manager",
            "File upload, storage and file sharing",
            topics=["file-manager"],
            tree=["src/auth/login.ts", "src/upload/files.ts", "src/storage/files.ts"],
        ),
    ])[0]

    assert "functionality" in result["reason"].lower()
    assert any(term in result["reason"].lower() for term in ("upload", "storage", "authentication"))
    assert "similarity_breakdown" in result
