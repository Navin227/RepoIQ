import re
from urllib.parse import urlparse


def _parse_github_repo_path(repo_url: str) -> tuple[str, str]:
    if not isinstance(repo_url, str):
        raise ValueError("Repository URL must be a string")

    candidate = repo_url.strip()
    if not candidate:
        raise ValueError("Repository URL is empty")

    parsed = urlparse(candidate)
    host = (parsed.netloc or parsed.path).lower()
    if parsed.scheme in {"git+ssh", "ssh"}:
        if candidate.startswith("git@github.com:"):
            path = candidate.split(":", 1)[1]
        else:
            raise ValueError("Invalid GitHub repository URL")
    else:
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Invalid GitHub repository URL")
        if host not in {"github.com", "www.github.com"}:
            raise ValueError("Invalid GitHub repository URL")
        path = parsed.path

    normalized_path = path.removesuffix(".git").strip("/")
    if not normalized_path:
        raise ValueError("Invalid GitHub repository URL")

    parts = [part for part in normalized_path.split("/") if part and part not in {".", ".."}]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")

    owner, repo = parts[:2]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository URL")

    return owner, repo


def normalize_github_url(repo_url: str) -> str:
    owner, repo = _parse_github_repo_path(repo_url)
    return f"https://github.com/{owner}/{repo}.git"


def repository_slug(repo_url: str) -> str:
    owner, repo = _parse_github_repo_path(repo_url)
    return f"{owner}__{repo}"
