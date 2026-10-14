from pathlib import Path
import logging
import re
from typing import Dict, Any

from app.services.source_evidence_extractor import SourceEvidenceExtractor
from app.utils.file_parser import parse_package_json, parse_requirements_txt, read_text_preview

logger = logging.getLogger(__name__)


IGNORED_DIRS = {
    ".git",
    ".yarn",
    ".claude",
    ".cache",
    ".parcel-cache",
    ".turbo",
    ".next",
    ".nuxt",
    "node_modules",
    "dist",
    "build",
    "out",
    "coverage",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    "target",
    "vendor",
    ".idea",
    ".vscode",
    ".gradle",
    ".mvn",
    ".pnpm-store",
    "tmp",
    "temp",
}
MAX_REPO_INVENTORY_FILES = 2000
ENTRYPOINT_FILENAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "main.ts",
    "main.tsx",
    "main.js",
    "main.jsx",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "server.ts",
    "server.js",
    "app.ts",
    "app.tsx",
    "app.js",
    "app.jsx",
}
HIGH_VALUE_DIRS = {
    "api",
    "routes",
    "routers",
    "controllers",
    "services",
    "models",
    "repositories",
    "migrations",
    "middleware",
    "auth",
    "jobs",
    "workers",
    "schema",
    "schemas",
    "config",
    "configs",
    "infrastructure",
    "deploy",
    "terraform",
    "k8s",
    "helm",
    "docker",
    "tests",
    "test",
    "__tests__",
    "spec",
    "docs",
    "documentation",
}
HIGH_VALUE_MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "terraform.tfvars",
}


