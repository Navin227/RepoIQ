import logging
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import LLMService
from app.services import llm_service as llm_service_module
from app.services import analysis_context
from app.services.similar_repo_service import SimilarRepoService


def test_llm_service_parses_structured_grok_json(monkeypatch):
    def fake_grok(self, payload):
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
              {"name": "Upload Files", "description": "Add files to the platform.", "evidence": ["UploadModal.tsx"]},
              {"name": "Manage Files", "description": "Keep files organized.", "evidence": ["pages/Auth.tsx"]},
              {"name": "Sign In", "description": "Access a personal account.", "evidence": ["auth/context.tsx"]},
              {"name": "Track Work", "description": "Follow file processing progress.", "evidence": ["worker.py"]},
              {"name": "Use Tools", "description": "Run available file actions.", "evidence": ["main.tf"]},
              {"name": "Frontend", "description": "A user interface.", "evidence": ["pages/Auth.tsx"]},
              {"name": ".Claude", "description": "Repository configuration.", "evidence": ["README.md"]},
              {"name": "Storage", "description": "A persistence layer.", "evidence": ["s3/main.tf"]}
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

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)

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
    assert len(analysis["executive_overview"]["user_features"]) == 4
    assert analysis["executive_overview"]["user_features"][0]["evidence"] == ["UploadModal.tsx"]
    assert analysis["modules"][0]["name"] == "Authentication"
    assert analysis["modules"][0]["purpose"] == "Handles user identity and protected access."
    assert analysis["modules"][0]["capabilities"] == ["Sign in users", "Protect private workflows", "Track current user"]
    assert analysis["modules"][0]["components"] == ["auth/context.tsx", "pages/Auth.tsx"]
    assert analysis["modules"][0]["connected_modules"] == []
    assert analysis["modules"][0]["confidence"] == 80
    assert analysis["architecture"]["flow"] == ["User", "Frontend", "API Layer", "Worker", "Storage"]


def test_llm_service_reports_grok_provider_failure_without_successful_analysis(monkeypatch):
    def failing_grok(self, payload):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(LLMService, "_generate_with_grok", failing_grok)

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

    assert analysis["overview"] == ""
    assert analysis["analysis_status"] == "failed"
    assert analysis["analysis_error"] == "grok_provider_failure"
    assert analysis["analysis_evidence"]["pipeline_diagnostics"]["grok"]["status"] == "failed"
    assert analysis["modules"] == []
    assert analysis["executive_overview"] is None
    assert {"summary", "flow"} <= set(analysis["architecture"])


def test_grok_modules_without_repository_evidence_are_not_returned(monkeypatch):
    def fake_grok(self, payload):
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

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)
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


def test_legacy_fallback_generators_are_retired():
    service = LLMService()
    assert not hasattr(service, "_fallback_analysis")
    assert not hasattr(service, "generate_overview")
    assert not hasattr(service, "generate_modules")
    assert not hasattr(service, "generate_architecture_summary")
    assert not hasattr(service, "generate_ai_insights")


