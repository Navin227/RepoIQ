import { useState, startTransition, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import DemoInfrastructureCard from './components/DemoInfrastructureCard';
import SearchResults from './components/SearchResults';
import AnalysisDashboard from './components/AnalysisDashboard';
import { getOrCreateRepository } from './data';
import {
  analyzeRepository,
  searchRepositories,
} from './services/api';
import { SimilarRepo, Repository } from './types';
import {
  Star,
  GitFork,
  BookMarked,
} from 'lucide-react';

interface DemoStatusReadiness {
  state?: string;
  message?: string;
  health_check?: {
    healthy?: boolean;
    reason?: string;
  };
}

interface DemoStatusInitializationLog {
  timestamp?: string;
  level?: string;
  stage?: string;
  message?: string;
}

interface DemoStatusInitialization {
  state?: string;
  status?: string;
  stage?: string | null;
  stage_name?: string | null;
  message?: string | null;
  completed_stages?: string[];
  logs?: DemoStatusInitializationLog[];
  error?: string | null;
}

interface DemoStatusTelemetry {
  available?: boolean;
  source?: string;
  key?: string | null;
  last_updated?: string | null;
  error?: string | null;
}

interface DemoStatusResponse {
  state?: 'running' | 'pending' | 'stopping' | 'stopped' | 'shutting-down' | 'terminated' | string;
  status?:
  | 'running'
  | 'pending'
  | 'stopping'
  | 'offline'
  | 'terminating'
  | 'terminated'
  | 'shutting-down'
  | 'failed'
  | string;

  public_ip: string | null;
  private_ip?: string | null;
  launch_time?: string | null;
  application_url?: string | null;
  instance_id: string | null;

  health?:
  | 'offline'
  | 'ok'
  | 'initializing'
  | 'stopping'
  | 'unavailable'
  | 'failed'
  | string;

  readiness?: DemoStatusReadiness;
  initialization?: DemoStatusInitialization;
  telemetry?: DemoStatusTelemetry;
  message?: string;
  error?: string | null;
}

interface DemoStartResponse {
  session_id: string;
  start_time: string;
  end_time: string;
  duration: number;
  state: string;
  public_ip: string | null;
}

const normalizeGitHubRepoInput = (value: string) => {
  const cleaned = value.trim();

  if (!cleaned) return '';

  const compactRepoPattern = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  if (compactRepoPattern.test(cleaned)) {
    return `https://github.com/${cleaned.replace(/\.git$/i, '')}`;
  }

  const sshRepoPattern = /^git@github\.com:([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)(?:\.git)?$/i;
  const sshMatch = cleaned.match(sshRepoPattern);
  if (sshMatch) {
    return `https://github.com/${sshMatch[1]}`;
  }

  try {
    const parsed = new URL(cleaned);
    const hostname = parsed.hostname.toLowerCase();
    if (
      hostname === 'github.com' ||
      hostname === 'www.github.com'
    ) {
      const pathParts = parsed.pathname
        .replace(/^\/+|\/+$/g, '')
        .replace(/\.git$/i, '')
        .split('/')
        .filter(Boolean);

      if (pathParts.length >= 2) {
        return `https://github.com/${pathParts[0]}/${pathParts[1]}`;
      }
    }
  } catch {
    // Ignore invalid URL format.
  }

  return cleaned;
};

const getRepoFullName = (repoUrl: string) => {
  const cleaned = repoUrl.trim();

  if (!cleaned) return '';

  const normalized = normalizeGitHubRepoInput(cleaned);
  if (normalized.startsWith('https://github.com/')) {
    try {
      const parsed = new URL(normalized);

      const pathParts = parsed.pathname
        .replace(/^\//, '')
        .replace(/\.git$/i, '')
        .split('/');

      if (pathParts.length >= 2) {
        return `${pathParts[0]}/${pathParts[1]}`;
      }
    } catch {
      // Ignore invalid URL format.
    }
  }

  const compactRepoPattern = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  if (compactRepoPattern.test(cleaned)) {
    return cleaned.replace(/\.git$/i, '');
  }

  return cleaned;
};

const isGitHubRepoUrl = (query: string) => {
  const cleaned = query.trim();

  if (!cleaned) return false;

  const compactRepoPattern = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  if (compactRepoPattern.test(cleaned)) {
    return true;
  }

  const sshRepoPattern = /^git@github\.com:[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/i;
  if (sshRepoPattern.test(cleaned)) {
    return true;
  }

  try {
    const parsed = new URL(cleaned);
    const hostname = parsed.hostname.toLowerCase();

    if (
      hostname !== 'github.com' &&
      hostname !== 'www.github.com'
    ) {
      return false;
    }

    const pathParts = parsed.pathname
      .replace(/^\/+|\/+$/g, '')
      .replace(/\.git$/i, '')
      .split('/');

    return (
      pathParts.length >= 2 &&
      Boolean(pathParts[0]) &&
      Boolean(pathParts[1])
    );
  } catch {
    return false;
  }
};

type ServerStatus =
  | 'checking'
  | 'starting'
  | 'online'
  | 'offline'
  | 'failed';

const SERVER_OFFLINE_MESSAGE = 'Server Offline';
const SERVER_OFFLINE_DETAIL =
  'Start the RepoIQ server to analyze repositories.';

const SERVER_ONLINE_MESSAGE = 'Server Online';
const SERVER_ONLINE_DETAIL =
  'RepoIQ server is ready to search and analyze repositories.';

const SERVER_FAILED_MESSAGE = 'Server Startup Failed';
const SERVER_CHECKING_MESSAGE =
  'Checking RepoIQ server...';

const SERVER_STARTING_MESSAGE =
  'Starting RepoIQ server...';

const INIT_STAGE_LABELS: Record<string, string> = {
  ec2_started: 'EC2 instance started',
  k3s_started: 'K3s started',
  node_ready: 'Kubernetes node Ready',
  images_imported: 'Images imported',
  manifests_applied: 'Manifests applied',
  postgres_ready: 'PostgreSQL Ready',
  backend_ready: 'Backend Ready',
  frontend_ready: 'Frontend Ready',
  traefik_ready: 'Traefik Ready',
  traefik_svc_valid: 'Traefik service valid',
  host_port_80_listening: 'Port 80 listening',
  localhost_health_ok: 'localhost /health',
  private_ip_health_ok: 'private IP /health',
  public_ip_health_ok: 'public /health',
  stage_summary: 'Summary written',
  completed: 'Application ready',
};

const INIT_STAGE_SEQUENCE = Object.keys(INIT_STAGE_LABELS);

const isValidAdminToken = (token: string) => {
  for (const character of token) {
    const codePoint = character.codePointAt(0) ?? 0;

    if (
      codePoint < 0x20 ||
      codePoint === 0x7f ||
      codePoint > 0xff
    ) {
      return false;
    }
  }

  return true;
};

const isServerOfflineError = (message?: string) => {
  if (!message) return false;

  const normalizedMessage = message.toLowerCase();

  return (
    normalizedMessage.includes('failed to fetch') ||
    normalizedMessage.includes('err_connection_refused') ||
    normalizedMessage.includes('networkerror') ||
    normalizedMessage.includes('network error') ||
    normalizedMessage.includes('demo server url is unavailable')
  );
};

export default function App() {
  // ──────────────────────────────────────────────
  // Navigation & Workspace State
  // ──────────────────────────────────────────────

  const [currentTab, setCurrentTab] =
    useState<string>('home');

  const [searchQuery, setSearchQuery] =
    useState<string>('');

  const [searchResults, setSearchResults] =
    useState<SimilarRepo[]>([]);

  const [isSearching, setIsSearching] =
    useState<boolean>(false);

  const [searchError, setSearchError] =
    useState<string | null>(null);

  const [analyzingRepoUrl, setAnalyzingRepoUrl] =
    useState<string | null>(null);

  const [analyzeMessageByUrl, setAnalyzeMessageByUrl] =
    useState<Record<string, string>>({});

  const [analyzedRepo, setAnalyzedRepo] =
    useState<Repository | null>(null);

  const [serverStatus, setServerStatus] =
    useState<ServerStatus>('checking');

  const [demoStatus, setDemoStatus] =
    useState<DemoStatusResponse | null>(null);

  const initialization = demoStatus?.initialization ?? null;
  const initializationStageName = initialization?.stage_name || initialization?.stage || null;
  const initializationLogs = initialization?.logs ?? [];
  const completedStages = initialization?.completed_stages ?? [];
  const failedInitialization = initialization?.state === 'failed' || Boolean(demoStatus?.error);
  const currentStage = initializationStageName || demoStatus?.readiness?.state || 'pending';
  const telemetryWarning = demoStatus?.telemetry?.available === false
    ? demoStatus.telemetry.error || 'Initialization telemetry unavailable.'
    : null;

  // Local startup console: records real status observations from /demo/status.
  // Backend-provided initialization logs are preferred; these observations ensure
  // the UI never appears completely silent while the control plane is polling.
  const [startupLogs, setStartupLogs] = useState<DemoStatusInitializationLog[]>([]);
  const lastObservedStageRef = useRef<string | null>(null);
  const lastObservedStateRef = useRef<string | null>(null);
  const lastObservedErrorRef = useRef<string | null>(null);

  const appendStartupLog = (
    message: string,
    stage?: string,
    level: string = 'info',
  ) => {
    const normalized = message.trim();
    if (!normalized) return;

    setStartupLogs(prev => {
      const last = prev[prev.length - 1];
      if (
        last?.message === normalized &&
        last?.stage === stage &&
        last?.level === level
      ) {
        return prev;
      }

      const next = [
        ...prev,
        {
          timestamp: new Date().toISOString(),
          level,
          stage,
          message: normalized,
        },
      ];

      return next.slice(-100);
    });
  };

  const launchAcceptedRef =
    useRef(false);

  const applicationReadyRef =
    useRef(false);

  // ──────────────────────────────────────────────
  // Saved repositories
  // ──────────────────────────────────────────────

  const [savedRepoNames, setSavedRepoNames] =
    useState<Set<string>>(
      new Set(['vercel/next.js'])
    );

  // ──────────────────────────────────────────────
  // Demo Infrastructure State
  // ──────────────────────────────────────────────

  const DEMO_CONTROL_API_BASE = (
    import.meta.env.VITE_DEMO_API_URL || ''
  )
    .trim()
    .replace(/\/$/, '');

  const [adminToken, setAdminToken] =
    useState('');

  const [duration, setDuration] =
    useState<30 | 45 | 60>(30);

  const [demoSessionId, setDemoSessionId] =
    useState<string | null>(null);

  const [demoSessionEndTime, setDemoSessionEndTime] =
    useState<string | null>(null);

  const [isDemoLoading, setIsDemoLoading] =
    useState(false);

  const [demoErrorMsg, setDemoErrorMsg] =
    useState<string | null>(null);

  const [demoSuccessMsg, setDemoSuccessMsg] =
    useState<string | null>(null);

  const [demoRemainingTime, setDemoRemainingTime] =
    useState<string>('00:00');

  const countdownTimer =
    useRef<ReturnType<typeof setInterval> | null>(null);

  /*
   * The actual RepoIQ backend URL comes from the running
   * demo infrastructure.
   *
   * We intentionally DO NOT fall back to localhost here.
   */
  const demoApiUrl =
    demoStatus?.application_url?.trim() || null;

  // ──────────────────────────────────────────────
  // Search
  // ──────────────────────────────────────────────

  const handleSearch = async (query: string) => {
    if (serverStatus !== 'online') {
      console.warn('[RepoIQ] Search blocked: server has not been started.');
      setSearchError(
        SERVER_OFFLINE_MESSAGE
      );

      return;
    }

    const trimmed = query.trim();

    if (!trimmed) return;

    setSearchQuery(trimmed);
    setSearchResults([]);
    setSearchError(null);

    if (isGitHubRepoUrl(trimmed)) {
      const normalizedRepoUrl = normalizeGitHubRepoInput(trimmed);
      await handleAnalyze(normalizedRepoUrl);
      return;
    }

    startTransition(() => {
      setCurrentTab('explore');
    });

    setIsSearching(true);

    try {
      console.log('[RepoIQ] Search started:', {
        query: trimmed,
      });
      const results = await searchRepositories(
        trimmed,
        demoApiUrl
      );

      setSearchResults(results);
    } catch (error) {
      console.error(
        '❌ Search failed:',
        error
      );

      setSearchError(
        isServerOfflineError(
          error instanceof Error
            ? error.message
            : String(error)
        )
          ? 'RepoIQ search request failed.'
          : error instanceof Error
            ? error.message
            : 'GitHub search failed'
      );

      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  // ──────────────────────────────────────────────
  // Repository Analysis
  // ──────────────────────────────────────────────

  const handleAnalyze = async (
    repoUrl: string
  ) => {
    if (serverStatus !== 'online') {
      console.warn('[RepoIQ] Analysis blocked: server has not been started.');
      setAnalyzeMessageByUrl(prev => ({
        ...prev,
        [repoUrl]: SERVER_OFFLINE_MESSAGE,
      }));

      return;
    }

    setAnalyzingRepoUrl(repoUrl);

    setAnalyzeMessageByUrl(prev => ({
      ...prev,
      [repoUrl]: '',
    }));

    try {
      const result =
        await analyzeRepository(
          {
            repo_url: repoUrl,
          },
          demoApiUrl
        );

      console.log(
        '📦 handleAnalyze result:',
        result
      );

      if (result.status === 'success') {
        const fullName =
          getRepoFullName(
            result.repoUrl ?? repoUrl
          );

        const [
          owner = '',
          name = '',
        ] = fullName.split('/');

        setAnalyzedRepo({
          owner,
          name,
          fullName,
          url:
            result.repoUrl ??
            repoUrl,
          description: '',

          localPath:
            result.localPath,

          readme:
            result.readme ?? '',
          readmePath: result.readmePath,

          overview: {
            aiSummary: result.overview || '',
            executiveOverview: result.executive_overview,

          },

          analysis: {
            projectSummary: result.overview || '',

            techStack: result.stack?.flat || {
                frontend: [],
                backend: [],
                database: [],
                infrastructure: [],
                devops: [],
              },

            keyFeatures:
              ((result.executive_overview?.user_features ?? []).map(
                    (feature) => feature?.name || ''
                  ).filter(Boolean)).slice(0, 10),

            businessModules: (result.modules || []).map(
                module => ({
                  name: module.name,

                  purpose:
                    module.purpose ||
                    module.description ||
                    '',

                  description:
                    module.description ||
                    module.purpose ||
                    '',

                  capabilities:
                    module.capabilities ||
                    [],

                  components:
                    module.components ||
                    [],

                  connected_modules:
                    module.connected_modules ||
                    [],

                  evidence:
                    module.evidence ||
                    module.components ||
                    [],

                  confidence:
                    module.confidence,
                })
              ),
          },

          folderStructure:
            result.folderStructure ??
            [],

          similarRepos: result.similar_repositories || [],

          languages: result.languages || [],

          rawStack:
            result.stack,

          architecture: result.architecture,

          analysisEvidence:
            result.analysis_evidence ?? {},
          analysisStatus: result.analysis_status ?? result.status,
          commitSha: result.commit_sha,
          repositoryModel: result.repository_model,
        });

        setAnalyzeMessageByUrl(prev => ({
          ...prev,
          [repoUrl]: '',
        }));

        setCurrentTab('analyze');
      } else {
        console.error(
          '⚠️ handleAnalyze error status:',
          result
        );

        setAnalyzeMessageByUrl(prev => ({
          ...prev,
          [repoUrl]:
            result.error ||
            'Failed to clone repository',
        }));
      }
    } catch (error) {
      console.error(
        '❌ handleAnalyze exception:',
        error
      );

      setAnalyzeMessageByUrl(prev => ({
        ...prev,
        [repoUrl]: 'RepoIQ analyze request failed.',
      }));
    } finally {
      setAnalyzingRepoUrl(null);
    }
  };

  // ──────────────────────────────────────────────
  // Saved Repository Toggle
  // ──────────────────────────────────────────────

  const handleSaveToggle = (
    fullName: string
  ) => {
    setSavedRepoNames(prev => {
      const next = new Set(prev);

      if (next.has(fullName)) {
        next.delete(fullName);
      } else {
        next.add(fullName);
      }

      return next;
    });
  };

  // ──────────────────────────────────────────────
  // Demo Infrastructure Status
  // ──────────────────────────────────────────────

  const fetchDemoStatus = async (
    tokenOverride?: string
  ): Promise<DemoStatusResponse | null> => {
    const token = (
      tokenOverride ??
      adminToken
    ).trim();

    if (!token) {
      return null;
    }

    if (!isValidAdminToken(token)) {
      setDemoStatus(null);
      setDemoErrorMsg(
        'Admin Access Token contains unsupported characters.'
      );

      return null;
    }

    if (!DEMO_CONTROL_API_BASE) {
      setDemoErrorMsg(
        'Demo API URL is not configured. Set VITE_DEMO_API_URL in Frontend/.env.'
      );

      return null;
    }

    try {
      const response = await fetch(
        `${DEMO_CONTROL_API_BASE}/demo/status`,
        {
          method: 'GET',
          headers: {
            Authorization:
              `Bearer ${token}`,
            'Content-Type':
              'application/json',
          },
          cache: 'no-store',
        }
      );

      if (response.ok) {
        const data =
          (await response.json()) as DemoStatusResponse;

        setDemoStatus(data);

        if (
            data.initialization?.state === 'failed' ||
            data.error ||
            data.health === 'unavailable'
          ) {
            setDemoErrorMsg(
              data.initialization?.error ||
              data.error ||
              data.message ||
              'Demo control plane is unavailable.'
            );
          } else {
            setDemoErrorMsg(null);
          }
        return data;
      }

      if (
        response.status === 401 ||
        response.status === 403
      ) {
        setDemoStatus(null);

        setDemoErrorMsg(
          response.status === 403
            ? 'Demo control plane rejected the Admin Access Token.'
            : 'Invalid Admin Access Token'
        );

        return null;
      }

      const errData =
        await response
          .json()
          .catch(() => ({}));

      setDemoErrorMsg(
        errData.message ||
        'Failed to fetch status'
      );

      return null;
    } catch (err) {
      console.error(
        'Error fetching demo status:',
        err
      );
      setDemoErrorMsg(
        'Network error. Failed to reach the control plane.'
      );

      return null;
    }
  };

  // ──────────────────────────────────────────────
  // SINGLE EC2 LIFECYCLE RECONCILER
  // ──────────────────────────────────────────────

  useEffect(() => {
    let isMounted = true;
    let requestInFlight = false;

    const reconcileServer =
      async () => {
        if (
          requestInFlight ||
          !isMounted
        ) {
          return;
        }

        requestInFlight = true;

        try {
          // Demo mode requires an Admin token.
          if (!DEMO_CONTROL_API_BASE) {
            if (isMounted) {
              setServerStatus(
                'offline'
              );
            }

            return;
          }

          const token =
            adminToken.trim();

          if (
            !token ||
            !isValidAdminToken(token)
          ) {
            if (isMounted) {
              setServerStatus(
                'offline'
              );
            }

            return;
          }

          const status =
            await fetchDemoStatus(
              token
            );

          if (!isMounted) {
            return;
          }

          // A failed poll is not evidence that EC2 stopped. Keep the
          // last authoritative lifecycle state until a successful response.
          if (!status) {
            return;
          }

          const authoritativeStatus =
            (status.status ?? 'offline').trim().toLowerCase();
          const ec2State = (status.state ?? '').trim().toLowerCase();
          const initializationState = (
            status.initialization?.state ?? status.readiness?.state ?? 'unknown'
          ).trim().toLowerCase();

          if (
            authoritativeStatus === 'stopped' ||
            authoritativeStatus === 'stopping' ||
            authoritativeStatus === 'terminating' ||
            authoritativeStatus === 'terminated' ||
            authoritativeStatus === 'shutting-down' ||
            authoritativeStatus === 'offline' ||
            ec2State === 'stopped' ||
            ec2State === 'stopping' ||
            ec2State === 'shutting-down' ||
            ec2State === 'terminated'
          ) {
            applicationReadyRef.current = false;
            launchAcceptedRef.current = false;
            setServerStatus('offline');
            return;
          }

          if (
            authoritativeStatus === 'pending' ||
            authoritativeStatus === 'starting' ||
            initializationState === 'initializing' ||
            initializationState === 'unknown'
          ) {
            applicationReadyRef.current = false;
            setServerStatus('starting');
            return;
          }

          if (initializationState === 'failed') {
            applicationReadyRef.current = false;
            setServerStatus('failed');
            return;
          }

          if (
            authoritativeStatus === 'running' &&
            (initializationState === 'ready' || status.readiness?.state === 'ready')
          ) {
            applicationReadyRef.current = true;
            setServerStatus('online');
            return;
          }

          if (authoritativeStatus === 'running') {
            applicationReadyRef.current = false;
            setServerStatus('starting');
            return;
          }

          applicationReadyRef.current = false;
          setServerStatus('offline');
        } finally {
          requestInFlight = false;
        }
      };

    if (
      DEMO_CONTROL_API_BASE &&
      adminToken.trim()
    ) {
      setServerStatus(
        'checking'
      );
    } else {
      setServerStatus(
        'offline'
      );
    }

    void reconcileServer();

    // Poll frequently while starting and periodically while running.
    const serverTimer =
      window.setInterval(
        () => {
          void reconcileServer();
        },
        5000
      );

    return () => {
      isMounted = false;
      window.clearInterval(
        serverTimer
      );
    };
  }, [
    adminToken,
    DEMO_CONTROL_API_BASE,
  ]);


  // ──────────────────────────────────────────────
  // Real startup console observations
  // ──────────────────────────────────────────────

  useEffect(() => {
    if (!demoStatus) return;

    const lifecycle = (demoStatus.state || demoStatus.status || '').toLowerCase();
    const initState = (initialization?.state || '').toLowerCase();
    const stage = initializationStageName || '';
    const message = initialization?.message?.trim();

    if (lifecycle === 'running' && lastObservedStateRef.current !== 'running') {
      lastObservedStateRef.current = 'running';
      appendStartupLog('[RepoIQ][K3s] EC2 instance is running', 'ec2_started');
    }

    if (stage && lastObservedStageRef.current !== stage) {
      lastObservedStageRef.current = stage;
      const stageMessage =
        message ||
        INIT_STAGE_LABELS[stage] ||
        `[RepoIQ][K3s] ${stage.replace(/_/g, ' ')}`;
      appendStartupLog(
        stageMessage.startsWith('[RepoIQ][K3s]')
          ? stageMessage
          : `[RepoIQ][K3s] ${stageMessage}`,
        stage,
      );
    }

    if (initState === 'initializing' && !stage) {
      appendStartupLog(
        '[RepoIQ][K3s] Initialization started — waiting for the first reported stage...',
        'initialization_started',
      );
    }

    if (initState === 'failed') {
      const errorMessage =
        initialization?.error ||
        demoStatus.error ||
        demoStatus.message ||
        'K3s initialization failed.';
      if (lastObservedErrorRef.current !== errorMessage) {
        lastObservedErrorRef.current = errorMessage;
        appendStartupLog(
          `[RepoIQ][K3s][ERROR] ${errorMessage}`,
          stage || 'failed',
          'error',
        );
      }
    }

    if (initState === 'ready') {
      appendStartupLog(
        '[RepoIQ][K3s] RepoIQ application ready',
        'completed',
      );
    }
  }, [
    demoStatus,
    initialization,
    initializationStageName,
  ]);

  // ──────────────────────────────────────────────
  // Countdown Timer
  // ──────────────────────────────────────────────

  useEffect(() => {
    if (countdownTimer.current) {
      clearInterval(
        countdownTimer.current
      );

      countdownTimer.current = null;
    }

    const state =
      demoStatus?.state ||
      demoStatus?.status ||
      'offline';

    if (
      !demoSessionEndTime ||
      state !== 'running'
    ) {
      setDemoRemainingTime(
        '00:00'
      );

      return;
    }

    const updateCountdown =
      () => {
        const difference =
          new Date(
            demoSessionEndTime
          ).getTime() -
          Date.now();

        if (difference <= 0) {
          setDemoRemainingTime(
            '00:00'
          );

          if (
            countdownTimer.current
          ) {
            clearInterval(
              countdownTimer.current
            );

            countdownTimer.current =
              null;
          }

          void fetchDemoStatus();

          return;
        }

        const totalSeconds =
          Math.floor(
            difference / 1000
          );

        const minutes =
          Math.floor(
            totalSeconds / 60
          );

        const seconds =
          totalSeconds % 60;

        const formattedMin =
          String(minutes).padStart(
            2,
            '0'
          );

        const formattedSec =
          String(seconds).padStart(
            2,
            '0'
          );

        setDemoRemainingTime(
          `${formattedMin}:${formattedSec}`
        );
      };

    updateCountdown();

    countdownTimer.current =
      setInterval(
        updateCountdown,
        1000
      );

    return () => {
      if (
        countdownTimer.current
      ) {
        clearInterval(
          countdownTimer.current
        );

        countdownTimer.current =
          null;
      }
    };
  }, [
    demoSessionEndTime,
    demoStatus?.state,
  ]);

  // ──────────────────────────────────────────────
  // Start Demo Server
  // ──────────────────────────────────────────────

  const handleDemoStart =
    async () => {
      const token =
        adminToken.trim();

      if (!token) {
        setDemoErrorMsg(
          'Please enter your Admin Access Token first.'
        );

        return;
      }

      if (
        !isValidAdminToken(token)
      ) {
        setDemoErrorMsg(
          'Admin Access Token contains unsupported characters.'
        );

        return;
      }

      if (
        !DEMO_CONTROL_API_BASE
      ) {
        setDemoErrorMsg(
          'Demo API URL is not configured. Set VITE_DEMO_API_URL in Frontend/.env.'
        );

        return;
      }

      setIsDemoLoading(true);

      console.log('[RepoIQ] Starting demo server:', {
        duration,
      });

      setDemoErrorMsg(null);
      setDemoSuccessMsg(null);

      try {
        const response =
          await fetch(
            `${DEMO_CONTROL_API_BASE}/demo/start`,
            {
              method: 'POST',
              headers: {
                Authorization:
                  `Bearer ${token}`,
                'Content-Type':
                  'application/json',
              },
              body: JSON.stringify({
                duration,
              }),
            }
          );

        if (response.ok) {
          const data =
            (await response.json()) as DemoStartResponse;

          console.log('[RepoIQ] Demo server launch accepted:', data);
          launchAcceptedRef.current = true;
          applicationReadyRef.current = false;
          setServerStatus('starting');

          setDemoSessionId(
            data.session_id
          );

          setDemoSessionEndTime(
            data.end_time
          );

          setDemoSuccessMsg(
            `Session initiated successfully for ${duration} minutes.`
          );

          console.log('[RepoIQ] Server launch accepted; waiting for EC2 lifecycle status.');
          await fetchDemoStatus(
            token
          );
        } else {
          const errData =
            await response
              .json()
              .catch(
                () => ({})
              );

          setDemoErrorMsg(
            errData.message ||
            'Failed to start demo server'
          );
          launchAcceptedRef.current = false;
          setServerStatus('offline');
          console.error('[RepoIQ] Demo server launch rejected:', response.status, errData);
        }
      } catch (err) {
        console.error(
          '[RepoIQ] Demo server launch error:',
          err
        );

        launchAcceptedRef.current = false;
        setServerStatus(
          'offline'
        );

        setDemoErrorMsg(
          'Network error. Failed to reach the control plane.'
        );
      } finally {
        setIsDemoLoading(
          false
        );
      }
    };

  // ──────────────────────────────────────────────
  // Stop Demo Server
  // ──────────────────────────────────────────────

  const handleDemoStop =
    async () => {
      const token =
        adminToken.trim();

      if (!token) {
        setDemoErrorMsg(
          'Please enter your Admin Access Token first.'
        );

        return;
      }

      if (
        !isValidAdminToken(token)
      ) {
        setDemoErrorMsg(
          'Admin Access Token contains unsupported characters.'
        );

        return;
      }

      if (
        !DEMO_CONTROL_API_BASE
      ) {
        setDemoErrorMsg(
          'Demo API URL is not configured. Set VITE_DEMO_API_URL in Frontend/.env.'
        );

        return;
      }

      setIsDemoLoading(true);
      setDemoErrorMsg(null);
      setDemoSuccessMsg(null);

      try {
        const response =
          await fetch(
            `${DEMO_CONTROL_API_BASE}/demo/stop`,
            {
              method: 'POST',
              headers: {
                Authorization:
                  `Bearer ${token}`,
                'Content-Type':
                  'application/json',
              },
              body: JSON.stringify({
                session_id:
                  demoSessionId,
              }),
            }
          );

        if (response.ok) {
          launchAcceptedRef.current = false;
          setServerStatus('offline');
          setDemoSuccessMsg(
            'Termination request sent successfully.'
          );

          setDemoSessionId(
            null
          );

          setDemoSessionEndTime(
            null
          );

          await fetchDemoStatus(
            token
          );
        } else {
          const errData =
            await response
              .json()
              .catch(
                () => ({})
              );

          setDemoErrorMsg(
            errData.message ||
            'Failed to stop demo server'
          );
        }
      } catch (err) {
        console.error(
          'Demo stop error:',
          err
        );

        setDemoErrorMsg(
          'Network error. Failed to reach the control plane.'
        );
      } finally {
        setIsDemoLoading(
          false
        );
      }
    };

  // ──────────────────────────────────────────────
  // Admin Token
  // ──────────────────────────────────────────────

  const handleDemoTokenChange =
    (val: string) => {
      const token =
        val.trim();

      setAdminToken(token);

      if (
        !isValidAdminToken(token)
      ) {
        launchAcceptedRef.current = false;
        setDemoStatus(null);

        setServerStatus(
          'offline'
        );

        setDemoErrorMsg(
          'Admin Access Token contains unsupported characters.'
        );

        return;
      }

      if (!token) {
        launchAcceptedRef.current = false;
        setDemoStatus(null);

        setServerStatus(
          'offline'
        );

        setDemoErrorMsg(null);

        return;
      }

      setServerStatus(
        'checking'
      );

      setDemoErrorMsg(null);
    };

  // ──────────────────────────────────────────────
  // Navigation
  // ──────────────────────────────────────────────

  const handleBackToHome =
    () => {
      setCurrentTab('home');
    };

  // ──────────────────────────────────────────────
  // Saved repositories
  // ──────────────────────────────────────────────

  const getSavedRepositories =
    (): SimilarRepo[] => {
      const list: SimilarRepo[] =
        [];

      savedRepoNames.forEach(
        name => {
          const repo =
            getOrCreateRepository(
              name
            );

          list.push({
            fullName:
              repo.fullName,

            description:
              repo.description,

            stars:
              repo.stars ?? 0,

            forks:
              repo.forks ?? 0,

            language:
              repo.language ?? '',

            topics:
              repo.topics ?? [],
          });
        }
      );

      return list;
    };

  // ──────────────────────────────────────────────
  // Render
  // ──────────────────────────────────────────────

  return (
    <div
      className="min-h-screen bg-[#0B0B0F] text-gray-100 flex flex-col selection:bg-[#8B5CF6]/30 selection:text-white"
      id="main-app-container"
    >
      <Navbar
        currentTab={currentTab}
        setCurrentTab={
          setCurrentTab
        }
        onNavigateHome={
          handleBackToHome
        }
        savedCount={
          savedRepoNames.size
        }
        adminToken={
          adminToken
        }
        demoStatus={
          demoStatus
        }
        isDemoLoading={
          isDemoLoading
        }
        onDemoStop={
          handleDemoStop
        }
      />

      <main className="flex-grow">
        {/* Server Status Banner — Home page only */}
        {currentTab === 'home' && (
          <div
            className="mx-auto max-w-5xl px-6 pt-6 lg:px-8"
            role="status"
            aria-live="polite"
          >
            <div
              className={`rounded-xl border px-4 py-3 text-center text-sm ${serverStatus ===
                  'online'
                  ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                  : serverStatus === 'failed'
                    ? 'border-red-400/30 bg-red-500/10 text-red-200'
                    : 'border-amber-400/30 bg-amber-400/10 text-amber-200'
                }`}
            >
              <strong>
                {serverStatus ===
                  'checking'
                  ? SERVER_CHECKING_MESSAGE
                  : serverStatus ===
                    'starting'
                    ? SERVER_STARTING_MESSAGE
                    : serverStatus ===
                      'online'
                      ? SERVER_ONLINE_MESSAGE
                      : serverStatus === 'failed'
                        ? SERVER_FAILED_MESSAGE
                        : SERVER_OFFLINE_MESSAGE}
              </strong>

              <span className="ml-2">
                {serverStatus ===
                  'checking'
                  ? 'Checking RepoIQ server status.'
                  : serverStatus ===
                    'starting'
                    ? initialization?.state === 'failed'
                      ? demoStatus?.message || 'Initialization failed.'
                      : 'Waiting for EC2 and K3s to finish the real initialization sequence.'
                    : serverStatus ===
                      'online'
                      ? SERVER_ONLINE_DETAIL
                      : serverStatus === 'failed'
                        ? demoStatus?.initialization?.error || demoStatus?.message || 'Initialization failed.'
                        : SERVER_OFFLINE_DETAIL}
              </span>
              {telemetryWarning && (
                <div className="mt-2 text-xs text-amber-200">
                  ⚠️ Initialization telemetry unavailable: {telemetryWarning}
                </div>
              )}
            </div>
          </div>
        )}

        {/* EC2/K3s startup initialization panel — Home page only */}
        {(serverStatus === 'starting' || serverStatus === 'online' || serverStatus === 'failed') && currentTab === 'home' && (
          <div className="mx-auto max-w-5xl px-6 pt-6 lg:px-8">
            <div className="rounded-2xl border border-white/10 bg-[#111218] p-5 shadow-xl shadow-[#0B0B0F]/30">
              <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-400">RepoIQ Server Startup</div>
                  <div className="mt-1 text-xl font-bold text-white">
                    {serverStatus === 'failed'
                      ? '🔴 Server Startup Failed'
                      : serverStatus === 'online'
                        ? '🟢 Server Online'
                        : '⟳ K3s Initializing...'}
                  </div>
                </div>
                {serverStatus === 'online' && (
                  <div className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                    🟢 Server Online
                  </div>
                )}
              </div>

              <div className="space-y-2">
                {INIT_STAGE_SEQUENCE.map(stageKey => {
                  const label = INIT_STAGE_LABELS[stageKey] || stageKey;
                  const active = initializationStageName === stageKey;
                  const completed = completedStages.includes(stageKey);
                  const failed = serverStatus === 'failed' && active;
                  const pending = !completed && !active && !failed;

                  return (
                    <div
                      key={stageKey}
                      className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${
                        failed
                          ? 'border-red-500/30 bg-red-500/10'
                          : completed
                            ? 'border-emerald-500/20 bg-emerald-500/5'
                            : active
                              ? 'border-amber-500/30 bg-amber-500/10'
                              : 'border-white/5 bg-white/[0.01]'
                      }`}
                    >
                      <span className="text-sm">
                        {failed ? '🔴' : completed ? '✓' : active ? '⟳' : '○'}
                      </span>
                      <span className={`flex-1 text-sm ${failed ? 'text-red-200' : completed ? 'text-emerald-200' : active ? 'text-amber-200' : 'text-gray-400'}`}>
                        {label}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-gray-400">Initialization Console</div>
                <div className="max-h-72 overflow-auto space-y-2 font-mono text-xs text-gray-200">
                  {(() => {
                    const mergedLogs = [...initializationLogs, ...startupLogs]
                      .filter(entry => Boolean(entry.message))
                      .reduce<DemoStatusInitializationLog[]>((acc, entry) => {
                        const duplicate = acc.some(
                          existing =>
                            existing.message === entry.message &&
                            existing.stage === entry.stage,
                        );
                        if (!duplicate) acc.push(entry);
                        return acc;
                      }, [])
                      .slice(-30);

                    return mergedLogs.length > 0 ? (
                      mergedLogs.map((entry, index) => (
                        <div
                          key={`${entry.timestamp ?? 'log'}-${entry.stage ?? 'stage'}-${index}`}
                          className={`whitespace-pre-wrap break-words ${
                            entry.level === 'error'
                              ? 'text-red-300'
                              : 'text-gray-200'
                          }`}
                        >
                          <span className="mr-2 text-gray-500">
                            {entry.timestamp
                              ? new Date(entry.timestamp).toLocaleTimeString()
                              : '--:--:--'}
                          </span>
                          {entry.message}
                        </div>
                      ))
                    ) : (
                      <div className="text-gray-400">
                        Waiting for real K3s initialization events...
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* HOME */}
        {currentTab ===
          'home' && (
            <div className="animate-fade-in">
              <Hero
                onSearch={
                  handleSearch
                }
                serverAvailable={
                  serverStatus === 'online'
                }
              />

              <DemoInfrastructureCard
                serverStatus={
                  serverStatus
                }
                adminToken={
                  adminToken
                }
                duration={
                  duration
                }
                onDurationChange={
                  setDuration
                }
                demoStatus={
                  demoStatus
                }
                demoSessionId={
                  demoSessionId
                }
                demoSessionEndTime={
                  demoSessionEndTime
                }
                isDemoLoading={
                  isDemoLoading
                }
                demoErrorMsg={
                  demoErrorMsg
                }
                demoSuccessMsg={
                  demoSuccessMsg
                }
                demoRemainingTime={
                  demoRemainingTime
                }
                onTokenChange={
                  handleDemoTokenChange
                }
                onStart={
                  handleDemoStart
                }
                onStop={
                  handleDemoStop
                }
              />

              <Features />
            </div>
          )}

        {/* SEARCH RESULTS */}
        {currentTab ===
          'explore' && (
            <div className="animate-fade-in">
              <SearchResults
                query={
                  searchQuery
                }
                results={
                  searchResults
                }
                isLoading={
                  isSearching
                }
                error={
                  searchError
                }
                analyzingRepoUrl={
                  analyzingRepoUrl
                }
                analyzeMessageByUrl={
                  analyzeMessageByUrl
                }
                onAnalyze={
                  handleAnalyze
                }
                onBackToHome={
                  handleBackToHome
                }
                onSearch={
                  handleSearch
                }
                serverAvailable={
                  serverStatus ===
                  'online'
                }
              />
            </div>
          )}

        {/* ANALYSIS */}
        {currentTab ===
          'analyze' &&
          analyzedRepo && (
            <div className="animate-fade-in">
              <AnalysisDashboard
                repo={
                  analyzedRepo
                }
                isSaved={savedRepoNames.has(
                  analyzedRepo.fullName
                )}
                onSaveToggle={
                  handleSaveToggle
                }
                onAnalyze={
                  handleAnalyze
                }
                serverAvailable={
                  serverStatus ===
                  'online'
                }
                onBackToSearch={() => {
                  if (
                    searchQuery
                  ) {
                    setCurrentTab(
                      'explore'
                    );
                  } else {
                    setCurrentTab(
                      'home'
                    );
                  }
                }}
              />
            </div>
          )}

        {/* SAVED LIBRARY */}
        {currentTab ===
          'saved' && (
            <div
              className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 animate-fade-in"
              id="saved-repositories-page"
            >
              <div className="border-b border-white/[0.08] pb-6 mb-8">
                <h1 className="text-3xl font-extrabold tracking-tight text-white font-sans">
                  Saved Repository Library
                </h1>

                <p className="text-sm text-gray-400 mt-1.5 font-sans">
                  Review and inspect your saved project reports quickly
                </p>
              </div>

              {getSavedRepositories()
                .length === 0 ? (
                <div className="text-center py-20 rounded-3xl bg-white/[0.01] border border-dashed border-white/[0.08]">
                  <BookMarked className="h-12 w-12 text-gray-500 mx-auto mb-4" />

                  <h3 className="text-lg font-bold text-white font-sans">
                    Your Saved Library is Empty
                  </h3>

                  <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto font-sans leading-relaxed">
                    Start scanning repositories and hit the &quot;Save Repository&quot; button to back up report blueprints here for instant access.
                  </p>

                  <button
                    onClick={() =>
                      setCurrentTab(
                        'home'
                      )
                    }
                    className="mt-6 px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#8B5CF6] to-purple-600 text-sm font-semibold text-white shadow"
                  >
                    Start Scanning
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {getSavedRepositories().map(
                    repo => (
                      <div
                        key={
                          repo.fullName
                        }
                        className="flex flex-col justify-between p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/[0.01] transition-all duration-300"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <BookMarked className="h-4.5 w-4.5 text-indigo-400 shrink-0" />

                            <h3 className="text-base font-bold text-white font-mono break-all line-clamp-1">
                              {
                                repo.fullName
                              }
                            </h3>
                          </div>

                          <p className="text-xs text-gray-400 leading-relaxed mt-2.5 line-clamp-2">
                            {
                              repo.description
                            }
                          </p>

                          <div className="flex flex-wrap gap-1 mt-3">
                            {repo.topics
                              .slice(
                                0,
                                3
                              )
                              .map(
                                top => (
                                  <span
                                    key={
                                      top
                                    }
                                    className="text-[10px] text-[#8B5CF6] font-mono bg-[#8B5CF6]/5 px-2 py-0.5 rounded border border-[#8B5CF6]/10"
                                  >
                                    #
                                    {
                                      top
                                    }
                                  </span>
                                )
                              )}
                          </div>
                        </div>

                        <div className="mt-6 pt-4 border-t border-white/[0.04] flex items-center justify-between">
                          <div className="flex items-center gap-3 text-[11px] text-gray-400 font-mono">
                            <span className="flex items-center gap-0.5">
                              <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />
                              {repo.stars.toLocaleString()}
                            </span>

                            <span className="flex items-center gap-0.5">
                              <GitFork className="h-3.5 w-3.5 text-blue-400" />
                              {repo.forks.toLocaleString()}
                            </span>
                          </div>

                          <button
                            onClick={() =>
                              handleAnalyze(
                                repo.fullName
                              )
                            }
                            disabled={
                              serverStatus !==
                              'online'
                            }
                            className="px-3 py-1.5 rounded-lg bg-white/[0.04] text-[11px] font-semibold text-white hover:bg-[#8B5CF6] transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            Inspect Code
                          </button>
                        </div>
                      </div>
                    )
                  )}
                </div>
              )}
            </div>
          )}
      </main>

      {/* Footer */}
      <footer
        className="border-t border-white/[0.05] bg-black/30 py-8 px-4"
        id="platform-footer"
      >
        <div className="mx-auto max-w-7xl flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-gray-500 font-mono">
          <div className="flex items-center gap-2">
            <span className="text-gray-400 font-bold tracking-tight">
              RepoIQ
            </span>

            <span>
              &copy;{' '}
              {new Date().getFullYear()}{' '}
              Platform Inc. All rights reserved.
            </span>
          </div>

          <div className="flex flex-wrap gap-4">
            <button
              onClick={() =>
                setCurrentTab(
                  'home'
                )
              }
              className="hover:text-white cursor-pointer"
            >
              Security
            </button>

            <button
              onClick={() =>
                setCurrentTab(
                  'home'
                )
              }
              className="hover:text-white cursor-pointer"
            >
              Privacy Policy
            </button>

            <button
              onClick={() =>
                setCurrentTab(
                  'home'
                )
              }
              className="hover:text-white cursor-pointer"
            >
              Contact
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