class RepoScanner:
    @staticmethod
    def _is_ignored_path(path: Path, repo_path: Path) -> bool:
        try:
            relative_parts = path.relative_to(repo_path).parts
        except ValueError:
            relative_parts = path.parts

        return any(part in IGNORED_DIRS for part in relative_parts)

    def scan(self, repo_path: Path) -> dict:
        files = self._collect_files(repo_path)
        dependencies = self._collect_dependencies_recursive(repo_path)
        readme = self._find_readme(repo_path)
        readme_text = read_text_preview(readme) if readme else ""
        source_previews = self._collect_source_previews(repo_path)
        evidence_extractor = SourceEvidenceExtractor()
        source_evidence = evidence_extractor.extract(repo_path, files, readme=readme_text)
        # Keep full file objects for LLM payload; bucket lists remain path-only for compatibility.
        file_details = source_evidence.pop("selected_source_file_details", [])
        source_evidence["selected_source_files"] = [
            item["path"] for item in file_details if isinstance(item, dict) and item.get("path")
        ]
        return {
            "files": files,
            "dependencies": dependencies,
            "source_previews": source_previews,
            "readme": readme_text,
            "top_level_dirs": self._top_level_dirs(repo_path),
            "source_evidence": source_evidence,
            "_selected_source_file_objects": file_details,
        }

    @staticmethod
    def _path_relevance_score(relative_path: str) -> int:
        normalized = relative_path.replace('\\', '/')
        name = Path(normalized).name.lower()
        parts = [part.lower() for part in Path(normalized).parts]
        score = 0

        if name in ENTRYPOINT_FILENAMES:
            score += 180
        if any(part in HIGH_VALUE_DIRS for part in parts[:-1]):
            score += 80
        if any(part in {"routes", "router", "controllers", "services", "models", "repositories"} for part in parts):
            score += 30
        if name in HIGH_VALUE_MANIFESTS or name.endswith("dockerfile"):
            score += 60
        if any(part in {"test", "tests", "spec", "__tests__"} for part in parts):
            score += 20
        if normalized.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs", ".rb", ".php", ".cs")):
            score += 15
        if "auth" in normalized or "middleware" in normalized or "schema" in normalized:
            score += 20
        if any(part in IGNORED_DIRS for part in parts[:-1]):
            score -= 500
        if any(part in {"node_modules", "vendor", "dist", "build", "coverage", ".next", ".nuxt", "site-packages"} for part in parts):
            score -= 200
        return score

    def _collect_files(self, repo_path: Path) -> list[str]:
        ranked_paths: list[tuple[int, str]] = []
        for path in repo_path.rglob("*"):
            if self._is_ignored_path(path, repo_path):
                continue
            if path.is_file():
                relative_path = path.relative_to(repo_path).as_posix()
                ranked_paths.append((self._path_relevance_score(relative_path), relative_path))

        ranked_paths.sort(key=lambda item: (-item[0], item[1].lower()))
        return [relative_path for _, relative_path in ranked_paths[:MAX_REPO_INVENTORY_FILES]]

    def _collect_dependencies_recursive(self, repo_path: Path) -> Dict[str, Any]:
        dependencies = {}

        for path in repo_path.rglob("*"):
            if self._is_ignored_path(path, repo_path):
                continue
            if not path.is_file():
                continue

            rel_path = path.relative_to(repo_path).as_posix()

            # JavaScript/TypeScript
            if path.name == "package.json":
                dependencies[rel_path] = {
                    "type": "package.json",
                    "content": parse_package_json(path),
                }
            elif path.name in ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"]:
                dependencies[rel_path] = {
                    "type": "lockfile",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Python
            elif path.name == "requirements.txt":
                dependencies[rel_path] = {
                    "type": "requirements.txt",
                    "content": parse_requirements_txt(path),
                }
            elif path.name == "pyproject.toml":
                dependencies[rel_path] = {
                    "type": "pyproject.toml",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.name == "poetry.lock":
                dependencies[rel_path] = {
                    "type": "poetry.lock",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Go
            elif path.name == "go.mod" or path.name == "go.sum":
                dependencies[rel_path] = {
                    "type": "go.mod",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Java
            elif path.name in ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"]:
                dependencies[rel_path] = {
                    "type": "java-build",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Rust
            elif path.name in ["Cargo.toml", "Cargo.lock"]:
                dependencies[rel_path] = {
                    "type": "Cargo.toml",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # PHP
            elif path.name == "composer.json":
                dependencies[rel_path] = {
                    "type": "composer.json",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Ruby
            elif path.name in ["Gemfile", "Gemfile.lock"]:
                dependencies[rel_path] = {
                    "type": "Gemfile",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Elixir
            elif path.name in ["mix.exs", "mix.lock"]:
                dependencies[rel_path] = {
                    "type": "mix.exs",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Scala
            elif path.name in ["build.sbt", "sbt.build"]:
                dependencies[rel_path] = {
                    "type": "build.sbt",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Dart/Flutter
            elif path.name == "pubspec.yaml":
                dependencies[rel_path] = {
                    "type": "pubspec.yaml",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Infrastructure
            elif path.name == "Dockerfile" or path.name.lower().endswith("dockerfile"):
                dependencies[rel_path] = {
                    "type": "dockerfile",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
                dependencies[rel_path] = {
                    "type": "docker-compose",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.suffix == ".tf" or path.name.endswith(".tfvars"):
                dependencies[rel_path] = {
                    "type": "terraform",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.suffix in (".yml", ".yaml"):
                dependencies[rel_path] = {
                    "type": "yaml",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # CI/CD
            elif (
                path.parent.name == "workflows" and
                path.parent.parent.name == ".github"
            ):
                dependencies[rel_path] = {
                    "type": "github-actions",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.name == ".gitlab-ci.yml":
                dependencies[rel_path] = {
                    "type": "gitlab-ci",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif path.name == "Jenkinsfile":
                dependencies[rel_path] = {
                    "type": "jenkins",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif ".circleci" in path.parts and path.name == "config.yml":
                dependencies[rel_path] = {
                    "type": "circleci",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Kubernetes
            elif "k8s" in path.parts or "kubernetes" in path.parts:
                dependencies[rel_path] = {
                    "type": "kubernetes",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Helm
            elif "helm" in path.parts or path.name == "Chart.yaml" or path.name == "values.yaml":
                dependencies[rel_path] = {
                    "type": "helm",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Kustomize
            elif path.name == "kustomization.yaml" or path.name == "kustomization.yml":
                dependencies[rel_path] = {
                    "type": "kustomize",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Ansible
            elif path.name in ["ansible.cfg", "playbook.yml", "playbook.yaml"]:
                dependencies[rel_path] = {
                    "type": "ansible",
                    "content": read_text_preview(path, max_chars=20000),
                }
            elif "roles" in path.parts and path.suffix in [".yml", ".yaml"]:
                dependencies[rel_path] = {
                    "type": "ansible",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Configs
            elif path.name.startswith(".env"):
                dependencies[rel_path] = {
                    "type": "env",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Readme
            elif path.name.lower().startswith("readme."):
                dependencies[rel_path] = {
                    "type": "readme",
                    "content": read_text_preview(path, max_chars=20000),
                }
            # Prometheus/Grafana
            elif "prometheus" in path.name.lower() or "grafana" in path.name.lower():
                dependencies[rel_path] = {
                    "type": "monitoring",
                    "content": read_text_preview(path, max_chars=20000),
                }

        return dependencies

    def _collect_source_previews(self, repo_path: Path) -> Dict[str, str]:
        previews: Dict[str, str] = {}
        interesting_path = re.compile(
            r"(api|route|router|controller|service|worker|queue|auth|middleware|handler|"
            r"storage|database|repository|model|schema|infra|terraform|docker|k8s|helm)",
            re.IGNORECASE,
        )
        interesting_suffixes = {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
            ".php", ".rb", ".cs", ".yml", ".yaml", ".tf", ".json", ".toml",
        }

        for path in repo_path.rglob("*"):
            if len(previews) >= 160:
                break
            if self._is_ignored_path(path, repo_path):
                continue
            if not path.is_file() or path.suffix.lower() not in interesting_suffixes:
                continue

            rel_path = path.relative_to(repo_path).as_posix()
            if not interesting_path.search(rel_path):
                continue
            previews[rel_path] = read_text_preview(path, max_chars=12000)

        return previews

    def _find_readme(self, repo_path: Path) -> Path | None:
        readme_candidates: list[tuple[int, int, int, Path]] = []
        for candidate in repo_path.rglob("*"):
            if not candidate.is_file() or not candidate.name.lower().startswith("readme."):
                continue
            relative_parts = candidate.relative_to(repo_path).parts
            if any(part.lower() in IGNORED_DIRS for part in relative_parts[:-1]):
                continue
            # Prefer the repository root README, then a README outside documentation
            # folders, then documentation-only README files as a fallback.
            root_rank = 0 if len(relative_parts) == 1 else 1
            docs_rank = 1 if any(
                part.lower() in {"docs", "documentation"} for part in relative_parts[:-1]
            ) else 0
            readme_candidates.append((root_rank, docs_rank, len(relative_parts), candidate))
        if not readme_candidates:
            return None
        return sorted(
            readme_candidates,
            key=lambda item: (item[0], item[1], item[2], item[3].as_posix().lower()),
        )[0][3]

    def _top_level_dirs(self, repo_path: Path) -> list[str]:
        return [
            path.name
            for path in repo_path.iterdir()
            if path.is_dir() and path.name not in IGNORED_DIRS
        ]
