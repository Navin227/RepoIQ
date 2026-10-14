import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class RepomixContextService:
    """Collect optional repository context from Repomix without mutating the repo."""

    IGNORE_PATTERNS = [
        ".git",
        "node_modules",
        "dist",
        "build",
        "coverage",
        ".next",
        ".nuxt",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "tmp",
        "temp",
    ]

    def collect_context(self, repo_path: str | Path | None) -> dict[str, Any]:
        if repo_path is None:
            return {}

        repo = Path(repo_path)
        if not repo.exists() or not repo.is_dir():
            return {}

        commands = []
        repomix_bin = shutil.which("repomix")
        if repomix_bin:
            commands.append([
                repomix_bin,
                "--path",
                str(repo),
                "--output",
                "repomix-context.md",
                "--ignore",
                ",".join(self.IGNORE_PATTERNS),
            ])

        npx_bin = shutil.which("npx")
        if npx_bin:
            commands.append([
                npx_bin,
                "--yes",
                "@repomix/repomix",
                "--path",
                str(repo),
                "--output",
                "repomix-context.md",
                "--ignore",
                ",".join(self.IGNORE_PATTERNS),
            ])

        if not commands:
            return {}

        with tempfile.TemporaryDirectory(prefix="repomix-safe-") as tmp_dir:
            temp_dir = Path(tmp_dir)
            for command in commands:
                temp_output = temp_dir / "repomix-context.md"
                command = command[:-2] + [str(temp_output)]
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                except (FileNotFoundError, OSError, subprocess.SubprocessError):
                    continue

                if temp_output.exists():
                    try:
                        content = temp_output.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    if content.strip():
                        return {
                            "source": "repomix",
                            "path": str(temp_output),
                            "content": content[:20_000],
                            "result_code": result.returncode,
                            "stdout": result.stdout[:2_000],
                            "stderr": result.stderr[:2_000],
                        }

                if result.returncode == 0 and result.stdout.strip():
                    return {
                        "source": "repomix",
                        "content": result.stdout[:20_000],
                        "result_code": result.returncode,
                    }

        return {}
