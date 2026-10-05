import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.llm_service import LLMService
from app.services.stack_detector import StackDetector
from app.utils.repo_scanner import RepoScanner


def test_llm_service_accepts_metadata_scan_and_stack():
    service = LLMService(provider="mock")

    response = service.generate_overview(
        repo_name="acme/example",
        description="Example repository",
        readme="README",
        technologies={"languages": ["Python"], "categories": {}},
        repo_structure=[],
        repo_stats={},
    )

    assert isinstance(response, str)
    assert response


def test_frontend_detection_is_categorized_and_aggregated():
    detector = StackDetector()
    scan = {
        "files": [
            "frontend/package.json",
            "frontend/src/main.tsx",
            "apps/web/package.json",
        ],
        "dependencies": {
            "frontend/package.json": {
                "type": "package.json",
                "content": {
                    "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
                    "devDependencies": {"vite": "^5.0.0", "tailwindcss": "^3.4.0"},
                },
            },
            "apps/web/package.json": {
                "type": "package.json",
                "content": {
                    "dependencies": {"next": "^14.0.0", "react": "^18.2.0"},
                    "devDependencies": {"typescript": "^5.0.0"},
                },
            },
        },
    }

    stack = detector.detect(scan)
    categories = stack["categories"]

    frontend_names = {item["name"] for item in categories["frontend"]}
    tooling_names = {item["name"] for item in categories["tooling"]}

    assert "React" in frontend_names
    assert "Next.js" in frontend_names
    assert "Vite" in tooling_names
    assert "TailwindCSS" in tooling_names

    react_item = next(item for item in categories["frontend"] if item["name"] == "React")
    assert react_item["count"] >= 2
    assert len(react_item["sources"]) >= 2


def test_terraform_aggregation_and_cloud_false_positives():
    detector = StackDetector()
    scan = {
        "files": ["main.tf", "variables.tf"],
        "dependencies": {
            "main.tf": {
                "type": "terraform",
                "content": 'resource "aws_s3_bucket" "uploads" {}\n# google users sign in here',
            },
            "variables.tf": {
                "type": "terraform",
                "content": 'variable "azure_region" {}\nvariable "google_project" {}',
            },
        },
    }

    stack = detector.detect(scan)
    categories = stack["categories"]
    infra_names = {item["name"] for item in categories["infrastructure"]}
    cloud_names = {item["name"] for item in categories["cloud"]}

    assert "Terraform" in infra_names
    assert "AWS" in cloud_names
    assert "S3" in cloud_names
    assert "GCP" not in cloud_names
    assert "Azure" not in cloud_names

    terraform_item = next(item for item in categories["infrastructure"] if item["name"] == "Terraform")
    assert terraform_item["count"] == 2
    assert sorted(terraform_item["sources"]) == ["main.tf", "variables.tf"]


def test_gofile_expected_stack_is_detected():
    repo_path = Path(__file__).resolve().parents[1] / "temp_repos" / "GoFileCloud" / "GoFile"
    scan = RepoScanner().scan(repo_path)
    stack = StackDetector().detect(scan)

    categories = stack["categories"]
    names_by_category = {
        category: {item["name"] for item in items}
        for category, items in categories.items()
    }

    assert {"React"}.issubset(names_by_category["frontend"])
    assert {"Vite", "TailwindCSS"}.issubset(names_by_category["tooling"])
    assert {"Terraform"}.issubset(names_by_category["infrastructure"])
    assert {"Docker"}.issubset(names_by_category["devops"])
    assert {
        "AWS",
        "S3",
        "Lambda",
        "API Gateway",
        "Cognito",
        "CloudWatch",
    }.issubset(names_by_category["cloud"])
    assert {"DynamoDB"}.issubset(names_by_category["database"])
    assert {"SQS"}.issubset(names_by_category["messaging"])


def test_repo_scanner_ignores_generated_tooling_directories(tmp_path):
    repo = tmp_path / "demo"
    (repo / ".yarn" / "cache").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / "frontend" / "src").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / ".yarn" / "cache" / "artifact.txt").write_text("ignore me")
    (repo / ".claude" / "settings.json").write_text("{}")
    (repo / "frontend" / "src" / "main.tsx").write_text("export const x = 1;")
    (repo / "docs" / "intro.md").write_text("# Demo")

    scan = RepoScanner().scan(repo)

    assert ".yarn" not in scan["top_level_dirs"]
    assert ".claude" not in scan["top_level_dirs"]
    assert not any(path.startswith(".yarn/") for path in scan["files"])
    assert not any(path.startswith(".claude/") for path in scan["files"])
    assert "frontend/src/main.tsx" in scan["files"]
    assert "docs/intro.md" in scan["files"]
