import assert from 'node:assert/strict';
import test from 'node:test';
import { filterSearchResultsInBackendOrder } from './search-ranking';

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
