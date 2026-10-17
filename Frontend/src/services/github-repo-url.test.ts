import assert from 'node:assert/strict';
import test from 'node:test';

import { getSavedRepositoryAnalysisUrl, normalizeGitHubRepoInput } from './github-repo-url';

test('saved repository identifiers become canonical GitHub URLs for known entries', () => {
  for (const fullName of ['vercel/next.js', 'navin227/gofilecloud', 'idealo/imagededup']) {
    assert.equal(
      getSavedRepositoryAnalysisUrl({ fullName }),
      `https://github.com/${fullName}`,
    );
  }
});

test('saved repository full URLs stay canonical and extra URL path/query data is removed', () => {
  assert.equal(
    getSavedRepositoryAnalysisUrl({
      fullName: 'vercel/next.js',
      url: 'https://www.github.com/vercel/next.js/tree/canary?tab=readme',
    }),
    'https://github.com/vercel/next.js',
  );
});

test('normalizer does not convert arbitrary invalid values into GitHub URLs', () => {
  assert.equal(normalizeGitHubRepoInput('not a repository'), 'not a repository');
});
