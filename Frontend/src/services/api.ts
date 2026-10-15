import type {
  AnalysisResult,
  ArchitectureAnalysis,
  BusinessModule,
  ExecutiveOverview,
  FileTreeNode,
  SimilarRepo,
  TechStack,
} from '../types';
import {
  buildSearchRequestUrl,
  getDevelopmentApiBaseOverride,
  resolveApiBase,
  usesDevelopmentApiBaseOverride,
} from './api-base';

class ApiNetworkError extends Error {
  constructor(operation: string, url: string) {
    const safeUrl = new URL(url).origin;
    super(
      `${operation} could not reach the RepoIQ API at ${safeUrl}. ` +
      'Check that the endpoint is deployed, DNS and TLS are valid, and backend CORS allows this Amplify origin.'
    );
    this.name = 'ApiNetworkError';
  }
}

const fetchWithDefensiveRetry = async (
  url: string,
  options: RequestInit | undefined,
  operation: string,
  onRetry?: (attempt: number, error: unknown) => void,
) => {
  const MAX_ATTEMPTS = 3;
  const RETRY_DELAY_MS = 1000;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const requestOptions = usesDevelopmentApiBaseOverride()
        ? { ...options, credentials: 'include' as const }
        : options;
      return await fetch(url, requestOptions);
    } catch (error) {
      if (attempt === MAX_ATTEMPTS) {
        if (error instanceof TypeError) {
          throw new ApiNetworkError(operation, url);
        }
        throw error;
      }

      if (onRetry) onRetry(attempt, error);
      else console.warn(
        `[RepoIQ] ${operation} transient network error (attempt ${attempt}/${MAX_ATTEMPTS}); retrying shortly.`
      );

      await new Promise(resolve =>
        window.setTimeout(resolve, RETRY_DELAY_MS)
      );
    }
  }

  throw new Error(`${operation} failed after defensive retry.`);
};

// ---------------------------------------------------------------------------
// Lightweight query normalization + domain expansion
// ---------------------------------------------------------------------------

/**
 * Domain synonym map: maps a normalized term to a list of related terms.
 * Used to expand the user query before sending to GitHub search, and also
 * for local relevance scoring of returned results.
 */
