from pathlib import Path
import re
from typing import Dict, Any

from app.utils.file_parser import parse_package_json, parse_requirements_txt, read_text_preview


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


class RepoScanner:
    def scan(self, repo_path: Path) -> dict:
        files = self._collect_files(repo_path)
        dependencies = self._collect_dependencies_recursive(repo_path)
        readme = self._find_readme(repo_path)
        return {
            "files": files,
            "dependencies": dependencies,
            "source_previews": self._collect_source_previews(repo_path),
            "readme": read_text_preview(readme) if readme else "",
            "top_level_dirs": self._top_level_dirs(repo_path),
        }

    def _collect_files(self, repo_path: Path) -> list[str]:
        paths = []
        for path in repo_path.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if path.is_file():
                paths.append(path.relative_to(repo_path).as_posix())
        return sorted(paths)[:2000]

    def _collect_dependencies_recursive(self, repo_path: Path) -> Dict[str, Any]:
        dependencies = {}

        for path in repo_path.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
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
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file() or path.suffix.lower() not in interesting_suffixes:
                continue

            rel_path = path.relative_to(repo_path).as_posix()
            if not interesting_path.search(rel_path):
                continue
            previews[rel_path] = read_text_preview(path, max_chars=12000)

        return previews

    def _find_readme(self, repo_path: Path) -> Path | None:
        for name in ["README.md", "README.rst", "readme.md", "README.txt"]:
            candidate = repo_path / name
            if candidate.exists():
                return candidate
        return None

    def _top_level_dirs(self, repo_path: Path) -> list[str]:
        return [
            path.name
            for path in repo_path.iterdir()
            if path.is_dir() and path.name not in IGNORED_DIRS
        ]
