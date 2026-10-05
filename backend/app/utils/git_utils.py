from urllib.parse import urlparse


def normalize_github_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    path = parsed.path.removesuffix(".git").strip("/")
    return f"https://github.com/{path}.git"


def repository_slug(repo_url: str) -> str:
    path = urlparse(repo_url).path.removesuffix(".git").strip("/")
    return path.replace("/", "__")