const DOMAIN_SYNONYMS: Record<string, string[]> = {
  // E-commerce
  'ecommerce': ['e-commerce', 'ecommerce', 'online store', 'shopping', 'marketplace', 'shop', 'retail', 'cart', 'checkout', 'commerce', 'storefront', 'product catalog', 'order management', 'payment'],
  'e-commerce': ['e-commerce', 'ecommerce', 'online store', 'shopping', 'marketplace', 'shop', 'retail', 'cart', 'checkout', 'commerce', 'storefront'],
  'shop': ['shop', 'store', 'ecommerce', 'e-commerce', 'marketplace', 'retail', 'shopping'],
  'store': ['store', 'shop', 'ecommerce', 'e-commerce', 'marketplace', 'retail'],
  'marketplace': ['marketplace', 'ecommerce', 'e-commerce', 'shop', 'platform', 'store', 'trading'],
  'shopping': ['shopping', 'ecommerce', 'e-commerce', 'shop', 'store', 'cart', 'checkout'],
  'cart': ['cart', 'shopping', 'ecommerce', 'checkout', 'basket'],
  'checkout': ['checkout', 'payment', 'cart', 'ecommerce', 'stripe'],
  'retail': ['retail', 'ecommerce', 'shop', 'store', 'commerce'],

  // Machine learning / AI
  'machine learning': ['machine-learning', 'ml', 'deep learning', 'neural network', 'ai', 'artificial intelligence', 'model', 'training', 'inference', 'pytorch', 'tensorflow', 'sklearn'],
  'ml': ['machine learning', 'machine-learning', 'deep learning', 'ai', 'neural network', 'model'],
  'deep learning': ['deep-learning', 'neural network', 'ml', 'machine learning', 'pytorch', 'tensorflow', 'ai'],
  'ai': ['artificial intelligence', 'machine learning', 'ml', 'deep learning', 'llm', 'neural network', 'nlp'],
  'llm': ['llm', 'language model', 'gpt', 'ai', 'nlp', 'transformer', 'chatbot'],
  'neural network': ['neural-network', 'deep learning', 'ml', 'machine learning', 'pytorch', 'tensorflow'],

  // Chat / messaging
  'chat': ['chat', 'messaging', 'realtime', 'chatroom', 'instant messaging', 'websocket', 'communication'],
  'chat app': ['chat', 'messaging', 'realtime', 'chatroom', 'instant messaging', 'websocket', 'communication'],
  'messaging': ['messaging', 'chat', 'realtime', 'chatroom', 'websocket', 'sms', 'communication'],
  'realtime': ['realtime', 'real-time', 'websocket', 'chat', 'live', 'streaming', 'socket.io'],
  'communication': ['communication', 'chat', 'messaging', 'realtime', 'collaboration'],

  // Portfolio / personal website
  'portfolio': ['portfolio', 'personal website', 'personal site', 'resume', 'cv', 'showcase', 'profile', 'landing page'],
  'personal website': ['portfolio', 'personal site', 'resume', 'showcase', 'landing page', 'blog'],
  'landing page': ['landing-page', 'portfolio', 'personal website', 'showcase', 'homepage'],

  // DevOps / infrastructure
  'devops': ['devops', 'ci/cd', 'infrastructure', 'kubernetes', 'docker', 'deployment', 'automation', 'pipeline'],
  'kubernetes': ['kubernetes', 'k8s', 'container orchestration', 'devops', 'helm', 'kubectl'],
  'docker': ['docker', 'container', 'kubernetes', 'devops', 'compose', 'dockerfile'],
  'infrastructure': ['infrastructure', 'devops', 'cloud', 'aws', 'terraform', 'kubernetes', 'docker'],

  // File sharing / storage
  'file sharing': ['file-sharing', 'file upload', 'cloud storage', 'file manager', 'storage', 's3', 'drive'],
  'file upload': ['file-upload', 'file sharing', 'storage', 'cloud', 'media upload'],
  'storage': ['storage', 'file sharing', 'cloud storage', 's3', 'drive', 'database'],

  // Dashboard / analytics
  'dashboard': ['dashboard', 'analytics', 'admin panel', 'metrics', 'visualization', 'charts', 'reporting'],
  'analytics': ['analytics', 'dashboard', 'metrics', 'reporting', 'data visualization', 'charts', 'tracking'],
  'admin': ['admin', 'dashboard', 'admin panel', 'management', 'backend', 'cms'],

  // Blog / CMS
  'blog': ['blog', 'cms', 'content management', 'publishing', 'markdown', 'articles'],
  'cms': ['cms', 'content management', 'blog', 'wordpress', 'headless', 'publishing'],

  // Social / community
  'social': ['social', 'community', 'social network', 'feed', 'followers', 'posts', 'profile'],
  'social media': ['social-media', 'social network', 'community', 'feed', 'posts', 'followers'],
  'community': ['community', 'social', 'forum', 'discussion', 'collaboration'],

  // SaaS / business tools
  'saas': ['saas', 'software as a service', 'subscription', 'multi-tenant', 'platform'],
  'crm': ['crm', 'customer relationship', 'sales', 'leads', 'customers', 'business'],
  'erp': ['erp', 'enterprise', 'business', 'management', 'inventory', 'accounting'],

  // Authentication / security
  'auth': ['auth', 'authentication', 'authorization', 'login', 'oauth', 'jwt', 'sso'],
  'authentication': ['authentication', 'auth', 'login', 'oauth', 'jwt', 'security', 'identity'],

  // API / backend
  'api': ['api', 'rest', 'graphql', 'backend', 'server', 'microservices', 'endpoint'],
  'rest api': ['rest-api', 'api', 'backend', 'server', 'microservices', 'graphql'],
  'graphql': ['graphql', 'api', 'query', 'schema', 'backend'],
  'microservices': ['microservices', 'microservice', 'api', 'backend', 'distributed', 'services'],
};

