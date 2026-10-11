from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.services.repository_discovery import build_analysis_evidence, score_analyzability
from app.services.semantic_profile_builder import build_semantic_repository_profile
from app.services.source_evidence_extractor import (
    SourceEvidenceExtractor,
    extract_routes_from_content,
    redact_secrets,
)
from app.services.llm_service import LLMService
from app.utils.repo_scanner import RepoScanner


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_fullstack_ecommerce_evidence(tmp_path):
    _write(
        tmp_path,
        "backend/main.py",
        '''
from fastapi import FastAPI
app = FastAPI()

@app.post("/api/cart/items")
def add_item():
    return {"ok": True}

@app.get("/api/products")
def list_products():
    return []
''',
    )
    _write(tmp_path, "backend/services/cart_service.py", "def add_to_cart(): pass\ndef remove_from_cart(): pass")
    _write(tmp_path, "backend/models/cart.py", "class Cart: pass")
    _write(tmp_path, "frontend/src/pages/CartPage.tsx", 'export function CartPage() { fetch("/api/cart/items"); return null; }')
    _write(tmp_path, "README.md", "# Shop\nE-commerce cart and checkout platform.")

    scan = RepoScanner().scan(tmp_path)
    routes = scan["source_evidence"]["routes"]
    assert any(r.get("path") == "/api/cart/items" and r.get("method") == "POST" for r in routes)
    assert "backend/services/cart_service.py" in scan["source_evidence"]["services"]
    assert scan["source_evidence"]["stats"]["selected_evidence_files"] >= 3


def test_file_manager_upload_storage(tmp_path):
    _write(tmp_path, "src/routes/upload.ts", 'router.post("/api/files/upload", uploadHandler);')
    _write(tmp_path, "src/services/storage_service.ts", "export class StorageService { save() {} }")
    _write(tmp_path, "src/controllers/file_controller.ts", "export function listFiles() {}")
    scan = RepoScanner().scan(tmp_path)
    assert scan["source_evidence"]["storage_files"] or scan["source_evidence"]["services"]


def test_chat_app_websocket_signals(tmp_path):
    _write(tmp_path, "server/chat_routes.py", '@router.post("/api/messages")\ndef send_message(): pass')
    _write(tmp_path, "frontend/pages/ChatPage.tsx", "export const ChatPage = () => null;")
    scan = RepoScanner().scan(tmp_path)
    caps = scan["source_evidence"].get("capability_signals", [])
    assert scan["source_evidence"]["stats"]["routes_detected"] >= 1


def test_no_readme_still_selects_entrypoint(tmp_path):
    _write(tmp_path, "app/main.py", "def main(): print('hi')")
    scan = RepoScanner().scan(tmp_path)
    assert "app/main.py" in scan["source_evidence"]["entrypoints"]


def test_large_file_smart_truncation(tmp_path):
    filler = "\n# comment line\npass\n" * 5000
    _write(
        tmp_path,
        "backend/routes/api.py",
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        + filler
        + '\n@router.get("/api/health")\ndef health_check():\n    return {"ok": True}\n',
    )
    scan = RepoScanner().scan(tmp_path)
    details = scan["_selected_source_file_objects"]
    api_file = next(d for d in details if d["path"].endswith("api.py"))
    assert "/api/health" in api_file["content"]
    assert len(api_file["content"]) <= 9000


def test_generated_directories_ignored(tmp_path):
    _write(tmp_path, "dist/bundle.js", "console.log('generated');" * 100)
    _write(tmp_path, "node_modules/pkg/index.js", "module.exports = {}")
    _write(tmp_path, "src/main.py", "print('real')")
    scan = RepoScanner().scan(tmp_path)
    paths = {d["path"] for d in scan["_selected_source_file_objects"]}
    assert not any("node_modules" in p for p in paths)
    assert not any(p.startswith("dist/") for p in paths)


def test_routes_include_handler_metadata():
    content = '''
@router.post("/api/orders")
async def create_order():
    return {}
'''
    routes = extract_routes_from_content(content, "routes/orders.py")
    assert routes[0]["method"] == "POST"
    assert routes[0]["path"] == "/api/orders"
    assert routes[0]["handler"] == "create_order"


def test_database_model_evidence(tmp_path):
    _write(tmp_path, "backend/models/user.py", "class User:\n    id: int")
    _write(tmp_path, "backend/repositories/user_repository.py", "def find_user(): pass")
    scan = RepoScanner().scan(tmp_path)
    assert scan["source_evidence"]["models"]
    assert scan["source_evidence"]["repositories"]


def test_infrastructure_docker_k8s(tmp_path):
    _write(tmp_path, "Dockerfile", "FROM python:3.12\n")
    _write(tmp_path, "k8s/deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\n")
    _write(tmp_path, "infra/main.tf", 'resource "aws_s3_bucket" "b" {}')
    scan = RepoScanner().scan(tmp_path)
    assert scan["source_evidence"]["infrastructure"]


