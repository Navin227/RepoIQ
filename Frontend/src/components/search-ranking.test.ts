import assert from 'node:assert/strict';
import test from 'node:test';
import { filterSearchResultsInBackendOrder, formatEvidenceReadiness, shouldShowEvidenceReadiness } from './search-ranking';

test('language filtering preserves backend ranking order', () => {
  const ranked = [
    { fullName: 'owner/relevant-ready', language: 'TypeScript' },
    { fullName: 'owner/topical-limited', language: 'Python' },
    { fullName: 'owner/next-ready', language: 'TypeScript' },
  ];
  assert.deepEqual(
    filterSearchResultsInBackendOrder(ranked as any, repo => repo.language === 'TypeScript')
      .map(repo => repo.fullName),
    ['owner/relevant-ready', 'owner/next-ready'],
  );
});

test('readiness labels distinguish missing metadata and failed inspection', () => {
  assert.equal(formatEvidenceReadiness('ready', 'inspected'), 'ready');
  assert.equal(formatEvidenceReadiness(undefined, 'inspected'), 'not assessed');
  assert.equal(formatEvidenceReadiness('unknown', 'not_inspected'), 'unknown (tree not inspected)');
  assert.equal(formatEvidenceReadiness('unknown', 'inspection_failed'), 'unknown (tree inspection failed)');
  assert.equal(formatEvidenceReadiness('not_assessed', 'not_assessed'), 'not assessed');
});

test('search hides evidence badges without assessed evidence', () => {
  assert.equal(shouldShowEvidenceReadiness(undefined, 'inspected'), false);
  assert.equal(shouldShowEvidenceReadiness('not_assessed', 'not_assessed'), false);
  assert.equal(shouldShowEvidenceReadiness('unknown', 'inspection_failed'), true);
  assert.equal(shouldShowEvidenceReadiness('ready', 'inspected'), true);
});
