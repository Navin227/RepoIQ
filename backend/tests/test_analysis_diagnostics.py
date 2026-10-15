import json
import logging

import pytest

from app.services.analysis_diagnostics import emit, run_context, stage


def test_diagnostic_events_carry_run_id_and_redact_secrets(caplog):
    logger = logging.getLogger("repoiq.test.diagnostics")
    caplog.set_level(logging.INFO, logger=logger.name)

    with run_context("run_test_123"):
        emit(logger, "test_event", stage="evidence_validation", api_key="super-secret-api-key",
             reason="password=hunter2", repository_url="https://user:repo-pass@github.com/acme/private",
             claim_count=3)

    record = next(item for item in caplog.records if item.name == logger.name)
    payload = json.loads(record.message)
    assert payload["analysis_run_id"] == "run_test_123"
    assert payload["stage"] == "evidence_validation"
    assert payload["claim_count"] == 3
    assert "super-secret-api-key" not in caplog.text
    assert "hunter2" not in caplog.text
    assert "repo-pass" not in caplog.text


def test_failed_stage_logs_stage_and_exception_context(caplog):
    logger = logging.getLogger("repoiq.test.stage")
    caplog.set_level(logging.INFO, logger=logger.name)

    with run_context("run_failure_456"):
        with pytest.raises(RuntimeError, match="parse exploded"):
            with stage(logger, "llm_response_parse", repository="acme/repo"):
                raise RuntimeError("parse exploded")

    failure = next(json.loads(item.message) for item in caplog.records
                   if item.name == logger.name and '"event":"stage_failed"' in item.message)
    record = next(item for item in caplog.records
                  if item.name == logger.name and '"event":"stage_failed"' in item.message)
    assert failure["analysis_run_id"] == "run_failure_456"
    assert failure["stage"] == "llm_response_parse"
    assert failure["exception_type"] == "RuntimeError"
    assert failure["reason"] == "parse exploded"
    assert "traceback" in failure
    assert "parse exploded" in failure["traceback"]


def test_run_context_is_isolated_between_analyses(caplog):
    logger = logging.getLogger("repoiq.test.concurrent")
    caplog.set_level(logging.INFO, logger=logger.name)
    with run_context("run_a"):
        emit(logger, "first")
    with run_context("run_b"):
        emit(logger, "second")
    payloads = [json.loads(item.message) for item in caplog.records if item.name == logger.name]
    assert [payload["analysis_run_id"] for payload in payloads] == ["run_a", "run_b"]
