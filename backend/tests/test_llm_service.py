import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import LLMService
from app.services.similar_repo_service import SimilarRepoService


def test_llm_service_parses_structured_gemini_json(monkeypatch):
    def fake_gemini(self, payload):
        return """
        {
          "overview": "A file processing platform for authenticated users.",
          "executive_overview": {
            "what_is_this_project": [
              "This project helps people manage files in one place.",
              "Users can upload, organize, and access file-related workflows."
            ],
            "why_was_it_built": "It was built to make file handling easier for people who need a central place to manage their work.",
            "user_features": [
              {"name": "Upload Files", "description": "Add files to the platform."},
              {"name": "Manage Files", "description": "Keep files organized."},
              {"name": "Sign In", "description": "Access a personal account."},
              {"name": "Track Work", "description": "Follow file processing progress."},
              {"name": "Use Tools", "description": "Run available file actions."}
            ],
            "typical_use_cases": ["A user stores files for later access."],
            "who_is_this_for": ["Individuals", "Teams"],
            "why_is_it_valuable": "It saves time by keeping file tasks together.",
            "one_line_summary": "A simple place to manage and process files."
          },
          "modules": [
            {
              "name": "Authentication",
              "purpose": "Handles user identity and protected access.",
              "capabilities": ["Sign in users", "Protect private workflows", "Track current user"],
              "components": ["auth/context.tsx", "pages/Auth.tsx"],
              "connected_modules": ["File Upload"],
              "confidence": 92
            },
            {"name": "File Upload", "purpose": "Lets users add files.", "capabilities": ["Upload files"], "components": ["UploadModal.tsx"], "connected_modules": ["Storage"], "confidence": 90},
            {"name": "Storage", "purpose": "Stores uploaded files.", "capabilities": ["Save files"], "components": ["s3/main.tf"], "connected_modules": ["File Upload"], "confidence": 90},
            {"name": "Worker", "purpose": "Processes queued jobs.", "capabilities": ["Run background tasks"], "components": ["worker.py"], "connected_modules": ["Storage"], "confidence": 85},
            {"name": "Infrastructure", "purpose": "Defines cloud resources.", "capabilities": ["Provision resources"], "components": ["main.tf"], "connected_modules": ["Storage"], "confidence": 80}
          ],
          "architecture": {
            "summary": "Users interact with a frontend that calls APIs and cloud services.",
            "flow": ["User", "Frontend", "API Layer", "Worker", "Storage"]
          }
        }
        """

    monkeypatch.setattr(LLMService, "_generate_with_gemini", fake_gemini)

    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/files", "description": "File tools"},
        readme="README",
        stack={"categories": {}},
        repository_structure=[],
        scan={
            "top_level_dirs": ["frontend", "infrastructure"],
            "files": [
                "auth/context.tsx",
                "pages/Auth.tsx",
                "UploadModal.tsx",
                "s3/main.tf",
                "worker.py",
                "main.tf",
            ],
            "dependencies": {},
            "source_previews": {},
        },
    )

    assert analysis["overview"].startswith("A file processing")
    assert analysis["executive_overview"]["what_is_this_project"][0].startswith("This project")
    assert len(analysis["executive_overview"]["user_features"]) == 5
    assert analysis["modules"][0]["name"] == "Authentication"
    assert analysis["modules"][0]["purpose"] == "Handles user identity and protected access."
    assert analysis["modules"][0]["capabilities"] == ["Sign in users", "Protect private workflows", "Track current user"]
    assert analysis["modules"][0]["components"] == ["auth/context.tsx", "pages/Auth.tsx"]
    assert analysis["modules"][0]["connected_modules"] == ["File Upload"]
    assert analysis["modules"][0]["confidence"] == 92
    assert analysis["architecture"]["flow"] == ["User", "Frontend", "API Layer", "Worker", "Storage"]


def test_llm_service_falls_back_when_gemini_fails(monkeypatch):
    def failing_gemini(self, payload):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(LLMService, "_generate_with_gemini", failing_gemini)

    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/files", "description": "File tools"},
        readme="README",
        stack={
            "categories": {
                "frontend": [{"name": "React"}],
                "cloud": [{"name": "API Gateway"}, {"name": "Cognito"}],
                "database": [{"name": "DynamoDB"}],
                "messaging": [{"name": "SQS"}],
                "infrastructure": [{"name": "Terraform"}],
            }
        },
        repository_structure=[],
        scan={
            "top_level_dirs": ["frontend", "infrastructure", "worker"],
            "files": [],
            "dependencies": {},
            "source_previews": {},
        },
    )

    assert analysis["overview"]
    assert analysis["modules"] == []
    assert analysis["executive_overview"]["user_features"] == []
    assert {"summary", "flow"} <= set(analysis["architecture"])


