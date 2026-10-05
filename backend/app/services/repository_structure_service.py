from pathlib import Path

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
    "venv",
    ".venv",
    "__pycache__",
    "vendor",
    "coverage",
    "tmp",
    "temp",
    ".idea",
    ".vscode",
}


class RepositoryStructureService:
    def build_tree(self, repo_path: Path) -> dict:
        return self._build_node(repo_path, repo_path.name or "root")

    def _build_node(self, path: Path, name: str) -> dict:
        if path.is_file():
            return {"name": path.name, "type": "file"}

        children = []
        for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in IGNORED_DIRS:
                continue
            children.append(self._build_node(child, child.name))

        return {"name": name, "type": "folder", "children": children}