def test_analyze_endpoint_uses_ai_generation_for_gofile(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    def fake_analysis(self, metadata, readme, stack, repository_structure, scan):
        return {
            "overview": "GoFile executive overview from Grok.",
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
    response = client.post("/analyze", json={"local_path": str(repo_path), "analysis_run_id": "run_gofile_test"},
                           headers={"X-Analysis-Run-Id": "run_gofile_test"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["analysis_run_id"] == "run_gofile_test"
    assert '"event":"analysis_request_received"' in caplog.text
    assert '"event":"repository_model_build_completed"' in caplog.text
    assert '"event":"response_schema_validated"' in caplog.text
    assert '"analysis_run_id":"run_gofile_test"' in caplog.text
    assert body["overview"] == "GoFile executive overview from Grok."
    assert body["modules"][0]["name"] == "Frontend"
    assert "API Gateway" in body["architecture_summary"]
    assert "stack" in body
    assert "folder_structure" in body
    assert body["similar_repositories"][0]["fullName"] == "appwrite/appwrite"
    assert "stages" in body["analysis_evidence"]["pipeline_diagnostics"]["output_filtering"]
    assert "validation_diagnostics" in body["repository_model"]


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


def test_repo_scanner_prefers_non_docs_readme_over_docs_fallback(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Docs\nInternal operations.", encoding="utf-8")
    service_dir = repo / "services"
    service_dir.mkdir()
    (service_dir / "README.md").write_text("# Service\nThis is the main product README.", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('demo')\n", encoding="utf-8")

    scan = __import__("app.utils.repo_scanner", fromlist=["RepoScanner"]).RepoScanner().scan(repo)

    assert "main product README" in scan["readme"]
    assert (service_dir / "README.md").resolve() == __import__("app.utils.repo_scanner", fromlist=["RepoScanner"]).RepoScanner()._find_readme(repo).resolve()


def test_repo_scanner_keeps_relevant_files_when_inventory_is_large(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()

    for index in range(2500):
        (repo / f"aaa_{index:04d}.txt").write_text("irrelevant placeholder\n", encoding="utf-8")

    app_dir = repo / "zz_generated" / "src"
    app_dir.mkdir(parents=True)
    app_file = app_dir / "main.py"
    app_file.write_text("def main():\n    return 'important'\n", encoding="utf-8")

    scan = __import__("app.utils.repo_scanner", fromlist=["RepoScanner"]).RepoScanner().scan(repo)

    assert app_file.relative_to(repo).as_posix() in scan["files"]
    assert len(scan["files"]) == 2501


def test_llm_service_debug_logging_emits_prompt_boundaries(monkeypatch, caplog):
    def fake_grok(self, payload):
        return '{"overview":"Deployment automation for release teams.","executive_overview":{"what_is_this_project":["This project helps teams ship updates."],"why_was_it_built":"It reduces release friction.","user_features":[{"name":"Deploy changes","description":"Ship code consistently."}],"typical_use_cases":["A team releases software"],"who_is_this_for":["Engineering teams"],"why_is_it_valuable":"It saves time.","one_line_summary":"Deployment automation for product teams."},"modules":[],"architecture":{"summary":"Single service architecture","flow":["User","Frontend","API"]}}'

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)
    monkeypatch.setattr('app.services.llm_service.settings.analysis_debug_logging', True, raising=False)
    caplog.set_level(logging.DEBUG)

    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/deploy", "description": "Deployment tooling"},
        readme="# Deploy\nThis project helps teams ship updates.",
        stack={"categories": {}},
        repository_structure=[],
        scan={"files": [], "dependencies": {}, "source_previews": {}, "source_evidence": {}},
    )

    assert analysis["executive_overview"]["what_is_this_project"][0].startswith("This project")
    assert '"event":"grok_input_summary"' in caplog.text
    assert '"event":"grok_input_debug_preview"' in caplog.text


def test_llm_service_tracks_ai_insights_and_status(monkeypatch):
    def fake_grok(self, payload):
        return '''
        {
          "overview": "A file processing platform for authenticated users.",
          "executive_overview": {
            "what_is_this_project": ["This project helps people manage files in one place."],
            "why_was_it_built": "It keeps file workflows organized.",
            "user_features": [{
              "name": "Upload files",
              "description": "Add files to the platform.",
              "evidence": ["UploadModal.tsx"]
            }],
            "typical_use_cases": ["A user stores files for later access."],
            "who_is_this_for": ["Individuals"],
            "why_is_it_valuable": "It saves time.",
            "one_line_summary": "A simple place to manage and process files."
          },
          "modules": [{
            "name": "File Upload",
            "purpose": "Lets users add files.",
            "components": ["UploadModal.tsx"],
            "connected_modules": [],
            "confidence": 90
          }],
          "architecture": {"summary": "Users upload files through a frontend and API.", "flow": ["User", "Frontend", "API"]}
        }
        '''

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)

    analysis = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/files", "description": "File tools"},
        readme="README",
        stack={"categories": {}},
        repository_structure=[],
        scan={
            "files": ["UploadModal.tsx"],
            "dependencies": {},
            "source_previews": {},
            "source_evidence": {"selected_source_file_details": [{"path": "UploadModal.tsx", "role": "frontend_component"}]},
        },
    )

    assert analysis["analysis_status"] == "complete"
    assert analysis["analysis_evidence"]["pipeline_diagnostics"]["grok_output"]["missing_fields"]
    assert analysis["ai_insights"] == []


def test_optional_unresolved_investigation_does_not_hide_useful_output(monkeypatch):
    captured = {}

    def fake_grok(self, payload):
        captured["analysis_run_id"] = payload["analysis_run_id"]
        return '{"overview":"Evidence-backed report.","modules":[],"architecture":{"summary":"Requests enter the API and are handled by the service layer."},"investigation_requests":[{"query":"BillingService","question":"confirm billing workflow"}]}'

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)
    result = LLMService().generate_repository_analysis(
        metadata={"full_name": "acme/example", "analysis_run_id": "run_partial_789"},
        readme="", stack={}, repository_structure=[], scan={"files": [], "source_evidence": {}},
    )

    assert captured["analysis_run_id"] == "run_partial_789"
    assert result["analysis_status"] == "complete", result["analysis_evidence"]["pipeline_diagnostics"].get("status_classification")
    assert result["analysis_evidence"]["investigation_coverage"]["unresolved"]


def test_llm_service_drops_architecture_components_without_repo_evidence():
    service = LLMService()
    payload = {
        "file_tree": ["src/app.py", "src/auth.py"],
        "api_routes": [],
        "api_routes_enriched": [],
        "top_level_modules": ["src"],
        "analysis_evidence": {"source_files": ["src/app.py", "src/auth.py"]},
    }
    analysis = service._normalize_analysis(
        {
            "overview": "A project for user identity and file flows.",
            "executive_overview": {
                "what_is_this_project": ["This project manages identities and files."],
                "why_was_it_built": "It streamlines file workflows.",
                "user_features": [{"name": "Upload files", "description": "Upload a file.", "evidence": ["src/app.py"]}],
                "typical_use_cases": ["Use the service to manage files."],
                "who_is_this_for": ["Teams"],
                "why_is_it_valuable": "It keeps tasks organized.",
                "one_line_summary": "Identity and file management.",
            },
            "modules": [{
                "name": "Authentication",
                "purpose": "Handles identity and signed-in users.",
                "components": ["src/auth.py"],
                "confidence": 90,
            }],
            "architecture": {
                "summary": "User requests are routed to the auth service and app layer.",
                "architecture_type": "Monolith",
                "flow": ["User", "Frontend", "API"],
                "components": [
                    {"name": "src/fake/payment-service.ts", "responsibility": "Processes payments."},
                    {"name": "API Gateway", "responsibility": "Routes requests to the backend."},
                ],
                "communication": ["HTTP"],
                "deployment": "Docker",
            },
        },
        payload,
    )

    assert analysis["modules"][0]["name"] == "Authentication"
    assert [component["name"] for component in analysis["architecture"]["components"]] == ["API Gateway"]


def test_generic_named_module_with_strong_source_evidence_is_retained():
    service = LLMService()
    payload = {
        "file_tree": ["src/orders.py"],
        "top_level_modules": ["src"],
        "analysis_evidence": {"source_files": ["src/orders.py"]},
    }
    analysis = service._normalize_analysis({
        "overview": "Order management.",
        "modules": [{"name": "Service", "purpose": "Creates and persists orders.", "components": ["src/orders.py"], "confidence": 10}],
        "architecture": {},
    }, payload)

    assert analysis["modules"][0]["name"] == "Service"
    assert analysis["modules"][0]["model_confidence"] == 10


def test_duplicate_features_are_deduplicated_by_name():
    service = LLMService()
    payload = {
        "source_evidence": {"selected_source_file_details": [{"path": "src/upload.ts", "role": "frontend_page"}]},
        "analysis_evidence": {},
        "file_tree": ["src/upload.ts"],
        "top_level_modules": [],
    }
    normalized = service._normalize_executive_overview({
        "user_features": [
            {"name": "Upload files", "description": "Upload a file", "evidence": ["src/upload.ts"]},
            {"name": "Upload files", "description": "Upload files to storage", "evidence": ["src/upload.ts"]},
        ]
    }, payload)
    assert [feature["name"] for feature in normalized["user_features"]] == ["Upload files"]


def test_gemma_bundle_and_source_excerpt_are_passed_to_the_single_grok_call(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("from service import run\nif __name__ == '__main__': run()\n", encoding="utf-8")
    (tmp_path / "service.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    monkeypatch.setattr(analysis_context.settings, "openrouter_api_key", "test-key")
    gemma_calls = []
    def fake_gemma(*args):
        gemma_calls.append(args)
        return json.dumps({"purpose": "prepared map", "evidence_paths": ["main.py", "service.py"]})
    monkeypatch.setattr(analysis_context, "_chat", fake_gemma)
    captured = {}

    def fake_grok(self, payload):
        captured.update(payload)
        return json.dumps({
            "overview": "A verified Python application.", "executive_overview": {}, "claims": [], "modules": [],
            "architecture": {}, "report_sections": {"recommendations": [], "limitations": []}, "investigation_requests": [],
        })

    monkeypatch.setattr(LLMService, "_generate_with_grok", fake_grok)
    result = LLMService().generate_repository_analysis(
        metadata={"full_name": "owner/project", "analysis_run_id": "run_context_handoff", "commit_sha": "abc"},
        readme="", stack={}, repository_structure=[], scan={"files": ["main.py", "service.py"], "dependencies": {}, "source_evidence": {}}, repo_path=tmp_path,
    )
    assert captured["context_bundle"]["repository_map"]["purpose"] == "prepared map"
    assert captured["context_bundle"]["commit_sha"] == "abc"
    assert captured["analysis_run_id"] == "run_context_handoff"
    assert {item["path"] for item in captured["context_bundle"]["source_excerpts"]} == {"main.py", "service.py"}
    assert len(gemma_calls) == 1
    assert "deterministic_context" not in captured["context_bundle"]
    assert "coverage_manifest" not in captured
    assert result["analysis_evidence"]["pipeline_diagnostics"]["gemma"]["status"] == "completed"
    assert result["analysis_evidence"]["pipeline_diagnostics"]["grok"]["status"] == "completed"
    assert result["analysis_evidence"]["context_preparation"]["status"] == "complete"
    assert result["analysis_status"] == "partial"


def test_modules_exclude_artifacts_and_only_report_import_verified_connections():
    service = LLMService()
    files = [
        {"path": "src/api.py", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationship_extraction": "python_ast_or_js_ts_imports", "relationships": ["src/orders.py"]},
        {"path": "src/orders.py", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationship_extraction": "python_ast_or_js_ts_imports", "relationships": ["src/store.py"]},
        {"path": "src/store.py", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationship_extraction": "python_ast_or_js_ts_imports", "relationships": []},
        {"path": "package-lock.json", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationships": []},
        {"path": "node_modules/lib/index.js", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationships": []},
        {"path": "infra/api-gateway.tf", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 10}], "relationships": []},
    ]
    normalized = service._normalize_analysis({
        "overview": "An order API with persistence.",
        "modules": [
            {"name": "Order API", "purpose": "Receives and validates order requests.", "capabilities": ["Manage project data", "Validates order requests"], "components": ["src/api.py", "package-lock.json", "node_modules/lib/index.js", "infra/api-gateway.tf"], "connected_modules": ["Order Store"], "confidence": 99},
            {"name": "Order Service", "purpose": "Applies order business rules.", "components": ["src/orders.py"], "confidence": 90},
            {"name": "Order Store", "purpose": "Persists order records.", "components": ["src/store.py"], "confidence": 90},
            {"name": "Infrastructure", "purpose": "Configures API gateway deployment.", "components": ["infra/api-gateway.tf"], "confidence": 90},
        ], "architecture": {},
    }, {"context_bundle": {"coverage_manifest": {"files": files}}})

    modules = {item["name"]: item for item in normalized["modules"]}
    assert modules["Order API"]["components"] == ["src/api.py"]
    assert modules["Order API"]["capabilities"] == ["Validates order requests"]
    assert modules["Order API"]["connected_modules"] == ["Order Service"]
    assert modules["Order API"]["confidence"] == 65
    assert modules["Order Service"]["connected_modules"] == ["Order Store"]
    assert modules["Order Service"]["confidence"] == 65
    assert modules["Order Store"]["connection_evidence_status"] == "verified_none"
    assert modules["Infrastructure"]["connection_evidence_status"] == "not_fully_assessed"
    assert "Infrastructure" not in modules["Order API"]["connected_modules"]


def test_end_user_use_cases_are_titled_evidence_backed_and_deduplicated():
    service = LLMService()
    payload = {
        "source_evidence": {"selected_source_file_details": [{"path": "src/pdf.py", "role": "service"}]},
        "analysis_evidence": {}, "file_tree": ["src/pdf.py"], "top_level_modules": [],
    }
    normalized = service._normalize_executive_overview({
        "end_user_use_cases": [
            {"title": "Prepare a PDF for sharing", "description": "Compress a PDF to reduce its file size before sharing.", "evidence": ["src/pdf.py"]},
            {"title": "Prepare a PDF for sharing", "description": "Compress a PDF to reduce its file size before sharing.", "evidence": ["src/pdf.py"]},
            {"title": "Manage project data", "description": "Compress the file to reduce its size before sharing.", "evidence": ["src/pdf.py"]},
            {"title": "Convert files", "description": "Convert supported files between formats.", "evidence": ["README.md"]},
        ],
    }, payload)
    assert normalized["end_user_use_cases"] == [{
        "title": "Prepare a PDF for sharing",
        "description": "Compress a PDF to reduce its file size before sharing.",
        "evidence": ["src/pdf.py"],
    }]


def test_generic_use_cases_and_typical_use_case_fallback_are_rejected():
    service = LLMService()
    payload = {"source_evidence": {"selected_source_file_details": [{"path": "src/orders.py", "role": "service"}]}, "file_tree": ["src/orders.py"]}
    phrases = [
        "A person wants one place to complete the workflow described by the project.",
        "A team wants to evaluate whether this project fits their needs before adopting it.",
        "A maintainer wants to understand the product purpose and visible capabilities quickly.",
    ]
    normalized = service._normalize_executive_overview({"typical_use_cases": phrases}, payload)
    assert normalized["end_user_use_cases"] == []
    assert normalized["typical_use_cases"] == []
    generic = service._normalize_executive_overview({"end_user_use_cases": [
        {"title": "Order workflows", "description": phrases[0], "evidence": ["src/orders.py"]},
    ]}, payload)
    assert generic["end_user_use_cases"] == []


def test_use_cases_from_distinct_implementation_evidence_remain_distinct():
    service = LLMService()
    cases = [
        ({"file_tree": ["src/pdf_compressor.py"], "source_evidence": {"selected_source_file_details": [{"path": "src/pdf_compressor.py", "role": "service"}]}},
         {"title": "Compress a PDF", "description": "Reduce a PDF's file size before sharing it.", "evidence": ["src/pdf_compressor.py"]}),
        ({"file_tree": ["src/oauth_client.py"], "source_evidence": {"selected_source_file_details": [{"path": "src/oauth_client.py", "role": "service"}]}},
         {"title": "Refresh an access token", "description": "Request a refreshed OAuth access token when the current token expires.", "evidence": ["src/oauth_client.py"]}),
    ]
    outputs = [service._normalize_executive_overview({"end_user_use_cases": [item]}, payload)["end_user_use_cases"] for payload, item in cases]
    assert outputs[0][0]["title"] == "Compress a PDF"
    assert outputs[1][0]["title"] == "Refresh an access token"
    assert outputs[0] != outputs[1]


def test_gemma_repository_map_supplies_verified_module_components_without_cross_mapping():
    service = LLMService()
    files = [
        {"path": "src/orders.py", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 8}]},
        {"path": "infra/deploy.tf", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 8}]},
        {"path": "package-lock.json", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 8}]},
        {"path": "src/unrelated.py", "status": "fully_inspected", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 8}]},
    ]
    result = service._normalize_analysis({"overview": "Order service and infrastructure.", "modules": [
        {"name": "Order Service", "purpose": "Applies order rules.", "components": []},
        {"name": "Infrastructure", "purpose": "Deploys the service.", "components": []},
        {"name": "Unrelated Module", "purpose": "Handles unrelated logic.", "components": ["missing.py", "src/unrelated.py"]},
        {"name": "No Evidence", "purpose": "No mapping is available.", "components": ["missing.py"]},
    ], "architecture": {}}, {"context_bundle": {
        "coverage_manifest": {"files": files},
        "repository_map": {"modules": [
            {"name": "Order Service", "purpose": "Applies order rules", "evidence_paths": ["src/orders.py", "missing.py", "package-lock.json"]},
            {"name": "Infrastructure", "purpose": "Deploys the service", "components": [{"path": "infra/deploy.tf"}]},
        ]},
    }})
    modules = {item["name"]: item["components"] for item in result["modules"]}
    assert modules["Order Service"] == ["src/orders.py"]
    assert modules["Infrastructure"] == ["infra/deploy.tf"]
    assert modules["Unrelated Module"] == ["src/unrelated.py"]
    assert "No Evidence" not in modules


