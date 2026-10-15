import pytest
from pydantic import ValidationError

from app.services.repository_model import (
    EvidenceReference,
    FunctionalComponent,
    RepositoryModel,
    RepositoryRetrieval,
)


def test_model_rejects_evidence_from_another_commit():
    ref = EvidenceReference(path="src/app.py", start_line=1, end_line=2, commit_sha="old")
    # Evidence is constrained when attached to a claim.
    from app.services.repository_model import RepositoryClaim
    with pytest.raises(ValidationError):
        RepositoryModel(commit_sha="new", claims=[RepositoryClaim(text="x", state="confirmed", confidence=1, evidence=[ref])])


def test_retrieval_returns_exact_lines_and_rejects_path_escape(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("one\ntwo\nthree", encoding="utf-8")
    retrieval = RepositoryRetrieval(tmp_path)
    assert retrieval.read("src/app.py", 2, 2)["content"] == "two"
    assert retrieval.search("three")[0]["line"] == 3
    with pytest.raises(ValueError):
        retrieval.read("../outside")


def test_model_rejects_relationship_endpoints_that_do_not_exist():
    from app.services.repository_model import Relationship
    with pytest.raises(ValidationError):
        RepositoryModel(commit_sha="sha", components=[FunctionalComponent(name="A", responsibility="")],
                        relationships=[Relationship(source="A", target="B", kind="imports")])


def test_source_validation_rejects_wrong_excerpt_and_unsupported_claim(tmp_path):
    (tmp_path / "service.py").write_text("def hello():\n    return 'hello world'\n", encoding="utf-8")
    retrieval = RepositoryRetrieval(tmp_path)
    model = RepositoryModel(
        commit_sha="sha",
        claims=[
            {
                "text": "Service provisions cryptocurrency payouts",
                "subject": "payouts",
                "category": "feature",
                "target_name": "Payouts",
                "state": "inferred",
                "confidence": 0.9,
                "evidence": [{"path": "service.py", "start_line": 1, "end_line": 2, "commit_sha": "sha", "excerpt": "withdraw funds"}],
            }
        ],
    ).validate_sources(retrieval)
    assert model.claims[0].state == "rejected"
    assert model.evidence_issues


def test_source_validation_rejects_line_range_past_eof(tmp_path):
    from app.services.repository_model import RepositoryClaim

    (tmp_path / "one.py").write_text("value = 1\n", encoding="utf-8")
    model = RepositoryModel(commit_sha="sha", claims=[RepositoryClaim(
        text="value is one", state="confirmed", confidence=1,
        evidence=[EvidenceReference(path="one.py", start_line=1, end_line=3, commit_sha="sha", excerpt="value = 1")],
    )]).validate_sources(RepositoryRetrieval(tmp_path))
    assert model.claims[0].state == "rejected"
    assert "beyond end of file" in model.evidence_issues[0]


def test_confirmed_claim_requires_exact_cited_excerpt(tmp_path):
    from app.services.repository_model import RepositoryClaim

    (tmp_path / "one.py").write_text("def send_invoice():\n    return True\n", encoding="utf-8")
    model = RepositoryModel(commit_sha="sha", claims=[RepositoryClaim(
        text="send_invoice sends invoices", state="confirmed", confidence=1,
        evidence=[EvidenceReference(path="one.py", start_line=1, end_line=2, commit_sha="sha")],
    )]).validate_sources(RepositoryRetrieval(tmp_path))
    assert model.claims[0].state == "inferred"
    assert model.claims[0].confidence <= 0.65


def test_exact_excerpt_does_not_confirm_a_semantically_unsupported_claim(tmp_path):
    from app.services.repository_model import RepositoryClaim

    (tmp_path / "settings.py").write_text("redis queue = True\n", encoding="utf-8")
    model = RepositoryModel(commit_sha="sha", claims=[RepositoryClaim(
        text="Redis handles asynchronous queue processing for workers",
        state="confirmed", confidence=1,
        evidence=[EvidenceReference(
            path="settings.py", start_line=1, end_line=1,
            commit_sha="sha", excerpt="redis queue = True",
        )],
    )]).validate_sources(RepositoryRetrieval(tmp_path))

    assert model.claims[0].state == "inferred"
    assert model.claims[0].confidence <= 0.55


def test_generic_repository_boilerplate_is_not_confirmed_by_unrelated_evidence(tmp_path):
    from app.services.repository_model import RepositoryClaim

    (tmp_path / "README.md").write_text(
        "# Package\n\nInstall dependencies with npm install.\n", encoding="utf-8"
    )
    model = RepositoryModel(commit_sha="sha", claims=[RepositoryClaim(
        text=(
            "It brings the project files, documented purpose, and visible "
            "repository structure together into a usable product for users."
        ),
        subject="overview", category="overview", state="confirmed", confidence=1,
        evidence=[EvidenceReference(
            path="README.md", start_line=1, end_line=3, commit_sha="sha",
            excerpt="# Package\n\nInstall dependencies with npm install.",
        )],
    )]).validate_sources(RepositoryRetrieval(tmp_path))

    assert model.claims[0].state == "rejected"


def test_claim_without_references_remains_unknown(tmp_path):
    from app.services.repository_model import RepositoryClaim

    model = RepositoryModel(commit_sha="sha", claims=[RepositoryClaim(
        text="The app supports billing", state="confirmed", confidence=1,
    )]).validate_sources(RepositoryRetrieval(tmp_path))
    assert model.claims[0].state == "unknown"
    assert model.claims[0].confidence == 0


def test_model_preserves_and_downgrades_contradictory_claims(tmp_path):
    (tmp_path / "settings.py").write_text("redis_enabled = True\n", encoding="utf-8")
    retrieval = RepositoryRetrieval(tmp_path)
    ref = EvidenceReference(path="settings.py", start_line=1, end_line=1, commit_sha="sha")
    model = RepositoryModel(
        commit_sha="sha",
        claims=[
            {"text": "Redis is enabled", "subject": "redis enabled", "state": "inferred", "confidence": 0.9, "evidence": [ref]},
            {"text": "Redis is not enabled", "subject": "redis enabled", "state": "inferred", "confidence": 0.9, "evidence": [ref]},
        ],
    ).validate_sources(retrieval)
    assert len(model.claims) == 2
    assert model.contradictions
    assert all(claim.state == "inferred" and claim.confidence < 0.5 for claim in model.claims)


def test_readme_bytes_preserve_crlf_markdown_and_links(tmp_path):
    from app.services.github_service import GitHubService

    content = "# Title\r\n\r\n[Guide](docs/guide.md)\r\n\r\n```sh\r\necho hi\r\n```\r\n"
    path = tmp_path / "README.md"
    path.write_bytes(content.encode("utf-8"))
    assert GitHubService().find_readme(tmp_path) == content


def test_structural_retrieval_keeps_text_search_for_unknown_language(tmp_path):
    path = tmp_path / "notes.mystery"
    path.write_text("unsupported language marker", encoding="utf-8")
    retrieval = RepositoryRetrieval(tmp_path)
    assert retrieval.parse("notes.mystery")["parser"] == "text_fallback"
    assert retrieval.search("marker")[0]["text"] == "unsupported language marker"


def test_ripgrep_windows_drive_paths_are_parsed_without_full_scan(tmp_path, monkeypatch):
    import subprocess
    from app.services import repository_model

    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def find_order():\n    return 'order'\n", encoding="utf-8")
    output = f"{source}:2:    return 'order'\n"
    monkeypatch.setattr(repository_model.shutil, "which", lambda _: "rg.exe")
    monkeypatch.setattr(repository_model.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""))
    monkeypatch.setattr(RepositoryRetrieval, "inventory", lambda self: pytest.fail("search fell back to a full inventory scan"))

    result = RepositoryRetrieval(tmp_path).search("order")
    assert result[0]["path"] == "src/service.py"
    assert result[0]["line"] == 2