def test_misleading_directory_names_weak_alone(tmp_path):
    _write(tmp_path, "cart/readme.txt", "not source")
    _write(tmp_path, "utils/helpers.py", "def noop(): pass")
    scan = RepoScanner().scan(tmp_path)
    caps = scan["source_evidence"].get("capability_signals", [])
    ecommerce = [c for c in caps if c.get("domain") == "ecommerce" and c.get("confidence", 0) >= 50]
    assert ecommerce == []


def test_secrets_redacted(tmp_path):
    secret_content = '''
API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
password = "super-secret-value"
DATABASE_URL = "postgresql://admin:secretpass@db.example.com:5432/app"
'''
    _write(tmp_path, "backend/config/settings.py", secret_content)
    scan = RepoScanner().scan(tmp_path)
    detail = scan["_selected_source_file_objects"][0]
    assert "sk-abc" not in detail["content"]
    assert "super-secret-value" not in detail["content"]
    assert redact_secrets(secret_content) != secret_content


def test_payload_bounded(tmp_path):
    for i in range(80):
        _write(tmp_path, f"backend/services/service_{i}.py", f"def fn_{i}(): pass\n" * 200)
    scan = RepoScanner().scan(tmp_path)
    stats = scan["source_evidence"]["stats"]
    assert stats["selected_evidence_files"] <= 45
    assert stats["evidence_payload_chars"] <= 120_000


def test_manifest_framework_config_and_source_are_selected_without_readme(tmp_path):
    _write(
        tmp_path,
        "package.json",
        '{"dependencies":{"react":"^19.0.0","vite":"^6.0.0","tailwindcss":"^4.0.0"}}',
    )
    _write(tmp_path, "vite.config.ts", "export default defineConfig({ base: '/app' });")
    _write(tmp_path, "tailwind.config.ts", "export default { theme: { extend: {} } };")
    _write(
        tmp_path,
        "src/App.tsx",
        "export default function App() { return <main>Repository-specific dashboard</main>; }",
    )

    scan = RepoScanner().scan(tmp_path)
    details = {
        item["path"]: item
        for item in scan["_selected_source_file_objects"]
    }

    assert not scan["readme"]
    assert {"package.json", "vite.config.ts", "tailwind.config.ts", "src/App.tsx"} <= details.keys()
    assert "react" in details["package.json"]["content"]
    assert "base: '/app'" in details["vite.config.ts"]["content"]
    assert "Repository-specific dashboard" in details["src/App.tsx"]["content"]
    stats = scan["source_evidence"]["stats"]
    assert stats["selected_evidence_files"] == 4
    assert stats["source_chars_selected"] > 0
    assert stats["source_chars_available"] >= stats["source_chars_selected"]

    profile = build_semantic_repository_profile(
        {"name": "sample-app"}, "", {"categories": {}}, scan, {}
    )
    assert any(
        item["path"] == "package.json"
        for item in profile["source_evidence_summary"]["files"]
    )


def test_selected_source_reaches_actual_gemini_request_serialization(tmp_path, monkeypatch, caplog):
    source_marker = "persist_invoice_and_publish_billing_event"
    _write(
        tmp_path,
        "src/services/billing_service.py",
        'GITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n'
        f"def {source_marker}(invoice, repository):\n"
        "    repository.save(invoice)\n"
        "    return invoice.id\n",
    )
    scan = RepoScanner().scan(tmp_path)
    stack = {"categories": {}}
    payload = LLMService()._build_input_payload(
        {"full_name": "example/billing"},
        "",
        stack,
        [],
        scan,
    )
    selected = payload["source_evidence"]["selected_source_file_details"]
    assert any(source_marker in item["content"] for item in selected)
    assert all("ghp_abcdefghijklmnopqrstuvwxyz" not in item["content"] for item in selected)
    assert any(
        item["path"] == "src/services/billing_service.py"
        for item in payload["semantic_repository_profile"]["source_evidence_summary"]["files"]
    )

    captured = {}

    class FakeModel:
        def count_tokens(self, prompt):
            captured["token_count_prompt"] = prompt
            return SimpleNamespace(total_tokens=1200)

        def generate_content(self, prompt, generation_config):
            captured["provider_prompt"] = prompt
            return SimpleNamespace(text='{"result":"ok"}')

    fake_genai = SimpleNamespace(
        configure=lambda **kwargs: None,
        types=SimpleNamespace(GenerationConfig=lambda **kwargs: kwargs),
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)
    monkeypatch.setattr("app.services.llm_service.settings.gemini_api_key", "test-key")

    assert LLMService()._generate_with_gemini(payload) == '{"result":"ok"}'
    request = captured["provider_prompt"]
    assert source_marker in request
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in request
    assert "[REDACTED]" in request
    assert "src/services/billing_service.py" in request
    assert '"semantic_repository_profile"' in request
    assert '"role": "service"' in request
    assert source_marker not in caplog.text
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in caplog.text