def test_evidence_backed_module_without_file_mapping_is_retained_without_invented_components():
    service = LLMService()
    result = service._normalize_analysis({
        "overview": "Order management.",
        "claims": [{
            "text": "Order reconciliation resolves duplicate order records.",
            "category": "module", "target_name": "Order reconciliation",
            "evidence": [{"path": "src/reconcile.py", "start_line": 1, "end_line": 4}],
        }],
        "modules": [{
            "name": "Order reconciliation",
            "purpose": "Resolves duplicate order records.",
            "components": ["README.md", "docs/reconcile.md", "src/missing.py"],
        }],
        "architecture": {},
    }, {"context_bundle": {"coverage_manifest": {"files": [
        {"path": "src/reconcile.py", "grok_supplied_line_ranges": [{"start_line": 1, "end_line": 4}]},
    ]}}})

    assert len(result["modules"]) == 1
    assert result["modules"][0]["components"] == []
    assert result["modules"][0]["evidence"] == []


def test_architecture_normalization_drops_placeholders_and_generic_components():
    normalized = LLMService()._normalize_architecture({
        "summary": "Unknown",
        "architecture_type": "N/A",
        "flow": ["Unknown", "API validates order input"],
        "components": [
            {"name": "Response", "responsibility": "Performs a specific runtime responsibility inferred from repository architecture evidence"},
            {"name": "Order API", "responsibility": "Validates order input", "input": "Unknown", "output": "Order record"},
        ],
        "deployment": "Not available",
    })
    assert normalized["summary"] == ""
    assert normalized["architecture_type"] == ""
    assert normalized["flow"] == ["API validates order input"]
    assert normalized["components"] == [{"name": "Order API", "responsibility": "Validates order input", "output": "Order record"}]
    assert normalized["deployment"] == ""


