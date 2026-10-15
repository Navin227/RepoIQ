import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveReadmeLink } from './readme-links';

test('relative README links resolve from a nested README at its pinned commit', () => {
  assert.equal(resolveReadmeLink('https://github.com/acme/project', 'abc123', 'docs/README.md', '../guide.md#setup'), 'https://github.com/acme/project/blob/abc123/guide.md#setup');
});

test('relative images use the raw URL at the same pinned commit', () => {
  assert.equal(resolveReadmeLink('https://github.com/acme/project', 'abc123', 'docs/README.md', 'assets/flow.svg', true), 'https://raw.githubusercontent.com/acme/project/abc123/docs/assets/flow.svg');
});

test('external and anchor README links remain unchanged', () => {
  assert.equal(resolveReadmeLink('https://github.com/acme/project', 'abc123', 'README.md', 'https://example.org/a'), 'https://example.org/a');
  assert.equal(resolveReadmeLink('https://github.com/acme/project', 'abc123', 'README.md', '#usage'), '#usage');
});
