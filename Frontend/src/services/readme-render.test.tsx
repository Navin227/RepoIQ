import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { RepositoryReadme } from '../components/RepositoryReadme';
import type { Repository } from '../types';

test('README renders Markdown and rewrites relative links to the pinned repository revision', () => {
  const repo = {
    url: 'https://github.com/acme/catalog',
    commitSha: 'c0ffee',
    readmePath: 'docs/README.md',
    readme: '# Catalog\n\n[Guide](../guide.md)\n\n| name | value |\n| --- | --- |\n| item | one |\n',
  } as Repository;
  const html = renderToStaticMarkup(React.createElement(RepositoryReadme, { repo }));
  assert.match(html, /<h1>Catalog<\/h1>/);
  assert.match(html, /href="https:\/\/github.com\/acme\/catalog\/blob\/c0ffee\/guide.md"/);
  assert.match(html, /<table>/);
});

test('README HTML is escaped rather than executed', () => {
  const repo = { url: 'https://github.com/acme/catalog', readme: '<script>alert(1)</script>' } as Repository;
  const html = renderToStaticMarkup(React.createElement(RepositoryReadme, { repo }));
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});