/**
 * Normalize the raw user query:
 * - Trim whitespace
 * - Lowercase
 * - Collapse multiple spaces
 * - Remove hyphenation variations (e-commerce → ecommerce for matching purposes)
 */
function normalizeQuery(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    // Do NOT strip hyphens entirely - keep 'e-commerce' as-is for GitHub
    ;
}

/**
 * Expand the user's query into a list of semantically related terms
 * by consulting the domain synonym map. Returns the original normalized
 * tokens plus any synonym expansions found.
 *
 * This is used for local relevance scoring only — we do NOT stuff all
 * expansions into the GitHub query string (that would degrade recall).
 */
function getQueryExpansion(normalizedQuery: string): string[] {
  const tokens = normalizedQuery
    .split(/[\s,]+/)
    .map(t => t.trim())
    .filter(Boolean);

  const expanded = new Set<string>([normalizedQuery]);

  // Also add the query with hyphens removed (e-commerce → ecommerce)
  const dehyphenated = normalizedQuery.replace(/-/g, '');
  if (dehyphenated !== normalizedQuery) expanded.add(dehyphenated);

  // Add singular/plural trivial forms
  for (const tok of tokens) {
    expanded.add(tok);
    // Singular → try stripping trailing s
    if (tok.endsWith('s') && tok.length > 3) expanded.add(tok.slice(0, -1));
    // Plural → try adding s
    expanded.add(tok + 's');
  }

  // Check multi-word and single-word synonyms
  for (const [key, synonyms] of Object.entries(DOMAIN_SYNONYMS)) {
    const keyTokens = key.split(/[\s-]+/).join(' ');
    const queryTokens = normalizedQuery.split(/[\s-]+/).join(' ');

    if (
      queryTokens.includes(keyTokens) ||
      keyTokens.includes(queryTokens) ||
      // Also check if any single token matches
      tokens.some(t => key.split(/[\s-]+/).includes(t))
    ) {
      synonyms.forEach(s => expanded.add(s));
    }
  }

  return Array.from(expanded);
}

/**
 * Compose a GitHub-compatible search query from the raw user input.
 * We send the normalized query to GitHub, potentially with a limited
 * set of OR-expanded terms to improve recall (but keep it short).
 */
function buildGitHubQuery(rawQuery: string): string {
  const normalized = normalizeQuery(rawQuery);

  // For GitHub, try to add the most common alternative form if the query
  // has a spacing/hyphen variant (e.g. "e commerce" → also include "ecommerce")
  const dehyphenated = normalized.replace(/\s+/g, '').replace(/-/g, '');
  const hyphenated = normalized.replace(/\s+/g, '-');

  const variants = new Set<string>([normalized]);
  if (dehyphenated !== normalized) variants.add(dehyphenated);
  if (hyphenated !== normalized) variants.add(hyphenated);

  // Use the original normalized query as the primary term; GitHub's own
  // fuzzy matching handles most variations. Only add 1-2 explicit OR
  // terms if we have well-known synonyms.
  const synonymSet = new Set<string>();
  for (const [key, synonyms] of Object.entries(DOMAIN_SYNONYMS)) {
    if (normalized.includes(key) || key.includes(normalized) || dehyphenated === key.replace(/\s+/g, '').replace(/-/g, '')) {
      // Add only the 2 most relevant synonym variants to keep query clean
      synonyms.slice(0, 2).forEach(s => synonymSet.add(s));
    }
  }

  // Build final query: original + up to 2 high-value synonyms
  const queryParts = [normalized];
  let added = 0;
  for (const syn of synonymSet) {
    if (syn !== normalized && !variants.has(syn) && added < 2) {
      queryParts.push(syn);
      added++;
    }
  }

  return queryParts.join(' OR ');
}

