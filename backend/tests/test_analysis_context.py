import json

import pytest

from app.services import analysis_context as context
from app.routes.analyze import _filter_claims_by_coverage, _validate_report_recommendations
from app.services.llm_service import LLMService
from app.services.repository_model import RepositoryRetrieval


def test_inventory_tracks_secret_binary_and_source_imports(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("from src.service import run\nrun()\n", encoding="utf-8")
    (tmp_path / "src" / "service.py").write_text("def run():\n    return True\n", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("export {}", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=secret-value", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\x00binary")
    external = tmp_path.parent / "outside-private.py"
    external.write_text("TOP_SECRET='should not read'\n", encoding="utf-8")
    try:
        (tmp_path / "linked.py").symlink_to(external)
    except (OSError, NotImplementedError):
        pass

    manifest, _ = context.build_inventory(tmp_path, "abc123", 1000)
    records = {item["path"]: item for item in manifest["files"]}
    assert manifest["commit_sha"] == "abc123"
    assert records[".env"]["status"] == "excluded"
    assert records["image.png"]["reason"] == "binary_file"
    assert records["src/app.py"]["relationships"] == ["src/service.py"]
    assert manifest["excluded_directories"] == [{"path": "node_modules", "reason": "generated_or_dependency_directory_policy"}]
    if "linked.py" in records:
        assert records["linked.py"]["reason"] == "symlink_policy"


def test_context_batches_are_bounded_and_manifest_marks_omissions(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "large.py").write_text("x = 1\n" * 12000, encoding="utf-8")
    (tmp_path / "zipped.py").write_text("y = 2\n" * 12000, encoding="utf-8")
    monkeypatch.setattr(context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(context.settings, "context_token_budget", 2500)
    monkeypatch.setattr(context.settings, "context_batch_files", 1)
    calls = []

    def fake_chat(key, model, messages):
        calls.append(json.loads(messages[1]["content"].split("\n", 1)[1]))
        return json.dumps({"purpose": "test", "modules": [], "evidence_paths": ["main.py"], "uncertainties": ["need follow-up"], "conflicts": ["conflicting evidence"]})

    monkeypatch.setattr(context, "_chat", fake_chat)
    bundle = context.prepare_context({}, {}, tmp_path, "abc", {})
    assert calls
    assert all(len(batch["files"]) <= 1 for batch in calls)
    assert bundle["coverage_manifest"]["commit_sha"] == "abc"
    assert bundle["coverage_manifest"]["inspected_count"] == 3
    assert bundle["coverage_manifest"]["partially_inspected_count"] >= 2
    assert all(
        entry["status"] in {"fully_inspected", "partially_inspected"}
        and entry["gemma_processed"]
        and entry["line_ranges_supplied"]
        for entry in bundle["coverage_manifest"]["files"]
        if entry["path"] in {"main.py", "large.py", "zipped.py"}
    )
    for entry in bundle["coverage_manifest"]["files"]:
        if entry["status"] == "partially_inspected":
            assert entry["reason"] == "bounded_excerpt_policy"
            assert entry["omitted_line_ranges"]
            assert entry["line_ranges_supplied"]
    assert bundle["source_excerpts"][0]["path"] == "main.py"
    assert bundle["limitations"]["unresolved_questions"]
    assert bundle["limitations"]["conflicting_findings"]
    assert bundle["coverage_gate"]["status"] == "sufficient"
    assert bundle["coverage_gate"]["core_execution_paths_sufficiently_covered"] is True


def test_library_without_executable_entrypoint_can_have_sufficient_core_coverage(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "package.py").write_text("def normalize(value):\n    return value.strip()\n", encoding="utf-8")
    monkeypatch.setattr(context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(context, "_chat", lambda *args: json.dumps({"purpose": "string normalization library", "evidence_paths": ["src/package.py"]}))

    bundle = context.prepare_context({}, {}, tmp_path, "abc", {})

    assert bundle["coverage_gate"]["important_entry_points"] == 0
    assert bundle["coverage_gate"]["core_execution_paths_sufficiently_covered"] is True
    assert bundle["coverage_gate"]["status"] == "sufficient"


def test_gemma_malformed_json_fails_closed(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(context, "_chat", lambda *args: "not json")
    with pytest.raises(RuntimeError, match="malformed context JSON"):
        context.prepare_context({}, {}, tmp_path, "abc", {})


def test_provider_request_uses_nonretention_and_bounded_retry(monkeypatch):
    monkeypatch.setattr(context.settings, "provider_retry_count", 1)
    captured = {}
    attempts = 0

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise context.httpx.TimeoutException("timed out")
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(context.httpx, "post", fake_post)
    monkeypatch.setattr(context.time, "sleep", lambda _: None)
    assert context._chat("key", "model", []) == "{}"
    assert attempts == 2
    assert captured["json"]["provider"] == {"data_collection": "deny", "zdr": True}


def test_coverage_gate_rejects_uninspected_source_references():
    claims = [{"text": "supported", "confidence": 0.9, "evidence": [{"path": "src/app.py"}]},
              {"text": "omitted", "confidence": 0.9, "evidence": [{"path": "src/hidden.py"}]}]
    result = _filter_claims_by_coverage(claims, {"files": [
        {"path": "src/app.py", "status": "inspected"},
        {"path": "src/hidden.py", "status": "omitted"},
    ]})
    assert len(result[0]["evidence"]) == 1
    assert result[1]["evidence"] == []
    assert result[1]["confidence"] == 0.2


def test_report_sections_are_normalized_and_prompt_is_versioned():
    report = LLMService._normalize_report_sections({
        "technical_analysis": "Verified flow.",
        "data_flow": ["route to service"],
        "recommendations": [{"priority": "high", "evidence": ["src/api.py"]}],
    })
    prompt = (context.Path(__file__).parents[1] / "app" / "services" / "prompts" / "repo_analysis_system.txt").read_text(encoding="utf-8")
    assert report["technical_analysis"] == "Verified flow."
    assert report["recommendations"][0]["priority"] == "high"
    for section in ("Technical analysis", "Data flow", "Technology stack", "Repository structure", "Recommendations", "Limitations"):
        assert section.lower() in prompt.lower()


def test_recommendations_need_valid_covered_source_evidence(tmp_path):
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    report = {"recommendations": [
        {"issue": "verified", "evidence": [{"path": "app.py", "start_line": 1, "end_line": 2, "excerpt": "def run():\n    return True"}]},
        {"issue": "fabricated", "evidence": [{"path": "missing.py", "start_line": 1, "end_line": 1, "excerpt": "return False"}]},
    ]}
    validated = _validate_report_recommendations(
        report, RepositoryRetrieval(tmp_path), {"files": [{"path": "app.py", "status": "inspected"}]}
    )
    assert [item["issue"] for item in validated["recommendations"]] == ["verified"]


def test_python_relative_and_javascript_alias_imports_are_traversed(tmp_path):
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "services").mkdir()
    (tmp_path / "src" / "api" / "main.py").write_text("from ..services import orders\nif __name__ == '__main__': run()\n", encoding="utf-8")
    (tmp_path / "src" / "services" / "orders.py").write_text("def create_order(): pass\n", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text(json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["web/*"]}}}), encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "App.tsx").write_text("import { api } from '@/api/client'; export default function App() {}\n", encoding="utf-8")
    (tmp_path / "web" / "api").mkdir()
    (tmp_path / "web" / "api" / "client.ts").write_text("export const api = {};\n", encoding="utf-8")

    manifest, _ = context.build_inventory(tmp_path, "abc", 10_000)
    records = {entry["path"]: entry for entry in manifest["files"]}
    assert records["src/api/main.py"]["relationships"] == ["src/services/orders.py"]
    assert records["web/App.tsx"]["relationships"] == ["web/api/client.ts"]
    assert records["src/services/orders.py"]["important_to_execution_path"] is True


def test_large_file_excerpt_includes_late_function_and_true_line_numbers(tmp_path):
    lines = [f"value_{i} = {i}" for i in range(1, 3000)]
    lines[-3:] = ["def late_critical_handler():", "    return 'late evidence'", ""]
    excerpt_ranges = context._selected_ranges("\n".join(lines), 1000, True)
    assert any("late_critical_handler" in item["content"] for item in excerpt_ranges)
    assert max(item["end_line"] for item in excerpt_ranges) == len("\n".join(lines).splitlines())
    assert all(item["start_line"] >= 1 for item in excerpt_ranges)


def test_cross_batch_findings_consolidate_and_flag_unsupported_gemma_paths(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    return worker()\n", encoding="utf-8")
    (tmp_path / "worker.py").write_text("def worker():\n    return True\n", encoding="utf-8")
    monkeypatch.setattr(context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(context.settings, "context_batch_files", 1)
    calls = []

    def fake_chat(_key, _model, messages):
        data = json.loads(messages[1]["content"].split("\n", 1)[1])
        path = data["files"][0]["path"]
        calls.append(path)
        return json.dumps({"purpose": "shared purpose", "modules": [{"name": path}], "relationships": [{"from": "main.py", "to": "worker.py"}], "evidence_paths": [path, "made-up.py"]})

    monkeypatch.setattr(context, "_chat", fake_chat)
    bundle = context.prepare_context({}, {}, tmp_path, "abc", {})
    assert len(calls) == 2
    assert len(bundle["repository_map"]["modules"]) == 2
    assert bundle["repository_map"]["unsupported_evidence_paths"] == ["made-up.py"]
    assert bundle["coverage_manifest"]["coverage"]["status"] == "sufficient"


def test_insufficient_total_context_budget_records_omissions(monkeypatch, tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "service.py").write_text("def service():\n    return 2\n", encoding="utf-8")
    monkeypatch.setattr(context.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(context.settings, "context_token_budget", 256)
    monkeypatch.setattr(context.settings, "context_per_file_token_budget", 128)
    monkeypatch.setattr(context, "_chat", lambda *args: json.dumps({"purpose": "test"}))
    with pytest.raises(RuntimeError, match="no readable files"):
        context.prepare_context({}, {}, tmp_path, "abc", {})


def test_unreadable_file_is_distinct_and_relationship_gaps_are_documented(monkeypatch, tmp_path):
    (tmp_path / "Main.java").write_text("class Main { public static void main(String[] args) {} }", encoding="utf-8")
    (tmp_path / "other.cs").write_text("class Other {}", encoding="utf-8")
    original = context.Path.read_bytes

    def failing_read(path):
        if path.name == "other.cs":
            raise OSError("unavailable")
        return original(path)

    monkeypatch.setattr(context.Path, "read_bytes", failing_read)
    manifest, _ = context.build_inventory(tmp_path, "abc", 10_000)
    entries = {entry["path"]: entry for entry in manifest["files"]}
    assert entries["other.cs"]["status"] == "unreadable"
    assert "relationship_extraction_unsupported:.java" in manifest["unsupported_relationship_extraction"]


def test_finding_caps_preserve_high_priority_and_report_truncation():
    findings = [{"purpose": "x" * 9000, "subsystems": [{"name": f"normal-{i}", "priority": "low"} for i in range(110)] + [{"name": "critical", "priority": "critical"}]}]
    merged = context._merge_findings(findings, set())
    assert len(merged["subsystems"]) == 100
    assert merged["subsystems"][0]["name"] == "critical"
    assert merged["truncated_categories"]["subsystems"] == 11
    assert merged["purpose_truncated_chars"] == 1000