def test_grok_input_budget_records_omissions_and_removes_duplicate_tree():
    bundle = {
        "coverage_manifest": {"files": [
            {"path": "main.py", "roles": ["entry_point"], "important_to_execution_path": True, "execution_path_distance": 0},
            {"path": "docs/example.py", "roles": [], "important_to_execution_path": False},
        ]},
        "coverage_gate": {"status": "sufficient", "known_critical_dependencies_not_inspected": []},
        "source_excerpts": [
            {"path": "main.py", "start_line": 1, "end_line": 3, "content": "def main():\n    return 1\n"},
            {"path": "docs/example.py", "start_line": 1, "end_line": 800, "content": "example source\n" * 800},
        ],
        "repository_map": {"purpose": "prepared"},
    }
    provider, prompt, manifest = llm_service_module._fit_grok_input(
        {"file_tree": ["main.py", "docs/example.py"], "context_bundle": bundle, "analysis_evidence": {"counts": {"files": 2}}},
        "system prompt", lambda text: (len(text) + 1) // 2, 2200,
    )
    assert manifest["estimated_tokens"] <= manifest["budget_tokens"]
    assert manifest["omitted_source_ranges"]
    assert all(item["reason"] == "grok_input_token_budget" for item in manifest["omitted_source_ranges"])
    assert any(item["path"] == "main.py" for item in provider["context_bundle"]["source_excerpts"])
    assert provider["context_bundle"]["coverage_gate"]["status"] == "sufficient"
    assert "file_tree" not in provider
    assert {item["field"] for item in manifest["omitted_fields"]} >= {"file_tree"}
    assert "grok_input_manifest" in prompt


