import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildSearchRequestUrl,
  resolveApiBase,
} from './api-base';

test('configured HTTPS API takes precedence over runtime HTTP application URL', () => {
  assert.equal(
    resolveApiBase({
      configuredApiBase: 'https://api.example.test/',
      runtimeApiBase: 'http://203.0.113.12',
      pageOrigin: 'https://main.example.test',
    }),
    'https://api.example.test',
  );
});

test('runtime HTTPS API is used when no explicit endpoint is configured', () => {
  assert.equal(
    resolveApiBase({
      runtimeApiBase: 'https://api.example.test',
      pageOrigin: 'https://main.example.test',
    }),
    'https://api.example.test',
  );
});

test('configured Lambda Function URL is resolved as the production API origin', () => {
  assert.equal(
    resolveApiBase({
      configuredApiBase: 'https://abc123.lambda-url.ap-south-1.on.aws/',
      runtimeApiBase: 'http://203.0.113.12',
      pageOrigin: 'https://main.d20r18yhh140ff.amplifyapp.com',
    }),
    'https://abc123.lambda-url.ap-south-1.on.aws',
  );
});

test('HTTPS frontend rejects HTTP runtime URL instead of falling back to it', () => {
  assert.throws(
    () => resolveApiBase({
      runtimeApiBase: 'http://203.0.113.12',
      pageOrigin: 'https://main.example.test',
    }),
    /Mixed-content configuration/,
  );
});

test('invalid configured HTTP endpoint does not silently use runtime HTTPS URL', () => {
  assert.throws(
    () => resolveApiBase({
      configuredApiBase: 'http://api.example.test',
      runtimeApiBase: 'https://runtime.example.test',
      pageOrigin: 'https://main.example.test',
    }),
    /Mixed-content configuration/,
  );
});

test('HTTPS frontend reports missing API config when no runtime URL exists', () => {
  assert.throws(
    () => resolveApiBase({ pageOrigin: 'https://main.example.test' }),
    /VITE_API_BASE_URL/,
  );
});

test('search request uses resolved base and URL-encodes normalized query', () => {
  const base = resolveApiBase({
    configuredApiBase: 'https://api.example.test',
    runtimeApiBase: 'http://203.0.113.12',
    pageOrigin: 'https://main.example.test',
  });

  assert.equal(
    buildSearchRequestUrl(base, 'healthcare platforms & clinics'),
    'https://api.example.test/search?q=healthcare%20platforms%20%26%20clinics',
  );
});

test('local development can use the runtime backend on port 8000', () => {
  assert.equal(
    resolveApiBase({
      runtimeApiBase: 'http://localhost:8000/',
      pageOrigin: 'http://localhost:3000',
    }),
    'http://localhost:8000',
  );
});