def test_gemini_modules_without_repository_evidence_are_not_returned(monkeypatch):
    def fake_gemini(self, payload):
        return """
        {
          "overview": "An unsupported description.",
          "executive_overview": {},
          "modules": [{
            "name": "Payments",
            "purpose": "Processes payments.",
            "components": ["src/fake/payment-service.ts"],
            "confidence": 99
          }],
          "architecture": {"summary": "Unable to determine.", "flow": []}
        }
        """

    monkeypatch.setattr(LLMService, "_generate_with_gemini", fake_gemini)
    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/example"},
        readme="",
        stack={"categories": {}},
        repository_structure=[],
        scan={"files": [], "dependencies": {}, "source_previews": {}},
    )

    assert analysis["modules"] == []
    assert analysis["executive_overview"]["user_features"] == []
    assert analysis["analysis_evidence"]["source_file_count"] == 0


def test_fallback_architecture_uses_supported_architecture_type():
    service = LLMService()
    payload = {
        "metadata": {"full_name": "acme/files", "description": "File tools"},
        "readme_summary": "",
        "detected_technology_stack": {
            "categories": {
                "frontend": [{"name": "React"}],
                "backend": [{"name": "FastAPI"}],
                "database": [{"name": "PostgreSQL"}],
                "infrastructure": [{"name": "Terraform"}],
                "cloud": [{"name": "AWS"}],
            }
        },
        "repository_structure": [],
        "top_level_modules": ["frontend", "backend", "infra"],
        "detected_cloud_infrastructure": {},
    }

    analysis = service._fallback_analysis(payload)

    assert analysis["architecture"]["architecture_type"] == "Layered"


def test_analyze_endpoint_uses_ai_generation_for_gofile(monkeypatch):
    def fake_analysis(self, metadata, readme, stack, repository_structure, scan):
        return {
            "overview": "GoFile executive overview from Gemini.",
            "modules": [
                {"name": "Frontend", "description": "React application."},
                {"name": "API Layer", "description": "API Gateway integration."},
                {"name": "Storage", "description": "S3 and DynamoDB storage."},
                {"name": "Worker", "description": "SQS driven processing."},
                {"name": "Infrastructure", "description": "Terraform definitions."},
            ],
            "architecture": {
                "summary": "Users move through frontend, API, workers, and cloud storage.",
                "flow": ["User", "Frontend", "API Gateway", "Lambda", "DynamoDB", "S3"],
            },
        }

    monkeypatch.setattr(LLMService, "generate_repository_analysis", fake_analysis)
    monkeypatch.setattr(
        SimilarRepoService,
        "find_similar_repositories",
        lambda self, metadata, stack, readme="", stats=None, limit=8, analysis_context=None, repository_structure=None: [
            {
                "name": "appwrite",
                "owner": "appwrite",
                "fullName": "appwrite/appwrite",
                "url": "https://github.com/appwrite/appwrite",
                "description": "Backend platform with storage and auth.",
                "stars": 52000,
                "forks": 0,
                "language": "TypeScript",
                "topics": ["storage"],
                "similarity": 88,
            }
        ],
    )

    repo_path = Path(__file__).resolve().parents[1] / "temp_repos" / "GoFileCloud" / "GoFile"
    client = TestClient(app)
    response = client.post("/analyze", json={"local_path": str(repo_path)})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["overview"] == "GoFile executive overview from Gemini."
    assert body["modules"][0]["name"] == "Frontend"
    assert "API Gateway" in body["architecture_summary"]
    assert "stack" in body
    assert "folder_structure" in body
    assert body["similar_repositories"][0]["fullName"] == "appwrite/appwrite"


def test_repo_scanner_finds_nested_readme(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Deploy orchestration\nThis project automates releases.",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('demo')\n", encoding="utf-8")

    scan = __import__("app.utils.repo_scanner", fromlist=["RepoScanner"]).RepoScanner().scan(repo)

    assert "automates releases" in scan["readme"]
    assert (repo / "docs" / "README.md").exists()


def test_llm_service_debug_logging_emits_prompt_boundaries(monkeypatch, caplog):
    def fake_gemini(self, payload):
        return '{"overview":"Deployment automation for release teams.","executive_overview":{"what_is_this_project":["This project helps teams ship updates."],"why_was_it_built":"It reduces release friction.","user_features":[{"name":"Deploy changes","description":"Ship code consistently."}],"typical_use_cases":["A team releases software"],"who_is_this_for":["Engineering teams"],"why_is_it_valuable":"It saves time.","one_line_summary":"Deployment automation for product teams."},"modules":[],"architecture":{"summary":"Single service architecture","flow":["User","Frontend","API"]}}'

    monkeypatch.setattr(LLMService, "_generate_with_gemini", fake_gemini)
    monkeypatch.setattr('app.services.llm_service.settings.analysis_debug_logging', True, raising=False)
    caplog.set_level(logging.INFO)

    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/deploy", "description": "Deployment tooling"},
        readme="# Deploy\nThis project helps teams ship updates.",
        stack={"categories": {}},
        repository_structure=[],
        scan={"files": [], "dependencies": {}, "source_previews": {}, "source_evidence": {}},
    )

    assert analysis["executive_overview"]["what_is_this_project"][0].startswith("This project")
    assert "GEMINI_INPUT_START" in caplog.text
    assert "GEMINI_INPUT_END" in caplog.text