def test_gemma_failure_is_not_hidden_by_a_grok_fallback(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(analysis_context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(analysis_context, "_chat", lambda *args: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    grok_calls = []
    monkeypatch.setattr(LLMService, "_generate_with_grok", lambda *args: grok_calls.append(True) or "{}")
    result = LLMService().generate_repository_analysis(
        metadata={"full_name": "owner/repo", "commit_sha": "abc"}, readme="", stack={},
        repository_structure=[], scan={"files": ["main.py"], "source_evidence": {}}, repo_path=tmp_path,
    )
    diagnostics = result["analysis_evidence"]["pipeline_diagnostics"]
    assert result["analysis_status"] == "failed"
    assert result["analysis_error"] == "gemma_provider_failure"
    assert diagnostics["gemma"]["status"] == "failed"
    assert diagnostics["grok"]["status"] == "not_run"
    assert not grok_calls


def test_malformed_and_partial_grok_outputs_are_distinguished(monkeypatch):
    monkeypatch.setattr(LLMService, "_generate_with_grok", lambda *args: "{}")
    malformed = LLMService().generate_repository_analysis({}, "", {}, [], {"files": [], "source_evidence": {}})
    assert malformed["analysis_status"] == "failed"
    assert malformed["analysis_error"] == "grok_malformed_output"
    assert malformed["analysis_evidence"]["pipeline_diagnostics"]["failure_stage"] == "grok_output"

    monkeypatch.setattr(LLMService, "_generate_with_grok", lambda *args: '{"overview":"Partial report"}')
    partial = LLMService().generate_repository_analysis({}, "", {}, [], {"files": [], "source_evidence": {}})
    assert partial["analysis_status"] == "partial"
    assert partial["analysis_evidence"]["pipeline_diagnostics"]["grok_output"]["status"] == "partial"


def test_insufficient_gemma_coverage_is_reported_and_blocks_grok(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(analysis_context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(analysis_context.settings, "context_per_file_token_budget", 128)
    grok_calls = []
    monkeypatch.setattr(LLMService, "_generate_with_grok", lambda *args: grok_calls.append(True) or "{}")
    result = LLMService().generate_repository_analysis(
        metadata={"full_name": "owner/repo"}, readme="", stack={}, repository_structure=[],
        scan={"files": ["main.py"], "source_evidence": {}}, repo_path=tmp_path,
    )
    assert result["analysis_error"] == "insufficient_repository_coverage"
    assert result["analysis_evidence"]["pipeline_diagnostics"]["coverage"]["status"] == "insufficient"
    assert not grok_calls


def test_malformed_gemma_response_has_a_distinct_stage_diagnostic(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(analysis_context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(analysis_context, "_chat", lambda *args: "not-json")
    result = LLMService().generate_repository_analysis(
        metadata={"full_name": "owner/repo"}, readme="", stack={}, repository_structure=[],
        scan={"files": ["main.py"], "source_evidence": {}}, repo_path=tmp_path,
    )
    diagnostics = result["analysis_evidence"]["pipeline_diagnostics"]
    assert result["analysis_error"] == "gemma_malformed_output"
    assert diagnostics["failure_stage"] == "gemma"
    assert diagnostics["grok"]["status"] == "not_run"