/**
 * Score a single repository against the user's expanded query terms.
 * Higher score = more relevant.
 *
 * Scoring factors (relevance-first, stars/forks are secondary):
 * - Repository name match: +8 per matching term (exact), +4 (partial)
 * - Description match: +5 per matching term (exact), +2 (partial)
 * - Topic match: +10 per matching topic (exact), +5 (partial)
 * - Language relevance: +3 if language is mentioned in query
 * - Stars: log-scale secondary signal (max +3 added to base score)
 */
function scoreRepository(repo: SimilarRepo, expandedTerms: string[]): number {
  const name = (repo.fullName ?? '').toLowerCase();
  const desc = (repo.description ?? '').toLowerCase();
  const topics = (repo.topics ?? []).map(t => t.toLowerCase());
  const lang = (repo.language ?? '').toLowerCase();

  let score = 0;

  for (const term of expandedTerms) {
    if (!term || term.length < 2) continue;

    // Name
    if (name.includes(term)) {
      score += name === term || name.endsWith('/' + term) ? 8 : 6;
    }

    // Description
    const descWords = desc.split(/[\s\-_/,.]+/);
    if (desc.includes(term)) {
      score += descWords.some(w => w === term) ? 5 : 2;
    }

    // Topics — highest weight because they are curated signals
    for (const topic of topics) {
      if (topic === term) {
        score += 10;
      } else if (topic.includes(term) || term.includes(topic)) {
        score += 5;
      }
    }

    // Language
    if (lang === term || lang.includes(term)) {
      score += 3;
    }
  }

  // Secondary: logarithmic star signal (avoids pure popularity sorting)
  const stars = typeof repo.stars === 'number' ? repo.stars : 0;
  const starBonus = stars > 0 ? Math.min(3, Math.log10(stars + 1)) : 0;
  score += starBonus;

  return score;
}

function normalizeSearchRepository(value: unknown): SimilarRepo {
  const repo =
    typeof value === 'object' && value !== null && !Array.isArray(value)
      ? value as Record<string, unknown>
      : {};
  const asString = (field: unknown) => String(field ?? '');
  const name = asString(repo.name);
  const owner = asString(repo.owner);
  const fullName =
    asString(repo.fullName) ||
    asString(repo.full_name) ||
    [owner, name].filter(Boolean).join('/');
  const fullNameParts = fullName.split('/');
  const stars = Number(repo.stars ?? repo.stargazers_count);
  const forks = Number(repo.forks ?? repo.forks_count);

  return {
    name: name || fullNameParts[fullNameParts.length - 1] || '',
    owner: owner || fullNameParts.slice(0, -1).join('/'),
    fullName,
    full_name: asString(repo.full_name) || fullName,
    description: asString(repo.description),
    url: asString(repo.url),
    html_url: asString(repo.html_url),
    language: asString(repo.language),
    topics: Array.isArray(repo.topics)
      ? repo.topics.map(asString)
      : [],
    stars: Number.isFinite(stars) ? stars : 0,
    forks: Number.isFinite(forks) ? forks : 0,
    relevance_score: typeof repo.relevance_score === 'number' && Number.isFinite(repo.relevance_score)
      ? repo.relevance_score
      : undefined,
    analyzability_score: repo.analyzability_score === null
      ? null
      : typeof repo.analyzability_score === 'number' && Number.isFinite(repo.analyzability_score)
        ? repo.analyzability_score
      : undefined,
    ranking_score: repo.ranking_score === null
      ? null
      : typeof repo.ranking_score === 'number' && Number.isFinite(repo.ranking_score)
        ? repo.ranking_score
      : undefined,
    tree_inspection_state: asString(repo.tree_inspection_state),
    tree_truncated: typeof repo.tree_truncated === 'boolean' ? repo.tree_truncated : undefined,
    evidence_readiness: asString(repo.evidence_readiness),
    readiness_reason: asString(repo.readiness_reason),
    repository_type: asString(repo.repository_type),
    inspected_file_count: typeof repo.inspected_file_count === 'number' ? repo.inspected_file_count : undefined,
    tree_reported_file_count: typeof repo.tree_reported_file_count === 'number' ? repo.tree_reported_file_count : undefined,
    meaningful_source_file_count: typeof repo.meaningful_source_file_count === 'number' ? repo.meaningful_source_file_count : undefined,
  };
}

