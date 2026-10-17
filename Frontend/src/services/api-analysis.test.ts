import assert from 'node:assert/strict';
import test from 'node:test';

import { analyzeRepository } from './api';
import { getSavedRepositoryAnalysisUrl } from './github-repo-url';

const successResponse = {
  status: 'success',
  analysis_run_id: 'run-123',
  repo_name: 'vercel/next.js',
  repo_url: 'https://github.com/vercel/next.js',
  analysis_status: 'complete',
  commit_sha: 'abc123',
  overview: 'A saved repository overview.',
  repository_model: { commit_sha: 'abc123', claims: [] },
  modules: [],
  analysis_evidence: {},
};

async function withFetchResponse(body: unknown, run: () => Promise<void>) {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let requestBody: Record<string, unknown> | undefined;
  globalThis.window = {
    location: { origin: 'https://repoiq.example.test' },
    localStorage: { getItem: () => null },
  } as unknown as Window & typeof globalThis;
  globalThis.fetch = async (_input, init) => {
    requestBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };
  try {
    await run();
    return requestBody;
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) globalThis.window = originalWindow;
    else Reflect.deleteProperty(globalThis, 'window');
  }
}

test('analysis request preserves fields and sends a normalized saved repository URL', async () => {
  const repositories: Array<[ { fullName: string; url?: string }, string ]> = [
    [{ fullName: 'vercel/next.js' }, 'https://github.com/vercel/next.js'],
    [{ fullName: 'navin227/gofilecloud' }, 'https://github.com/navin227/gofilecloud'],
    [{ fullName: 'idealo/imagededup' }, 'https://github.com/idealo/imagededup'],
    [{ fullName: 'vercel/next.js', url: 'https://github.com/vercel/next.js' }, 'https://github.com/vercel/next.js'],
  ];
  for (const [repository, expectedUrl] of repositories) {
    const requestBody = await withFetchResponse(successResponse, async () => {
      const result = await analyzeRepository(
        {
          repo_url: getSavedRepositoryAnalysisUrl(repository),
          analysis_run_id: 'run-123',
        },
        'https://api.example.test',
      );
      assert.equal(result.status, 'success');
      assert.equal(result.analysis_status, 'complete');
      assert.equal(result.commit_sha, 'abc123');
      assert.deepEqual(result.repository_model, { commit_sha: 'abc123', claims: [] });
    });
    assert.equal(requestBody?.repo_url, expectedUrl);
    assert.equal(requestBody?.analysis_run_id, 'run-123');
  }
});

test('HTTP 200 application error is returned as a failure with its actual reason', async () => {
  await withFetchResponse({ error: 'Invalid GitHub repository URL' }, async () => {
    const result = await analyzeRepository(
      { repo_url: 'vercel/next.js', analysis_run_id: 'run-123' },
      'https://api.example.test',
    );
    assert.equal(result.status, 'error');
    assert.equal(result.error, 'Invalid GitHub repository URL');
  });
});

test('HTTP 200 success without required analysis metadata is rejected', async () => {
  await withFetchResponse({ status: 'success', overview: 'Looks done.' }, async () => {
    const result = await analyzeRepository(
      { repo_url: 'https://github.com/vercel/next.js', analysis_run_id: 'run-123' },
      'https://api.example.test',
    );
    assert.equal(result.status, 'error');
    assert.match(result.error || '', /analysis_status, repository_model, commit_sha/);
  });
});
