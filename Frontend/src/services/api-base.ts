export interface ApiBaseContext {
  configuredApiBase?: string | null;
  runtimeApiBase?: string | null;
  pageOrigin: string;
}

export function resolveApiBase({
  configuredApiBase,
  runtimeApiBase,
  pageOrigin,
}: ApiBaseContext): string {
  const configured = configuredApiBase?.trim();
  const runtime = runtimeApiBase?.trim();
  const candidateValue = configured || runtime;

  if (!candidateValue) {
    if (new URL(pageOrigin).protocol === 'https:') {
      throw new Error(
        'RepoIQ HTTPS API is not configured. Set VITE_API_BASE_URL in the Amplify app to the HTTPS API endpoint.'
      );
    }
    return '';
  }

  try {
    const pageUrl = new URL(pageOrigin);
    const url = new URL(candidateValue.replace(/\/+$/, ''), pageUrl.origin);
    const isLocalBrowser =
      pageUrl.hostname === 'localhost' ||
      pageUrl.hostname === '127.0.0.1';
    const isLocalCandidate =
      url.hostname === 'localhost' ||
      url.hostname === '127.0.0.1';

    if (!['http:', 'https:'].includes(url.protocol)) {
      throw new Error('The API URL must use HTTP or HTTPS.');
    }
    if (url.username || url.password || url.search || url.hash) {
      throw new Error('The API base URL must not contain credentials, a query, or a fragment.');
    }
    if (url.pathname !== '/') {
      throw new Error('Set VITE_API_BASE_URL to the API origin only, without a path.');
    }
    if (isLocalCandidate && !isLocalBrowser) {
      throw new Error('A deployed frontend cannot use a localhost API URL.');
    }
    if (pageUrl.protocol === 'https:' && url.protocol !== 'https:') {
      throw new Error(
        'Mixed-content configuration: this HTTPS page received an HTTP backend URL. ' +
        'Set VITE_API_BASE_URL in the Amplify app to the HTTPS API endpoint.'
      );
    }
    if (isLocalCandidate && isLocalBrowser) {
      return url.toString().replace(/\/$/, '');
    }
    if (url.port === '8000') {
      url.port = '';
    }
    return url.toString().replace(/\/$/, '');
  } catch (error) {
    if (error instanceof Error && error.message.startsWith('Mixed-content configuration:')) {
      throw error;
    }
    throw new Error(
      `Invalid RepoIQ API URL configuration: ${
        error instanceof Error ? error.message : 'could not parse the API base URL'
      }`
    );
  }
}

export function buildSearchRequestUrl(apiBase: string, normalizedQuery: string): string {
  return `${apiBase}/search?q=${encodeURIComponent(normalizedQuery)}`;
}