def test_tree_sitter_parser_extracts_symbols_imports_and_line_ranges(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    class Node:
        def __init__(self, kind, start, end, children=(), name=None):
            self.type, self.start_point, self.end_point = kind, SimpleNamespace(row=start - 1), SimpleNamespace(row=end - 1)
            self.named_children = list(children)
            self.children = self.named_children
            self.start_byte, self.end_byte = 0, 0
            self._name = name

        def child_by_field_name(self, field):
            return self._name if field == "name" else None

    source = b"import os\ndef run():\n    return os.getcwd()\n"
    imported = Node("import_statement", 1, 1)
    imported.start_byte, imported.end_byte = 0, 9
    identifier = Node("identifier", 2, 2)
    identifier.start_byte, identifier.end_byte = 14, 17
    function = Node("function_definition", 2, 3, name=identifier)
    function.start_byte, function.end_byte = 10, len(source)
    root = Node("module", 1, 3, [imported, function])
    root.start_byte, root.end_byte = 0, len(source)

    class FakeParser:
        def parse(self, _):
            return SimpleNamespace(root_node=root)

    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", SimpleNamespace(get_parser=lambda language: FakeParser()))
    (tmp_path / "service.py").write_bytes(source)
    parsed = RepositoryRetrieval(tmp_path).parse("service.py")
    assert parsed["parser"] == "tree_sitter"
    assert parsed["symbols"][0]["name"] == "run"
    assert parsed["symbols"][0]["start_line"] == 2
    assert parsed["imports"][0]["start_line"] == 1