// ---------------------------------------------------------------------------
// Exported API functions
// ---------------------------------------------------------------------------

export interface AnalyzeRepositoryRequest {
  repo_url?: string;
  local_path?: string;
  analysis_run_id?: string;
}

export interface AnalyzeRepositoryResponse {
  status: 'success' | 'error';
  analysis_run_id?: string;
  error_code?: string;
  repo_name?: string;
  repo_url?: string;
  local_path?: string;
  readme?: string;
  readme_path?: string;
  stack?: {
    categories?: Partial<TechStack>;
    flat?: TechStack;
    languages?: string[];
  };
  folder_structure?: FileTreeNode[];
  languages?: string[];
  overview?: string;
  executive_overview?: ExecutiveOverview;
  architecture?: ArchitectureAnalysis;
  architecture_summary?: string;
  modules?: BusinessModule[];
  analysis_evidence?: Record<string, unknown>;
  analysis_status?: string;
  commit_sha?: string;
  repository_model?: Record<string, unknown>;
  coverage_manifest?: Record<string, unknown>;
  report_sections?: Record<string, unknown>;
  ai_insights?: string[];
  similar_repositories?: SimilarRepo[];
  message?: string;
}

function sanitizeAnalysisLog(value: unknown, depth = 0): unknown {
  if (depth > 5) return '[nested value omitted]';
  if (typeof value === 'string') {
    return value
      .replace(/(Bearer\s+)[A-Za-z0-9._~+/-]+=*/gi, '$1[REDACTED]')
      .replace(/AIza[0-9A-Za-z_-]{20,}/g, '[REDACTED_API_KEY]')
      .replace(/\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/g, '[REDACTED_TOKEN]')
      .slice(0, 1200);
  }
  if (Array.isArray(value)) {
    return value.slice(0, 24).map(item => sanitizeAnalysisLog(item, depth + 1));
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).slice(0, 48).map(([key, item]) =>
      /api.?key|authorization|secret|password|credential/i.test(key)
        ? [key, '[REDACTED]']
        : [key, sanitizeAnalysisLog(item, depth + 1)]
    ));
  }
  return value;
}

function normalizeAiInsights(result: Partial<AnalyzeRepositoryResponse>): string[] {
  const explicit = Array.isArray(result.ai_insights)
    ? result.ai_insights.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];

  if (explicit.length > 0) {
    return explicit;
  }

  const executive = result.executive_overview;
  const featureNames = Array.isArray(executive?.user_features)
    ? executive.user_features
        .map((feature) => {
          const record = (feature ?? {}) as Record<string, unknown>;
          const name = typeof record.name === 'string' ? record.name.trim() : '';
          return name;
        })
        .filter((name): name is string => name.length > 0)
    : [];

  if (featureNames.length > 0) {
    return featureNames;
  }

  const moduleNames = Array.isArray(result.modules)
    ? result.modules
        .map((module) => (module && typeof module.name === 'string' ? module.name : ''))
        .filter((name): name is string => Boolean(name && name.trim().length > 0))
    : [];

  return moduleNames.slice(0, 10);
}

export async function searchRepositories(
  query: string,
  runtimeApiBase?: string | null
): Promise<SimilarRepo[]> {
  console.log('🔍 [API] Requesting search:', query);

  const apiBase = resolveApiBase({
    configuredApiBase: import.meta.env.VITE_API_BASE_URL,
    runtimeApiBase,
    developmentApiBase: getDevelopmentApiBaseOverride(),
    pageOrigin: window.location.origin,
  });

  if (!apiBase) {
    throw new Error(
      'RepoIQ API URL is unavailable. Configure a backend API endpoint first.'
    );
  }

  // The backend owns concept expansion and ranking so it can use repository evidence.
  const normalizedQuery = normalizeQuery(query);
  console.log('[RepoIQ] Query normalization:', { original: query, normalized: normalizedQuery });

  try {
    const url = buildSearchRequestUrl(apiBase, normalizedQuery);

    const response = await fetchWithDefensiveRetry(
      url,
      { cache: 'no-store' },
      'Search'
    );

    if (!response.ok) {
      throw new Error(
        `Search failed: RepoIQ API returned HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}.`
      );
    }

    const responseData: unknown = await response.json();
    if (!Array.isArray(responseData)) {
      throw new Error('Search returned an invalid repository list');
    }
    const data = responseData.map(normalizeSearchRepository);

    console.log('✅ [API] Search response ranked by repository evidence:', data);
    return data;
  } catch (error) {
    console.error('❌ [API] Search error:', error);
    throw error instanceof Error
      ? error
      : new Error('Failed to search repositories');
  }
}

