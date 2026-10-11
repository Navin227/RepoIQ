import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from enum import Enum

import httpx

from app.config import settings
from app.schemas.search import SearchRepositoryItem
from app.services.repository_discovery import (
    build_candidate_queries,
    rank_candidates,
    score_relevance,
)

logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    URL_SEARCH = "url"
    NAME_SEARCH = "name"
    IDEA_SEARCH = "idea"


class GitHubService:
    def __init__(self, token: str | None = settings.github_token) -> None:
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _detect_search_mode(self, query: str) -> tuple[SearchMode, str]:
        """Detect search mode and return (mode, cleaned_query)."""
        clean_query = query.strip()
        
        # MODE 1: GitHub URL Search
        if "github.com" in clean_query.lower():
            return SearchMode.URL_SEARCH, clean_query
        
        # MODE 2: Repository Name Search (single-word queries)
        words = clean_query.split()
        if len(words) == 1 and len(clean_query) > 2:
            return SearchMode.NAME_SEARCH, clean_query
        
        # MODE 3: Idea Search (multi-word natural language)
        return SearchMode.IDEA_SEARCH, clean_query

    def search_repositories(self, query: str, limit: int = 10) -> list[SearchRepositoryItem]:
        """Route to appropriate search mode based on query type."""
        search_mode, clean_query = self._detect_search_mode(query)
        
        if search_mode == SearchMode.URL_SEARCH:
            return self._search_url(clean_query, limit)
        return self._search_discovery(clean_query, limit)

    def _search_url(self, query: str, limit: int = 10) -> list[SearchRepositoryItem]:
        """Search by direct GitHub URL."""
        try:
            owner, repo_name = self._owner_and_repo(query)
            response = httpx.get(
                f"https://api.github.com/repos/{owner}/{repo_name}",
                headers=self._headers(),
                timeout=20,
            )
            response.raise_for_status()
            item = response.json()
            return [self._to_search_item(item)]
        except Exception:
            return []

    def _search_discovery(self, query: str, limit: int) -> list[SearchRepositoryItem]:
        """Retrieve a broad candidate set, then rank it using relevance and evidence."""
        candidates: dict[int, dict] = {}
        pool_size = 30

        with httpx.Client(headers=self._headers(), timeout=12) as client:
            for search_query in build_candidate_queries(query):
                response = client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": search_query,
                        "per_page": pool_size,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                items = payload.get("items", []) if isinstance(payload, dict) else []
                for item in items:
                    if (
                        isinstance(item, dict)
                        and item.get("id") is not None
                        and item.get("name")
                        and item.get("full_name")
                    ):
                        candidates.setdefault(item["id"], item)

        ranked_by_relevance = sorted(
            candidates.values(),
            key=lambda item: score_relevance(query, item),
            reverse=True,
        )
        candidate_pool = ranked_by_relevance[:pool_size]
        analyzable_candidates = [
            item for item in candidate_pool
            if score_relevance(query, item) >= 12
        ][:10]
        self._add_candidate_evidence(analyzable_candidates)

        ranked = rank_candidates(query, candidate_pool)
        return [self._to_search_item(item) for item in ranked[:limit]]

    def _add_candidate_evidence(self, candidates: list[dict]) -> None:
        """Inspect tree paths only for the strongest candidates; never clone them."""
        if not candidates:
            return

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._fetch_candidate_tree, candidate): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    paths = future.result()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning(
                        "Could not inspect candidate repository tree %s: %s",
                        candidate.get("full_name", candidate.get("name")),
                        exc,
                    )
                    paths = []
                candidate["_repo_paths"] = paths
                candidate["_readme_present"] = any(
                    path.rsplit("/", 1)[-1].lower().startswith("readme.")
                    for path in paths
                )

    def _fetch_candidate_tree(self, candidate: dict) -> list[str]:
        owner = candidate.get("owner")
        owner_name = owner.get("login") if isinstance(owner, dict) else owner
        full_name = candidate.get("full_name") or f"{owner_name}/{candidate.get('name', '')}"
        branch = str(candidate.get("default_branch") or "").strip()
        if not full_name or "/" not in str(full_name) or not branch:
            return []

        url = (
            f"https://api.github.com/repos/{full_name}/git/trees/"
            f"{quote(branch, safe='')}?recursive=1"
        )
        with httpx.Client(headers=self._headers(), timeout=6) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

        tree = payload.get("tree", []) if isinstance(payload, dict) else []
        return [
            str(item["path"])
            for item in tree[:5000]
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ]

    def _to_search_item(self, item: dict) -> SearchRepositoryItem:
        """Convert GitHub API response to SearchRepositoryItem."""
        full_name = str(item.get("full_name") or "")
        owner = item.get("owner")
        owner_name = (
            owner.get("login")
            if isinstance(owner, dict)
            else str(owner or full_name.partition("/")[0])
        )
        name = str(item.get("name") or full_name.rpartition("/")[2] or "unknown")
        full_name = full_name or f"{owner_name}/{name}".strip("/")
        url = str(item.get("html_url") or f"https://github.com/{full_name}")
        return SearchRepositoryItem(
            id=self._safe_count(item.get("id")),
            name=name,
            owner=str(owner_name or ""),
            full_name=full_name,
            description=item.get("description"),
            stars=self._safe_count(item.get("stargazers_count")),
            forks=self._safe_count(item.get("forks_count")),
            language=item.get("language"),
            html_url=url,
            topics=[
                str(topic) for topic in item.get("topics", [])
                if isinstance(topic, str) and topic
            ] if isinstance(item.get("topics"), list) else [],
            relevance_score=item.get("relevance_score", 0),
            analyzability_score=item.get("analyzability_score", 0),
            ranking_score=item.get("ranking_score", 0),
        )

    @staticmethod
    def _safe_count(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def fetch_default_branch(self, repo_url: str) -> str:
        owner, name = self._owner_and_repo(repo_url)
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return str(response.json().get("default_branch") or "main")

    def fetch_readme(self, repo_url: str, default_branch: str | None = None) -> str | None:
        owner, name = self._owner_and_repo(repo_url)
        branch = default_branch or self.fetch_default_branch(repo_url)
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}/readme",
            headers=self._headers(),
            params={"ref": branch},
            timeout=20,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(content, str):
            return None
        import base64
        return base64.b64decode(content).decode("utf-8", errors="replace")

    def fetch_metadata(self, repo_url: str) -> dict:
        owner, name = self._owner_and_repo(repo_url)
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def clone_repository(self, repo_url: str, target_dir: Path | None = None) -> dict[str, str]:
        owner, repo_name = self._owner_and_repo(repo_url)
        clone_url = f"https://github.com/{owner}/{repo_name}.git"
        repo_dir = target_dir or Path("temp_repos") / repo_name

        if repo_dir.exists():
            return {
                "repo_name": repo_name,
                "local_path": repo_dir.as_posix(),
            }

        repo_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Failed to clone repository") from exc

        return {
            "repo_name": repo_name,
            "local_path": repo_dir.as_posix(),
        }

    def find_readme_path(self, repository_path: Path) -> tuple[Path | None, str]:
        readme_candidates: list[tuple[int, int, Path]] = []
        for candidate in repository_path.rglob("*"):
            if not candidate.is_file() or not candidate.name.lower().startswith("readme."):
                continue
            relative_parts = candidate.relative_to(repository_path).parts
            docs_rank = 0 if "docs" in relative_parts or "documentation" in relative_parts else 1
            readme_candidates.append((docs_rank, len(relative_parts), candidate))

        if not readme_candidates:
            return None, "not_found"

        _, _, selected = sorted(readme_candidates, key=lambda item: (item[0], item[1]))[0]
        return selected, str(selected.relative_to(repository_path))

    def find_readme(self, repository_path: Path) -> str | None:
        readme_path, _ = self.find_readme_path(repository_path)
        if readme_path is None:
            return None
        try:
            return readme_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return readme_path.read_text(encoding="utf-8", errors="ignore")

    def _owner_and_repo(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse(repo_url)
        netloc_lower = parsed.netloc.lower()
        is_github = netloc_lower in {"github.com", "www.github.com"}
        
        if parsed.scheme not in {"http", "https"} or not is_github:
            raise ValueError("Invalid GitHub repository URL")

        parts = parsed.path.removesuffix(".git").strip("/").split("/")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid GitHub repository URL")

        owner, repo = parts[:2]
        return owner, repo


def get_github_service() -> GitHubService:
    return GitHubService()