def test_token_budget_omits_low_priority_source_before_business_routes(tmp_path, monkeypatch):
    _write(
        tmp_path,
        "src/services/low_priority.py",
        "def low_priority_operation():\n    return 'LOW_PRIORITY_MARKER'\n",
    )
    _write(
        tmp_path,
        "src/routes/orders.py",
        '@router.post("/api/orders")\n'
        "def create_order():\n"
        "    return 'HIGH_VALUE_BODY'\n",
    )
    scan = RepoScanner().scan(tmp_path)
    payload = LLMService()._build_input_payload(
        {"full_name": "example/orders"}, "", {"categories": {}}, [], scan
    )
    captured = {}

    class FakeModel:
        def count_tokens(self, prompt):
            return SimpleNamespace(
                total_tokens=120_000 if "LOW_PRIORITY_MARKER" in prompt else 1000
            )

        def generate_content(self, prompt, generation_config):
            captured["prompt"] = prompt
            return SimpleNamespace(text='{"result":"ok"}')

    fake_genai = SimpleNamespace(
        configure=lambda **kwargs: None,
        types=SimpleNamespace(GenerationConfig=lambda **kwargs: kwargs),
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)
    monkeypatch.setattr("app.services.llm_service.settings.gemini_api_key", "test-key")

    LLMService()._generate_with_gemini(payload)

    request = captured["prompt"]
    assert "LOW_PRIORITY_MARKER" not in request
    assert "HIGH_VALUE_BODY" in request
    assert "Gemini input token budget" in request
    assert "src/services/low_priority.py" in request


def test_oversized_source_preserves_route_handler_business_logic(tmp_path):
    filler = "\n# filler\npass\n" * 2500
    business_logic = (
        '@router.post("/api/invoices")\n'
        "def create_invoice():\n"
        "    invoice = calculate_tax_and_total()\n"
        "    repository.save(invoice)\n"
        '    return {"invoice_id": invoice.id}\n'
    )
    _write(
        tmp_path,
        "backend/routes/invoices.py",
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        + filler
        + business_logic,
    )

    scan = RepoScanner().scan(tmp_path)
    item = next(
        item for item in scan["_selected_source_file_objects"]
        if item["path"] == "backend/routes/invoices.py"
    )
    assert len(item["content"]) <= 8000
    assert "from fastapi import APIRouter" in item["content"]
    assert '@router.post("/api/invoices")' in item["content"]
    assert "def create_invoice():" in item["content"]
    assert "calculate_tax_and_total()" in item["content"]
    assert "repository.save(invoice)" in item["content"]


def test_parent_temp_repos_directory_does_not_hide_repository(tmp_path):
    repo = tmp_path / "temp_repos" / "checkout" / "project"
    _write(repo, "src/main.py", "def start_checkout(): return True")

    scan = RepoScanner().scan(repo)

    assert "src/main.py" in scan["files"]
    assert any(
        item["path"] == "src/main.py"
        for item in scan["_selected_source_file_objects"]
    )


def test_semantic_profile_and_analysis_evidence(tmp_path):
    _write(tmp_path, "backend/main.py", '@app.get("/api/cart")\ndef cart(): pass')
    _write(tmp_path, "README.md", "# Store")
    scan = RepoScanner().scan(tmp_path)
    stack = {"categories": {"backend": [{"name": "FastAPI"}]}}
    code_signals = {"api_routes": ["/api/cart"], "api_routes_enriched": scan["source_evidence"]["routes"]}
    evidence = build_analysis_evidence(scan, stack, "cart checkout products", code_signals)
    profile = build_semantic_repository_profile(
        {"full_name": "acme/shop", "description": "Online store", "topics": ["ecommerce"]},
        "cart checkout",
        stack,
        scan,
        code_signals,
    )
    assert evidence.get("selected_evidence_file_count", 0) >= 1
    assert "api_evidence" in profile
    assert profile["project_identity"]["name"] == "acme/shop"


def test_analyzability_bonus_from_scan_evidence(tmp_path):
    paths = ["src/main.py"]
    base = score_analyzability(paths, readme_present=False)
    scan = {
        "source_evidence": {
            "stats": {"selected_evidence_files": 5, "routes_detected": 4},
            "capability_signals": [{"domain": "ecommerce", "confidence": 70, "matched_signals": ["cart", "checkout"]}],
        }
    }
    boosted = score_analyzability(paths, readme_present=False, scan=scan)
    assert boosted > base