export async function analyzeRepository(
  data: AnalyzeRepositoryRequest,
  runtimeApiBase?: string | null
): Promise<AnalysisResult> {
  const runId = data.analysis_run_id || crypto.randomUUID();
  const requestStarted = performance.now();
  const safeRepoUrl = data.repo_url?.replace(/\/\/[^/@]+@/, '//[redacted]@').split('?')[0];
  const log = (event: string, fields: Record<string, unknown> = {}) =>
    console.info('[RepoIQ analysis]', sanitizeAnalysisLog({ analysis_run_id: runId, event, ...fields }));
  log('analyze_click_or_request_initiated', { repository_url: safeRepoUrl, has_local_path: Boolean(data.local_path) });

  let apiBase: string;
  try {
    apiBase = resolveApiBase({
      configuredApiBase: import.meta.env.VITE_API_BASE_URL,
      runtimeApiBase,
      developmentApiBase: getDevelopmentApiBaseOverride(),
      pageOrigin: window.location.origin,
    });
  } catch (error) {
    log('api_configuration_failed', { error: error instanceof Error ? error.message : 'Invalid API configuration' });
    return { status: 'error', analysis_run_id: runId, error: `Invalid API configuration. Correlation ID: ${runId}` };
  }

  if (!apiBase) {
    log('api_configuration_missing');
    return { status: 'error', analysis_run_id: runId, error: `RepoIQ API URL is unavailable. Correlation ID: ${runId}` };
  }

  try {
    log('api_request_body_prepared', {
      method: 'POST',
      repository_url: safeRepoUrl,
      has_local_path: Boolean(data.local_path),
      analysis_run_id: runId,
      content_type: 'application/json',
      body_bytes: new TextEncoder().encode(
        JSON.stringify({ ...data, analysis_run_id: runId })
      ).length,
    });
    const response = await fetchWithDefensiveRetry(`${apiBase}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, analysis_run_id: runId }),
    }, 'Analysis', (attempt, error) => log('api_retry_scheduled', {
      attempt, max_attempts: 3, error_type: error instanceof Error ? error.name : 'UnknownError',
    }));
    log('api_response_received', { http_status: response.status,
      duration_ms: Math.round(performance.now() - requestStarted) });
    let rawResult: unknown;
    try {
      rawResult = await response.json();
    } catch (error) {
      log('api_response_json_invalid', { http_status: response.status, error_type: error instanceof Error ? error.name : 'UnknownError' });
      return { status: 'error', analysis_run_id: runId, error: `Invalid analysis response. Correlation ID: ${runId}` };
    }
    if (!rawResult || typeof rawResult !== 'object' || Array.isArray(rawResult)) {
      log('api_response_schema_invalid', { received_type: Array.isArray(rawResult) ? 'array' : typeof rawResult });
      return { status: 'error', analysis_run_id: runId, error: `Invalid analysis response. Correlation ID: ${runId}` };
    }
    const result = rawResult as AnalyzeRepositoryResponse;
    const responseRunId = result.analysis_run_id || runId;
    log('api_response_parsed_snapshot', {
      response_status: result.status,
      analysis_status: result.analysis_status,
      commit_sha: result.commit_sha,
      repo_name: result.repo_name,
      overview: result.overview,
      executive_overview: result.executive_overview,
      modules: Array.isArray(result.modules) ? result.modules.slice(0, 8) : [],
      architecture: result.architecture,
      repository_model: result.repository_model
        ? {
            commit_sha: result.repository_model.commit_sha,
            claims: Array.isArray(result.repository_model.claims)
              ? result.repository_model.claims.slice(0, 24)
              : [],
            components: Array.isArray(result.repository_model.components)
              ? result.repository_model.components.slice(0, 16)
              : [],
            contradictions: result.repository_model.contradictions,
            evidence_issues: result.repository_model.evidence_issues,
            unresolved_questions: result.repository_model.unresolved_questions,
            coverage: result.repository_model.coverage,
          }
        : undefined,
    });
    if (!result.analysis_run_id) log('api_response_missing_run_id');
    if (responseRunId !== runId) log('api_response_run_id_mismatch', { response_run_id: responseRunId });
    if (typeof result.status !== 'string' || !['success', 'error'].includes(result.status)) {
      log('api_response_schema_invalid', { missing_or_invalid_field: 'status' });
      return { status: 'error', analysis_run_id: runId, error: `Invalid analysis response. Correlation ID: ${runId}` };
    }
    for (const field of ['analysis_status', 'repository_model', 'commit_sha']) {
      if (!(field in result)) log('api_response_field_missing', { field });
    }
    if (!response.ok || result.status !== 'success') {
      const code = result.error_code || `http_${response.status}`;
      log('analysis_failed', { http_status: response.status, error_code: code, analysis_status: result.analysis_status || 'error' });
      return { status: 'error', analysis_run_id: responseRunId,
        error: result.message || `Analysis failed. Correlation ID: ${responseRunId}` };
    }

    const hasValidatedModel = Boolean(
      result.analysis_run_id && result.commit_sha && result.repository_model &&
      ['complete', 'success', 'ai_generated', 'partial', 'degraded'].includes(result.analysis_status || '')
    );
    const analysisStatus = result.analysis_status || 'partial';
    const finalState = !hasValidatedModel
      ? 'partial'
      : analysisStatus === 'degraded'
        ? 'degraded'
        : analysisStatus === 'partial'
          ? 'partial'
          : 'success';
    if (!hasValidatedModel) {
      log('api_response_incomplete_analysis_metadata', {
        missing_fields: [
          !result.analysis_run_id && 'analysis_run_id',
          !result.commit_sha && 'commit_sha',
          !result.repository_model && 'repository_model',
          !result.analysis_status && 'analysis_status',
        ].filter(Boolean),
        final_state: finalState,
      });
    }
    const keyFeatures = normalizeAiInsights(result);
    log('api_analysis_result_received', {
      final_state: finalState, analysis_status: analysisStatus, commit_sha: result.commit_sha,
      claim_count: Array.isArray(result.repository_model?.claims) ? result.repository_model.claims.length : 0,
      module_count: Array.isArray(result.modules) ? result.modules.length : 0,
    });
    return {
      status: 'success', analysis_run_id: responseRunId, repoName: result.repo_name, repoUrl: result.repo_url,
      localPath: result.local_path, readme: result.readme, readmePath: result.readme_path,
      stack: result.stack, folderStructure: result.folder_structure, projectSummary: result.architecture_summary,
      keyFeatures, overview: result.overview, executive_overview: result.executive_overview,
      architecture: result.architecture, architecture_summary: result.architecture_summary, modules: result.modules,
      similar_repositories: result.similar_repositories, analysis_evidence: result.analysis_evidence ?? {},
      analysis_status: finalState, commit_sha: result.commit_sha, repository_model: result.repository_model,
      coverage_manifest: result.coverage_manifest,
      report_sections: result.report_sections,
      ai_insights: result.ai_insights ?? keyFeatures, languages: result.languages,
    };
  } catch (error) {
    console.error('[RepoIQ analysis]', { analysis_run_id: runId, event: 'api_request_failed',
      error_type: error instanceof Error ? error.name : 'UnknownError' });
    return { status: 'error', analysis_run_id: runId,
      error: `Analysis request failed. Correlation ID: ${runId}` };
  }
}
