
import base64
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.config import settings
from app.schemas.search import SearchRepositoryItem
from app.services.repository_discovery import (
    build_candidate_queries,
    rank_candidates,
    score_relevance,
)

logger = logging.getLogger(__name__)


IGNORED_README_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "site-packages",
    "bower_components",
    "target",
    "out",
}

README_PREFIX = "readme."


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

        if "github.com" in clean_query.lower():
            return SearchMode.URL_SEARCH, clean_query

        words = clean_query.split()
        if len(words) == 1 and len(clean_query) > 2:
            return SearchMode.NAME_SEARCH, clean_query

        return SearchMode.IDEA_SEARCH, clean_query

    def search_repositories(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchRepositoryItem]:
        """Route to the appropriate search flow based on the query."""
        search_mode, clean_query = self._detect_search_mode(query)

        if search_mode == SearchMode.URL_SEARCH:
            return self._search_url(clean_query, limit)

        return self._search_discovery(clean_query, limit)

    def _search_url(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchRepositoryItem]:
        """Search for a repository using its direct GitHub URL."""
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

        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("GitHub URL search failed for %s: %s", query, exc)
            return []

    def _search_discovery(
        self,
        query: str,
        limit: int,
    ) -> list[SearchRepositoryItem]:
        """Retrieve candidates and rank them using relevance and evidence."""
        if not query.strip() or limit <= 0:
            return []

        candidates: dict[int, dict] = {}
        pool_size = 30

        try:
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
                    items = (
                        payload.get("items", [])
                        if isinstance(payload, dict)
                        else []
                    )

                    for item in items:
                        if (
                            isinstance(item, dict)
                            and item.get("id") is not None
                            and item.get("name")
                            and item.get("full_name")
                        ):
                            candidates.setdefault(item["id"], item)

        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("GitHub repository discovery failed: %s", exc)

        if not candidates:
            return []

        ranked_by_relevance = sorted(
            candidates.values(),
            key=lambda item: score_relevance(query, item),
            reverse=True,
        )

        candidate_pool = ranked_by_relevance[:pool_size]

        analyzable_candidates = [
            item
            for item in candidate_pool
            if score_relevance(query, item) >= 12
        ][:10]

        self._add_candidate_evidence(analyzable_candidates)

        ranked = rank_candidates(query, candidate_pool)
        return [
            self._to_search_item(item)
            for item in ranked[:limit]
        ]

    def _add_candidate_evidence(self, candidates: list[dict]) -> None:
        """Inspect repository tree paths for promising candidates."""
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
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    logger.warning(
                        "Could not inspect candidate repository tree %s: %s",
                        candidate.get("full_name", candidate.get("name")),
                        exc,
                    )
                    paths = []

                candidate["_repo_paths"] = paths
                candidate["_readme_present"] = any(
                    Path(path).name.lower().startswith(README_PREFIX)
                    for path in paths
                )

    def _fetch_candidate_tree(self, candidate: dict) -> list[str]:
        owner = candidate.get("owner")
        owner_name = owner.get("login") if isinstance(owner, dict) else owner

        full_name = candidate.get("full_name") or (
            f"{owner_name}/{candidate.get('name', '')}"
        )
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
            if isinstance(item, dict)
            and isinstance(item.get("path"), str)
        ]

    def _to_search_item(self, item: dict) -> SearchRepositoryItem:
        """Convert a GitHub API response into a search result."""
        full_name = str(item.get("full_name") or "")
        owner = item.get("owner")

        owner_name = (
            owner.get("login")
            if isinstance(owner, dict)
            else str(owner or full_name.partition("/")[0])
        )

        name = str(
            item.get("name")
            or full_name.rpartition("/")[2]
            or "unknown"
        )

        full_name = full_name or f"{owner_name}/{name}".strip("/")
        url = str(
            item.get("html_url")
            or f"https://github.com/{full_name}"
        )

        topics = item.get("topics", [])
        if not isinstance(topics, list):
            topics = []

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
                str(topic)
                for topic in topics
                if isinstance(topic, str) and topic
            ],
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

        payload = response.json()
        return str(payload.get("default_branch") or "main")

    def fetch_readme(
        self,
        repo_url: str,
        default_branch: str | None = None,
    ) -> str | None:
        """Fetch the repository's default README through the GitHub API."""
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

        try:
            return base64.b64decode(content).decode(
                "utf-8",
                errors="replace",
            )
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Could not decode README for %s: %s",
                repo_url,
                exc,
            )
            return None

    def fetch_metadata(self, repo_url: str) -> dict:
        owner, name = self._owner_and_repo(repo_url)

        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected GitHub repository metadata response")

        return payload

    def clone_repository(
        self,
        repo_url: str,
        target_dir: Path | None = None,
    ) -> dict[str, str]:
        owner, repo_name = self._owner_and_repo(repo_url)
        clone_url = f"https://github.com/{owner}/{repo_name}.git"

        if target_dir is not None:
            repo_dir = Path(target_dir)
        else:
            repo_dir = Path("temp_repos") / repo_name

        repo_dir = repo_dir.resolve(strict=False)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)

        if repo_dir.exists():
            if not repo_dir.is_dir():
                raise RuntimeError(f"Clone target exists and is not a directory: {repo_dir}")

            git_dir = repo_dir / ".git"
            if git_dir.exists():
                # Never reuse a prior checkout: each analysis observes a fresh remote HEAD.
                suffix = 1
                while True:
                    candidate = repo_dir.parent / f"{repo_dir.name}_{suffix}"
                    if not candidate.exists():
                        repo_dir = candidate.resolve(strict=False)
                        break
                    suffix += 1

            logger.warning(
                "Clone target already exists but is not a valid repository; preserving user data and creating a distinct clone directory."
            )
            suffix = 1
            while True:
                candidate = repo_dir.parent / f"{repo_dir.name}_{suffix}"
                if not candidate.exists():
                    repo_dir = candidate.resolve(strict=False)
                    break
                suffix += 1

        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    clone_url,
                    str(repo_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Failed to clone repository %s: %s",
                repo_url,
                exc.stderr,
            )
            raise RuntimeError("Failed to clone repository") from exc

        revision = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        return {
            "repo_name": repo_name,
            "local_path": repo_dir.as_posix(),
            "commit_sha": revision,
        }

    def find_readme_path(
        self,
        repository_path: Path,
    ) -> tuple[Path | None, str]:
        """
        Select the most relevant README.

        Priority:
        1. README in the repository root.
        2. README outside documentation directories.
        3. Shallower paths.
        4. Stable alphabetical order for ties.

        Generated, vendor, and cache directories are excluded.
        """
        if not repository_path.exists() or not repository_path.is_dir():
            return None, "not_found"

        readme_candidates: list[tuple[int, int, int, str, Path]] = []

        try:
            for candidate in repository_path.rglob("*"):
                try:
                    relative_path = candidate.relative_to(repository_path)
                except ValueError:
                    continue

                relative_parts = relative_path.parts

                if any(
                    part.lower() in IGNORED_README_DIRS
                    for part in relative_parts[:-1]
                ):
                    continue

                if candidate.is_symlink() or not candidate.is_file():
                    continue

                if not candidate.name.lower().startswith(README_PREFIX):
                    continue

                parts_lower = {part.lower() for part in relative_parts[:-1]}
                is_root_readme = len(relative_parts) == 1
                is_documentation_readme = bool(
                    parts_lower.intersection({"docs", "documentation"})
                )

                root_rank = 0 if is_root_readme else 1
                docs_rank = 1 if is_documentation_readme else 0

                readme_candidates.append(
                    (
                        root_rank,
                        docs_rank,
                        len(relative_parts),
                        relative_path.as_posix().lower(),
                        candidate,
                    )
                )

        except OSError as exc:
            logger.warning(
                "Error while searching for README files in %s: %s",
                repository_path,
                exc,
            )

        if not readme_candidates:
            return None, "not_found"

        selected = min(readme_candidates, key=lambda item: item[:4])[4]

        return selected, selected.relative_to(repository_path).as_posix()

    def find_readme(self, repository_path: Path) -> str | None:
        """Read the selected README, returning None when it cannot be read."""
        readme_path, _ = self.find_readme_path(repository_path)

        if readme_path is None:
            return None

        try:
            # Decode bytes directly so universal newline conversion cannot alter
            # the README that is persisted and returned by the API.
            return readme_path.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            logger.warning(
                "Could not read README at %s: %s",
                readme_path,
                exc,
            )
            return None

    def _owner_and_repo(self, repo_url: str) -> tuple[str, str]:
        """Validate a GitHub URL and extract its owner and repository name."""
        parsed = urlparse(repo_url.strip())
        netloc_lower = parsed.netloc.lower()

        is_github = netloc_lower in {"github.com", "www.github.com"}

        if parsed.scheme not in {"http", "https"} or not is_github:
            raise ValueError("Invalid GitHub repository URL")

        parts = parsed.path.removesuffix(".git").strip("/").split("/")

        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid GitHub repository URL")

        owner, repo = parts[:2]

        if owner in {".", ".."} or repo in {".", ".."}:
            raise ValueError("Invalid GitHub repository URL")

        return owner, repo


def get_github_service() -> GitHubService:
    return GitHubService()
