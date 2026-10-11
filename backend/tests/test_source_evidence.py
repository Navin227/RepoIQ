from pathlib import Path

import pytest

from app.services.repository_discovery import build_analysis_evidence, score_analyzability
from app.services.semantic_profile_builder import build_semantic_repository_profile
from app.services.source_evidence_extractor import (
    SourceEvidenceExtractor,
    extract_routes_from_content,
    redact_secrets,
)
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
