import json
from pathlib import Path


def parse_package_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        **data.get("dependencies", {}),
        **data.get("devDependencies", {}),
    }


def parse_requirements_txt(path: Path) -> list[str]:
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            packages.append(clean.split("==")[0].split(">=")[0].lower())
    return packages


def read_text_preview(path: Path, max_chars: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""
