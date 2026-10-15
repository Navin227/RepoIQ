import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeTerminalAnalysisStatus } from './analysis-status';

test('useful legacy report with missing commit SHA stays visible as partial', () => {
  assert.equal(normalizeTerminalAnalysisStatus({
    backendStatus: 'failed', hasUsefulOutput: true,
    hasValidationMetadata: false, requiredStageFailed: false,
  }), 'partial');
});

test('a diagnosed provider failure remains failed even if partial output exists', () => {
  assert.equal(normalizeTerminalAnalysisStatus({
    backendStatus: 'failed', hasUsefulOutput: true,
    hasValidationMetadata: false, requiredStageFailed: true,
  }), 'failed');
});

test('a backend failure with complete validation metadata remains failed', () => {
  assert.equal(normalizeTerminalAnalysisStatus({
    backendStatus: 'failed', hasUsefulOutput: true,
    hasValidationMetadata: true, requiredStageFailed: false,
  }), 'failed');
});

test('complete output without its evidence model is downgraded to partial, not failed', () => {
  assert.equal(normalizeTerminalAnalysisStatus({
    backendStatus: 'complete', hasUsefulOutput: true,
    hasValidationMetadata: false, requiredStageFailed: false,
  }), 'partial');
});

test('an empty response without a recognized terminal status remains failed', () => {
  assert.equal(normalizeTerminalAnalysisStatus({
    hasUsefulOutput: false, hasValidationMetadata: false, requiredStageFailed: false,
  }), 'failed');
});
